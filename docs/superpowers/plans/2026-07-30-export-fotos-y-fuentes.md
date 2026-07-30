# Exportación con fotos y selección fiable de fuentes — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la exportación del registro de auditoría pueda llevarse las fotos en un ZIP, y que los scripts de generación elijan siempre la descarga del MAPA correcta avisando cuando las fuentes no se bajaron juntas.

**Architecture:** Dos bloques independientes. En Python, los tres `find_by_prefix` duplicados se unifican en un `elegir_fuente()` que ordena por la fecha del nombre en lugar de alfabéticamente, y `avisar_desincronizacion()` pasa a comparar la fecha de descarga (`mtime`) en lugar del nombre. En el navegador, un generador de ZIP propio de unas 45 líneas (método almacenado, sin compresión) y un selector de formato que sustituye a los dos botones de exportación actuales.

**Tech Stack:** Python 3.12 (openpyxl, pdfplumber) para los scripts; JavaScript ES5 sin dependencias ni build dentro de `index.html`; Node 24 y el módulo `zipfile` de Python como instrumental de prueba.

## Global Constraints

- **Sin dependencias nuevas.** Ni en Python ni en el navegador. El repo no tiene build ni gestor de paquetes de front, y no se le añade uno.
- **JavaScript ES5 dentro de `index.html`**, el estilo del resto del fichero: `var`, `function`, sin arrow functions, sin `const`/`let`, sin plantillas de cadena. Se sirve tal cual a móviles antiguos. **Esta restricción no alcanza a `scripts/tests/*.mjs`**, que se ejecutan en Node 24 y nunca llegan al navegador: ahí la sintaxis moderna es correcta y preferible.
- **Todo el JS va dentro de `index.html`**, en el IIFE existente. No se crean ficheros `.js` nuevos: `sw.js` tendría que precachearlos.
- **Los textos de interfaz van en español con acentos correctos**, igual que el resto de la app.
- **Comentarios en español**, explicando el *porqué* y no el *qué*, siguiendo el estilo del código existente (ver los comentarios de las capas 2 y 3 en `index.html`).
- **Ficheros de prueba en `scripts/tests/`**, ejecutables directamente sin framework (`python scripts/tests/x.py`, `node scripts/tests/x.mjs`). El repo no tiene pytest ni jest y no se añaden.
- **No ejecutar los scripts de generación contra el repo.** Regenerarían `registro.json`, `alias.json` y los 2063 ficheros de `detalle/`, que están versionados. Las pruebas usan `--src` y `--out` apuntando a carpetas temporales fuera del repo.
- **Carpeta temporal de trabajo:** `../fito-pruebas/` (hermana del repo, nunca dentro). Se crea en la Tarea 1 y se borra al final.

---

## Estructura de ficheros

| Fichero | Responsabilidad | Acción |
|---|---|---|
| `scripts/fuentes_comun.py` | Localización de fuentes y control de frescura. Es el único sitio que sabe de nomenclaturas y fechas. | Modificar |
| `scripts/unificar.py` | Capa 1. Pierde su `find_by_prefix` local. | Modificar |
| `scripts/extract_alias.py` | Capa 2. Pierde su `find_by_prefix` local. | Modificar |
| `scripts/trocear_detalle.py` | Capa 3. Pierde su `find_by_prefix` local. | Modificar |
| `scripts/tests/test_fuentes_comun.py` | Pruebas de las dos funciones anteriores, con ficheros de mentira en una carpeta temporal. | Crear |
| `index.html` | La PWA entera. Gana el generador de ZIP, el selector de exportación y el refactor del CSV. | Modificar |
| `scripts/tests/test_zip.mjs` | Extrae `zipStore()` de `index.html` y lo ejercita en Node. | Crear |
| `scripts/tests/verifica_zip.py` | Abre el ZIP generado con `zipfile` y comprueba CRC, nombres y contenido. | Crear |
| `docs/actualizar-fuentes.md` | El procedimiento semanal, para leerlo dentro de tres meses sin acordarse de nada. | Crear |

**Orden:** las tareas 1–3 (Python) y 4–6 (navegador) son independientes entre sí. Dentro de cada bloque el orden sí importa. La tarea 7 va al final porque documenta el comportamiento ya implementado.

---

### Task 1: `elegir_fuente()` elige por fecha, no por orden alfabético

**Files:**
- Modify: `scripts/fuentes_comun.py`
- Test: `scripts/tests/test_fuentes_comun.py`

**Interfaces:**
- Consumes: `fecha_de_fuente(path)` y `fmt_fecha(f)`, ya existentes en `scripts/fuentes_comun.py`.
- Produces: `elegir_fuente(folder, prefix, exts) -> str | None`. `exts` es una **lista** de extensiones con punto (`[".xlsx"]`), en orden de preferencia. Devuelve la ruta de la candidata más reciente, o `None` si no hay ninguna. Imprime por pantalla la elegida y las descartadas. La usan las tareas 3.

- [ ] **Step 1: Crear la carpeta de pruebas y escribir el test que falla**

Crear `scripts/tests/test_fuentes_comun.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de scripts/fuentes_comun.py.  Ejecutar:  python scripts/tests/test_fuentes_comun.py

Sin framework a proposito: el repo no tiene pytest y no se le anade una dependencia
por tres funciones. Un fallo aborta con AssertionError y traza.
"""

import os, shutil, sys, tempfile, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fuentes_comun import elegir_fuente


def _tocar(carpeta, nombre, antiguedad_h=0):
    """Crea un fichero vacio y le pone el mtime que se pida."""
    p = os.path.join(carpeta, nombre)
    with open(p, "w") as fh:
        fh.write("x")
    if antiguedad_h:
        t = time.time() - antiguedad_h * 3600
        os.utime(p, (t, t))
    return p


def test_elige_la_fecha_mas_reciente_no_la_alfabetica():
    """El caso que motiva el arreglo: los XLSX del MAPA usan DD_MM_AAAA, donde
    '05_08_2026' ordena ANTES que '20_07_2026' como texto. El sorted()[-1] de antes
    se quedaba con la de julio."""
    tmp = tempfile.mkdtemp()
    try:
        _tocar(tmp, "ProductosAutorizados-20_07_2026.xlsx")
        esperada = _tocar(tmp, "ProductosAutorizados-05_08_2026.xlsx")
        assert elegir_fuente(tmp, "ProductosAutorizados", [".xlsx"]) == esperada
    finally:
        shutil.rmtree(tmp)


def test_reconoce_las_dos_nomenclaturas_del_mapa():
    """Los XLSX van DD_MM_AAAA y el JSON grande AAAA_MM_DD."""
    tmp = tempfile.mkdtemp()
    try:
        _tocar(tmp, "ProductosAutorizados_2026_07_17.json")
        esperada = _tocar(tmp, "ProductosAutorizados_2026_07_27.json")
        assert elegir_fuente(tmp, "ProductosAutorizados", [".json"]) == esperada
    finally:
        shutil.rmtree(tmp)


def test_sin_fecha_en_el_nombre_desempata_la_descarga():
    """Los PDF de alias llegan siempre como dc_web.pdf. Sin fecha que comparar,
    manda el mtime."""
    tmp = tempfile.mkdtemp()
    try:
        _tocar(tmp, "dc_web_viejo.pdf", antiguedad_h=72)
        esperada = _tocar(tmp, "dc_web.pdf")
        assert elegir_fuente(tmp, "dc_web", [".pdf"]) == esperada
    finally:
        shutil.rmtree(tmp)


def test_respeta_el_orden_de_preferencia_de_extensiones():
    """extract_alias.py pasa varias extensiones y espera que gane la primera que
    tenga candidatas, no la mas reciente de todas."""
    tmp = tempfile.mkdtemp()
    try:
        esperada = _tocar(tmp, "dc_web_2026_07_01.pdf")
        _tocar(tmp, "dc_web_2026_07_30.xlsx")
        assert elegir_fuente(tmp, "dc_web", [".pdf", ".xlsx"]) == esperada
    finally:
        shutil.rmtree(tmp)


def test_sin_candidatas_devuelve_none():
    tmp = tempfile.mkdtemp()
    try:
        assert elegir_fuente(tmp, "NoExiste", [".xlsx"]) is None
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print("  ok   %s" % nombre)
            except Exception as e:
                fallos += 1
                print("  FALLA %s: %s" % (nombre, e))
    print("\n%d prueba(s) fallida(s)" % fallos if fallos else "\nTodo correcto")
    sys.exit(1 if fallos else 0)
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
cd "C:/Users/Zerbinek SL/Desktop/DESARROLLOS/fitoScannerMini"
python scripts/tests/test_fuentes_comun.py
```

