"""Download every locked wheel for an offline / flaky-network install.

uv's own downloader fails on machines whose DNS only works through the system
resolver (e.g. Tailscale MagicDNS + Nix-built uv). This reads uv.lock, picks the
wheel for the target platform, and downloads it with the system ``curl``
(resumable, retried). Then install without touching the network:

    uv export --frozen --no-hashes --no-emit-project --group server --group ml --group dev > /tmp/req.txt
    python3 tools/fetch_wheels.py --req /tmp/req.txt --out /mnt/storage/simonpro/wheels
    uv venv --python 3.11 $VENV
    uv pip install --python $VENV/bin/python --no-index --find-links /mnt/storage/simonpro/wheels -r /tmp/req.txt

Only needs the standard library (Python >= 3.11 for tomllib).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def wanted(req: Path) -> set[tuple[str, str]]:
    # Keep every (name, version): a package may be pinned differently per Python version.
    out = set()
    for raw in req.read_text().splitlines():
        line, _, marker = raw.partition(";")
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        # Target is linux x86_64: drop requirements meant for other platforms.
        if any(m in marker for m in ("sys_platform != 'linux'", "sys_platform == 'win32'",
                                     "sys_platform == 'darwin'", "platform_machine == 'aarch64'")):
            continue
        name, _, ver = line.partition("==")
        out.add((norm(name.split("[")[0]), ver.strip()))
    return out


def score(filename: str, py: str) -> int:
    """Higher is better; -1 = not installable on linux x86_64 / this python."""
    if "musl" in filename:
        return -1
    if filename.endswith("none-any.whl"):
        return 1
    plat_ok = "linux_x86_64" in filename or ("manylinux" in filename and "x86_64" in filename)
    if not plat_ok:
        return -1
    if f"-{py}-{py}-" in filename or f"-{py}-abi3-" in filename:
        return 3
    if "-abi3-" in filename:
        major_minor = re.search(r"-cp3(\d+)-abi3-", filename)
        return 2 if major_minor and int(major_minor.group(1)) <= int(py[3:]) else -1
    if "py3-none" in filename or "py2.py3-none" in filename:
        return 2
    return -1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--req", type=Path, required=True, help="output of `uv export --no-hashes`")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lock", type=Path, default=ROOT / "uv.lock")
    ap.add_argument("--python-tag", default=f"cp{sys.version_info.major}{sys.version_info.minor}")
    a = ap.parse_args()

    lock = tomllib.loads(a.lock.read_text())
    need = wanted(a.req)
    a.out.mkdir(parents=True, exist_ok=True)
    missing, todo = [], []
    for name, ver in sorted(need):
        cands = []
        for p in lock["package"]:
            if norm(p["name"]) != name or p["version"] != ver:
                continue
            for w in p.get("wheels", []):
                fn = unquote(w["url"].rsplit("/", 1)[-1])
                s = score(fn, a.python_tag)
                if s >= 0:
                    cands.append((s, fn, w["url"]))
        if not cands:
            missing.append(f"{name}=={ver}")
            continue
        _, fn, url = max(cands)
        todo.append((fn, url))

    for i, (fn, url) in enumerate(todo, 1):
        dest = a.out / fn
        print(f"[{i}/{len(todo)}] {fn}", flush=True)
        for _ in range(8):
            r = subprocess.run(["curl", "-sS", "-L", "-C", "-", "--connect-timeout", "20", "--retry", "5",
                                "--retry-all-errors", "-o", str(dest), url])
            if r.returncode in (0, 33):  # 33 = range not supported: file already complete
                break
    if missing:
        print("No suitable wheel (needs a source build or another platform):", ", ".join(missing))
    print("done")


if __name__ == "__main__":
    main()
