#!/usr/bin/env python3
"""Verifica y ESTANDARIZA una lista M3U/TXT.

- Prueba cada stream (pide los primeros bytes, mide TTFB) y clasifica
  OK / LENTO / CAIDO.
- Saca los caídos.
- Reescribe cada entrada al formato canónico de Miro:
    #EXTINF:-1 tvg-name="..." tvg-logo="..." group-title="...",Nombre
    URL
- En modo "series" hace MUESTREO: prueba 1 episodio por serie; si anda,
  deja la serie completa; si está caído, la saca entera.

Uso:
    python scripts/verificar.py <entrada> <modo:full|series> <salida.m3u>

Genera:
    <salida.m3u>            (lista limpia + estandarizada, lista para pegar)
    <salida>_caidos.m3u     (caidos + duplicados, para buscar reemplazos)
    <salida>_reporte.html   (reporte con colores)
"""
import os
import re
import sys
import time

import requests

TIMEOUT = int(os.environ.get("MIRO_TIMEOUT", "12"))
SLOW_MS = int(os.environ.get("MIRO_SLOW_MS", "5000"))
READ_BYTES = 16384  # con confirmar que fluyen los primeros ~16KB alcanza

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "MiroChecker/1.0"})


def attr(s, key):
    m = re.search(key + r'="([^"]*)"', s)
    return m.group(1) if m else ""


def dispname(ext):
    i = ext.rfind(",")
    return ext[i + 1:].strip() if i >= 0 else ""


def standardize(ext):
    name = dispname(ext) or attr(ext, "tvg-name")
    logo = attr(ext, "tvg-logo")
    group = attr(ext, "group-title") or "Sin categoria"
    tvgname = attr(ext, "tvg-name") or name
    return f'#EXTINF:-1 tvg-name="{tvgname}" tvg-logo="{logo}" group-title="{group}",{name}'


def series_key(ext):
    name = dispname(ext) or attr(ext, "tvg-name")
    group = attr(ext, "group-title")
    m = re.match(r"^(.*?)[\s\-\|]*[sS]\d{1,2}\s*[eExX]\s*\d{1,3}\b", name)
    base = (m.group(1).strip() if m else name).lower()
    return f"{group}||{base}"


def parse(path):
    entries = []
    ext = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            l = raw.strip()
            if not l or l.startswith("#EXTM3U"):
                continue
            if l.startswith("#EXTINF"):
                ext = l
                continue
            if l.startswith("#"):
                continue
            if ext is None:
                continue
            entries.append((ext, l))
            ext = None
    return entries


