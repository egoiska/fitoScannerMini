#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Capa 3 - trocea el JSON grande del MAPA (ProductosAutorizados_*.json, ~48 MB) en un
fichero pequeño por producto:  /detalle/<Num_Registro normalizado>.json

Se guardan SOLO los campos que la ficha de la PWA pinta (renderDetalle()):
  - 10 campos de USOS[i]  (los 10 restantes se descartan: codigos internos,
    volumenes, Bbch, TipoUsuario, SistemaCultivo y CondicionamientoEspecifico,
    este ultimo porque duplicaria el peso total: +11,8 MB sobre 14,6 MB)
  - COMPOSICION (sustancia / concentracion / unidad)
  - Condicionamiento general del producto

Los campos vacios se omiten, y solo se escribe fichero para los productos que
tienen detalle: la ausencia (404) es la senal de "sin usos publicados".

Uso:
    python scripts/trocear_detalle.py --src fuentes --out .
"""

import argparse, glob, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuentes_comun import avisar_desincronizacion

# Campos de USOS[i] que se publican, en el orden en que se escriben.
USO_CAMPOS = [
    "Cultivo", "Agente",
    "Dosis_Min", "Dosis_Max", "Unidad Medida dosis",
    "Plazo Seguridad",
    "Aplicaciones", "IntervaloAplicaciones",
    "MetodoAplicacion", "Ambito",
]
COMP_CAMPOS = ["Nombre Sustancia", "Concentracion", "DescripcionNota"]

VACIOS = (None, "", 0, 0.0)


def norm_nreg(s):
    """Misma normalizacion que normNreg() en la PWA (ES-00461 -> ES00461)."""
    return re.sub(r'[^A-Za-z0-9]', '', str(s or '')).upper()


def find_by_prefix(folder, prefix, ext):
    hits = sorted(glob.glob(os.path.join(folder, prefix + "*" + ext)))
    return hits[-1] if hits else None


def build_doc(prod):
    """Documento de detalle de un producto, sin campos vacios."""
    dp = prod.get("DATOSPRODUCTO", {})
    doc = {"nreg": dp.get("Num_Registro", "")}

    cond = (dp.get("Condicionamiento") or "").strip()
    if cond:
        doc["Condicionamiento"] = cond

    comp = []
    for c in prod.get("COMPOSICION", []):
        item = {k: c[k] for k in COMP_CAMPOS if c.get(k) not in VACIOS}
        if item:
            comp.append(item)
    if comp:
        doc["COMPOSICION"] = comp

    usos = []
    for u in prod.get("USOS", []):
        item = {k: u[k] for k in USO_CAMPOS if u.get(k) not in VACIOS}
        if item:
            usos.append(item)
    # renderDetalle() pinta los usos en el orden del array (no agrupa ni ordena),
    # asi que se ordenan aqui: por cultivo y, dentro de cada cultivo, por agente.
    usos.sort(key=lambda x: (str(x.get("Cultivo", "")).upper(),
                             str(x.get("Agente", "")).upper()))
    doc["usos"] = usos
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="fuentes", help="carpeta con ProductosAutorizados_*.json")
    ap.add_argument("--out", default=".", help="raiz del sitio (se escribe <out>/detalle/)")
    ap.add_argument("--keep", action="store_true",
                    help="no borrar los ficheros de detalle previos")
    args = ap.parse_args()

    src = find_by_prefix(args.src, "ProductosAutorizados", ".json")
    if not src:
        sys.exit("No encuentro ProductosAutorizados*.json en " + args.src)

    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    productos = data.get("Productos") if isinstance(data, dict) else data
    if not productos:
        sys.exit("El JSON no trae lista 'Productos'")

    outdir = os.path.join(args.out, "detalle")
    # Regenerar limpio: si un producto desaparece del MAPA, su fichero no debe
    # quedarse huerfano dando detalle de algo que ya no esta autorizado.
    if os.path.isdir(outdir) and not args.keep:
        shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)

    total, escritos, sin_usos, dup = 0, 0, 0, 0
    vistos = set()
    for p in productos:
        total += 1
        nreg = norm_nreg(p.get("DATOSPRODUCTO", {}).get("Num_Registro"))
        if not nreg:
            continue
        if nreg in vistos:
            dup += 1
            continue
        vistos.add(nreg)
        doc = build_doc(p)
        if not doc["usos"] and "COMPOSICION" not in doc and "Condicionamiento" not in doc:
            sin_usos += 1
            continue          # nada que mostrar: mejor 404 que un fichero vacio
        with open(os.path.join(outdir, nreg + ".json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        escritos += 1

    peso = sum(os.path.getsize(os.path.join(outdir, n)) for n in os.listdir(outdir))
    print("\n== RESUMEN detalle ==")
    print(f"  fuente            : {os.path.basename(src)}")
    print(f"  productos leidos  : {total}")
    print(f"  ficheros escritos : {escritos}")
    if dup:
        print(f"  duplicados omitidos: {dup}")
    if sin_usos:
        print(f"  sin nada que mostrar: {sin_usos}")
    print(f"  peso total        : {peso/1048576:.1f} MB  (media {peso/max(escritos,1)/1024:.1f} KB)")
    print(f"  -> {outdir}")

    # El detalle sale del JSON grande, pero el registro sale de los XLSX: si no son
    # de la misma descarga aparecen productos sin detalle o detalle inalcanzable.
    otras = sorted(glob.glob(os.path.join(args.src, "Productos*.xlsx")))
    avisar_desincronizacion([src] + otras, "fuentes del MAPA")


if __name__ == "__main__":
    main()
