/* Prueba de zipStore() sin sacarlo de index.html.
   Ejecutar:  node scripts/tests/test_zip.mjs

   El generador vive dentro del IIFE de index.html porque el repo no tiene build ni
   modulos: aqui se extrae el bloque delimitado por marcadores y se evalua suelto.
   Los marcadores son parte del contrato — si se renombran, este test deja de
   encontrarlo y falla ruidosamente, que es lo que se quiere. */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const html = readFileSync('index.html', 'utf8');
const bloque = html.match(/\/\* --- zip: inicio --- \*\/([\s\S]*?)\/\* --- zip: fin --- \*\//);
if (!bloque) throw new Error('No encuentro el bloque "zip" en index.html');

const api = new Function(bloque[1] + '; return {crc32:crc32, zipStore:zipStore, dataUrlABytes:dataUrlABytes, pad4:pad4, saneaNombre:saneaNombre};')();

let fallos = 0;
function comprueba(nombre, fn) {
  try { fn(); console.log('  ok   ' + nombre); }
  catch (e) { fallos++; console.log('  FALLA ' + nombre + ': ' + e.message); }
}
function igual(a, b, msg) {
  if (a !== b) throw new Error((msg || '') + ' esperaba ' + b + ' y salio ' + a);
}

comprueba('crc32 sobre el vector estandar', () => {
  const u8 = new TextEncoder().encode('123456789');
  igual(api.crc32(u8).toString(16), 'cbf43926');
});

comprueba('crc32 de vacio es 0', () => igual(api.crc32(new Uint8Array(0)), 0));

comprueba('pad4 rellena a cuatro digitos', () => {
  igual(api.pad4(1), '0001');
  igual(api.pad4(42), '0042');
  igual(api.pad4(1234), '1234');
});

comprueba('saneaNombre respeta lo valido y sustituye lo demas', () => {
  igual(api.saneaNombre('ES-00891'), 'ES-00891');
  igual(api.saneaNombre('25.123'), '25.123');
  igual(api.saneaNombre('—'), '_');
  igual(api.saneaNombre('a/b c'), 'a_b_c');
});

comprueba('dataUrlABytes decodifica base64 tras la coma', () => {
  const u8 = api.dataUrlABytes('data:image/jpeg;base64,SG9sYQ==');
  igual(new TextDecoder().decode(u8), 'Hola');
});

comprueba('zipStore produce un Blob con la firma PK', async () => {
  const blob = api.zipStore([
    { nombre: 'a.txt', datos: new TextEncoder().encode('hola'), fecha: new Date(2026, 6, 30, 12, 34, 56) }
  ]);
  igual(blob.type, 'application/zip');
  if (blob.size < 22) throw new Error('demasiado pequeno: ' + blob.size);
});

/* El artefacto se deja escrito para que verifica_zip.py lo abra con una
   implementacion independiente del formato. */
const csv = '﻿a;b\r\n1;2';
const blob = api.zipStore([
  { nombre: 'auditoria.csv', datos: new TextEncoder().encode(csv), fecha: new Date(2026, 6, 30, 12, 34, 56) },
  { nombre: 'fotos/0001_ES-00891.jpg', datos: api.dataUrlABytes('data:image/jpeg;base64,/9j/4AAQSkZJRg=='), fecha: new Date(2026, 6, 20, 9, 0, 0) },
  { nombre: 'fotos/0004_25.123.jpg', datos: new Uint8Array([1, 2, 3, 4, 5]), fecha: new Date(1970, 0, 1) }
]);
mkdirSync('../fito-pruebas', { recursive: true });
writeFileSync('../fito-pruebas/prueba.zip', Buffer.from(await blob.arrayBuffer()));
console.log('\n  escrito ../fito-pruebas/prueba.zip (' + blob.size + ' bytes)');

console.log(fallos ? '\n' + fallos + ' prueba(s) fallida(s)' : '\nTodo correcto');
process.exit(fallos ? 1 : 0);
