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
