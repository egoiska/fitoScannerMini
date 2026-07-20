#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_alias.py  --  Capa 2 (Alias) de "Almacen Fitos"

Extrae los alias (Denominaciones Comunes + Importaciones Paralelas) de los dos
PDF originales del MAPA y los cruza, BLINDADO POR NUMERO, contra el registro
unificado (registro.json) para producir:

    alias.json          lista de {alias, tipo:"DC"|"IP", nreg, oficial}
    alias_dudosos.csv   filas que no cerraron el cruce (repaso manual)

METODO DE EXTRACCION (validado sobre dc_web.pdf, 89 pag, 1772 alias, 0 vacios):
  El PDF viene exportado de Excel con BORDES de celda reales. Se usan esas
  lineas como rejilla:
    - lineas VERTICALES  -> separadores de COLUMNA (bandas x)
    - lineas HORIZONTALES -> separadores de FILA   (bandas y)
  Cada palabra se asigna a la celda cuyo CENTRO la contiene. Asi las celdas
  multilinea (direcciones de 3 renglones, nombres largos) se agrupan bien y NO
  se entrelazan columnas. NUNCA se lee "por flujo de texto".

Requisitos:  pip install pdfplumber openpyxl
Uso tipico:  python extract_alias.py --src ./fuentes --out .
Diagnostico: python extract_alias.py --src ./fuentes --report ip   # mapear columnas IP
"""
import argparse, csv, glob, json, os, re, sys, unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fuentes_comun import avisar_desincronizacion

try:
    import pdfplumber
except ImportError:
    sys.exit("Falta pdfplumber:  pip install pdfplumber")

# ---------------------------------------------------------------- utilidades --
NREG_RE = re.compile(r'^(ES-\d{3,5}|\d{4,6})$')

def norm_nreg(s):
    """Normaliza un numero de registro para casar formatos mixtos (ES-00169 vs 22720)."""
    return re.sub(r'[^A-Za-z0-9]', '', str(s or '')).upper()

def norm_name(s):
    return re.sub(r'[^A-Za-z0-9]', '', str(s or '')).upper()

def norm_alias(s):
    """Igual que normAlias() de la PWA (colapsa espacios, trim, mayusculas) pero
    ademas insensible a acentos, como la normalizacion de busqueda de la app."""
    s = unicodedata.normalize('NFD', str(s or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s).strip().upper()

def find_by_prefix(folder, prefix, exts):
    """Localiza una fuente por PREFIJO (los nombres del MAPA llevan fecha)."""
    for ext in exts:
        hits = sorted(glob.glob(os.path.join(folder, prefix + "*" + ext)))
        if hits:
            return hits[0]
    return None

def cluster(vals, tol):
    vals = sorted(vals); out = []
    for v in vals:
        if not out or v - out[-1] > tol:
            out.append(v)
    return out

# ------------------------------------------------ extractor generico de tabla --
def extract_grid(page, vtol=3, htol=3):
    """Devuelve (rows, vx, hy). rows = lista de filas; cada fila = lista de celdas
    (texto ya unido) segun la rejilla real de lineas del PDF."""
    vx = cluster([round(e['x0'], 1) for e in page.edges if e['orientation'] == 'v'], vtol)
    hy = cluster([round(e['top'], 1) for e in page.edges if e['orientation'] == 'h'], htol)
    if len(vx) < 3 or len(hy) < 2:
        return [], vx, hy
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    ncol = len(vx) - 1
    rows = []
    for i in range(len(hy) - 1):
        y0, y1 = hy[i], hy[i + 1]
        cells = [[] for _ in range(ncol)]
        for w in words:
            yc = (w['top'] + w['bottom']) / 2
            if not (y0 <= yc < y1):
                continue
            xc = (w['x0'] + w['x1']) / 2
            for j in range(ncol):
                if vx[j] - 1 <= xc < vx[j + 1] + 1:
                    cells[j].append((w['top'], w['x0'], w['text']))
                    break
        row = [' '.join(t for _, _, t in sorted(c)) for c in cells]
        if any(row):
            rows.append(row)
    return rows, vx, hy

# ---------------------------------------------------- mapeos por fuente (DC/IP) --
# Indices de columna 0-based dentro de la rejilla detectada.
# DC validado: 0 nreg | 1 oficial | 2 empresa | 3 alias | 4 fecha | 5 notas
DC_MAP = {"nreg": 0, "oficial": 1, "alias": 3}
DC_HEADER_HINTS = ("DENOMINACIONES", "Producto de Referencia")

# IP (segun descripcion de columnas del MAPA; la subcolumna DOBLE va DESPUES de
# estas tres, asi que estos indices son estables). CONFIRMAR con --report ip.
#   0 Exp.Nº | 1 Nombre comercial en Espana | 2 Nº de Registro en Espana
#   3 Nombre para su distribucion en Espana | 4a/4b pais origen (DOBLE) | ...
IP_MAP = {"nreg": 2, "oficial": 1, "alias": 3}
IP_HEADER_HINTS = ("Nombre comercial", "Distribuci", "Registro")

def extract_source(pdf_path, colmap, header_hints, tipo):
    """Extrae filas {nreg, oficial, alias, tipo, page} de un PDF con un mapeo dado."""
    recs, pages_no_grid = [], []
    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages, 1):
            rows, vx, hy = extract_grid(page)
            if not rows:
                pages_no_grid.append(pi)
                continue
            need = max(colmap.values())
            for r in rows:
                if len(r) <= need:
                    continue
                joined = ' '.join(r)
                if any(h in joined for h in header_hints) and not NREG_RE.match(norm_and_raw(r[colmap['nreg']])[1]):
                    continue
                nreg_raw = r[colmap['nreg']].strip()
                if not NREG_RE.match(nreg_raw):
                    continue  # cabeceras / basura -> fuera
                recs.append({
                    "tipo": tipo,
                    "page": pi,
                    "nreg": norm_nreg(nreg_raw),
                    "nreg_raw": nreg_raw,
                    "oficial": r[colmap['oficial']].strip(),
                    "alias": r[colmap['alias']].strip(),
                })
    return recs, pages_no_grid

def norm_and_raw(s):
    s = (s or '').strip()
    return s, s

# ---------------------------------------------------------- registro unificado --
def load_register(path):
    """Carga registro.json (lista de dicts). Auto-detecta clave de nº y de nombre."""
    data = json.load(open(path, encoding="utf-8"))
    if not isinstance(data, list) or not data:
        sys.exit("registro.json vacio o no es una lista")
    keys = list(data[0].keys())
    def pick(cands):
        for k in keys:
            if norm_name(k) in [norm_name(c) for c in cands]:
                return k
        for k in keys:
            if any(norm_name(c) in norm_name(k) for c in cands):
                return k
        return None
    k_nreg = pick(["Num_Registro", "NumRegistro", "N Registro", "Nº Registro", "registro"])
    k_name = pick(["Nombre", "Producto", "Denominacion"])
    if not k_nreg:
        sys.exit(f"No encuentro columna de nº de registro en registro.json (claves: {keys})")
    reg_set, name_index = set(), {}
    for row in data:
        nr = norm_nreg(row.get(k_nreg))
        if not nr:
            continue
        reg_set.add(nr)
        if k_name:
            nm = norm_name(row.get(k_name))
            if nm:
                name_index.setdefault(nm, set()).add(nr)
    return reg_set, name_index, k_nreg, k_name

# --------------------------------------------------------- cruce blindado + IO --
def crosscheck(recs, reg_set, name_index):
    alias, dudosos = [], []
    seen = set()
    autoref = {"DC": 0, "IP": 0}
    for r in recs:
        # Un "alias" identico al nombre oficial no es un alias: publicarlo haria que
        # el producto buscado por su propio nombre apareciese marcado como DC/IP.
        if norm_alias(r["alias"]) == norm_alias(r["oficial"]):
            autoref[r["tipo"]] = autoref.get(r["tipo"], 0) + 1
            continue
        key = (r["tipo"], r["nreg"], re.sub(r'\s+', ' ', r["alias"]).strip().upper())
        if key in seen:
            continue
        seen.add(key)
        if r["nreg"] in reg_set:
            r["match"] = "numero"
            alias.append({"alias": r["alias"], "tipo": r["tipo"],
                          "nreg": r["nreg"], "oficial": r["oficial"]})
        else:
            # recuperacion por NOMBRE OFICIAL unico
            cand = name_index.get(norm_name(r["oficial"]))
            if cand and len(cand) == 1:
                r["match"] = "nombre"
                alias.append({"alias": r["alias"], "tipo": r["tipo"],
                              "nreg": next(iter(cand)), "oficial": r["oficial"]})
            else:
                r["match"] = "dudoso"
                dudosos.append(r)
    return alias, dudosos, autoref

def write_outputs(alias, dudosos, outdir):
    ap = os.path.join(outdir, "alias.json")
    json.dump(alias, open(ap, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    dp = os.path.join(outdir, "alias_dudosos.csv")
    with open(dp, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["tipo", "page", "nreg_leido", "oficial_leido", "alias", "motivo"])
        for r in dudosos:
            wr.writerow([r["tipo"], r["page"], r["nreg_raw"], r["oficial"],
                         r["alias"], "sin match numero ni nombre unico"])
    return ap, dp

# --------------------------------------------------------------------- report --
def report_columns(pdf_path, tipo):
    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages, 1):
            rows, vx, hy = extract_grid(page)
            if len(rows) >= 2:
                print(f"[{tipo}] pagina {pi}: {len(vx)-1} columnas detectadas")
                print("  separadores x:", vx)
                print("  fila cabecera detectada (indice -> texto):")
                for j, c in enumerate(rows[0]):
                    print(f"    [{j}] {c!r}")
                print("  primera fila de datos:")
                for j, c in enumerate(rows[1]):
                    print(f"    [{j}] {c!r}")
                return
    print(f"[{tipo}] no se detecto rejilla con lineas; revisar si el PDF tiene bordes.")

# ----------------------------------------------------------------------- main --
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".", help="carpeta con dc_web*.pdf / ip_web*.pdf / registro.json")
    ap.add_argument("--register", default=None, help="ruta a registro.json (por defecto se busca en <out>/, <src>/ y la raiz)")
    ap.add_argument("--out", default=".", help="carpeta de salida para alias.json / alias_dudosos.csv")
    ap.add_argument("--report", choices=["dc", "ip"], help="solo diagnostico de columnas, no genera nada")
    args = ap.parse_args()

    dc_pdf = find_by_prefix(args.src, "dc_web", [".pdf"])
    ip_pdf = find_by_prefix(args.src, "ip_web", [".pdf"])

    if args.report:
        path = dc_pdf if args.report == "dc" else ip_pdf
        if not path:
            sys.exit(f"No encuentro {args.report}_web*.pdf en {args.src}")
        report_columns(path, args.report.upper())
        return

    # Sin --register se busca donde lo deja unificar.py: primero la raiz del sitio
    # (--out, que es donde se publica), luego la carpeta de fuentes.
    if args.register:
        reg_path = args.register
        if not os.path.exists(reg_path):
            sys.exit(f"No encuentro registro.json en {reg_path}")
    else:
        candidatos = [os.path.join(args.out, "registro.json"),
                      os.path.join(args.src, "registro.json"),
                      "registro.json"]
        reg_path = next((p for p in candidatos if os.path.exists(p)), None)
        if not reg_path:
            sys.exit("No encuentro registro.json (buscado en: %s). "
                     "Ejecuta antes unificar.py o pasa --register."
                     % ", ".join(candidatos))

    reg_set, name_index, k_nreg, k_name = load_register(reg_path)
    print(f"registro.json: {len(reg_set)} nº unicos (clave nº='{k_nreg}', nombre='{k_name}')")

    all_recs, warnings = [], []
    if dc_pdf:
        recs, nogrid = extract_source(dc_pdf, DC_MAP, DC_HEADER_HINTS, "DC")
        print(f"DC ({os.path.basename(dc_pdf)}): {len(recs)} filas leidas"
              + (f"  [sin rejilla en pag {nogrid}]" if nogrid else ""))
        all_recs += recs
        if nogrid: warnings.append(("DC", nogrid))
    else:
        print("AVISO: no encuentro dc_web*.pdf")
    if ip_pdf:
        recs, nogrid = extract_source(ip_pdf, IP_MAP, IP_HEADER_HINTS, "IP")
        print(f"IP ({os.path.basename(ip_pdf)}): {len(recs)} filas leidas"
              + (f"  [sin rejilla en pag {nogrid}]" if nogrid else ""))
        all_recs += recs
        if nogrid: warnings.append(("IP", nogrid))
    else:
        print("AVISO: no encuentro ip_web*.pdf (¿lo has descargado?)")

    alias, dudosos, autoref = crosscheck(all_recs, reg_set, name_index)
    ap_path, dp_path = write_outputs(alias, dudosos, args.out)

    by_num = sum(1 for a in all_recs if a.get("match") == "numero")
    by_nam = sum(1 for a in all_recs if a.get("match") == "nombre")
    dud    = len(dudosos)
    tot    = by_num + by_nam + dud
    print("\n== RESUMEN ==")
    print(f"  alias publicados : {len(alias)}")
    print(f"  descartados alias==oficial: {sum(autoref.values())}"
          f"  (DC {autoref.get('DC',0)} / IP {autoref.get('IP',0)})")
    print(f"  cruce por numero : {by_num}"
          + (f"  ({100*by_num/tot:.1f}%)" if tot else ""))
    print(f"  recuperados nombre: {by_nam}")
    print(f"  dudosos          : {dud}"
          + (f"  ({100*dud/tot:.1f}%)" if tot else ""))
    if warnings:
        print("  AVISO rejilla ausente en:", warnings,
              "-> revisar esas paginas (¿PDF sin bordes / reexportado?)")
    print(f"  -> {ap_path}")
    print(f"  -> {dp_path}")

    # Los PDF de alias no llevan fecha en el nombre; se comprueba que las hojas del
    # MAPA presentes en la misma carpeta sean de una unica descarga.
    avisar_desincronizacion(sorted(glob.glob(os.path.join(args.src, "Productos*"))),
                            "fuentes del MAPA")

if __name__ == "__main__":
    main()