Esperado: falla con `ImportError: cannot import name 'elegir_fuente'`.

- [ ] **Step 3: Implementar `elegir_fuente()`**

En `scripts/fuentes_comun.py`, añadir `glob` al `import os, re` de arriba (queda `import glob, os, re`) y escribir la función al final del fichero:

```python
def _orden_fuente(path):
    """Clave de ordenacion: primero las fechadas, de mas nueva a mas vieja; las que
    no llevan fecha en el nombre, despues, por fecha de descarga.

    Las fechas se niegan para poder ordenar ascendente y que salga primero la mas
    reciente. El primer elemento de la tupla separa los dos grupos, asi que nunca
    se comparan entre si una tupla de fecha y un mtime."""
    f = fecha_de_fuente(path)
    if f:
        return (0, tuple(-n for n in f))
    return (1, -os.path.getmtime(path))


def elegir_fuente(folder, prefix, exts):
    """Devuelve la ruta de la fuente MAS RECIENTE que casa con el prefijo, o None.

    Sustituye a los tres find_by_prefix que habia repartidos por los scripts, que
    ordenaban alfabeticamente. Con los XLSX del MAPA en formato DD_MM_AAAA eso no es
    orden cronologico: '05_08_2026' va antes que '20_07_2026' como texto, de modo
    que una carpeta con dos descargas generaba el sitio con la vieja y sin avisar.
    Ademas cada script cogia un extremo distinto de la lista (unos [-1] y otro [0]),
    con lo que podian llegar a leer descargas diferentes entre si.

    exts es una lista en orden de preferencia: gana la primera extension que tenga
    candidatas, no la candidata mas reciente de todas (extract_alias.py depende de
    ello para preferir el PDF).
    """
    for ext in exts:
        cands = sorted(glob.glob(os.path.join(folder, prefix + "*" + ext)), key=_orden_fuente)
        if not cands:
            continue
        elegida = cands[0]
        if len(cands) > 1:
            print("  fuente: %s  (%s)" % (os.path.basename(elegida),
                                          fmt_fecha(fecha_de_fuente(elegida))))
            for otra in cands[1:]:
                print("     descartada: %s  (%s)" % (os.path.basename(otra),
                                                     fmt_fecha(fecha_de_fuente(otra))))
        return elegida
    return None
```

- [ ] **Step 4: Ejecutar y ver que pasa**

```bash
python scripts/tests/test_fuentes_comun.py
```

Esperado: las cinco pruebas en `ok`, `Todo correcto`, código de salida 0.

- [ ] **Step 5: Comprobarlo contra las fuentes reales**

```bash
python -c "import sys; sys.path.insert(0,'scripts'); from fuentes_comun import elegir_fuente; print(elegir_fuente('fuentes','ProductosAutorizados',['.xlsx']))"
```

Esperado: elige `ProductosAutorizados-30_07_2026.xlsx` y anuncia la del 20/07 como descartada. (Con el código viejo también acertaría, porque `20` < `30` como texto; el caso que discrimina es el de agosto, que cubre la prueba automática.)

- [ ] **Step 6: Commit**

```bash
git add scripts/fuentes_comun.py scripts/tests/test_fuentes_comun.py
git commit -m "fix(fuentes): elegir la descarga por fecha del nombre, no alfabeticamente"
```

---

### Task 2: El aviso de desfase mira la fecha de descarga

**Files:**
- Modify: `scripts/fuentes_comun.py` (función `avisar_desincronizacion`, y el docstring del módulo)
- Test: `scripts/tests/test_fuentes_comun.py` (añadir casos)

**Interfaces:**
- Consumes: `fecha_de_fuente(path)`, `fmt_fecha(f)`, y el helper `_tocar()` del fichero de pruebas.
- Produces: `avisar_desincronizacion(paths, etiqueta="fuentes") -> bool`. **La firma no cambia**, sólo el criterio: devuelve `True` si hay desfase. Las tres llamadas existentes en `unificar.py`, `extract_alias.py` y `trocear_detalle.py` siguen valiendo sin tocarlas.

- [ ] **Step 1: Escribir los tests que fallan**

Añadir a `scripts/tests/test_fuentes_comun.py`, justo debajo del `import` (que pasa a ser `from fuentes_comun import elegir_fuente, avisar_desincronizacion`):

