import json
import os
import re
import shutil
import sys
import unicodedata


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    s = re.sub(r"-+", "-", s)
    return s or "cat"


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else "peliculas.m3u"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "peliculas"
    index_name = f"{out_dir}_index.json"

    if not os.path.isfile(input_path):
        print(f"No existe el archivo: {input_path}")
        sys.exit(1)

    grp = re.compile(r'group-title="([^"]*)"')
    order, by = [], {}
    ext = None
    with open(input_path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#EXTM3U"):
                continue
            if line.startswith("#EXTINF"):
                ext = line
                continue
            if line.startswith("#"):
                continue
            if ext is None:
                continue
            m = grp.search(ext)
            cat = m.group(1).strip() if (m and m.group(1).strip()) else "Sin categoria"
            if cat not in by:
                by[cat] = []
                order.append(cat)
            by[cat].append(ext)
            by[cat].append(line)
            ext = None

    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)

    used, index = set(), []
    for cat in order:
        entries = by[cat]
        count = len(entries) // 2
        base = slug(cat)
        s, i = base, 2
        while s in used:
            s = f"{base}-{i}"
            i += 1
        used.add(s)
        rel = f"{out_dir}/{s}.m3u"
        with open(rel, "w", encoding="utf-8") as o:
            o.write("#EXTM3U\n" + "\n".join(entries) + "\n")
        index.append({"name": cat, "file": rel, "count": count})

    with open(index_name, "w", encoding="utf-8") as o:
        json.dump(index, o, ensure_ascii=False, indent=2)

    total = sum(e["count"] for e in index)
    print(f"Categorias: {len(index)}  |  Total: {total}  ->  {index_name}")


if __name__ == "__main__":
    main()
