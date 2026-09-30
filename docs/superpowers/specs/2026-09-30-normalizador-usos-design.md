# Normalizador de usos autorizados del MAPA — diseño

Fecha: 2026-09-30. Estado: diseño aprobado en conversación; pendiente de revisión escrita.

## 1. Propósito

Una pieza nueva, separada de la PWA del scanner, que convierte los datos del
Registro de Productos Fitosanitarios del MAPA en un conjunto **normalizado** —valor,
unidad, contexto y procedencia de cada límite— para que otra webapp (sobre Firebase)
lo consuma.

Esa webapp tiene un wizard que recomienda o registra aplicaciones y hará de
**guardián normativo**: avisará si se supera la dosis máxima por ha, el número de
aplicaciones al año, si no se respeta el plazo de seguridad o el intervalo entre
aplicaciones, o si el cultivo no está autorizado. También avisará si se selecciona un
producto cancelado o retirado.

**El guardián queda fuera de este diseño.** Aquí se construye solo el dato que
necesita. Lo que no se pueda resolver con seguridad se publica marcado como tal y con
el texto original del MAPA, para que decida el usuario final.

### Criterio de éxito

- Cada límite de cada uso queda **resuelto** (con su origen) o marcado
  explícitamente **`sin_resolver`** con el texto original. Nunca un valor adivinado.
- Hay un recuento por campo y origen de lo resuelto y lo pendiente, generado en cada
  ejecución.
- Las resoluciones hechas por el agente o a mano **sobreviven** a las actualizaciones
  semanales mientras el texto del MAPA del que salen no cambie.

## 2. Descomposición

Tres subproyectos, cada uno con su spec y su plan:

1. **Normalizador** (este documento): fuentes del MAPA → `salida/` normalizada.
2. **Cargador a Firebase**: sube `salida/` a Firestore de forma incremental. Nunca
   borra usos; conserva los de productos que pasan a cancelados y fija
   `ultima_vez_en_mapa`. En Firebase no hay nada en producción: el esquema se diseña
   desde cero y el catálogo existente se adaptará a él.
3. **Automatización semanal**: descarga del MAPA → normalizador → cargador, con aviso
   cuando crezcan los pendientes. Falta comprobar si la descarga de regfiweb se puede
   automatizar (hoy es manual, ver `docs/actualizar-fuentes.md`).

## 3. Entradas

Las mismas que ya usa el scanner, en `fuentes/`, elegidas con
`scripts/fuentes_comun.elegir_fuente` (la más reciente de cada tipo):

- `ProductosAutorizados_AAAA_MM_DD.json`: 2081 productos y 62 648 usos
  (cifras de la descarga del 30/09/2026). Es la única fuente con usos.
- `registro.json` (salida de `scripts/unificar.py`): los 8921 productos de las tres
  hojas XLSX (1994 autorizados, 5837 cancelados, 1090 retirados), ya deduplicados.
  El normalizador lo reutiliza; no vuelve a leer los XLSX.
- `alias.json` (salida de `scripts/extract_alias.py`): 2856 alias.

Los cancelados y retirados **no tienen usos** en ninguna fuente del MAPA.

## 4. Modelo de datos de salida

### 4.1 `salida/productos.json` — un registro por número de registro (8921)

```
nreg          "25854" | "ES-00849"   Num_Registro literal del MAPA. Comprobado el 2026-09-30:
                                     registro.json y el JSON usan los mismos dos formatos
                                     (7669 numéricos y 1252 ES- en registro.json)
nombre, titular, formulado
estado        "autorizado" | "cancelado" | "retirado"
fechas        { caducidad, cancelacion, resolucion, limite_venta, inscripcion }
                                     ISO AAAA-MM-DD o null
sustancias    [ { nombre, nombre_ue, concentracion, unidad } ]       solo autorizados
alias         [ "HERMENON 500", ... ]
```

**No se publica ningún veredicto precalculado** («en vigor», «periodo de uso»,
«caducado»): depende de la fecha del día y quedaría obsoleto entre cargas. El wizard
lo calcula con las fechas publicadas. El criterio de referencia es la función
`evaluar()` de `index.html`, para que el scanner y el wizard no discrepen sobre el
mismo producto:

- **Retirado**: fecha decisiva = límite de venta, o si falta cancelación, o si falta
  caducidad. Siempre aviso fuerte.
- **Cancelado**: si hay fecha límite de uso y ya pasó → retirar; si no ha pasado →
  periodo de uso. Si solo hay límite de venta → cancelado, con aviso de verificar la
  fecha límite de uso. Sin fechas → cancelado, comprobar la resolución.
  **Ninguna fuente actual trae la fecha límite de uso** (las hojas XLSX solo tienen
  caducidad, resolución y límite de venta): `evaluar()` la contempla pero en la
  práctica cae siempre en la rama del límite de venta. No se inventa ese campo.
- **Autorizado**: caducidad pasada → caducado; caduca en ≤ 90 días → en vigor con
  aviso; si no, en vigor.