def check(url):
    t0 = time.time()
    try:
        r = SESSION.get(
            url,
            headers={"Range": "bytes=0-%d" % (READ_BYTES - 1)},
            stream=True,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        if r.status_code >= 400:
            r.close()
            return ("CAIDO", int((time.time() - t0) * 1000), f"HTTP {r.status_code}")
        got = 0
        ttfb = None
        for chunk in r.iter_content(8192):
            if ttfb is None:
                ttfb = int((time.time() - t0) * 1000)
            got += len(chunk)
            if got >= READ_BYTES:
                break
        r.close()
        if got == 0:
            return ("CAIDO", int((time.time() - t0) * 1000), "Sin datos")
        tt = ttfb if ttfb is not None else int((time.time() - t0) * 1000)
        if tt > SLOW_MS:
            return ("LENTO", tt, f"{tt}ms")
        return ("OK", tt, f"{got // 1024}KB")
    except Exception as e:
        return ("CAIDO", int((time.time() - t0) * 1000), type(e).__name__)


def html_report(path, rows, kept, dropped, dupd):
    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    color = {"OK": "#1f9d55", "LENTO": "#c98a00", "CAIDO": "#c0392b",
             "DUP": "#6c7a89"}
    b = ['<!doctype html><html lang="es"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         f"<title>Reporte {esc(os.path.basename(path))}</title>",
         "<style>body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;"
         "background:#0e1116;color:#e6e6e6;margin:0;padding:20px}"
         "h1{font-size:18px;margin:0 0 10px}"
         ".chips span{display:inline-block;padding:4px 10px;border-radius:20px;"
         "font-weight:700;font-size:13px;margin-right:8px;color:#fff}"
         "input{width:100%;max-width:420px;padding:10px;border-radius:8px;"
         "border:1px solid #2a3140;background:#161b22;color:#fff;margin:14px 0}"
         "table{width:100%;border-collapse:collapse;font-size:13px}"
         "th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #1e2531}"
         "th{position:sticky;top:0;background:#0e1116;color:#8a94a6}"
         ".st{font-weight:800;white-space:nowrap}.u{color:#5aa9ff;font-size:12px;"
         "word-break:break-all}</style></head><body>",
         f"<h1>Verificación — {esc(os.path.basename(path))}</h1>",
         f'<div class="chips"><span style="background:{color["OK"]}">Mantenidas: {kept}</span>'
         f'<span style="background:{color["CAIDO"]}">Sacadas: {dropped}</span>'
         f'<span style="background:{color["DUP"]}">Duplicadas: {dupd}</span></div>',
         '<input id="q" placeholder="Filtrar...">',
         '<table id="t"><thead><tr><th>#</th><th>Estado</th><th>Nombre</th>'
         "<th>ms</th><th>Motivo</th><th>URL</th></tr></thead><tbody>"]
    for i, (status, name, ms, reason, url) in enumerate(rows, 1):
        b.append(
            f'<tr><td>{i}</td><td class="st" style="color:{color.get(status,"#ccc")}">'
            f"{status}</td><td>{esc(name)}</td><td>{ms}</td><td>{esc(reason)}</td>"
            f'<td class="u">{esc(url)}</td></tr>')
    b.append("</tbody></table><script>const q=document.getElementById('q'),"
             "rs=[...document.querySelectorAll('#t tbody tr')];"
             "q.oninput=()=>{const s=q.value.toLowerCase();rs.forEach(r=>"
             "r.style.display=r.innerText.toLowerCase().includes(s)?'':'none')};"
             "</script></body></html>")
    return "".join(b)


def main():
    if len(sys.argv) < 4:
        print("Uso: python scripts/verificar.py <entrada> <full|series> <salida.m3u>")
        sys.exit(1)
    src, mode, out = sys.argv[1], sys.argv[2], sys.argv[3]
    if not os.path.isfile(src):
        print(f"No existe: {src}")
        sys.exit(1)

    entries = parse(src)
    print(f"{src}: {len(entries)} entradas | modo {mode} | timeout {TIMEOUT}s")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    fout = open(out, "w", encoding="utf-8")
    fout.write("#EXTM3U\n")

    rows = []
    dead = []  # entradas caídas (ext, url)
    dups = []  # entradas repetidas por URL (se dejó 1 sola)
    seen = set()
    kept = dropped = 0

    if mode == "series":
        # Un chequeo por serie; el primer episodio decide toda la serie.
        first = {}
        for ext, url in entries:
            k = series_key(ext)
            if k not in first:
                first[k] = (ext, url)
        alive = {}
        n = 0
        for k, (ext, url) in first.items():
            n += 1
            status, ms, reason = check(url)
            alive[k] = status != "CAIDO"
            rows.append((status, dispname(ext), ms, reason, url))
            print(f"\r  Series probadas {n}/{len(first)}   ", end="", flush=True)
        print()
        for ext, url in entries:
            if url in seen:
                dups.append((ext, url))
                continue
            seen.add(url)
            if alive.get(series_key(ext)):
                fout.write(standardize(ext) + "\n" + url + "\n")
                kept += 1
            else:
                dropped += 1
        for k, (ext, url) in first.items():
            if not alive.get(k):
                dead.append((ext, url))
    else:
        n = 0
        for ext, url in entries:
            n += 1
            # Un repetido (misma URL) no se vuelve a probar: se informa y se saltea.
            if url in seen:
                dups.append((ext, url))
                rows.append(("DUP", dispname(ext), 0, "Duplicado", url))
                continue
            seen.add(url)
            status, ms, reason = check(url)
            rows.append((status, dispname(ext), ms, reason, url))
            if status != "CAIDO":
                fout.write(standardize(ext) + "\n" + url + "\n")
                kept += 1
            else:
                dropped += 1
                dead.append((ext, url))
            if n % 25 == 0 or n == len(entries):
                fout.flush()
                print(f"\r  Probadas {n}/{len(entries)}   ", end="", flush=True)
        print()

    fout.close()
    base = out[:-4] if out.lower().endswith(".m3u") else out

    # Archivo con lo caído + los duplicados (para revisar / buscar reemplazos).
    dead_path = base + "_caidos.m3u"
    if dead or dups:
        with open(dead_path, "w", encoding="utf-8") as fd:
            fd.write("#EXTM3U\n")
            if dead:
                fd.write("# ===== CAIDOS (no responden) =====\n")
                for ext, url in dead:
                    fd.write(standardize(ext) + "\n" + url + "\n")
            if dups:
                fd.write("# ===== DUPLICADOS (repetidos, se dejo 1) =====\n")
                for ext, url in dups:
                    fd.write(standardize(ext) + "\n" + url + "\n")

    with open(base + "_reporte.html", "w", encoding="utf-8") as f:
        f.write(html_report(src, rows, kept, dropped, len(dups)))

    unidad = "series" if mode == "series" else "entradas"
    print(f"Mantenidas: {kept}  |  Caidas ({unidad}): {len(dead)}  |  "
          f"Duplicadas: {len(dups)}")
    print(f"Salida:  {out}")
    print(f"Caidos/duplicados: {dead_path if (dead or dups) else '(ninguno)'}")
    print(f"Reporte: {base}_reporte.html")

    # Resumen visible en la pestaña Actions de GitHub.
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as s:
            s.write(f"### {os.path.basename(src)} (modo {mode})\n\n")
            s.write(f"- Mantenidas: **{kept}**\n")
            s.write(f"- Caídas ({unidad}): **{len(dead)}**\n")
            s.write(f"- Duplicadas (repetidas): **{len(dups)}**\n\n")
            if dead:
                s.write("**Lo que no anda:**\n\n")
                for ext, _ in dead[:150]:
                    s.write(f"- {dispname(ext)}  _({attr(ext, 'group-title') or '-'})_\n")
                if len(dead) > 150:
                    s.write(f"\n… y {len(dead) - 150} más (archivo `_caidos`).\n")
                s.write("\n")
            if dups:
                s.write("**Duplicadas (se dejó 1):**\n\n")
                for ext, _ in dups[:150]:
                    s.write(f"- {dispname(ext)}  _({attr(ext, 'group-title') or '-'})_\n")
                if len(dups) > 150:
                    s.write(f"\n… y {len(dups) - 150} más (archivo `_caidos`).\n")
            s.write("\n")


if __name__ == "__main__":
    main()