```python
def test_no_avisa_si_todo_se_descargo_a_la_vez():
    """El caso normal: nombres con tres fechas distintas (XLSX con la de descarga,
    JSON con la del volcado del MAPA, PDF sin fecha) pero una sola sesion de
    descarga. Comparando nombres esto avisaba siempre."""
    tmp = tempfile.mkdtemp()
    try:
        paths = [_tocar(tmp, "ProductosAutorizados-30_07_2026.xlsx"),
                 _tocar(tmp, "ProductosAutorizados_2026_07_27.json"),
                 _tocar(tmp, "dc_web.pdf")]
        assert avisar_desincronizacion(paths) is False
    finally:
        shutil.rmtree(tmp)


def test_avisa_si_una_fuente_es_de_otra_descarga():
    tmp = tempfile.mkdtemp()
    try:
        paths = [_tocar(tmp, "ProductosAutorizados-30_07_2026.xlsx"),
                 _tocar(tmp, "ProductosCancelados-30_07_2026.xlsx"),
                 _tocar(tmp, "ProductosRetirados-20_07_2026.xlsx", antiguedad_h=240)]
        assert avisar_desincronizacion(paths) is True
    finally:
        shutil.rmtree(tmp)


def test_los_pdf_tambien_cuentan():
    """Con el criterio del nombre los PDF quedaban fuera de toda vigilancia."""
    tmp = tempfile.mkdtemp()
    try:
        paths = [_tocar(tmp, "ProductosAutorizados-30_07_2026.xlsx"),
                 _tocar(tmp, "dc_web.pdf", antiguedad_h=240)]
        assert avisar_desincronizacion(paths) is True
    finally:
        shutil.rmtree(tmp)


def test_red_secundaria_por_nombre_si_el_mtime_engana():
    """Copiar ficheros pone el mtime a la hora de la copia y borra la senal. Si las
    fechas de los nombres se separan mas de una semana, eso ya no lo explica el
    desfase estructural entre JSON y XLSX: avisa igual."""
    tmp = tempfile.mkdtemp()
    try:
        paths = [_tocar(tmp, "ProductosAutorizados-30_07_2026.xlsx"),
                 _tocar(tmp, "ProductosCancelados-01_06_2026.xlsx")]
        assert avisar_desincronizacion(paths) is True
    finally:
        shutil.rmtree(tmp)


def test_una_sola_fuente_nunca_desfasa():
    tmp = tempfile.mkdtemp()
    try:
        assert avisar_desincronizacion([_tocar(tmp, "dc_web.pdf")]) is False
    finally:
        shutil.rmtree(tmp)
```

- [ ] **Step 2: Ejecutar y ver qué falla exactamente**

```bash
python scripts/tests/test_fuentes_comun.py
```

Esperado: fallan `test_no_avisa_si_todo_se_descargo_a_la_vez` (la implementación vieja compara nombres y las tres fechas difieren, así que avisa) y `test_los_pdf_tambien_cuentan` (los PDF no tienen fecha en el nombre y hoy se ignoran). Los otros tres ya pasan por casualidad; deben seguir pasando después.

- [ ] **Step 3: Reescribir `avisar_desincronizacion()`**

En `scripts/fuentes_comun.py`, añadir `datetime` al import (`import datetime, glob, os, re`), la constante bajo los `_ISO`/`_DMA` existentes:

```python
# Margen para considerar que dos fuentes salen de la misma sesion de descarga.
VENTANA_DESCARGA_H = 24
# Separacion entre fechas de NOMBRE que ya no explica el desfase estructural entre
# el JSON (fechado por el MAPA) y los XLSX (fechados al descargar).
MARGEN_NOMBRE_D = 7
```

y sustituir la función entera por:

```python
def avisar_desincronizacion(paths, etiqueta="fuentes"):
    """Imprime un WARNING si las fuentes usadas no salen de la misma descarga.
    Devuelve True si hay desfase. Nunca aborta: informa.

    Mira la fecha de MODIFICACION, no el nombre. Cada fuente del MAPA fecha una cosa
    distinta -los XLSX el dia de descarga, el JSON grande el del volcado, y los PDF
    de alias no fechan nada-, asi que comparar nombres avisaba en casi todas las
    generaciones. Un aviso que salta siempre se aprende a ignorar y deja de proteger
    del caso real. Lo que de verdad importa es si se bajo todo de una vez, y eso lo
    dice el mtime.
    """
    reales = [p for p in paths if p and os.path.exists(p)]
    if len(reales) < 2:
        return False

    porfecha = sorted((os.path.getmtime(p), p) for p in reales)
    horas = (porfecha[-1][0] - porfecha[0][0]) / 3600.0

    # Red secundaria: copiar ficheros iguala los mtime y borra la senal de arriba.
    nombradas = [(f, p) for f, p in ((fecha_de_fuente(p), p) for p in reales) if f]
    dias_nombre = 0
    if len(nombradas) > 1:
        fechas = [datetime.date(*f) for f, _ in nombradas]
        dias_nombre = (max(fechas) - min(fechas)).days

    if horas <= VENTANA_DESCARGA_H and dias_nombre <= MARGEN_NOMBRE_D:
        return False

    vieja = porfecha[0][1]
    print("")
    print("  " + "!" * 68)
    if horas > VENTANA_DESCARGA_H:
        print("  AVISO: las %s NO salen de la misma descarga (%.0f h de diferencia)."
              % (etiqueta, horas))
    else:
        print("  AVISO: las %s se descargaron juntas, pero sus nombres llevan fechas"
              % etiqueta)
        print("  separadas %d dias. Revisa si alguna es una copia antigua." % dias_nombre)
    for mt, p in porfecha:
        marca = "  <-- la mas antigua" if p == vieja else ""
        print("     descargada %s   %s%s"
              % (datetime.datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M"),
                 os.path.basename(p), marca))
    print("")
    print("  Los tres pasos (unificar / extract_alias / trocear_detalle) deben")
    print("  partir de la MISMA descarga. Con fuentes descoordinadas pueden aparecer")
    print("  productos sin detalle, alias huerfanos o caducidades desfasadas que den")
    print("  un veredicto erroneo.")
    print("  Vuelve a descargarlo todo del MAPA de una vez y repite el flujo.")
    print("")
    print("  (Mover o copiar ficheros cambia su fecha de modificacion y puede")
    print("   disparar este aviso sin que haya desfase real.)")
    print("  " + "!" * 68)
    print("")
    return True
```

- [ ] **Step 4: Actualizar el docstring del módulo**

En `scripts/fuentes_comun.py`, sustituir el párrafo del docstring que empieza en «Si se actualizan unas fuentes y otras no» por:

```
Si se actualizan unas fuentes y otras no, los tres pasos quedan descoordinados sin
que nada falle de forma visible: fue lo que paso con un registro.json generado con
XLSX viejos, que marcaba como caducados productos ya prorrogados.

Las fechas de los nombres NO sirven para detectarlo, porque cada fuente fecha una
cosa distinta: los XLSX el dia en que los descargas, el JSON grande el dia en que el
MAPA genero el volcado (suele ir unos dias por detras) y los PDF de alias no llevan
fecha ninguna. Comparar nombres avisaria en casi todas las generaciones. Por eso el
aviso mira la fecha de modificacion: lo que importa es si se bajo todo de una vez.
```

- [ ] **Step 5: Ejecutar las pruebas**

```bash
python scripts/tests/test_fuentes_comun.py
```

Esperado: las diez en `ok`.

- [ ] **Step 6: Comprobarlo contra las fuentes reales**

```bash
python -c "import sys; sys.path.insert(0,'scripts'); from fuentes_comun import avisar_desincronizacion as a; print('desfase:', a(['fuentes/ProductosAutorizados-30_07_2026.xlsx','fuentes/ProductosAutorizados_2026_07_27.json','fuentes/dc_web.pdf']))"
```

Esperado: `desfase: False`, sin ningún aviso, pese a que los tres nombres llevan fechas distintas. Y mezclando una del 20/07:

```bash
python -c "import sys; sys.path.insert(0,'scripts'); from fuentes_comun import avisar_desincronizacion as a; print('desfase:', a(['fuentes/ProductosAutorizados-30_07_2026.xlsx','fuentes/ProductosRetirados-20_07_2026.xlsx']))"
```

Esperado: el aviso completo y `desfase: True`.