### 4.2 `salida/usos.jsonl` — un uso por producto × cultivo × agente (solo autorizados)

```
id            "11179_0101010101010000_6.1.2"      nreg_CodigoCultivo_CodigoAgente
nreg
cultivo       { codigo, nombre }
agente        { codigo, nombre }
limites {
  dosis_max     [ { valor, unidad, base, contexto, origen, derivada } ]
  aplicaciones  [ { max, contexto, origen } ]
  plazo_seg     [ { dias | "no_procede", contexto, origen } ]
  intervalo     [ { min, max, contexto, origen } ]
}
original      { los campos del uso del MAPA tal cual }
huellas       { dosis, aplicaciones, plazo_seg, intervalo }
```

Reglas:

- **Cada límite es una lista**, para desdoblar por contexto (decisión del usuario:
  desdoblar, no quedarse con el más restrictivo ni con el más permisivo). Sin
  variantes, la lista tiene un elemento con `contexto: null`.
- `contexto` = `{ sistema: "aire_libre" | "invernadero" | null,
  usuario: "profesional" | "no_profesional" | null }`.
- `origen` ∈ `mapa` (el campo venía ya estructurado y se ha copiado) · `parser` ·
  `agente` · `manual` · `sin_resolver`. Un límite `sin_resolver` es una lista de un
  elemento con ese origen y sin valor; el texto está en `original`.
- **`no_procede` ≠ `sin_resolver`**: el primero dice que no hay límite; el segundo,
  que no lo sabemos.
- **Dosis y `base`**: se convierte a `l` o `kg` por `ha` todo lo que sea una dosis
  por superficie. Lo que no lo es por naturaleza **no se fuerza**: tratamiento de
  semilla (`base: "100kg_semilla"`, `"t_semilla"`), fumigación de espacios
  (`base: "m3"`), por planta o árbol (`base: "planta"`). Trampas y difusores por ha
  quedan con `unidad: "ud"`, `base: "ha"`. El wizard compara directamente cuando
  `base = "ha"` y, si no, pide el dato que falta.
- `derivada`: null si el valor por ha viene del MAPA; `"superficie"` si se ha
  convertido de m²; `"concentracion*caldo"` si es concentración máxima × volumen de
  caldo máximo. Este último es un **máximo teórico** y el wizard debe presentarlo así.
- Los cultivos se comparan por `CodigoCultivo` (jerárquico, 16 dígitos), nunca por
  nombre. Resolver la jerarquía queda para el wizard.

## 5. Resolución en tres pasadas

### 5.1 Unidad de resolución: la huella

Se resuelve cada **entrada distinta**, no cada uso. La huella es un hash de los campos
que determinan el límite, tras normalizar diferencias irrelevantes (`\r` → `\n`,
espacios sobrantes):

- dosis: `Unidad Medida dosis`, `Dosis_Min`, `Dosis_Max`, `Volumen Caldo`,
  `Volumen_Min`, `VolumenMax`, `Unidades Volumen`, `CondicionamientoEspecifico`
- aplicaciones / plazo_seg / intervalo: su campo + `CondicionamientoEspecifico`

Un texto repetido en cientos de usos se resuelve una vez. Si el MAPA no lo cambia, no
se vuelve a procesar.

**Prioridad:** manual > agente > parser. Lo manual puede corregir también lo que
resolvió el parser o el agente.

**Huérfanas:** si el MAPA cambia un texto, cambia su huella y la resolución antigua
deja de aplicarse. El informe lista esas resoluciones huérfanas; nunca se aplica una
corrección vieja a un texto nuevo sin que nadie lo vea.

### 5.2 Pasada 1 — parser determinista

Funciones puras por campo que devuelven un resultado o `no_se`. **Nunca adivinan**:
si el texto no encaja exactamente en un patrón conocido, `no_se`. Cubren: unificación
de unidades por ha, conversión de superficie, concentración × volumen de caldo, las
variantes de «no procede» (`NO PROCEDE`, `NP`, `N.P.`, `NA`, `NO RELEVANTE`, `-`),
`Máx. N`, rangos, y el desdoble aire libre / invernadero.

**Hito de salida:** informe con recuentos y una muestra aleatoria de unos 50 casos
resueltos, que el usuario revisa antes de empezar la pasada 2.

### 5.3 Pasada 2 — agente (API de Claude)

- Solo recibe huellas que el parser dejó en `no_se`.
- Respuesta estructurada (esquema JSON). Por cada límite debe **citar el fragmento
  literal** del texto del MAPA del que lo extrae; el código comprueba que el fragmento
  aparece en la entrada. Si no aparece, el resultado se descarta → `sin_resolver`.
- **Calibración** antes de la pasada completa: ~100 casos ya resueltos por el parser,
  sin darle la respuesta, para medir su tasa de acierto.
- **Piloto**: ~100 casos difusos reales, revisados por el usuario. Solo si convence
  se lanza sobre todo lo pendiente; el coste se estima con el piloto.
