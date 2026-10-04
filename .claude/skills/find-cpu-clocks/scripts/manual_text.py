"""Per-page text of one service manual, and the clock values in it with links to their pages.

A source is an archive.org item (https://archive.org/details/<item>[/<doc>]) or a direct PDF URL.
Text, best first:
  1. archive.org's own OCR, page by page (<doc>_djvu.xml);
  2. the PDF's text layer (pypdf);
  3. the PDF's page scans, OCR'd with the Windows built-in engine (scripts/ocr.ps1). A scan may be
     stored flipped or rotated in the PDF, so every orientation is tried and the most readable kept.
Pages are numbered like archive.org's viewer (n0 = first scan), so a hit on page nN links to
https://archive.org/details/<item>[/<doc>]/page/nN/mode/1up (or <pdf>#page=N+1).

usage: python manual_text.py <source> [--doc NAME] [--find DIGITS] [--cache DIR]
  --find 21328125   list the pages whose digits contain these digits (to cite a value you know)
Needs: pypdf, Pillow, lxml (pip install pypdf pillow lxml), curl, and Windows for step 3.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

HERE = Path(os.path.dirname(os.path.abspath(__file__)))
# Clock-like numbers: 21.x / 10.7x / 14.31x / 28.63x crystals, 3.55–3.58 MHz clocks (also "3,554,685 Hz"),
# 445/447 kHz GROM clocks (TMS99x8 pin 37 = crystal / 24).
CLOCK = re.compile(r"(?<![\d])(?:21\s?[.,]\s?\d{2,6}|10\s?[.,]\s?7\d{1,5}|3\s?[.,]\s?5[5-8]\d{0,5}"
                   r"|3[.,]?55[34][.,]?\d{3}|3[.,]?579[.,]?\d{3}|14[.,]31\d{0,4}|28[.,]63\d{0,3}|44[57][.,]\d)"
                   r"\s*(?:[MK]?Hz)?", re.I)
DISK = re.compile(r"\b3[.,]5\s*(?:\"|’|'|inch|MB)")          # 3.5" floppy disks are not clocks
WORDS = re.compile(r"\b(the|and|to|of|for|on|with|is|frequency|connect|adjust|probe|set|clock|de|en|van|"
                   r"het|op|een|voltage|mhz|khz)\b", re.I)


def curl(url: str, dest: Path | None = None) -> bytes:
    args = ["curl", "-sL", "--max-time", "600", "-A", "Mozilla/5.0", url]
    if dest is None:
        return subprocess.run(args, capture_output=True).stdout
    if not dest.exists() or dest.stat().st_size == 0:
        subprocess.run(args + ["-o", str(dest)])
    return b""


def archive_pages(item: str, doc: str | None, cache: Path) -> tuple[list[str], str, str | None]:
    """(page texts, link base, pdf file name) of an archive.org item's document."""
    meta_path = cache / f"{item}.meta.json"
    if not meta_path.exists():
        meta_path.write_bytes(curl(f"https://archive.org/metadata/{item}"))
    files = [f["name"] for f in json.loads(meta_path.read_text(encoding="utf-8")).get("files", [])]
    xmls = [f for f in files if f.endswith("_djvu.xml")]
    pdfs = [f for f in files if f.lower().endswith(".pdf") and not f.endswith("_text.pdf")]
    if doc is None:
        doc = (xmls[0][: -len("_djvu.xml")] if xmls else Path(pdfs[0]).stem) if (xmls or pdfs) else item
    base = f"https://archive.org/details/{item}" + ("" if doc == item else f"/{quote(doc)}")
    pdf = next((f for f in pdfs if Path(f).stem == doc), pdfs[0] if pdfs else None)
    xml_name = f"{doc}_djvu.xml"
    if xml_name in files:
        from lxml import etree
        path = cache / f"{item}__{re.sub(r'[^A-Za-z0-9]', '_', doc)}_djvu.xml"
        curl(f"https://archive.org/download/{item}/{quote(xml_name)}", path)
        root = etree.parse(str(path), etree.XMLParser(recover=True, huge_tree=True)).getroot()
        pages = [" ".join(w.text or "" for w in obj.iter("WORD")) for obj in root.iter("OBJECT")]
        if sum(len(p) for p in pages) > 200 * max(1, len(pages)) // 10:     # some real text
            return pages, base, pdf
    return [], base, pdf


