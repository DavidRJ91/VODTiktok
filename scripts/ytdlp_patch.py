from __future__ import annotations

import sys

from yt_dlp.extractor.tiktok import TikTokLiveIE
from yt_dlp.utils import UserNotLive


def _patch_tiktok_live() -> None:
    original_call_api = TikTokLiveIE._call_api

    def patched_call_api(self, url, param, room_id, uploader, key=None):
        try:
            return original_call_api(self, url, param, room_id, uploader, key)
        except UserNotLive:
            if "api/live/detail" in url:
                self.report_warning(
                    "No se pudo obtener la lista HLS (400); se usará el stream FLV disponible."
                )
                return {}
            raise

    TikTokLiveIE._call_api = patched_call_api


if __name__ == "__main__":
    _patch_tiktok_live()
    import yt_dlp

    sys.exit(yt_dlp.main())
