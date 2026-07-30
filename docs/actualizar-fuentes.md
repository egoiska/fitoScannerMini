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
depende de si el nombre trae fecha:

- Para los tres XLSX y el JSON (todos llevan fecha en el nombre), gana
  la fecha del **nombre**, no la de modificación del fichero.
- Sólo para `dc_web.pdf` e `ip_web.pdf` (que no llevan fecha ninguna) se
  usa la fecha de **modificación** como criterio, al no haber otra cosa
  que mirar.

Consecuencia práctica: copiar un XLSX viejo a `fuentes/` no lo convierte
en el elegido por tener ahora un `mtime` fresco; seguirá perdiendo frente
a uno con fecha de nombre más reciente, tenga éste el `mtime` que tenga.

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
- **`trocear_detalle.py`**: 2062 ficheros de detalle escritos.

No hace falta que coincidan exactamente en cada ejecución (el MAPA da de
alta y de baja productos constantemente), pero un cambio brusco —la mitad
de alias, el doble de duplicados descartados— es señal de que algo no
cuadra: revisa antes de publicar.

Dos advertencias:

- **Si aparece el aviso de desincronización** («AVISO: las fuentes... NO
  salen de la misma descarga», u otro con fechas de nombre separadas),
  **para y vuelve a descargar todo de una vez**. No sigas adelante con los
  ficheros existentes: con fuentes descoordinadas pueden aparecer productos
  sin detalle, alias huérfanos o caducidades desfasadas que den un veredicto
  erróneo.
- **Que una fuente llegue idéntica a la anterior es normal** y no es un
  fallo de descarga. Entre el 20 y el 30 de julio de 2026,
  `ProductosCancelados` se descargó byte a byte igual mientras
  `ProductosAutorizados` y `ProductosRetirados` sí habían cambiado. Un
  recuento de esa hoja que no se mueve de una generación a otra no significa
  que la descarga haya fallado ni que haya que repetirla.

## 6. Publicar

Antes de subir nada, sube el número de versión de `CACHE` en `sw.js` (por
ejemplo, de `fitos-v4` a `fitos-v5`). Esto es lo que consigue, y lo que no:

- Lo que sí hace: fuerza a que los móviles con la app ya instalada
  descarguen de red el `index.html` y el `sw.js` nuevos, en vez de seguir
  sirviendo la versión anterior desde el caché.
- `registro.json` y `alias.json` **no dependen de este número**: van en el
  caché `CORE` con estrategia *stale-while-revalidate*, así que se
  refrescan solos en la siguiente visita aunque no toques `CACHE`.
- `detalle/*.json` (dosis, plazo de seguridad, etc. de cada producto) vive
  en un caché aparte (`fitos-detalle`) que el `activate` del service
  worker excluye a propósito del borrado por versión, para no hacer perder
  al usuario lo que ya tenía descargado. Subir `CACHE` **no** refresca el
  detalle de un producto que ese móvil ya haya consultado antes: seguirá
  viendo los datos viejos hasta que ese caché se vacíe por su tope de 300
  entradas (el más antiguo se descarta al superarlo). Es una decisión de
  diseño existente, no un fallo — pero quien publique debe saber que un
  cambio en el detalle de un producto ya consultado no llega de inmediato
  a todos los móviles.

Después:

```bash
git add registro.json alias.json detalle/ sw.js
git commit -m "datos: actualizacion de fuentes del MAPA"
git push
```

Recuerda que `fuentes/` está en `.gitignore` a propósito (son 50 MB
regenerables): no debe aparecer en el commit.
