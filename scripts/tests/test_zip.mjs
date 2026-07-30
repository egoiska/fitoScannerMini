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

comprueba('pad4 crece en vez de truncar por encima de cuatro digitos', () => {
  igual(api.pad4(10001), '10001');
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

comprueba('zipStore produce un Blob con la firma PK', () => {
  const blob = api.zipStore([
    { nombre: 'a.txt', datos: new TextEncoder().encode('hola'), fecha: new Date(2026, 6, 30, 12, 34, 56) }
  ]);
  igual(blob.type, 'application/zip');
  if (blob.size < 22) throw new Error('demasiado pequeno: ' + blob.size);
});

/* csvTexto vive en otro bloque de index.html, con sus propias dependencias (LOG,
   fmtDate, pad). Se extrae igual y se le inyecta un LOG de mentira. */
const bloqueCsv = html.match(/\/\* --- csv: inicio --- \*\/([\s\S]*?)\/\* --- csv: fin --- \*\//);
if (!bloqueCsv) throw new Error('No encuentro el bloque "csv" en index.html');

const csvApi = new Function('LOG', `
  function pad(n){return(n<10?'0':'')+n;}
  function fmtDate(d){ if(!d) return '—'; var p=function(n){return(n<10?'0':'')+n;};
    return p(d.getDate())+'/'+p(d.getMonth()+1)+'/'+d.getFullYear(); }
  ${bloqueCsv[1]}
  return csvTexto;
`);

const LOG_FALSO = [
  { ts: Date.UTC(2026, 6, 30, 10, 0), nreg: '25.123', nombre: 'GLIFOMAX', titular: 'T1', estado: 'EN VIGOR', decisive: '01/03/2030', note: '', foto: true, id: 'e2' },
  { ts: Date.UTC(2026, 6, 29, 9, 0), nreg: '—', nombre: 'sin;punto,coma', titular: '', estado: 'NO ENCONTRADO', decisive: '', note: 'con "comillas"', foto: false, id: 'e1' }
];

comprueba('csvTexto sin rutas escribe si/no', () => {
  const txt = csvApi(LOG_FALSO)(null);
  const filas = txt.split('\r\n');
  igual(filas[0].charCodeAt(0), 0xFEFF, 'falta el BOM');
  if (!filas[1].endsWith(';no')) throw new Error('la entrada vieja deberia acabar en ;no -> ' + filas[1]);
  if (!filas[2].endsWith(';sí')) throw new Error('la nueva deberia acabar en ;sí -> ' + filas[2]);
});

comprueba('csvTexto con rutas escribe la ruta', () => {
  const txt = csvApi(LOG_FALSO)({ e2: 'fotos/0002_25.123.jpg' });
  if (txt.indexOf('fotos/0002_25.123.jpg') === -1) throw new Error('no aparece la ruta');
});

comprueba('csvTexto con rutas vacio distingue "sin foto" de "foto no disponible"', () => {
  // Mapa de rutas presente pero vacio: todas las fotos anunciadas estan ausentes de
  // IndexedDB (registro restaurado en otro movil, o almacen purgado). La entrada con
  // foto:true no debe confundirse con la que nunca tuvo foto.
  const txt = csvApi(LOG_FALSO)({});
  const filas = txt.split('\r\n');
  if (!filas[1].endsWith(';')) throw new Error('la entrada sin foto deberia acabar en ; (vacio) -> ' + filas[1]);
  if (!filas[2].endsWith(';foto no disponible')) throw new Error('la entrada con foto ausente deberia acabar en ;foto no disponible -> ' + filas[2]);
});

comprueba('csvTexto entrecomilla lo que lleva separador', () => {
  const txt = csvApi(LOG_FALSO)(null);
  if (txt.indexOf('"sin;punto,coma"') === -1) throw new Error('no entrecomilla el punto y coma');
  if (txt.indexOf('""comillas""') === -1) throw new Error('no duplica las comillas internas');
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