- [ ] **Step 7: Commit**

```bash
git add scripts/fuentes_comun.py scripts/tests/test_fuentes_comun.py
git commit -m "fix(fuentes): avisar por fecha de descarga en vez de por el nombre"
```

---

### Task 3: Los tres scripts usan `elegir_fuente()`

**Files:**
- Modify: `scripts/unificar.py:70-72` (borrar `find_by_prefix`) y `:179`
- Modify: `scripts/extract_alias.py:53-59` (borrar `find_by_prefix`) y `:243-244`
- Modify: `scripts/trocear_detalle.py:44-46` (borrar `find_by_prefix`) y `:87`

**Interfaces:**
- Consumes: `elegir_fuente(folder, prefix, exts)` de la Tarea 1.
- Produces: nada nuevo. Es una sustitución con salida idéntica.

- [ ] **Step 1: Guardar la referencia de regresión**

Antes de tocar nada, apartar una copia del artefacto publicado y montar una carpeta con **sólo** las fuentes del 20/07, que son las que lo generaron:

```bash
cd "C:/Users/Zerbinek SL/Desktop/DESARROLLOS/fitoScannerMini"
mkdir -p ../fito-pruebas/fuentes20 ../fito-pruebas/salida
cp registro.json ../fito-pruebas/registro-publicado.json
cp fuentes/*-20_07_2026.xlsx ../fito-pruebas/fuentes20/
cp fuentes/ProductosAutorizados_2026_07_17.json ../fito-pruebas/fuentes20/
ls ../fito-pruebas/fuentes20/
```

Esperado: los tres XLSX del 20/07 y el JSON del 17/07.

- [ ] **Step 2: Comprobar que la referencia reproduce el artefacto actual**

Con el código **sin tocar todavía**:

```bash
python scripts/unificar.py --src ../fito-pruebas/fuentes20 --out ../fito-pruebas/salida
python -c "import hashlib;h=lambda p:hashlib.md5(open(p,'rb').read()).hexdigest();print(h('../fito-pruebas/salida/registro.json'));print(h('../fito-pruebas/registro-publicado.json'))"
```

Esperado: los dos hashes iguales. Si no lo son, **parar**: significa que el `registro.json` publicado no salió de esas fuentes, y hay que averiguar por qué antes de seguir (si no, la regresión del paso 6 no demuestra nada).

- [ ] **Step 3: Sustituir en `unificar.py`**

Borrar la función completa (líneas 70-72):

```python
def find_by_prefix(folder, prefix):
    hits = sorted(glob.glob(os.path.join(folder, prefix + "*.xlsx")))
    return hits[-1] if hits else None
```

Cambiar el import de `fuentes_comun` (línea 26) a:

```python
from fuentes_comun import avisar_desincronizacion, elegir_fuente
```

Y en `main()` (línea 179), sustituir:

```python
        path = find_by_prefix(args.src, prefijo)
```

por:

```python
        path = elegir_fuente(args.src, prefijo, [".xlsx"])
```

Quitar `glob` del import de la línea 23 si ya no se usa en el fichero (comprobar con `grep -n "glob\." scripts/unificar.py` antes de tocarlo).

- [ ] **Step 4: Sustituir en `trocear_detalle.py`**

Borrar la función (líneas 44-46), cambiar el import a `from fuentes_comun import avisar_desincronizacion, elegir_fuente`, y en la línea 87 sustituir:

```python
    src = find_by_prefix(args.src, "ProductosAutorizados", ".json")
```

por:

```python
    src = elegir_fuente(args.src, "ProductosAutorizados", [".json"])
```

Quitar `glob` del import si queda sin uso (`grep -n "glob\." scripts/trocear_detalle.py`).

- [ ] **Step 5: Sustituir en `extract_alias.py`**

Borrar la función (líneas 53-59), cambiar el import a `from fuentes_comun import avisar_desincronizacion, elegir_fuente`, y en las líneas 243-244 sustituir:

```python
    dc_pdf = find_by_prefix(args.src, "dc_web", [".pdf"])
    ip_pdf = find_by_prefix(args.src, "ip_web", [".pdf"])
```

por:

```python
    dc_pdf = elegir_fuente(args.src, "dc_web", [".pdf"])
    ip_pdf = elegir_fuente(args.src, "ip_web", [".pdf"])
```

La lista de extensiones ya era una lista, así que las llamadas quedan idénticas salvo el nombre. Quitar `glob` del import si queda sin uso (`grep -n "glob\." scripts/extract_alias.py`).

- [ ] **Step 6: Regresión — el artefacto no cambia**

```bash
rm -f ../fito-pruebas/salida/registro.json
python scripts/unificar.py --src ../fito-pruebas/fuentes20 --out ../fito-pruebas/salida
python -c "import hashlib;h=lambda p:hashlib.md5(open(p,'rb').read()).hexdigest();print(h('../fito-pruebas/salida/registro.json'));print(h('../fito-pruebas/registro-publicado.json'))"
```

Esperado: los dos hashes siguen coincidiendo. El refactor no altera la salida.

- [ ] **Step 7: Comprobar los otros dos scripts sin escribir en el repo**

```bash
python scripts/extract_alias.py --src fuentes --out ../fito-pruebas/salida
python scripts/trocear_detalle.py --src fuentes --out ../fito-pruebas/salida
```

Esperado: ambos terminan sin error, anuncian qué fuente eligen y qué descartan, y **no** dan aviso de desfase (todas las fuentes elegidas son de la descarga de hoy). Anotar de la salida el número de alias y el de ficheros de detalle: son los valores de referencia que necesita la Tarea 7.

Comprobar que no han tocado el repo:

```bash
git status --porcelain
```

Esperado: sólo los tres `scripts/*.py` modificados. Si aparecen `alias.json`, `registro.json` o `detalle/`, es que un `--out` estaba mal puesto: revertir con `git checkout -- <fichero>`.

- [ ] **Step 8: Commit**

```bash
git add scripts/unificar.py scripts/extract_alias.py scripts/trocear_detalle.py
git commit -m "refactor(scripts): unificar la localizacion de fuentes en elegir_fuente()"
```

---

### Task 4: Generador de ZIP en el navegador

**Files:**
- Modify: `index.html` (funciones nuevas junto a `download()`, sobre la línea 852)
- Test: `scripts/tests/test_zip.mjs`, `scripts/tests/verifica_zip.py`

**Interfaces:**
- Consumes: nada del código existente.
- Produces, todo dentro del IIFE de `index.html`:
  - `crc32(u8) -> Number` — CRC32 sin signo de un `Uint8Array`.
  - `zipStore(entradas) -> Blob` — `entradas` es un array de `{nombre: String, datos: Uint8Array, fecha: Date}`. Devuelve un Blob `application/zip`.
  - `dataUrlABytes(dataUrl) -> Uint8Array`.
  - `pad4(n) -> String`, `saneaNombre(s) -> String`.
  - Los usa la Tarea 5.

- [ ] **Step 1: Escribir el test que falla**

Crear `scripts/tests/test_zip.mjs`:

```js
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
const csv = '\uFEFFa;b\r\n1;2';
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
```

