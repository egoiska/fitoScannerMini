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

### B.3 El aviso de desfase mira cuándo se descargó, no el nombre

La fecha del nombre no sirve para detectar el desfase, porque **cada fuente fecha
una cosa distinta**:

| Fuente | Ejemplos observados | Qué fecha es |
|---|---|---|
| Los tres XLSX | `-20_07_2026`, `-30_07_2026` | la de **descarga** |
| El JSON grande | `_2026_07_17`, `_2026_07_27` | la del **volcado del MAPA** |
| Los dos PDF | `dc_web.pdf` | ninguna: nombre fijo |

Las dos descargas disponibles dan un JSON tres días anterior al XLSX en ambos casos
(17→20 y 27→30), pero en días de la semana distintos: el 17 fue viernes y el 27
lunes. Con dos muestras no hay regla de calendario que sostener. Lo único firme es
que el JSON va sistemáticamente por detrás, y que el desfase de fechas entre fuentes
es **estructural**: `avisar_desincronizacion()`, comparando nombres, saltaría en casi
todas las generaciones. Un aviso que salta siempre se aprende a ignorar, y entonces
deja de proteger del caso en que el desfase sí es real.

El JSON tampoco trae metadatos internos de generación —su estructura es solo
`{"Productos":[…]}`— así que no hay una fecha mejor escondida dentro.

Lo que el aviso quiere saber en realidad no es de qué día son los datos, sino **si
las fuentes se bajaron todas en la misma sesión**. Y eso está en la fecha de
modificación del fichero. En las descargas actuales se ve limpio: las cuatro nuevas
entre las 08:56 y las 08:58 de hoy, las anteriores el 20/07 por la mañana.

Así que `avisar_desincronizacion()` pasa a comparar `mtime`: avisa si las fuentes
usadas no se descargaron dentro de la misma ventana, con `VENTANA_DESCARGA_H = 24`
como constante documentada. Ventajas sobre el criterio del nombre:

- No hay que modelar tres nomenclaturas distintas ni suponer nada sobre el
  calendario de publicación del MAPA.
- **Los dos PDF entran en el control sin renombrarlos**, que es justo lo que el
  nombre fijo impedía. Desaparece un paso manual del flujo (ver B.4).

Limitación, que se documenta en el aviso y en el doc de la parte C: el `mtime` se
altera al copiar o mover ficheros entre carpetas, así que puede dar un falso
positivo si reorganizas `fuentes/` a mano. Para que se distinga de un vistazo, el
aviso lista cada fuente con su fecha de descarga y marca la descolgada. Como red
secundaria se mantiene la comparación por nombre, pero solo salta cuando la
diferencia supera una semana, que ya no se explica por el desfase estructural.

### B.4 Los PDF, sin renombrar

`dc_web.pdf` e `ip_web.pdf` se descargan de una URL fija y siempre con el mismo
nombre, sin fecha. Hoy quedan fuera de toda vigilancia: `fecha_de_fuente()` no los
reconoce y `avisar_desincronizacion()` no los compara nunca con los XLSX.

Con el criterio de B.3 quedan cubiertos sin tocar nada: su `mtime` dice cuándo se
bajaron, igual que el de cualquier otra fuente. **No hay que renombrarlos**, que era
la alternativa manual y olvidable.

La contrapartida es que descargarlos sobrescribe los anteriores y no queda copia de
la versión previa. Es aceptable —los alias no son datos de los que haga falta
histórico— y lo cubre el paso de mover las fuentes viejas a `fuentes/historico/` de
la parte C, para quien quiera conservarlas.

En `elegir_fuente()` esto se traduce en que, cuando una candidata no tiene fecha en
el nombre, se ordena por `mtime` en lugar de por nombre.

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

2. **Cómo llegan.** La tabla de los seis ficheros con el nombre que trae cada uno,
   advirtiendo de que **no hay que renombrar nada**: los XLSX y el JSON ya vienen
   fechados por el MAPA, y los dos PDF llegan siempre con el mismo nombre y quedan
   controlados por su fecha de descarga.

   **Descárgalo todo en la misma sesión.** Es la única regla que importa, y de la
   que depende el aviso de la parte B. Las fechas de los nombres no coinciden entre
   sí ni tienen por qué: el JSON viene fechado unos días antes que los XLSX porque
   es la fecha del volcado del MAPA, no la de la descarga.

3. **Qué hacer con las viejas.** Moverlas a `fuentes/historico/` antes de descargar
   las nuevas, para que en `fuentes/` haya siempre un único juego. Con el arreglo de
   la parte B ya no es imprescindible, pero mantiene la carpeta legible y las
   ejecuciones rápidas.

4. **Los tres comandos**, en orden, con la ruta exacta.

5. **Qué mirar en la salida de cada uno.** El recuento de filas por listado, los
   duplicados descartados, el aviso de desincronización, el número de alias y el de
   ficheros de detalle. Con los valores de la última generación como referencia de
   qué es normal.

   Con una advertencia: **que una fuente llegue idéntica a la anterior es normal**.
   Entre el 20 y el 30 de julio, `ProductosCancelados` se descargó byte a byte igual
   —los otros dos XLSX sí cambiaron—, así que un recuento que no se mueve no
   significa que la descarga haya fallado.

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

**Parte B.** La carpeta `fuentes/` contiene ya dos juegos completos, del 20 y del 30
de julio, que es el escenario real que hay que cubrir. Cuatro comprobaciones:

1. **Selección correcta.** `elegir_fuente()` debe quedarse con los cuatro ficheros
   del 30/07 y anunciar los del 20/07 como descartados, con sus fechas.
2. **El fallo que hoy no se ve.** Este escenario concreto no discrimina: como texto,
   `20` < `30`, así que el `sorted()[-1]` actual acierta por casualidad. Para probar
   el arreglo de verdad hace falta una copia de `ProductosAutorizados-30_07_2026.xlsx`
   renombrada a `05_08_2026`, que ordena *antes* alfabéticamente. El código actual
   elige la de julio; el arreglado debe elegir la de agosto.
3. **Aviso por fecha de descarga.** Con las fuentes del 30/07, cuyos `mtime` están
   todos entre las 08:56 y las 08:58, no debe saltar ningún aviso, pese a que sus
   nombres lleven tres fechas distintas (`30_07_2026`, `2026_07_27` y los PDF sin
   fecha). Después se retrasa el `mtime` de una sola fuente diez días y se confirma
   que el aviso salta señalándola a ella.
4. **Los PDF cuentan.** El mismo retraso de `mtime` aplicado a `dc_web.pdf` debe
   hacer saltar el aviso: es lo que hoy no ocurre nunca.

Como red de seguridad de que el arreglo no altera la salida, el `registro.json`
generado con las fuentes del 20/07 debe ser idéntico byte a byte al que hay
publicado en el repo.

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
