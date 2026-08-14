from __future__ import annotations
import json, os, time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def youtube_service():
    token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
    if token_json:
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    else:
        refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]
        client_id = os.environ["YOUTUBE_CLIENT_ID"]
        client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)

def upload_video(filepath, title, description, privacy, scheduled_at=""):
    youtube = youtube_service()
    status = {"privacyStatus": "private" if privacy == "scheduled" else privacy}
    if privacy == "scheduled":
        if not scheduled_at:
            raise RuntimeError("Falta SCHEDULED_AT para programar el vídeo.")
        status["publishAt"] = scheduled_at

    body = {
        "snippet": {"title": title or "TikTok LIVE", "description": description or ""},
        "status": status,
    }
    media = MediaFileUpload(filepath, chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()
        time.sleep(0.2)

    video_id = response["id"]
    return {
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": title,
        "privacy": privacy,
    }