Crear `scripts/tests/verifica_zip.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abre el ZIP que genera test_zip.mjs con el modulo zipfile, que es una
implementacion del formato independiente de la nuestra: si el ZIP esta mal
construido, aqui se ve.

Ejecutar (despues de node scripts/tests/test_zip.mjs):
    python scripts/tests/verifica_zip.py
"""

import sys, zipfile

RUTA = "../fito-pruebas/prueba.zip"

with zipfile.ZipFile(RUTA) as z:
    malo = z.testzip()                      # None si todos los CRC cuadran
    assert malo is None, "CRC incorrecto en %s" % malo

    nombres = z.namelist()
    assert nombres == ["auditoria.csv",
                       "fotos/0001_ES-00891.jpg",
                       "fotos/0004_25.123.jpg"], nombres

    csv = z.read("auditoria.csv").decode("utf-8-sig")
    assert csv == "a;b\r\n1;2", repr(csv)

    assert z.read("fotos/0004_25.123.jpg") == b"\x01\x02\x03\x04\x05"

    info = z.getinfo("auditoria.csv")
    assert info.date_time[:5] == (2026, 7, 30, 12, 34), info.date_time
    assert info.compress_type == zipfile.ZIP_STORED

    # Una fecha anterior a 1980 no cabe en el formato DOS: se guarda como 1980-01-01
    # en vez de corromper la entrada.
    assert z.getinfo("fotos/0004_25.123.jpg").date_time[:3] == (1980, 1, 1)

print("ZIP correcto: %d entradas, CRC y fechas validados por zipfile" % len(nombres))
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
node scripts/tests/test_zip.mjs
```

Esperado: `Error: No encuentro el bloque "zip" en index.html`.

- [ ] **Step 3: Implementar el bloque en `index.html`**

Insertar justo **antes** de la función `download()` (línea 852), dentro del IIFE:

```js
/* --- zip: inicio ---------------------------------------------------------------
   Generador de ZIP minimo, metodo 0 (almacenado, sin comprimir). Las fotos ya son
   JPEG y el CSV pesa kilobytes, asi que deflate no aportaria nada y obligaria a
   meter la unica pieza realmente delicada del formato. Sin ZIP64: el formato
   clasico admite 65.535 entradas y 4 GB, y un registro de almacen no se acerca.
   Los nombres se sanean a ASCII (saneaNombre), asi que no hace falta la bandera
   de UTF-8 del bit 11.
   Ojo: scripts/tests/test_zip.mjs localiza este bloque por estos marcadores. */
var CRC_TABLA=null;
function crc32(u8){
  if(!CRC_TABLA){                       // se construye en la primera exportacion, no al arrancar
    CRC_TABLA=new Uint32Array(256);
    for(var n=0;n<256;n++){ var c=n;
      for(var k=0;k<8;k++){ c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1); }
      CRC_TABLA[n]=c>>>0;
    }
  }
  var crc=0xFFFFFFFF;
  for(var i=0;i<u8.length;i++) crc=(crc>>>8)^CRC_TABLA[(crc^u8[i])&0xFF];
  return (crc^0xFFFFFFFF)>>>0;
}
/* Hora y fecha en formato MS-DOS, que es lo que guarda el ZIP. No representa nada
   anterior a 1980: una fecha imposible se guarda como 1980-01-01 antes que corromper
   la entrada. */
function dosFecha(d){
  var y=d.getFullYear();
  if(y<1980) return {t:0, f:33};        // 33 = (0<<9)|(1<<5)|1
  return { t:((d.getHours()<<11)|(d.getMinutes()<<5)|(d.getSeconds()>>1))>>>0,
           f:(((y-1980)<<9)|((d.getMonth()+1)<<5)|d.getDate())>>>0 };
}
function pad4(n){ return ('000'+n).slice(-4); }
function saneaNombre(s){ return String(s==null?'':s).replace(/[^A-Za-z0-9._-]/g,'_'); }
function dataUrlABytes(u){
  var s=String(u), bin=atob(s.slice(s.indexOf(',')+1)), u8=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++) u8[i]=bin.charCodeAt(i);
  return u8;
}
function zipStore(entradas){
  var enc=new TextEncoder(), partes=[], central=[], off=0;
  entradas.forEach(function(e){
    var nom=enc.encode(e.nombre), datos=e.datos, crc=crc32(datos), dt=dosFecha(e.fecha);
    var lh=new Uint8Array(30+nom.length), v=new DataView(lh.buffer);
    v.setUint32(0,0x04034b50,true); v.setUint16(4,20,true); v.setUint16(6,0,true);
    v.setUint16(8,0,true); v.setUint16(10,dt.t,true); v.setUint16(12,dt.f,true);
    v.setUint32(14,crc,true); v.setUint32(18,datos.length,true); v.setUint32(22,datos.length,true);
    v.setUint16(26,nom.length,true); v.setUint16(28,0,true);
    lh.set(nom,30);
    partes.push(lh,datos);
    var ch=new Uint8Array(46+nom.length), w=new DataView(ch.buffer);
    w.setUint32(0,0x02014b50,true); w.setUint16(4,20,true); w.setUint16(6,20,true);
    w.setUint16(8,0,true); w.setUint16(10,0,true); w.setUint16(12,dt.t,true); w.setUint16(14,dt.f,true);
    w.setUint32(16,crc,true); w.setUint32(20,datos.length,true); w.setUint32(24,datos.length,true);
    w.setUint16(28,nom.length,true); w.setUint32(42,off,true);
    ch.set(nom,46);
    central.push(ch);
    off+=lh.length+datos.length;
  });
  var tam=0; central.forEach(function(c){ tam+=c.length; });
  var eocd=new Uint8Array(22), z=new DataView(eocd.buffer);
  z.setUint32(0,0x06054b50,true);
  z.setUint16(8,entradas.length,true); z.setUint16(10,entradas.length,true);
  z.setUint32(12,tam,true); z.setUint32(16,off,true);
  return new Blob(partes.concat(central,[eocd]), {type:'application/zip'});
}
/* --- zip: fin --- */
```

- [ ] **Step 4: Ejecutar el test de Node**

```bash
node scripts/tests/test_zip.mjs
```

Esperado: las seis comprobaciones en `ok` y `escrito ../fito-pruebas/prueba.zip`.

- [ ] **Step 5: Verificar el ZIP con una implementación independiente**

```bash
python scripts/tests/verifica_zip.py
```

Esperado: `ZIP correcto: 3 entradas, CRC y fechas validados por zipfile`. Si `testzip()` señala una entrada, el CRC o los tamaños están mal escritos.

- [ ] **Step 6: Abrirlo a mano una vez**

```bash
explorer.exe "$(cygpath -w ../fito-pruebas/prueba.zip)"
```

Esperado: el Explorador de Windows lo abre sin avisos y muestra `auditoria.csv` y la carpeta `fotos`. Es la comprobación de que un consumidor real lo acepta, no sólo las librerías.

- [ ] **Step 7: Commit**

```bash
git add index.html scripts/tests/test_zip.mjs scripts/tests/verifica_zip.py
git commit -m "feat(export): generador de ZIP sin dependencias para el registro"
```

