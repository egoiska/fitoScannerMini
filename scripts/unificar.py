#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capa 1 - unifica los tres listados XLSX del MAPA en un unico registro.json.

Fuentes (se localizan por PREFIJO porque el nombre lleva fecha):
    ProductosAutorizados*.xlsx   cabecera en fila 5, columnas sin guion bajo
    ProductosCancelados*.xlsx    cabecera en fila 1, columnas con guion bajo
    ProductosRetirados*.xlsx     cabecera en fila 5, columnas sin guion bajo

La cabecera se detecta buscando la fila que contiene la columna del numero de
registro, asi que los preambulos ("Filtros usados", "Fecha informe: ...") no
importan aunque cambien de tamano entre descargas.

Salida: registro.json en --out, array plano. Cada listado aporta su propio juego
de campos (el XLSX de cancelados trae 7 columnas y el de autorizados 13), igual
que el registro.json historico; se anade el campo Origen.

Uso:
    python scripts/unificar.py --src fuentes --out .
"""

import argparse, datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuentes_comun import avisar_desincronizacion, elegir_fuente

try:
    import openpyxl
except ImportError:
    sys.exit("Falta openpyxl:  pip install openpyxl")

# ------------------------------------------------------------------ utilidades --
def norm_nreg(s):
    """Misma normalizacion que normNreg() en la PWA (ES-00461 -> ES00461)."""
    return re.sub(r'[^A-Za-z0-9]', '', str(s or '')).upper()


def norm_key(s):
    """'Fecha_Caducidad' y 'FechaCaducidad' son la misma columna."""
    return re.sub(r'[^a-z0-9]', '', str(s or '').lower())


def to_iso(v):
    """Fecha a ISO YYYY-MM-DD. Los XLSX mezclan datetime (cancelados) y texto
    dd/mm/aaaa (autorizados y retirados)."""
    if v is None or v == "":
        return ""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    if not s or s == "0":
        return ""
    m = re.match(r'^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', s)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.match(r'^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', s)
    if m:
        return "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return s


def txt(v):
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s == "0" else s


def leer_xlsx(path, col_nreg_norm="numregistro"):
    """Devuelve (cabeceras_normalizadas, filas). Detecta la fila de cabecera
    buscando la columna del numero de registro."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    filas = list(ws.iter_rows(values_only=True))
    wb.close()
    hi = None
    for i, r in enumerate(filas[:20]):
        if any(norm_key(c) == col_nreg_norm for c in r if c is not None):
            hi = i
            break
    if hi is None:
        sys.exit("No encuentro la cabecera (columna del nº de registro) en " + path)
    cab = [norm_key(c) for c in filas[hi]]
    idx = {k: j for j, k in enumerate(cab) if k}
    datos = []
    for r in filas[hi + 1:]:
        if idx.get(col_nreg_norm) is None:
            continue
        if not txt(r[idx[col_nreg_norm]]):
            continue
        datos.append({k: r[j] for k, j in idx.items() if j < len(r)})
    return idx, datos


# ------------------------------------------------------- mapeos por listado --
def rec_autorizado(f):
    return {
        "Origen": "Autorizado",
        "Num_Registro": txt(f.get("numregistro")),
        "Nombre": txt(f.get("nombre")),
        "Titular": txt(f.get("titular")),
        "Fabricante": txt(f.get("fabricante")),
        "Fabrica": txt(f.get("fabrica")),
        "Formulado": txt(f.get("formulado")),
        "Estado": txt(f.get("estado")),          # el XLSX distingue Vigente/Cancelado
        "Fecha_Caducidad": to_iso(f.get("fechacaducidad")),
        "Fecha_Inscripcion": to_iso(f.get("fechainscripcion")),
        "Fecha_LimiteVenta": to_iso(f.get("fechalimiteventa")),
    }


def rec_cancelado(f):
    # El XLSX de cancelados no trae Estado ni fecha de cancelacion: el estado es
    # fijo y la cancelacion es la fecha de resolucion.
    resol = to_iso(f.get("fecharesolucion"))
    return {
        "Origen": "Cancelado",
        "Num_Registro": txt(f.get("numregistro")),
        "Nombre": txt(f.get("nombre")),
        "Titular": txt(f.get("titular")),
        "Formulado": txt(f.get("formulado")),
        "Fecha_Caducidad": to_iso(f.get("fechacaducidad")),
        "Fecha_Resolucion": resol,
        "Fecha_LimiteVenta": to_iso(f.get("fechalimiteventa")),
        "Estado": "Cancelado",
        "Fecha_Cancelacion": resol,
    }


