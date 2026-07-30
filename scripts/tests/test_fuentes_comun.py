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
