# -*- coding: utf-8 -*-
"""
Utilidades compartidas por los scripts de las tres capas.

Las descargas del MAPA llevan la fecha en el nombre, con DOS formatos distintos:
    ProductosAutorizados-20_07_2026.xlsx    -> DD_MM_AAAA
    ProductosAutorizados_2026_07_17.json    -> AAAA_MM_DD

Si se actualizan unas fuentes y otras no, los tres pasos quedan descoordinados sin
que nada falle de forma visible: fue lo que paso con un registro.json generado con
XLSX viejos, que marcaba como caducados productos ya prorrogados.

Las fechas de los nombres NO sirven para detectarlo, porque cada fuente fecha una
cosa distinta: los XLSX el dia en que los descargas, el JSON grande el dia en que el
MAPA genero el volcado (suele ir unos dias por detras) y los PDF de alias no llevan
fecha ninguna. Comparar nombres avisaria en casi todas las generaciones. Por eso el
aviso mira la fecha de modificacion: lo que importa es si se bajo todo de una vez.
"""

import datetime, glob, os, re

# AAAA_MM_DD primero: si empieza por 4 digitos no puede ser DD_MM_AAAA.
_ISO = re.compile(r'(?<!\d)(\d{4})[-_](\d{1,2})[-_](\d{1,2})(?!\d)')
_DMA = re.compile(r'(?<!\d)(\d{1,2})[-_](\d{1,2})[-_](\d{4})(?!\d)')

# Margen para considerar que dos fuentes salen de la misma sesion de descarga.
VENTANA_DESCARGA_H = 24
# Separacion entre fechas de NOMBRE que ya no explica el desfase estructural entre
# el JSON (fechado por el MAPA) y los XLSX (fechados al descargar).
MARGEN_NOMBRE_D = 7


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