---

### Task 5: El CSV admite rutas de fotos y aparece `exportZip()`

**Files:**
- Modify: `index.html:853-859` (`exportCsv`), y añadir `exportZip` a continuación
- Test: `scripts/tests/test_zip.mjs` (ampliar)

**Interfaces:**
- Consumes: `zipStore`, `dataUrlABytes`, `pad4`, `saneaNombre` (Tarea 4); `allPhotos()`, `download()`, `stamp()`, `fmtDate()`, `pad()`, `showBusy()`, `hideBusy()`, `toast()`, `LOG` (ya existentes).
- Produces: `csvTexto(rutas) -> String` (si `rutas` es nulo, la columna `Foto` vuelve a `sí`/`no`); `exportCsv()`, `exportZip()`, `exportJson()`, las tres sin argumentos y sin comprobar si el registro está vacío — de eso se encarga el botón en la Tarea 6.

- [ ] **Step 1: Añadir el test que falla**

Añadir a `scripts/tests/test_zip.mjs`, antes del bloque que escribe el ZIP. Como `csvTexto` usa `LOG`, se declara la variable en el propio bloque evaluado:

```js
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

comprueba('csvTexto entrecomilla lo que lleva separador', () => {
  const txt = csvApi(LOG_FALSO)(null);
  if (txt.indexOf('"sin;punto,coma"') === -1) throw new Error('no entrecomilla el punto y coma');
  if (txt.indexOf('""comillas""') === -1) throw new Error('no duplica las comillas internas');
});
```

Ojo con el orden: `LOG` guarda lo más reciente primero (`LOG.unshift`), y el CSV lo invierte, así que `e1` es la fila 1 y `e2` la fila 2.

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
node scripts/tests/test_zip.mjs
```

Esperado: `Error: No encuentro el bloque "csv" en index.html`.

- [ ] **Step 3: Refactorizar `exportCsv()` y añadir `exportZip()`**

Sustituir la función `exportCsv()` entera (líneas 853-859) por:

```js
/* --- csv: inicio ---------------------------------------------------------------
   rutas: mapa id -> ruta del fichero dentro del ZIP. Sin el (exportacion suelta)
   la columna Foto vuelve a si/no, porque ahi no hay ficheros a los que apuntar.
   Ojo: scripts/tests/test_zip.mjs localiza este bloque por estos marcadores. */
