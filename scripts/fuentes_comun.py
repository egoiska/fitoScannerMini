# -*- coding: utf-8 -*-
"""
Utilidades compartidas por los scripts de las tres capas.

Las descargas del MAPA llevan la fecha en el nombre, con DOS formatos distintos:
    ProductosAutorizados-20_07_2026.xlsx    -> DD_MM_AAAA
    ProductosAutorizados_2026_07_17.json    -> AAAA_MM_DD

Si se actualizan unas fuentes y otras no, los tres pasos quedan descoordinados sin
que nada falle de forma visible: fue lo que paso con un registro.json generado con
XLSX viejos, que marcaba como caducados productos ya prorrogados. Estas funciones
detectan ese desfase y lo avisan.
"""

import glob, os, re

# AAAA_MM_DD primero: si empieza por 4 digitos no puede ser DD_MM_AAAA.
_ISO = re.compile(r'(?<!\d)(\d{4})[-_](\d{1,2})[-_](\d{1,2})(?!\d)')
_DMA = re.compile(r'(?<!\d)(\d{1,2})[-_](\d{1,2})[-_](\d{4})(?!\d)')


def fecha_de_fuente(path):
    """Devuelve (AAAA, MM, DD) de la fecha del nombre de fichero, o None."""
    base = os.path.basename(path or "")
    m = _ISO.search(base)
    if m:
        a, mes, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _DMA.search(base)
        if not m:
            return None
        d, mes, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mes <= 12 and 1 <= d <= 31):
        return None
    return (a, mes, d)


def fmt_fecha(f):
    return "%04d-%02d-%02d" % f if f else "sin fecha"


def avisar_desincronizacion(paths, etiqueta="fuentes"):
    """Imprime un WARNING si las fuentes usadas no son de la misma fecha.
    Devuelve True si hay desfase. Nunca aborta: informa."""
    conocidas = []
    for p in paths:
        if not p:
            continue
        f = fecha_de_fuente(p)
        if f:
            conocidas.append((f, os.path.basename(p)))
    fechas = {f for f, _ in conocidas}
    if len(fechas) <= 1:
        return False
    nueva, vieja = max(fechas), min(fechas)
    dias = (nueva[0] - vieja[0]) * 365 + (nueva[1] - vieja[1]) * 30 + (nueva[2] - vieja[2])
    print("")
    print("  " + "!" * 68)
    print("  AVISO: las %s NO son todas de la misma fecha (desfase ~%d dias)." % (etiqueta, abs(dias)))
    for f, nombre in sorted(conocidas):
        marca = "  <-- la mas antigua" if f == vieja else ""
        print("     %s  %s%s" % (fmt_fecha(f), nombre, marca))
    print("")
    print("  Los tres pasos (unificar / extract_alias / trocear_detalle) deben")
    print("  partir de la MISMA descarga. Con fuentes de fechas distintas pueden")
    print("  aparecer productos sin detalle, alias huerfanos o caducidades")
    print("  desfasadas que den un veredicto erroneo.")
    print("  Vuelve a descargar todo del MAPA con la misma fecha y repite el flujo.")
    print("  " + "!" * 68)
    print("")
    return True


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
