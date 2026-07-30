# Actualizar las fuentes del MAPA

Este documento explica cómo regenerar los datos de la PWA (`registro.json`,
`alias.json` y `detalle/`) a partir de descargas nuevas del Ministerio de
Agricultura, Pesca y Alimentación (MAPA). Está escrito para que lo siga
alguien que no recuerda nada del pipeline: no da por supuesto ningún paso
previo.

## 1. Qué descargar

Hacen falta seis ficheros, de dos orígenes distintos:

| Fichero | Origen |
|---|---|
| `ProductosAutorizados-DD_MM_AAAA.xlsx` | <https://servicio.mapa.gob.es/regfiweb> |
| `ProductosCancelados-DD_MM_AAAA.xlsx` | <https://servicio.mapa.gob.es/regfiweb> |
| `ProductosRetirados-DD_MM_AAAA.xlsx` | <https://servicio.mapa.gob.es/regfiweb> |
| `ProductosAutorizados_AAAA_MM_DD.json` | <https://servicio.mapa.gob.es/regfiweb> |
| `dc_web.pdf` | <https://www.mapa.gob.es/dam/mapa/contenido/agricultura/temas/sanidad-vegetal/medios-de-defensa-fitosanitaria/registro-productos-fitosanitarios/dc_web.pdf> |
| `ip_web.pdf` | la misma ruta que `dc_web.pdf`, cambiando solo el nombre del fichero final |

No se documenta aquí la secuencia de clics dentro de regfiweb: es una
aplicación web que puede cambiar de un día para otro. Para saber si has
descargado lo correcto, guíate por el nombre con el que llega cada
fichero (sección siguiente), que es lo que los scripts necesitan reconocer.

Todos los ficheros van a la carpeta `fuentes/` en la raíz del repo (créala
si no existe). Esa carpeta está en `.gitignore` a propósito: son unos 50 MB
regenerables, no se publican en git.

## 2. Cómo llegan

Cada fichero trae su nombre en un formato distinto y **no hay que renombrar
nada**:

- `ProductosAutorizados-DD_MM_AAAA.xlsx`, `ProductosCancelados-DD_MM_AAAA.xlsx`,
  `ProductosRetirados-DD_MM_AAAA.xlsx` — formato `DD_MM_AAAA` (guion antes de
  la fecha, guion bajo entre sus partes). Es la fecha en que **tú** los
  descargas.
- `ProductosAutorizados_AAAA_MM_DD.json` — formato `AAAA_MM_DD` (guion bajo
  en vez de guion, y el orden invertido: año primero). Es la fecha del
  **volcado del MAPA**, que va unos días por detrás de tu descarga. En las
  dos descargas usadas para verificar este procedimiento (20/07/2026 y
  30/07/2026) el volcado iba tres días por detrás en ambas ocasiones.
- `dc_web.pdf` e `ip_web.pdf` — nombre fijo, sin fecha ninguna.

La única regla que importa de verdad: **descargar los seis en la misma
sesión**. El aviso de desincronización se dispara por dos vías distintas:

- Principal: la fecha de **modificación** de los ficheros en disco. Si
  mezclas una descarga de hoy con un XLSX que dejaste de la semana pasada,
  salta el aviso aunque los nombres parezcan coherentes.
- Secundaria: la fecha que llevan los **nombres**, como red de seguridad
  para cuando mover o copiar ficheros iguala sus fechas de modificación y
  borra la señal anterior. Si los nombres difieren en más de 7 días (el
  margen que ya explica el desfase estructural entre el JSON, fechado por
  el MAPA, y los XLSX, fechados al descargar), salta un segundo aviso
  aunque los `mtime` estén dentro de las 24 horas.

## 3. Las viejas

Si quieres conservar la descarga anterior, muévela a `fuentes/historico/`
antes de traer los ficheros nuevos. No es obligatorio: los tres scripts
eligen automáticamente, para cada tipo de fichero, la fuente más reciente
y avisan por consola cuál han descartado. El criterio de "más reciente"
es la fecha efectiva de cada candidata:

- Cada candidata se ordena por su **fecha efectiva**: la fecha que lleva
  en el nombre si la trae (los tres XLSX y el JSON siempre la traen); si
  no la trae (`dc_web.pdf`, `ip_web.pdf`), su fecha efectiva es la de
  **modificación** del fichero, al no haber otra cosa que mirar. Gana la
  fecha efectiva más reciente; si dos candidatas empatan, desempata el
  `mtime`.

Consecuencia práctica: copiar un XLSX viejo a `fuentes/` no lo convierte
en el elegido por tener ahora un `mtime` fresco, porque su fecha efectiva
sigue siendo la del nombre; seguirá perdiendo frente a uno con fecha de
nombre más reciente. Y al revés: un `dc_web.pdf` de archivo con fecha en
el nombre no le gana a un `dc_web.pdf` recién descargado hoy sin fecha en
el nombre, porque la fecha efectiva de este último es la de hoy.

## 4. Los tres comandos

Con todo en `fuentes/`, desde la raíz del repo, en este orden:

```bash
python scripts/unificar.py --src fuentes --out .
python scripts/extract_alias.py --src fuentes --out .
python scripts/trocear_detalle.py --src fuentes --out .
```

