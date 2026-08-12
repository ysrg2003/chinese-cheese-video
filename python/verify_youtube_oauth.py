from __future__ import annotations

import json
import sys
from pathlib import Path

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

TOKEN_PATH = Path(sys.argv[1])
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
credentials = Credentials.from_authorized_user_info(data, SCOPES)
youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
channel = youtube.channels().list(part="id,snippet,contentDetails", mine=True).execute()
items = channel.get("items", [])
if not items:
    raise SystemExit("No channel returned for the authorized account")
item = items[0]
playlists = youtube.playlists().list(part="id,snippet", mine=True, maxResults=50).execute()
print(json.dumps({
    "channel_id": item.get("id"),
    "channel_title": item.get("snippet", {}).get("title"),
    "playlist_count_returned": len(playlists.get("items", [])),
    "playlist_titles": [p.get("snippet", {}).get("title") for p in playlists.get("items", [])],
    "write_test_performed": False,
}, ensure_ascii=False))
