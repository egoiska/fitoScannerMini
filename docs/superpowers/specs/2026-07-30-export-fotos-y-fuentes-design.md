# Exportación con fotos y selección fiable de fuentes

Fecha: 2026-07-30

Dos cambios independientes que se implementan juntos porque ambos atacan el mismo
riesgo: que la auditoría del almacén salga incompleta o apoyada en datos viejos sin
que nada lo avise.

1. **Exportación con fotos.** El registro de auditoría guarda fotos, pero la única
   forma de sacarlas hoy es el export JSON, que nadie abre. El CSV, que es el que se
   usa, las descarta y solo anota «sí/no».
2. **Selección fiable de fuentes.** Los scripts eligen la descarga del MAPA por
   orden alfabético del nombre. Con los XLSX nombrados `DD_MM_AAAA` eso no es orden
   cronológico, así que una carpeta con dos descargas puede generar el sitio con la
   vieja, en silencio.

---

## Parte A · Exportación con fotos

### A.1 Estado actual

En `index.html`, la vista `#logView` tiene tres botones: `Exportar CSV`,
`Exportar JSON` y `Vaciar`.

- `exportCsv()` escribe un CSV con BOM UTF-8, separador `;`, en orden cronológico
  ascendente (`LOG.slice().reverse()`). Su última columna, `Foto`, contiene el texto
  `sí` o `no`.
- `exportJson()` recupera todas las imágenes con `allPhotos()` y las embute como
  `foto_base64` en cada comprobación.

Las fotos viven en IndexedDB (almacén `fotos`, base `fitos_fotos`), como data-URL
JPEG de calidad 0,6 y lado máximo 1200 px, con reserva en memoria (`MEM`) si
IndexedDB no está disponible.

### A.2 Interfaz

Los botones `Exportar CSV` y `Exportar JSON` se sustituyen por uno solo,
`Exportar`, que abre una hoja inferior. `Vaciar` no se toca.

La hoja reutiliza los estilos `.modal` / `.sheet` que ya existen para la
correspondencia de campos: mismo comportamiento de cierre (botón, clic en el fondo)
y misma adaptación a pantalla ancha por el `@media (min-width:560px)` vigente.
No se añade CSS nuevo salvo el mínimo para las filas de opción.

Tres opciones, cada una con una línea de descripción:

| Opción | Fichero | Contenido |
|---|---|---|
| CSV | `auditoria_fitos_<sello>.csv` | Igual que hoy. Columna `Foto` = `sí`/`no`. |
| CSV + fotos | `auditoria_fitos_<sello>.zip` | CSV con rutas + carpeta `fotos/`. |
| JSON | `auditoria_fitos_<sello>.json` | Igual que hoy, con `foto_base64`. |

`<sello>` es el `stamp()` actual: `AAAAMMDD_HHMM`.

Elegir una opción cierra la hoja y lanza la descarga. Con el registro vacío, el
botón `Exportar` no abre la hoja: muestra el `toast` «No hay nada que exportar»,
que es la comprobación que hoy hacen `exportCsv()` y `exportJson()` por separado.
Así la comprobación queda en un solo sitio.

### A.3 Contenido del ZIP

```
auditoria_fitos_20260730_1830.csv
fotos/0001_ES00891.jpg
fotos/0004_25123.jpg
```

Sin carpeta raíz dentro del ZIP: tanto Archivos de iOS como el Explorador de
Windows ya descomprimen en una carpeta con el nombre del archivo.

**Nombres de las fotos.** `fotos/NNNN_<nreg>.jpg`, donde:

- `NNNN` es el número de fila del CSV con cuatro dígitos, en el mismo orden
  cronológico ascendente que el CSV. Correlaciona por posición además de por
  nombre, y garantiza que el nombre sea único aunque se hayan comprobado dos botes
  del mismo producto.
- `<nreg>` es el nº de registro saneado: todo lo que no sea `[A-Za-z0-9._-]` pasa a
  `_`. Esto cubre el `—` que `addLog()` guarda en las entradas «no encontrado».

Solo se escribe entrada para las comprobaciones que tienen foto. Un `e.foto` a
`true` cuya imagen no aparezca en `allPhotos()` (registro restaurado en otro
dispositivo, o IndexedDB purgado por el sistema) se trata como sin foto: no rompe
la exportación y su celda `Foto` queda vacía.

**El CSV dentro del ZIP** es idéntico al suelto salvo la última columna, que en vez
de `sí`/`no` contiene la ruta de la imagen (`fotos/0001_ES00891.jpg`) o queda
vacía. Es la razón de ser del ZIP: abres el CSV y sabes qué archivo mirar. El CSV
suelto conserva `sí`/`no`, porque ahí no hay ficheros a los que apuntar.

Para no duplicar la lógica, `exportCsv()` se generaliza a `csvTexto(rutas)`, que
recibe un mapa `id → ruta`; si el mapa está vacío escribe `sí`/`no`. La cabecera y
el escapado de comillas no cambian.

### A.4 Construcción del ZIP