Escriben, respectivamente, `registro.json`, `alias.json` y la carpeta
`detalle/` en la raíz del repo. Esos tres sí se versionan: son los datos
que consume la PWA.

## 5. Qué mirar

Cifras de referencia de la última generación conocida, para saber si algo
se ha ido de madre:

- **`unificar.py`**: 8904 filas leídas, 8903 registros publicados
  (1980 Autorizado, 5837 Cancelado, 1086 Retirado), 1 duplicado descartado.
- **`extract_alias.py`**: 2871 alias extraídos.
- **`trocear_detalle.py`**: 2063 ficheros de detalle escritos (la cifra del
  artefacto publicado en este repo ahora mismo; baila de una generación a
  otra según lo que el MAPA dé de alta o de baja).

No hace falta que coincidan exactamente en cada ejecución (el MAPA da de
alta y de baja productos constantemente), pero un cambio brusco —la mitad
de alias, el doble de duplicados descartados— es señal de que algo no
cuadra: revisa antes de publicar.

Dos advertencias, una por cada vía por la que puede saltar el aviso de
desincronización (ver sección 2):

- **Si salta el aviso principal** («AVISO: las fuentes... NO salen de la
  misma descarga», por fecha de modificación), **para y vuelve a
  descargar todo de una vez**. No sigas adelante con los ficheros
  existentes: con fuentes descoordinadas pueden aparecer productos sin
  detalle, alias huérfanos o caducidades desfasadas que den un veredicto
  erróneo.
- **Si salta el aviso secundario** (por fechas de *nombre* separadas más
  de `MARGEN_NOMBRE_D` días, con los `mtime` dentro de la ventana), parar
  y volver a descargar no sirve de nada si ya descargaste todo en la
  misma sesión: la fecha del nombre del JSON la pone el MAPA, no tú, y el
  margen de 7 días está calibrado sobre solo dos observaciones. Comprueba
  en su lugar que el JSON es el último que publica el MAPA (mira la fecha
  de volcado en la web de origen); si lo es, el desfase es del origen y
  puedes seguir adelante. Si no lo es —descargaste un JSON viejo por
  error—, vuelve a bajarlo.
- **Que una fuente llegue idéntica a la anterior es normal** y no es un
  fallo de descarga. Entre el 20 y el 30 de julio de 2026,
  `ProductosCancelados` se descargó byte a byte igual mientras
  `ProductosAutorizados` y `ProductosRetirados` sí habían cambiado. Un
  recuento de esa hoja que no se mueve de una generación a otra no significa
  que la descarga haya fallado ni que haya que repetirla.

## 6. Publicar

Antes de subir nada, sube el número de versión de `CACHE` en `sw.js` (por
ejemplo, de `fitos-v4` a `fitos-v5`). Esto es lo que consigue, y lo que no:

- `index.html`, `registro.json` y `alias.json` viven todos en el
  mismo caché `CORE` y reciben el mismo trato *stale-while-revalidate* del
  `fetch` de `sw.js`: sirve lo cacheado al instante y refresca en segundo
  plano para la próxima visita. Eso pasa siempre, subas o no `CACHE` — la
  diferencia es cuándo se nota. Sin subir `CACHE`, el contenido de
  `sw.js` no cambia, así que el navegador no detecta versión nueva del
  service worker y el refresco depende solo de ese `fetch` en segundo
  plano: la primera carga tras el despliegue sigue sirviendo lo viejo (y
  de paso actualiza el caché), hace falta una segunda carga para ver lo
  nuevo. Subir `CACHE` sí cambia el contenido de `sw.js`, así que el
  navegador instala una versión nueva del service worker; su `install`
  precachea todo `CORE` de red antes de activarse y su `activate` borra
  el caché anterior. Lo que consigue subir `CACHE`, entonces, es
  **adelantar** ese refresco a la primera carga en vez de dejarlo para la
  siguiente.
- `detalle/*.json` (dosis, plazo de seguridad, etc. de cada producto) vive
  en un caché aparte (`fitos-detalle`) que el `activate` del service
  worker excluye a propósito del borrado por versión, para no hacer perder
  al usuario lo que ya tenía descargado. Ese caché es *cache-first* sin
  revalidación: una vez que un producto está guardado ahí, se sirve tal
  cual, sin caducidad. El tope de 300 entradas solo se comprueba al
  descargar el detalle de un producto **nuevo** para ese móvil (ahí se
  descarta la entrada más antigua si se supera el tope); si el agricultor
  siempre consulta el mismo puñado de productos, ese tope no se alcanza
  nunca y el detalle de esos productos no se refresca solo, tras subir
  `CACHE` ni de ninguna otra forma. Es una decisión de diseño existente,
  no un fallo — pero quien publique debe saber que un cambio en el
  detalle de un producto ya consultado no le llegará a ese móvil por sí
  solo.

Después:

```bash
git add registro.json alias.json detalle/ sw.js
git commit -m "datos: actualizacion de fuentes del MAPA"
git push
```

Recuerda que `fuentes/` está en `.gitignore` a propósito (son 50 MB
regenerables): no debe aparecer en el commit.