- Persistencia: `resoluciones/agente.jsonl` (huella, resultado, fragmento, modelo,
  fecha). La clave de API vive fuera del repo.

### 5.4 Pasada 3 — manual

`pendientes` exporta a CSV lo que sigue sin resolver, con el texto original y columnas
para rellenar; `importar-manual` lo valida y lo añade a `resoluciones/manual.jsonl`.
Lo que nadie resuelva se publica como `sin_resolver`.

## 6. Tasación de casos difusos (estimación previa)

Medida el 2026-09-30 sobre los 62 648 usos con un clasificador desechable. Son
órdenes de magnitud; la cifra real la dará el informe del propio normalizador.

| Campo | Resoluble por reglas | Difuso o remite a texto | Vacío |
|---|---|---|---|
| Dosis máx./ha | ~62 % | ~13 000 usos → 3318 combinaciones distintas | 10 294 sin `Dosis_Max` (5763 citan una dosis por ha en el condicionado) |
| Plazo de seguridad | ~96 % | 2395 usos → 204 textos | 0,2 % |
| Aplicaciones/año | ~82 % | 1115 usos → 48 textos | 9783 (8897 con condicionado) |
| Intervalo | ~76 % | 976 usos → 48 textos | ~22 % |

Unidades de dosis (61 distintas): 35 290 ya por ha · 1283 por superficie ·
23 539 concentración (16 668 con volumen de caldo; de los 6871 sin él, 3492 lo citan
en el condicionado) · 1548 «ver nota / condicionado» · 304 por semilla · 170 por m³ ·
343 trampas/difusores · ~180 rarezas (`ml/árbol`, `ppm`…).

Estimación tras las tres pasadas: ~89 % de usos con dosis máxima por ha, 5–6 %
`sin_resolver`, el resto con otra `base`. **1040 de los 2081 productos** tienen algún
uso con dosis difusa.

## 7. Estructura del código

```
normalizador/
  __main__.py      python -m normalizador <comando>
  entrada.py       fuentes/ (vía fuentes_comun) + registro.json + alias.json
  huella.py
  parser/          dosis.py · plazo.py · aplicaciones.py · intervalo.py
  agente.py        (pasada 2)
  manual.py        (pasada 3)
  ensamblar.py     prioridad manual > agente > parser → productos + usos
  informe.py       recuentos por campo y origen, huérfanas, muestra aleatoria
  validar.py       contrato de salida
  tests/
resoluciones/      agente.jsonl · manual.jsonl         versionado en git
salida/            productos.json · usos.jsonl · informe.md   en .gitignore
```

- `salida/` no se versiona: decenas de MB regenerables cada semana, y la raíz del
  repo se publica como PWA en GitHub Pages. Lo que no se puede regenerar son las
  resoluciones, y esas sí van a git.
- No se toca nada del scanner (`index.html`, `sw.js`, `scripts/`, datos publicados).

**Comandos:**

- `generar`: parser sobre todo + resoluciones guardadas → `salida/` + informe. Sin red.
- `pendientes`: CSV con lo que sigue en `no_se`.
- `importar-manual <csv>`: valida y añade a `manual.jsonl`.
- `agente [--calibrar N | --piloto N]`: pasada 2.

**Salida determinista:** orden estable y sin marcas de tiempo por registro. Mismas
fuentes → ficheros idénticos, de modo que un diff muestra exactamente qué cambió.

**Sin estado entre ejecuciones:** el normalizador produce una foto de la semana.
Conservar usos de productos cancelados es tarea del cargador. Para recuperar los usos
de lo cancelado desde julio, se normalizan los JSON del 17/07 y del 27/07 (en
`fuentes/`) y el cargador los procesa antes que la foto actual, en orden.

## 8. Pruebas

Sin framework, siguiendo la convención del repo (`scripts/tests/`): scripts con
`assert`, dirigidos por tablas de casos.

- **Parser**: tablas de textos reales del MAPA → resultado esperado, incluidos casos
  que deben dar `no_se`.
- **Huella**: estable ante diferencias irrelevantes; cambia ante las relevantes.
- **Ensamblado**: prioridad manual > agente > parser; detección de huérfanas.
- **Contrato**: cada límite resuelto o `sin_resolver` con `original`; ninguna dosis
  con `base: "ha"` en unidad distinta de `l`, `kg` o `ud`; sin negativos ni
  valores absurdos.
- **Agente** (pasada 2): cliente falso sin red; verificación del fragmento citado y
  descarte de lo no citado.

## 9. Alcance del primer plan

El plan de implementación cubre **solo** el esqueleto (entrada, huella, ensamblado,
informe, validador) y la **pasada 1**. Las pasadas 2 y 3, el cargador y la
automatización se planifican cuando el usuario haya validado la pasada 1.

## 10. Fuera de alcance

- El guardián y el wizard.
- Resolver la jerarquía de `CodigoCultivo`.
- Usos de productos cancelados antes de julio de 2026: no existen en ninguna fuente
  que conservemos.