Función nueva `zipStore(entradas)`, donde cada entrada es
`{nombre, datos: Uint8Array, fecha: Date}`. Devuelve un `Blob`
`application/zip` que se pasa al `download()` existente.

Método **0 (almacenado, sin comprimir)**. Las fotos ya son JPEG y el CSV pesa
kilobytes: deflate no aportaría nada y obligaría a escribir la única pieza
realmente delicada del formato.

Estructura escrita, por entrada y en este orden:

1. *Local file header* (firma `PK\x03\x04`, versión 20, método 0, hora y fecha DOS,
   CRC32, tamaño comprimido = tamaño sin comprimir, longitud del nombre).
2. Los bytes del fichero.

Y al final del archivo:

3. Un *central directory record* por entrada (firma `PK\x01\x02`), con el
   desplazamiento del *local header* correspondiente.
4. El *end of central directory* (firma `PK\x05\x06`), con el número de entradas y
   el tamaño y desplazamiento del directorio central.

Decisiones concretas:

- **CRC32** con tabla de 256 entradas generada de forma diferida la primera vez que
  se exporta un ZIP. No se calcula al arrancar la app.
- **Nombres en ASCII** por el saneado de A.3, así que no hace falta la bandera de
  UTF-8 (bit 11) ni ningún campo extra.
- **Fecha DOS**: cada foto lleva la fecha y hora de su propia comprobación
  (`e.ts`), y el CSV la de generación. Sale gratis y deja las fotos ordenadas por
  fecha real al descomprimir. Como el formato DOS no representa años anteriores a
  1980, una fecha imposible se sustituye por la de generación.
- **Sin ZIP64.** El formato clásico admite hasta 65 535 entradas y 4 GB; un registro
  de almacén no se acerca a ninguno de los dos límites.
- Los data-URL de IndexedDB se convierten a `Uint8Array` con `atob`, recortando el
  prefijo `data:image/jpeg;base64,`.

La exportación muestra el `showBusy()` existente mientras construye el ZIP, porque
con varias decenas de fotos la codificación bloquea el hilo principal un momento.

---

## Parte B · Selección fiable de fuentes

### B.1 El fallo

Los tres scripts localizan su fuente con una función `find_by_prefix` propia, y las
tres ordenan alfabéticamente:

| Script | Fuente | Selección |
|---|---|---|
| `unificar.py` | `ProductosAutorizados*.xlsx` y las otras dos | `sorted(...)[-1]` |
| `trocear_detalle.py` | `ProductosAutorizados*.json` | `sorted(...)[-1]` |
| `extract_alias.py` | `dc_web*.pdf`, `ip_web*.pdf` | `sorted(...)[0]` |

Dos problemas encadenados:

**Orden alfabético que no es cronológico.** Los XLSX del MAPA se llaman
`DD_MM_AAAA`. Con `ProductosAutorizados-20_07_2026.xlsx` y
`ProductosAutorizados-05_08_2026.xlsx` en la carpeta, `sorted()` devuelve
`["05_08_2026", "20_07_2026"]` y `[-1]` elige **la de julio**. El JSON, que usa
`AAAA_MM_DD`, sí ordena bien; los PDF no llevan fecha, así que el orden entre
`dc_web.pdf` y `dc_web_2026_07_30.pdf` lo decide el sufijo, y con `[0]` gana el
que no tiene fecha.

**Criterios opuestos entre scripts.** Dos toman el último y uno el primero, de modo
que con varias descargas conviviendo pueden llegar a leer fuentes de fechas
distintas. Es precisamente el desfase que `avisar_desincronizacion()` existe para
detectar, provocado por el propio código.

Y el aviso no lo ve: `avisar_desincronizacion()` recibe solo las rutas ya elegidas,
nunca las candidatas descartadas. El resultado es un sitio generado con datos viejos
sin una sola advertencia — el mismo fallo que el docstring de `fuentes_comun.py`
describe («un registro.json generado con XLSX viejos, que marcaba como caducados
productos ya prorrogados»).

### B.2 El arreglo

Se borran las tres `find_by_prefix` y se sustituyen por una única función en
`fuentes_comun.py`, que es donde ya vive `fecha_de_fuente()`:

```python
def elegir_fuente(folder, prefix, exts):
    """Devuelve la ruta de la fuente MÁS RECIENTE que casa con el prefijo."""
```

Comportamiento:

- Recoge las candidatas de todas las extensiones de `exts`, en el orden de
  preferencia dado (`extract_alias.py` depende de ese orden).
- Ordena por la fecha que devuelve `fecha_de_fuente()`, de más nueva a más vieja.
  Las candidatas sin fecha van al final, ordenadas por nombre.
- Imprime siempre qué elige y, si había más de una, **qué descarta y con qué
  fecha**. Ese es el aviso que hoy no existe.
- Si la elegida no tiene fecha en el nombre y había más de una candidata, avisa
  aparte: no hay forma de saber cuál es la nueva.
- Devuelve `None` si no hay candidatas, como hoy, para que cada script conserve su
  propio mensaje de error.

