#!/usr/bin/env python3
"""MAIZO Store v1: curated GitHub homebrews for PS2 Ethernet.

Run: python3 server.py   (PORT=8080 by default)
Use a public RAW TCP proxy to port 8080: the PS2 OPL transport speaks HTTP,
not HTTPS. Installations are safe against injected binaries because the PS2
also pins exact SHA-256 and size of every approved app in its own build.
Routes:
  GET /health                    -> OK
  GET /v1/catalog                -> ASCII MAIZOSTORE1 + pipe-delimited rows
  GET /v1/apps/<approved-id>.elf -> verified ELF, fixed Content-Length
Each upstream release is obtained over verified HTTPS. No arbitrary proxying.
The 'latest' tags are pinned to the asset metadata as of Nov 23, 2026.
A changed upstream binary is rejected until the catalogue is reviewed.
This file intentionally includes the complete catalogue and server so that
this initially empty repository can be bootstrapped in ONE Git commit.
Deployment on Railway requires an explicit Start Command: python3 server.py
(or build and deploy the same Python script with another provider).
"""
import hashlib
import os
from pathlib import Path
import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CATALOG = [
    dict(id="wlaunchelf", title="wLaunchELF", category="Ferramentas",
         summary="Gerenciador de arquivos para PS2", version="latest",
         size=497908, sha256="beb688160ab29ba441f5b4f9a20fb151a4abb44ee4a285a7b1a702b6542c2c66",
         source="https://github.com/ps2homebrew/wLaunchELF/releases/download/latest/BOOT.ELF",
         project="https://github.com/ps2homebrew/wLaunchELF"),
    dict(id="wlaunchelf-ds4", title="wLaunchELF DS34", category="Ferramentas",
         summary="Arquivos e controles DualShock 3/4", version="latest",
         size=366868, sha256="4ed8eb48b735411356012946082d2d61d1f72a1aad613cb6d1f5e65953187df2",
         source="https://github.com/israpps/wLaunchELF_ISR/releases/download/latest/BOOT-DS34.ELF",
         project="https://github.com/israpps/wLaunchELF_ISR"),
    dict(id="wlaunchelf-exfat", title="wLaunchELF exFAT", category="Ferramentas",
         summary="Gerenciador de arquivos com exFAT", version="latest",
         size=356052, sha256="2254d5684904d42088421fc6ef6cf46299faa8c85e5764a3789de7108180a6d7",
         source="https://github.com/israpps/wLaunchELF_ISR/releases/download/latest/BOOT-EXFAT.ELF",
         project="https://github.com/israpps/wLaunchELF_ISR"),
    dict(id="fceumm", title="FCEUmm PS2", category="Emuladores",
         summary="Emulador NES para PlayStation 2", version="latest",
         size=1384060, sha256="aeebec25228ed2fe2261f22e1ab692d4d518f2dbca84e81d980a4a1bc53f3a3e",
         source="https://github.com/ps2homebrew/Fceumm-PS2/releases/download/latest/fceu.elf",
         project="https://github.com/ps2homebrew/Fceumm-PS2"),
]
APPS = {item["id"]: item for item in CATALOG}
CACHE = Path(os.environ.get("MAIZO_STORE_CACHE", "/tmp/maizo-store"))
LOCK = threading.RLock()
MAX_FILE = 8 * 1024 * 1024


def validate():
    assert len(APPS) == len(CATALOG) and len(APPS) > 0
    for item in CATALOG:
        assert re.fullmatch(r"[a-z0-9-]{1,31}", item["id"])
        assert re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        assert item["source"].startswith("https://github.com/")
        assert item["source"].lower().endswith(".elf")
        assert 64 <= item["size"] < MAX_FILE
        assert all("|" not in str(item[k]) and "\n" not in str(item[k])
                   for k in ("id", "title", "category", "summary", "version"))


def get_verified_elf(item):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / (item["id"] + "-" + item["sha256"] + ".elf")
    with LOCK:
        if target.exists():
            if (target.stat().st_size == item["size"] and
                    hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"]):
                return target
            target.unlink()
        tmp = target.with_suffix(".partial")
        tmp.unlink(missing_ok=True)
        request = urllib.request.Request(item["source"],
                                         headers={"User-Agent": "MaizoStore/1.0"})
        total, sha = 0, hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=35) as response, tmp.open("wb") as out:
                while True:
                    block = response.read(65536)
                    if not block:
                        break
                    total += len(block)
                    if total > item["size"] or total > MAX_FILE:
                        raise ValueError("Upstream ELF is larger than pinned size")
                    sha.update(block)
                    out.write(block)
            if total != item["size"] or sha.hexdigest() != item["sha256"]:
                raise ValueError("Upstream release differs from pinned SHA-256")
            with tmp.open("rb") as src:
                if src.read(4) != b"\x7fELF":
                    raise ValueError("Upstream file is not an ELF")
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
    return target


class StoreHTTP(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def answer(self, payload, content_type="text/plain; charset=ascii"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)
        self.close_connection = True

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path == "/health":
            return self.answer(b"OK\n")
        if self.path == "/v1/catalog":
            rows = ["MAIZOSTORE1"]
            for item in CATALOG:
                rows.append("|".join(str(item[k]) for k in (
                    "id", "title", "category", "summary", "version", "size", "sha256")))
            return self.answer(("\n".join(rows) + "\n").encode("ascii"))
        match = re.fullmatch(r"/v1/apps/([a-z0-9-]{1,31})\.elf", self.path)
        if not match or match.group(1) not in APPS:
            self.send_error(404, "Unknown application")
            self.close_connection = True
            return
        item = APPS[match.group(1)]
        try:
            src = get_verified_elf(item)
        except (OSError, ValueError, TimeoutError) as exc:
            self.log_error("Release rejected: %s", exc)
            self.send_error(502, "Source unavailable or verification failed")
            self.close_connection = True
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(item["size"]))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            if self.command != "HEAD":
                with src.open("rb") as stream:
                    while block := stream.read(8192):
                        self.wfile.write(block)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True


if __name__ == "__main__":
    validate()
    port = int(os.environ.get("PORT", "8080"))
    print("MAIZO Store: %d vetted releases, port %d" % (len(CATALOG), port), flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), StoreHTTP).serve_forever()