function csvTexto(rutas){
  var rows=[['Fecha','Hora','N registro','Producto','Titular','Veredicto','Fecha limite','Nota','Foto']];
  LOG.slice().reverse().forEach(function(e){
    var d=new Date(e.ts);
    var foto=rutas ? (rutas[e.id]||'') : (e.foto?'sí':'no');
    rows.push([fmtDate(d), pad(d.getHours())+':'+pad(d.getMinutes()), e.nreg, e.nombre,
               e.titular, e.estado, e.decisive||'', e.note||'', foto]);
  });
  return '\uFEFF'+rows.map(function(r){
    return r.map(function(c){ c=String(c==null?'':c);
      return /[";,\n]/.test(c)?'"'+c.replace(/"/g,'""')+'"':c;
    }).join(';');
  }).join('\r\n');
}
/* --- csv: fin --- */

function exportCsv(){ download('auditoria_fitos_'+stamp()+'.csv', csvTexto(null), 'text/csv;charset=utf-8'); }

/* El ZIP lleva el CSV mas una carpeta fotos/. El numero del nombre de cada foto es
   su numero de fila en el CSV, asi que ademas de por la columna Foto se pueden
   correlacionar por posicion. Una entrada marcada con foto cuya imagen no aparezca
   -registro restaurado en otro movil, o IndexedDB purgado por el sistema- se trata
   como sin foto en vez de romper la exportacion. */
function exportZip(){
  showBusy('Preparando el ZIP…');
  allPhotos().then(function(all){
    var rutas={}, entradas=[];
    LOG.slice().reverse().forEach(function(e,i){
      if(!e.foto || !all[e.id]) return;
      var nom='fotos/'+pad4(i+1)+'_'+saneaNombre(e.nreg)+'.jpg';
      rutas[e.id]=nom;
      entradas.push({nombre:nom, datos:dataUrlABytes(all[e.id]), fecha:new Date(e.ts)});
    });
    var sello=stamp(), fotos=entradas.length;
    entradas.unshift({nombre:'auditoria_fitos_'+sello+'.csv',
                      datos:new TextEncoder().encode(csvTexto(rutas)), fecha:new Date()});
    // download() envuelve lo que reciba en un Blob, y new Blob([blob]) es valido:
    // asi la descarga se hace en un solo sitio para los tres formatos.
    download('auditoria_fitos_'+sello+'.zip', zipStore(entradas), 'application/zip');
    hideBusy();
    toast(fotos?(fotos+' foto'+(fotos===1?'':'s')+' en el ZIP'):'ZIP sin fotos');
  }).catch(function(){ hideBusy(); toast('No se pudo generar el ZIP'); });
}
```

Y quitar de `exportJson()` (línea 860) su comprobación de registro vacío, que pasa al botón:

```js
function exportJson(){
  allPhotos().then(function(all){
```

- [ ] **Step 4: Ejecutar los tests**

```bash
node scripts/tests/test_zip.mjs && python scripts/tests/verifica_zip.py
```

Esperado: las nueve comprobaciones en `ok` y el ZIP sigue validando.

- [ ] **Step 5: Commit**

```bash
git add index.html scripts/tests/test_zip.mjs
git commit -m "feat(export): exportacion en ZIP con el CSV apuntando a cada foto"
```

---

### Task 6: Selector de formato

**Files:**
- Modify: `index.html:258-262` (botones), `:214` (zona de CSS de modales), `:279` (tras `#mapModal`), `:908` (handlers)

**Interfaces:**
- Consumes: `exportCsv()`, `exportZip()`, `exportJson()` (Tarea 5); `toast()`, `LOG`.
- Produces: nada que consuma otra tarea.

- [ ] **Step 1: Sustituir los dos botones**

En `index.html`, líneas 258-262, sustituir:

```html
      <button class="btn ghost sm" id="expCsv">Exportar CSV</button>
      <button class="btn ghost sm" id="expJson">Exportar JSON</button>
```

por:

```html
      <button class="btn ghost sm" id="btnExport">Exportar</button>
```

- [ ] **Step 2: Añadir el CSS de las opciones**

Justo antes de la línea `@media (min-width:560px)` (línea 214), añadir:

```css
  .expopt{display:block; width:100%; text-align:left; background:var(--panel2); color:var(--tx);
    border:1px solid var(--line2); border-radius:11px; padding:12px 14px; margin-bottom:8px}
  .expopt:active{background:var(--panel)}
  .expopt b{display:block; font-size:15px; font-weight:700}
  .expopt span{display:block; font-size:12.5px; color:var(--tx-mut); margin-top:2px}
```

- [ ] **Step 3: Añadir la hoja**

Después del `</div>` que cierra `#mapModal` (línea 279), añadir:

```html
<div class="modal" id="expModal">
  <div class="sheet">
    <h3>Exportar el registro</h3>
    <p class="d">Elige qué formato necesitas.</p>
    <button class="expopt" data-exp="csv"><b>CSV</b><span>Tabla para Excel. Sin fotos.</span></button>
    <button class="expopt" data-exp="zip"><b>CSV + fotos</b><span>Un ZIP con la tabla y las fotos en una carpeta.</span></button>
    <button class="expopt" data-exp="json"><b>JSON</b><span>Todos los datos, con las fotos incrustadas.</span></button>
    <div class="closeacts"><button class="btn ghost" id="expCancel">Cerrar</button></div>
  </div>
</div>
```

- [ ] **Step 4: Cambiar los handlers**

En la línea 908, sustituir:

```js
$('#expCsv').onclick=exportCsv; $('#expJson').onclick=exportJson;
```

por:

```js
/* La comprobacion de registro vacio vive aqui y no en cada exportador: es la unica
   puerta de entrada a los tres. */
function cerrarExp(){ $('#expModal').classList.remove('show'); }
$('#btnExport').onclick=function(){
  if(!LOG.length){ toast('No hay nada que exportar'); return; }
  $('#expModal').classList.add('show');
};
$('#expCancel').onclick=cerrarExp;
$('#expModal').onclick=function(e){ if(e.target===$('#expModal')) cerrarExp(); };
document.querySelectorAll('.expopt').forEach(function(b){
  b.onclick=function(){ cerrarExp();
    ({csv:exportCsv, zip:exportZip, json:exportJson})[b.dataset.exp]();
  };
});
```

- [ ] **Step 5: Comprobar que no quedan referencias a los botones viejos**

```bash
grep -n "expCsv\|expJson" index.html
```

Esperado: sin resultados.

- [ ] **Step 6: Probarlo en el navegador**

Levantar el servidor **en segundo plano** (con `python -m http.server` en primer
plano el terminal queda bloqueado y no se puede seguir):

```bash
python -m http.server 8765
```

Abrir `http://localhost:8765/`, y con el catálogo cargado:

1. Ir a «Registro» sin nada registrado y pulsar `Exportar` → sale el aviso «No hay nada que exportar» y **no** se abre la hoja.
2. Buscar tres productos y registrarlos: uno con foto, uno sin, y un cuarto buscando algo inexistente para usar «Registrar como no encontrado» (es el que lleva `—` como nº de registro; su foto, si la tiene, prueba el saneado del nombre).
3. `Exportar` → `CSV` → se abre en Excel con acentos correctos y la columna `Foto` en sí/no.
4. `Exportar` → `CSV + fotos` → llega el ZIP; cada ruta de la columna `Foto` corresponde a un fichero existente y cada imagen es la del producto de su fila.
5. `Exportar` → `JSON` → sigue trayendo `foto_base64`.
6. Cerrar la hoja con el botón y tocando el fondo.

- [ ] **Step 7: Verificar el ZIP real con `zipfile`**

Sobre el ZIP descargado en el paso anterior:

```bash
python -c "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); print(z.testzip() or 'CRC correcto'); [print(' ', n) for n in z.namelist()]" ~/Downloads/auditoria_fitos_*.zip
```

Esperado: `CRC correcto` y el listado con el CSV y las fotos.

- [ ] **Step 8: Subir la versión del service worker**

En `sw.js` línea 7, `var CACHE = 'fitos-v3';` pasa a `'fitos-v4'`. Sin esto, los móviles con la app ya instalada seguirían sirviendo el `index.html` viejo del caché.

- [ ] **Step 9: Commit**

```bash
git add index.html sw.js
git commit -m "feat(export): selector de formato en lugar de dos botones"
```

---

### Task 7: Documentar el procedimiento de actualización

**Files:**
- Create: `docs/actualizar-fuentes.md`

**Interfaces:**
- Consumes: los recuentos reales anotados en la Tarea 3, paso 7.
- Produces: nada de código.

- [ ] **Step 1: Reunir las cifras de referencia**

```bash
python scripts/unificar.py --src fuentes --out ../fito-pruebas/salida
```

Anotar de la salida: filas leídas por listado, registros publicados, reparto por origen y duplicados descartados. Junto con el número de alias y de ficheros de detalle de la Tarea 3, son los valores que el doc da como referencia de normalidad.

- [ ] **Step 2: Escribir `docs/actualizar-fuentes.md`**

Con esta estructura, rellenando los recuentos con los del paso anterior:

1. **Qué descargar** — tabla de los seis ficheros con su origen:
   - Los tres XLSX y el JSON: <https://servicio.mapa.gob.es/regfiweb>
   - `dc_web.pdf`: <https://www.mapa.gob.es/dam/mapa/contenido/agricultura/temas/sanidad-vegetal/medios-de-defensa-fitosanitaria/registro-productos-fitosanitarios/dc_web.pdf>
   - `ip_web.pdf`: la misma ruta, cambiando el nombre del fichero.
2. **Cómo llegan** — `ProductosAutorizados-DD_MM_AAAA.xlsx` (fecha de descarga), `ProductosAutorizados_AAAA_MM_DD.json` (fecha del volcado del MAPA, va unos días por detrás), `dc_web.pdf` e `ip_web.pdf` (nombre fijo). **No hay que renombrar nada.** La única regla: descargarlo todo en la misma sesión.
3. **Las viejas** — a `fuentes/historico/` si se quieren conservar. No es obligatorio: los scripts eligen la más reciente.
4. **Los tres comandos**, en este orden:
   ```bash
   python scripts/unificar.py --src fuentes --out .
   python scripts/extract_alias.py --src fuentes --out .
   python scripts/trocear_detalle.py --src fuentes --out .
   ```
5. **Qué mirar** — los recuentos de referencia, y dos advertencias: que si sale el aviso de desincronización hay que parar y volver a descargar; y que **una fuente idéntica a la anterior es normal** (entre el 20 y el 30 de julio de 2026, `ProductosCancelados` llegó byte a byte igual mientras los otros dos sí cambiaron), así que un recuento que no se mueve no significa que la descarga fallara.
6. **Publicar** — subir la versión de `CACHE` en `sw.js` para que los móviles ya instalados recojan el cambio, y `git add` / `commit` / `push`. Recordar que `fuentes/` está en `.gitignore` a propósito: son 50 MB regenerables.

- [ ] **Step 3: Verificar los enlaces**

```bash
curl -sI "https://www.mapa.gob.es/dam/mapa/contenido/agricultura/temas/sanidad-vegetal/medios-de-defensa-fitosanitaria/registro-productos-fitosanitarios/dc_web.pdf" | head -1
```

Esperado: `HTTP/1.1 200 OK` o equivalente. Repetir con `ip_web.pdf`.

- [ ] **Step 4: Limpiar y comprobar que el repo queda como debe**

```bash
rm -rf ../fito-pruebas
git status --porcelain
```

Esperado: sólo `docs/actualizar-fuentes.md` sin seguir. Ni `registro.json`, ni `alias.json`, ni `detalle/` modificados.

- [ ] **Step 5: Commit**

```bash
git add docs/actualizar-fuentes.md
git commit -m "docs: procedimiento de actualizacion de las fuentes del MAPA"
```

---

### Task 8: El aviso recibe solo las fuentes que se usan

Añadida durante la ejecución, al descubrirse al revisar la Tarea 3. No es un fallo de
esa tarea —que era una sustitución sin cambio de comportamiento— sino un hueco del
plan: dos de los tres scripts pasan al aviso ficheros que no son los que
`elegir_fuente()` selecciona.

| Script | Qué pasa hoy al aviso | |
|---|---|---|
| `unificar.py:228` | las tres rutas elegidas | correcto, no se toca |
| `trocear_detalle.py:132` | el JSON elegido **+ todos** los XLSX de la carpeta | incorrecto |
| `extract_alias.py:306` | **todos** los `Productos*`, y **ninguno** de los dos PDF que usa | incorrecto |

Dos consecuencias. Con dos lotes en `fuentes/` —el estado normal tras actualizar, y
el que el arreglo de la Tarea 1 vuelve seguro— el aviso salta siempre: es el falso
positivo permanente que la Tarea 2 vino a eliminar, reintroducido por otra vía. Y la
spec B.4, que exige que los PDF de alias entren en el control de frescura, no se
cumple: con `glob("Productos*")` no entran en ninguna parte.

**Files:**
- Modify: `scripts/extract_alias.py:303-307`
- Modify: `scripts/trocear_detalle.py:130-133`

**Interfaces:**
- Consumes: `elegir_fuente(folder, prefix, exts)` y `avisar_desincronizacion(paths, etiqueta)`, ambas ya implementadas y probadas. **Ninguna de las dos se modifica en esta tarea.**
- Produces: nada nuevo.

- [ ] **Step 1: Comprobar el falso positivo antes de arreglarlo**

```bash
cd "C:/Users/Zerbinek SL/Desktop/DESARROLLOS/fitoScannerMini"
mkdir -p ../fito-pruebas/salida
python scripts/trocear_detalle.py --src fuentes --out ../fito-pruebas/salida 2>&1 | tail -25
```

Esperado: sale el bloque de `AVISO` con los `!!!!`, pese a que las fuentes que el
script elige son todas de la misma descarga. Es el fallo a corregir; anotar la salida
para el informe.

- [ ] **Step 2: Arreglar `trocear_detalle.py`**

Sustituir las líneas 130-133:

```python
    # El detalle sale del JSON grande, pero el registro sale de los XLSX: si no son
    # de la misma descarga aparecen productos sin detalle o detalle inalcanzable.
    otras = sorted(glob.glob(os.path.join(args.src, "Productos*.xlsx")))
    avisar_desincronizacion([src] + otras, "fuentes del MAPA")
```

por:

```python
    # El detalle sale del JSON grande, pero el registro sale de los XLSX: si no son
    # de la misma descarga aparecen productos sin detalle o detalle inalcanzable.
    # Se comparan las fuentes que de verdad se usan, no todo lo que haya en la
    # carpeta: con dos descargas conviviendo, mirar las descartadas hacia saltar el
    # aviso siempre, que es justo lo que lo vuelve inutil.
    otras = [elegir_fuente(args.src, p, [".xlsx"])
             for p in ("ProductosAutorizados", "ProductosCancelados", "ProductosRetirados")]
    avisar_desincronizacion([src] + [o for o in otras if o], "fuentes del MAPA")
```

Comprobar si `glob` sigue usándose en el fichero (`grep -n "glob\." scripts/trocear_detalle.py`) y quitarlo del import solo si no.

- [ ] **Step 3: Arreglar `extract_alias.py`**

Sustituir las líneas 303-307:

```python
    # Los PDF de alias no llevan fecha en el nombre; se comprueba que las hojas del
    # MAPA presentes en la misma carpeta sean de una unica descarga.
    avisar_desincronizacion(sorted(glob.glob(os.path.join(args.src, "Productos*"))),
                            "fuentes del MAPA")
```

por:

```python
    # Los PDF de alias no llevan fecha en el nombre, asi que su unica senal de
    # frescura es el mtime: por eso entran en la comparacion en lugar de quedarse
    # fuera, como estaban. El XLSX de autorizados va como referencia de cuando fue
    # la ultima descarga; se toma el que elegiria cualquier otro paso, no todo lo
    # que haya en la carpeta.
    ref = elegir_fuente(args.src, "ProductosAutorizados", [".xlsx"])
    avisar_desincronizacion([p for p in (dc_pdf, ip_pdf, ref) if p],
                            "fuentes del MAPA")
```

Comprobar si `glob` sigue usándose (`grep -n "glob\." scripts/extract_alias.py`) y quitarlo del import solo si no.

- [ ] **Step 4: El falso positivo desaparece**

```bash
python scripts/trocear_detalle.py --src fuentes --out ../fito-pruebas/salida 2>&1 | tail -12
python scripts/extract_alias.py --src fuentes --out ../fito-pruebas/salida 2>&1 | tail -12
```

Esperado: ninguno de los dos imprime el bloque de `AVISO`, y ambos terminan con sus
recuentos normales (unos 2871 alias y 2062 ficheros de detalle).

- [ ] **Step 5: El aviso verdadero sigue saltando**

Ahora se retrasa a mano el `mtime` de uno de los PDF diez días y se comprueba que el
aviso vuelve — es lo que la spec B.4 pide y hoy no ocurre nunca:

```bash
python -c "
import os, time
p='fuentes/dc_web.pdf'
t=time.time()-10*86400
os.utime(p,(t,t))
print('mtime de dc_web.pdf retrasado 10 dias')
"
python scripts/extract_alias.py --src fuentes --out ../fito-pruebas/salida 2>&1 | tail -20
```

Esperado: aparece el bloque de `AVISO` señalando `dc_web.pdf` como la más antigua.

Devolver el fichero a su estado real, porque es una fuente de verdad del usuario y no
un fichero de prueba:

```bash
python -c "
import os, time
p='fuentes/dc_web.pdf'
t=time.time()
os.utime(p,(t,t))
print('mtime de dc_web.pdf restaurado a ahora')
"
```

- [ ] **Step 6: Comprobar que el repo no ha cambiado**

```bash
git status --porcelain
```

Esperado: sólo los dos `.py` modificados. Si aparecen `registro.json`, `alias.json` o
`detalle/`, revertir con `git checkout -- <ruta>`.

- [ ] **Step 7: Commit**

```bash
git add scripts/extract_alias.py scripts/trocear_detalle.py
git commit -m "fix(fuentes): comparar solo las fuentes usadas, con los PDF incluidos"
```

---

## Comprobación final

- [ ] `python scripts/tests/test_fuentes_comun.py` → las diez en `ok`
- [ ] `node scripts/tests/test_zip.mjs` → las nueve en `ok`
- [ ] `python scripts/tests/verifica_zip.py` → ZIP correcto
- [ ] `git status --porcelain` → limpio, con `registro.json`, `alias.json` y `detalle/` intactos
- [ ] `git log --oneline -7` → siete commits, uno por tarea