def pdf_pages(pdf_path: Path, workdir: Path, rotate: bool = True) -> list[str]:
    """Text layer per page; pages without one are OCR'd from their scans (all orientations)."""
    import pypdf
    reader = pypdf.PdfReader(str(pdf_path))
    texts = [(page.extract_text() or "") for page in reader.pages]
    for n, page in enumerate(reader.pages):
        if len(WORDS.findall(texts[n])) >= 10:
            continue
        texts[n] = ocr_page(page, n, workdir, rotate) or texts[n]
    return texts


def ocr_page(page, n: int, workdir: Path, rotate: bool = True) -> str:
    from PIL import Image
    images = []
    try:
        for k, im in enumerate(page.images):
            img = (im.image or Image.open(io.BytesIO(im.data))).convert("L")
            if min(img.size) < 40:
                continue
            if max(img.size) > 8000:                     # Windows OCR's size limit is 10000 px
                s = 8000 / max(img.size)
                img = img.resize((int(img.width * s), int(img.height * s)))
            images.append(img)
    except Exception:  # noqa: BLE001
        return ""
    texts = []
    for k, img in enumerate(images):
        variants = {"": img, "fv": img.transpose(Image.Transpose.FLIP_TOP_BOTTOM),
                    "fh": img.transpose(Image.Transpose.FLIP_LEFT_RIGHT), "r180": img.rotate(180, expand=True),
                    "r90": img.rotate(90, expand=True), "r270": img.rotate(270, expand=True)}
        if not rotate:                              # --no-rotate: scans stored upright (faster)
            variants = {"": img}
        paths = []
        for tag, v in variants.items():
            p = workdir / f"p{n:03d}_{k:02d}{tag}.png"
            v.save(p)
            paths.append(os.path.normpath(str(p)))
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.normpath(str(HERE / "ocr.ps1")), *paths], capture_output=True)
        best = ""
        for part in r.stdout.decode("utf-8", errors="replace").split("=== ")[1:]:
            _, _, body = part.partition("\n")
            if not body.startswith("ERROR") and len(WORDS.findall(body)) > len(WORDS.findall(best)):
                best = body
        texts.append(best)
    return "\n".join(texts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--doc", help="document inside an archive.org item (default: its first)")
    ap.add_argument("--find", help="digits to locate (e.g. 21328125)")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "msx-manuals")
    ap.add_argument("--no-rotate", action="store_true", help="OCR scans as stored only (large, upright documents)")
    args = ap.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)

    m = re.match(r"https?://archive\.org/(?:details|stream|download)/([^/?#]+)(?:/([^?#]+?))?(?:/page/.*)?$", args.source)
    pages: list[str] = []
    if m:
        item, doc = m.group(1), args.doc or (unquote(m.group(2)) if m.group(2) else None)
        pages, base, pdf = archive_pages(item, doc, args.cache)
        link = lambda n: f"{base}/page/n{n}/mode/1up"
        if not pages and pdf:
            path = args.cache / f"{item}__{pdf.replace(' ', '_')}"
            curl(f"https://archive.org/download/{item}/{quote(pdf)}", path)
            work = args.cache / path.stem
            work.mkdir(exist_ok=True)
            pages = pdf_pages(path, work, not args.no_rotate)
    else:
        name = re.sub(r"[^A-Za-z0-9._-]", "_", unquote(urlparse(args.source).path.split("/")[-1]))
        path = args.cache / name
        curl(args.source, path)
        work = args.cache / path.stem
        work.mkdir(exist_ok=True)
        pages = pdf_pages(path, work, not args.no_rotate)
        link = lambda n: f"{args.source}#page={n + 1}"

    out = args.cache / (re.sub(r"[^A-Za-z0-9]", "_", args.source)[-80:] + ".pages.json")
    out.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    print(f"{len(pages)} pages, {sum(len(p) for p in pages)} chars of text -> {out}")
    for n, text in enumerate(pages):
        if args.find:
            if args.find in re.sub(r"\D", "", text):
                print(f"  n{n}: {link(n)}")
            continue
        flat = re.sub(r"\s+", " ", text)
        hits = [flat[max(0, h.start() - 60): h.end() + 30] for h in CLOCK.finditer(flat)
                if not DISK.search(flat[h.start(): h.end() + 8])]
        if hits:
            print(f"  n{n}: {link(n)}")
            for h in hits[:6]:
                print(f"      {h[:110]}")


if __name__ == "__main__":
    main()