def rec_retirado(f):
    # En este XLSX la columna Estado viene a 0 para todas las filas: se fija.
    return {
        "Origen": "Retirado",
        "Num_Registro": txt(f.get("numregistro")),
        "Nombre": txt(f.get("nombre")),
        "Titular": txt(f.get("titular")),
        "Fabricante": txt(f.get("fabricante")),
        "Fabrica": txt(f.get("fabrica")),
        "Formulado": txt(f.get("formulado")),
        "Estado": "Retirado",
        "Fecha_Caducidad": to_iso(f.get("fechacaducidad")),
        "Fecha_Inscripcion": to_iso(f.get("fechainscripcion")),
        "Fecha_Cancelacion": to_iso(f.get("fechacancelacion")),
        "Fecha_LimiteVenta": to_iso(f.get("fechalimiteventa")),
    }


# Orden de preferencia al deduplicar: si un mismo nº aparece en dos listados, gana
# el estado mas "vivo". Autorizado manda sobre todo (el producto sigue en vigor);
# entre Retirado y Cancelado gana Retirado, que en la practica es la resolucion mas
# reciente y trae mas campos (fecha de inscripcion, fabricante, limite de uso).
PRIORIDAD = {"Autorizado": 0, "Retirado": 1, "Cancelado": 2}

LISTADOS = [
    ("ProductosAutorizados", "Autorizado", rec_autorizado),
    ("ProductosCancelados",  "Cancelado",  rec_cancelado),
    ("ProductosRetirados",   "Retirado",   rec_retirado),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="fuentes", help="carpeta con los tres XLSX")
    ap.add_argument("--out", default=".", help="carpeta donde escribir registro.json")
    args = ap.parse_args()

    por_nreg = {}          # nreg normalizado -> registro elegido
    leidos = {}
    descartes = []         # (nreg, origen_descartado, origen_ganador)
    usados = []            # rutas de las fuentes, para el aviso de desfase

    for prefijo, origen, mapper in LISTADOS:
        path = elegir_fuente(args.src, prefijo, [".xlsx"])
        if not path:
            sys.exit("No encuentro %s*.xlsx en %s" % (prefijo, args.src))
        usados.append(path)
        _, filas = leer_xlsx(path)
        leidos[origen] = len(filas)
        print("%-14s %-45s %5d filas" % (origen, os.path.basename(path), len(filas)))
        for f in filas:
            rec = mapper(f)
            k = norm_nreg(rec["Num_Registro"])
            if not k:
                continue
            prev = por_nreg.get(k)
            if prev is None:
                por_nreg[k] = rec
                continue
            pr, pp = PRIORIDAD[rec["Origen"]], PRIORIDAD[prev["Origen"]]
            if pr < pp:
                gana, pierde = rec, prev
            elif pr > pp:
                gana, pierde = prev, rec
            else:
                # Mismo listado: el MAPA repite el nº con datos distintos (una
                # renovacion). Gana la caducidad mas lejana, que es la vigente;
                # asi el resultado no depende del orden de las filas del XLSX.
                gana, pierde = ((rec, prev)
                                if rec.get("Fecha_Caducidad", "") > prev.get("Fecha_Caducidad", "")
                                else (prev, rec))
            por_nreg[k] = gana
            descartes.append((pierde["Num_Registro"], pierde["Origen"], gana["Origen"],
                              pierde.get("Fecha_Caducidad", ""), gana.get("Fecha_Caducidad", "")))

    # Se publica agrupado por Origen, respetando el orden de cada XLSX.
    salida = []
    for _, origen, _ in LISTADOS:
        salida.extend(r for r in por_nreg.values() if r["Origen"] == origen)

    out = os.path.join(args.out, "registro.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False)

    por_origen = {}
    for r in salida:
        por_origen[r["Origen"]] = por_origen.get(r["Origen"], 0) + 1
    print("\n== RESUMEN registro ==")
    print("  filas leidas      : %d" % sum(leidos.values()))
    print("  registros publicados: %d" % len(salida))
    for o in ("Autorizado", "Cancelado", "Retirado"):
        print("    %-11s %5d" % (o, por_origen.get(o, 0)))
    print("  duplicados descartados: %d" % len(descartes))
    for n, o_p, o_g, f_p, f_g in descartes[:10]:
        print("    %s: descarta %s (cad. %s) -> gana %s (cad. %s)"
              % (n, o_p, f_p or "—", o_g, f_g or "—"))
    print("  -> %s  (%.1f MB)" % (out, os.path.getsize(out) / 1048576))
    avisar_desincronizacion(usados, "hojas XLSX del MAPA")


if __name__ == "__main__":
    main()
