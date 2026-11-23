#!/usr/bin/env python3
"""Create a zero-cost, static MAIZO Store from GitHub release assets.
No HTTP server, Railway, payment, DNS subscription, cloud VM or smartphone.
The GitHub Actions runner fetches source assets through HTTPS and verifies
the release-pinned size, hash, and ELF header BEFORE Pages deployment.
"""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
from server import CATALOG, validate

ROOT = Path("site")
PAGE = """<!doctype html>
<html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAIZO Store — Homebrews PS2</title>
<style>
:root{color-scheme:dark}body{max-width:870px;margin:auto;background:#11141c;
color:#f6f8ff;font:16px system-ui;padding:2rem}
h1{color:#8eafff}section{border:1px solid #354056;background:#1c2230;
border-radius:12px;padding:1rem;margin:1rem 0}
a{color:#a6c9ff}code{word-break:break-all}small{color:#9ca9ba}
</style>
<header><h1>🎮 MAIZO Store</h1>
<p>Catálogo gratuito de homebrews para PlayStation 2. Arquivos ELF oficiais
do GitHub, validados por SHA-256 antes da publicação.</p></header>
<main>{rows}</main>
<footer><p>Projeto independente. Não inclui jogos comerciais ou ROMs.
Para usar no MAIZO SUPREME, instale a versão com suporte HTTPS/Pages.</p></footer></html>
"""


def download(entry):
    dest = ROOT / "v1" / "apps" / (entry["id"] + ".elf")
    dest.parent.mkdir(parents=True, exist_ok=True)
    hash_state = hashlib.sha256()
    count = 0
    req = Request(entry["source"], headers={"User-Agent": "MaizoStore-Pages/1"})
    with urlopen(req, timeout=80) as response, dest.open("wb") as sink:
        while block := response.read(65536):
            count += len(block)
            if count > entry["size"]:
                raise ValueError(f"{entry['id']}: release is too long")
            sink.write(block)
            hash_state.update(block)
    if count != entry["size"] or hash_state.hexdigest() != entry["sha256"]:
        dest.unlink(missing_ok=True)
        raise ValueError(f"{entry['id']}: released ELF changed; bump pinned SHA")
    if dest.open("rb").read(4) != b"\x7fELF":
        dest.unlink(missing_ok=True)
        raise ValueError(f"{entry['id']}: not an ELF")


def main():
    validate()
    ROOT.mkdir(exist_ok=True)
    (ROOT / ".nojekyll").write_text("", encoding="ascii")
    (ROOT / "health").write_text("OK\n", encoding="ascii")
    catalog = ["MAIZOSTORE1"]
    cards = []
    for entry in CATALOG:
        download(entry)
        catalog.append("|".join(str(entry[k]) for k in
                       ("id", "title", "category", "summary", "version",
                        "size", "sha256")))
        cards.append(
            '<section><h2>{title}</h2><p>{summary}</p><small>{category} · '
            '{version} · {size} bytes</small><p>'
            '<a href="v1/apps/{id}.elf">Arquivo ELF</a> · '
            '<a href="{project}">Código-fonte</a></p></section>'.format(**entry))
    (ROOT / "v1" / "catalog").write_text("\n".join(catalog)+"\n", encoding="ascii")
    (ROOT / "index.html").write_text(PAGE.format(rows="".join(cards)), encoding="utf-8")
    print(f"Static MAIZO Store ready: {len(CATALOG)} verified ELF downloads")


if __name__ == "__main__":
    main()
