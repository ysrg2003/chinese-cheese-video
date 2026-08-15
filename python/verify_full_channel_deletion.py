from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import youtube_publisher

EXPECTED_CHANNEL_ID='UCM7pTdgZRwDZ2gZDtC6SITg'

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    args=parser.parse_args()
    manifest=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
    service=youtube_publisher.build_service()
    channel=youtube_publisher._execute_with_backoff(lambda: service.channels().list(part='id',mine=True,maxResults=1))
    ids=[str(item.get('id')) for item in channel.get('items') or [] if item.get('id')]
    if ids != [EXPECTED_CHANNEL_ID]:
        raise SystemExit(f'channel mismatch: expected {EXPECTED_CHANNEL_ID}, received {ids}')
    target_ids=[str(item.get('video_id')) for item in manifest.get('videos') or [] if item.get('video_id')]
    present=[]
    for start in range(0,len(target_ids),50):
        chunk=target_ids[start:start+50]
        response=youtube_publisher._execute_with_backoff(lambda chunk=chunk: service.videos().list(part='id,snippet,status',id=','.join(chunk),maxResults=len(chunk)))
        present.extend([{'video_id':str(item.get('id')),'title':(item.get('snippet') or {}).get('title'),'privacy_status':(item.get('status') or {}).get('privacyStatus')} for item in response.get('items') or [] if item.get('id')])
    report={'channel_id':EXPECTED_CHANNEL_ID,'target_count':len(target_ids),'present_count':len(present),'present_videos':present,'verified_absent':not present}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if present: return 1
    return 0
if __name__=='__main__': raise SystemExit(main())
