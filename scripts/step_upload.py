from __future__ import annotations
from common import env, read_json, write_json
from youtube_common import upload_video

def main():
    manifest = read_json("run_data/manifest.json")
    if not manifest:
        raise RuntimeError("No existe run_data/manifest.json")

    result = upload_video(
        manifest["filepath"],
        manifest.get("title") or "TikTok LIVE",
        manifest.get("description") or "",
        env("PRIVACY_STATUS", "unlisted"),
        env("SCHEDULED_AT", ""),
    )
    result["source_url"] = manifest.get("source_url", "")
    result["duration"] = manifest.get("duration")
    result["part_number"] = manifest.get("part_number")
    write_json("run_data/result.json", result)
    print(result["video_url"])

if __name__ == "__main__":
    main()
