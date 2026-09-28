#!/usr/bin/env python3
"""One-time warmup: mirror every static asset the game references so it can
run 100% offline. Scans the already-mirrored code/text files for asset paths,
fetches any missing file from the live host, caches to disk.
Run:  python warmup.py
"""
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serve  # noqa: E402  (reuses fetch_and_cache / BASE_DIR / STATIC_EXT)

ASSET_RE = __import__("re").compile(
    r"(?:image|sound|font)/[A-Za-z0-9_./\-]+?"
    r"\.(?:png|jpg|jpeg|gif|webp|bmp|mp3|wav|ogg|m4a|fnt|plist|xml|atlas|json|svga)",
    __import__("re").IGNORECASE)
TEXT_EXT = {".js", ".css", ".html", ".htm", ".php", ".json", ".xml",
            ".plist", ".atlas", ".fnt", ".txt", ".svga"}

def scan_text(path: Path) -> set[str]:
    out = set()
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for m in ASSET_RE.finditer(data):
        out.add(m.group(0))
    return out

def main():
    import re
    todo = [p for p in serve.WEB_ROOT.rglob("*")
            if p.is_file() and p.suffix.lower() in TEXT_EXT]
    seen_files = set()
    wanted: set[str] = set()
    while todo:
        p = todo.pop()
        if p in seen_files:
            continue
        seen_files.add(p)
        refs = scan_text(p)
        wanted |= refs
        # also scan newly discovered text assets that already exist locally
        for r in refs:
            cand = serve.BASE_DIR / ("ELDORADO_WEB/" + r)
            if cand.is_file() and cand.suffix.lower() in TEXT_EXT and cand not in seen_files:
                todo.append(cand)

    missing = []
    for r in sorted(wanted):
        dest = serve.BASE_DIR / ("ELDORADO_WEB/" + r)
        if not (dest.is_file() and dest.stat().st_size):
            missing.append(r)
    print(f"referenced assets : {len(wanted)}   already mirrored: {len(wanted) - len(missing)}   missing: {len(missing)}")

    if missing:
        ok = no = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(lambda r: (r, serve.fetch_and_cache("/ELDORADO_WEB/" + r) is not None), r)
                    for r in missing]
            for f in as_completed(futs):
                r, good = f.result()
                if good:
                    ok += 1
                else:
                    no += 1
                    print("  MISS " + r)
        print(f"warmup done: fetched={ok} missed={no}")
    else:
        print("nothing to fetch - fully offline already")

if __name__ == "__main__":
    main()