El docstring de `fuentes_comun.py`, que hoy explica el desfase entre fuentes pero no
este fallo, se amplía.

### B.3 Los PDF entran en el control de frescura

`dc_web.pdf` e `ip_web.pdf` se descargan de una URL fija y sin fecha en el nombre,
así que hoy quedan fuera de toda vigilancia: `fecha_de_fuente()` no los reconoce y
`avisar_desincronizacion()` no los compara nunca con los XLSX.

Se resuelve sin tocar código, solo con la convención que documenta la parte C:
renombrarlos al descargar a `dc_web_AAAA_MM_DD.pdf` e `ip_web_AAAA_MM_DD.pdf`. El
prefijo sigue casando con `elegir_fuente()`, y el patrón ISO de `fecha_de_fuente()`
reconoce ese sufijo, de modo que los PDF empiezan a contar para el aviso de desfase.

---

## Parte C · Documentación del flujo de actualización

Fichero nuevo `docs/actualizar-fuentes.md`, en pasos numerados y sin suponer que
quien lo lee recuerda cómo funciona el pipeline.

**Contenido:**

1. **Qué se descarga y de dónde.**
   - Los tres XLSX y el JSON grande, del registro de fitosanitarios:
     <https://servicio.mapa.gob.es/regfiweb>
   - Alias de denominaciones comunes:
     <https://www.mapa.gob.es/dam/mapa/contenido/agricultura/temas/sanidad-vegetal/medios-de-defensa-fitosanitaria/registro-productos-fitosanitarios/dc_web.pdf>
   - Alias de importaciones paralelas: la misma ruta con `ip_web.pdf`.

2. **Cómo nombrarlas.** La tabla de los seis ficheros con el nombre que espera cada
   script, señalando que los XLSX y el JSON ya vienen con fecha del MAPA y los dos
   PDF hay que renombrarlos a mano según B.3.

3. **Qué hacer con las viejas.** Moverlas a `fuentes/historico/` antes de descargar
   las nuevas, para que en `fuentes/` haya siempre un único juego. Con el arreglo de
   la parte B ya no es imprescindible, pero mantiene la carpeta legible y las
   ejecuciones rápidas.

4. **Los tres comandos**, en orden, con la ruta exacta.

5. **Qué mirar en la salida de cada uno.** El recuento de filas por listado, los
   duplicados descartados, el aviso de desincronización, el número de alias y el de
   ficheros de detalle. Con los valores de la última generación como referencia de
   qué es normal.

6. **Publicar.** Subir la versión de `CACHE` en `sw.js` (hoy `fitos-v3`) para que
   los móviles ya instalados recojan el cambio, y el `git add` / `commit` / `push`.
   Se avisa de que `fuentes/` está en `.gitignore` a propósito y no se sube.

La secuencia exacta de clics dentro de regfiweb no se documenta: es una aplicación
web que puede cambiar y no se ha verificado paso a paso. El doc identifica los
ficheros por el nombre con el que llegan, que es lo que los scripts necesitan.

---

## Verificación

El repo no tiene framework de test ni proceso de build, así que la comprobación es
manual y explícita.

**Parte B.** Se ejecuta `unificar.py` con las fuentes reales de `fuentes/` más una
copia de `ProductosAutorizados-20_07_2026.xlsx` renombrada a una fecha posterior en
formato `DD_MM_AAAA` que ordene antes alfabéticamente (p. ej. `05_08_2026`). Se
confirma que elige la copia de agosto, que anuncia la de julio como descartada, y
que el `registro.json` resultante es idéntico al actual salvo por ese cambio de
fuente. Después se repite con `dc_web.pdf` sin fecha junto a `dc_web_2026_07_30.pdf`
y se confirma que `extract_alias.py` elige el fechado y avisa del otro.

**Parte A.** Con el `registro.json` publicado cargado en el navegador, se registran
al menos tres comprobaciones —una sin foto, una de un producto vigente y una de un
«no encontrado», que es la que lleva `—` como nº de registro— y se exporta en los
tres formatos. Se comprueba:

- El CSV suelto se abre en Excel con los acentos correctos y la columna `Foto` en
  `sí`/`no`, igual que antes del cambio.
- El ZIP se descomprime sin avisos en Windows y en Archivos de iOS; cada ruta de la
  columna `Foto` corresponde a un fichero existente, y cada imagen es la del bote de
  su fila.
- La entrada «no encontrado» no rompe el nombre del fichero.
- El JSON sigue trayendo `foto_base64`.
- Con el registro vacío, `Exportar` avisa y no abre la hoja.

## Fuera de alcance

Las cuatro mejoras detectadas al leer el código que no se abordan aquí, anotadas
para no perderlas: la antigüedad de `registro.json` no se ve en ninguna parte de la
app; `TODAY` se calcula una sola vez al cargar y se queda congelado en una PWA que
se suspende en vez de recargarse; en la lista de resultados el veredicto se
comunica solo por color; y no hay filtro por estado.
