from __future__ import annotations
import subprocess, sys
from pathlib import Path
from common import env, read_json, write_json
from tiktok_live_capture import TikTokLiveError, capture_live_segment, is_live

def main():
    url = env("TIKTOK_LIVE_URL")
    max_seconds = max(300, min(int(env("CHUNK_SECONDS", "300")), 3600))
    base_title = env("VIDEO_TITLE", "TikTok LIVE")
    description = env("VIDEO_DESCRIPTION")
    parts = []
    part = 1

    while True:
        if not is_live(url):
            if part == 1:
                raise TikTokLiveError("El LIVE no está activo.")
            break

        result = capture_live_segment(
            url, f"work/part_{part:03d}", max_seconds, f"part_{part:03d}"
        )
        write_json("run_data/manifest.json", {
            "source_url": url,
            "filepath": result.filepath,
            "title": f"{base_title} — Parte {part}",
            "description": description,
            "duration": result.duration_seconds,
            "part_number": part,
        })
        subprocess.run([sys.executable, "scripts/step_upload.py"], check=True)
        upload = read_json("run_data/result.json")
        parts.append(upload)
        write_json("run_data/live_parts.json", parts)
        try:
            Path(result.filepath).unlink()
        except FileNotFoundError:
            pass
        part += 1

if __name__ == "__main__":
    main()
