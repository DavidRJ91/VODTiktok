from __future__ import annotations
from common import env, write_json
from tiktok_live_capture import capture_live_segment

def main():
    url = env("TIKTOK_LIVE_URL")
    max_seconds = int(env("MAX_RECORD_SECONDS", "16800"))
    result = capture_live_segment(url, "work/live", max_seconds, "tiktok_live")
    write_json("run_data/manifest.json", {
        "source_url": url,
        "filepath": result.filepath,
        "title": env("VIDEO_TITLE") or result.info.title,
        "description": env("VIDEO_DESCRIPTION"),
        "duration": result.duration_seconds,
    })

if __name__ == "__main__":
    main()
