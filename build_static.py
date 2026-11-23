#!/usr/bin/env python3
"""Build the free, serverless MAIZO Store from public GitHub Releases.

Conservative publish rules:
- Known owner/repo + exact release tag + exact release asset, no user URL proxy.
- Do not mirror repos whose redistributable license has not been verified.
- Validate upstream digests when supplied and ELF class/endianness/machine.
- Produce an immutable local SHA-256 manifest and detailed per-app credits.
- Never execute anything from the internet in this build script.
"""
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import hashlib
import json
import re
import sys

ROOT = Path("site")
CATALOG = Path("catalog_sources.json")
MAX_ELF = 12 * 1024 * 1024
CHUNK = 65536

HTML = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAIZO STORE — Homebrews PS2</title>
<style>
:root{color-scheme:dark;font-family:system-ui,Arial,sans-serif;color:#e6ecf9}
*{box-sizing:border-box}body{max-width:1200px;margin:auto;background:#090d15;padding:2rem}
header{border-bottom:1px solid #39465e;margin-bottom:1.2rem;padding-bottom:1rem}
h1{font-size:clamp(32px,5vw,56px);margin:0;color:#c0d4ff}
p{color:#afbed9;line-height:1.5}#search{width:100%;border:1px solid #4d6283;
background:#1c2436;color:#fff;padding:15px;font-size:17px;border-radius:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(275px,1fr));gap:15px;margin-top:22px}
.card{border:1px solid #364257;border-radius:14px;padding:17px;background:#161d2b}
.tag{display:inline-block;background:#263c55;color:#bbd5ff;padding:5px 9px;border-radius:7px;font-size:12px}
h2{font-size:20px;margin-bottom:5px;overflow-wrap:anywhere}
small{color:#9cacba}a{color:#9ac2ff}a:hover{text-decoration:none}
.warn{color:#f4bd6a}footer{margin-top:28px;border-top:1px solid #313849;padding-top:14px}
</style></head><body>
<header><h1>MAIZO STORE</h1>
<p>Homebrews para PlayStation 2 · Catálogo gratuito no GitHub ·
Instalação pela Ethernet no MAIZO SUPREME, sem servidor próprio.</p>
<p id="count">{count} aplicativos e variantes; créditos aos criadores originais.</p>
<input id="search" type="search" placeholder="Pesquisar aplicativos, autores ou categorias..." autocomplete="off">
</header>
<main class="grid">{cards}</main>
<footer><p>Distribuição de projetos independentes de terceiros.
Respeite licenças, instruções e requisitos. Alguns homebrews precisam
de arquivos adicionais que não são incluídos. O instalador não executa
automaticamente homebrews e confere o SHA-256 de cada ELF.</p>
<a href="credits.json">Créditos e licenças (JSON)</a> ·
<a href="v1/catalog">Catálogo para PS2</a> ·
<a href="https://github.com/maizon/MaizoOPLstore">Código-fonte da loja</a>
</footer><script>
const q=document.querySelector("#search"), cards=[...document.querySelectorAll(".card")];
q.addEventListener("input",()=>{
 const needle=q.value.toLowerCase();
 for(const card of cards)
  card.hidden=!card.textContent.toLowerCase().includes(needle);
});
</script></body></html>"""


def check_source(entry):
    assert re.fullmatch(r"[a-z0-9-]{2,32}", entry["id"])
    assert re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", entry["repo"])
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", entry["tag"])
    assert re.fullmatch(r"[A-Za-z0-9_.-]+", entry["asset"])
    assert entry["asset"].lower().endswith(".elf")
    assert 64 <= entry["size"] <= MAX_ELF
    assert not any("|" in str(entry[k]) or "\n" in str(entry[k])
                   for k in ("id", "title", "category", "summary", "tag"))
    digest = entry.get("sha256")
    assert digest is None or re.fullmatch(r"[a-f0-9]{64}", digest)


def github_url(item):
    return "https://github.com/{}/releases/download/{}/{}".format(
        item["repo"], quote(item["tag"], safe=""), quote(item["asset"], safe=""))


def copy_verified_elf(item):
    url = github_url(item)
    dest = ROOT / "v1" / "apps" / (item["id"] + ".elf")
    dest.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    req = Request(url, headers={"User-Agent": "MaizoStore-GitHubBuild/2"})
    with urlopen(req, timeout=70) as response, dest.open("wb") as out:
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > item["size"] or size > MAX_ELF:
                raise ValueError("Asset size exceeds pinned length")
            digest.update(chunk)
            out.write(chunk)
    actual = digest.hexdigest()
    if size != item["size"] or (item.get("sha256") and item["sha256"] != actual):
        dest.unlink(missing_ok=True)
        raise ValueError("Size/SHA-256 changed upstream")
    with dest.open("rb") as stream:
        header = stream.read(20)
    if (len(header) < 20 or header[:4] != b"\x7fELF" or
            header[4] != 1 or header[5] != 1 or
            int.from_bytes(header[18:20], "little") != 8):
        dest.unlink(missing_ok=True)
        raise ValueError("ELF is not a 32-bit little-endian MIPS executable")
    return actual, size


def build():
    entries = json.loads(CATALOG.read_text(encoding="utf-8"))["sources"]
    assert entries
    ROOT.mkdir(exist_ok=True)
    (ROOT / ".nojekyll").write_bytes(b"")
    (ROOT / "health").write_text("OK\n", encoding="ascii")
    (ROOT / "v1").mkdir(exist_ok=True)
    seen = set()
    catalogue = ["MAIZOSTORE1"]
    metadata = []
    cards = []
    verified = 0
    errors = []
    for item in entries:
        check_source(item)
        if item["id"] in seen:
            raise ValueError("Duplicate application ID: " + item["id"])
        seen.add(item["id"])
        url = github_url(item)
        status = "reference"
        sha = None
        length = 0
        if item["redistribute"]:
            try:
                sha, length = copy_verified_elf(item)
                status = "available"
                catalogue.append("|".join(str(v) for v in (
                    item["id"], item["title"], item["category"],
                    item["summary"], item["tag"], length, sha)))
                verified += 1
            except Exception as err:
                (ROOT / "v1" / "apps" / (item["id"] + ".elf")).unlink(missing_ok=True)
                errors.append((item["id"], str(err)))
                status = "unavailable"

        row = dict(item)
        row.update({"source": url, "project": "https://github.com/" + item["repo"],
                    "status": status, "verified_sha256": sha,
                    "verified_bytes": length})
        metadata.append(row)
        title = escape(item["title"])
        credits = escape(item["credits"])
        desc = escape(item["summary"])
        link = "v1/apps/" + quote(item["id"]) + ".elf" if status == "available" else url
        action = "Baixar ELF verificado" if status == "available" else "Ver release oficial"
        warning = ("<p class='warn'>Link externo: direitos de redistribuicao nao confirmados</p>"
                   if not item["redistribute"] else
                   ("<p class='warn'>Download temporariamente indisponivel</p>"
                    if status == "unavailable" else ""))
        cards.append(
            '<section class="card"><span class="tag">{category}</span>'
            "<h2>{title}</h2><p>{desc}</p>"
            "<small>Autor(es): {credits}<br>Licenca: {license}<br>"
            "Release: {tag}</small>{warning}<p>"
            '<a href="{link}">{action}</a> · '
            '<a href="https://github.com/{repo}">Projeto original</a>'
            "</p></section>".format(
                category=escape(item["category"]), title=title, desc=desc,
                credits=credits, license=escape(item["license"]),
                tag=escape(item["tag"]), warning=warning,
                link=escape(link, quote=True), action=action,
                repo=escape(item["repo"], quote=True)))

    (ROOT / "v1" / "catalog").write_text("\n".join(catalogue) + "\n", encoding="ascii")
    (ROOT / "credits.json").write_text(
        json.dumps({"catalog_version": 2, "homebrews": metadata},
                   indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    page = HTML.replace("{count}", str(len(entries))).replace("{cards}", "\n".join(cards))
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    summary = {"sources": len(entries), "verified_mirror": verified,
               "external_only": sum(not p["redistribute"] for p in entries),
               "errors": errors}
    (ROOT / "build-report.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if verified < 10:
        raise RuntimeError("Only %d verified apps; refusing tiny catalogue" % verified)


if __name__ == "__main__":
    build()
