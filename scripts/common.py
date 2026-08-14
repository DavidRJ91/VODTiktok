from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()

def die(message: str):
    raise RuntimeError(message)

def write_json(path: str | Path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def read_json(path: str | Path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def probe_duration_seconds(filepath: str | Path):
    p = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(filepath)],
        capture_output=True, text=True
    )
    if p.returncode != 0:
        return None
    try:
        return int(float(p.stdout.strip()))
    except Exception:
        return None
