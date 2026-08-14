from __future__ import annotations
import os, subprocess
from pathlib import Path
from common import read_json, write_json

def git(*args):
    subprocess.run(["git", *args], check=True)

def main():
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    main_result = read_json("run_data/result.json")
    parts = read_json("run_data/live_parts.json", [])
    payload = {
        "run_id": run_id,
        "main": main_result if not parts else None,
        "live_parts": parts,
    }
    path = Path("run_status") / f"{run_id}.json"
    write_json(path, payload)

    if os.environ.get("GITHUB_ACTIONS") != "true":
        return

    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", str(path))
    subprocess.run(["git","commit","-m",f"Publish result for run {run_id}"], check=False)

    # Reintenta con rebase por si otra ejecución concurrente publicó su
    # resultado justo antes (evita que el job falle solo por un push no-ff).
    for attempt in range(3):
        push = subprocess.run(["git", "push"])
        if push.returncode == 0:
            break
        subprocess.run(["git", "pull", "--rebase"], check=True)
    else:
        subprocess.run(["git", "push"], check=True)

if __name__ == "__main__":
    main()
