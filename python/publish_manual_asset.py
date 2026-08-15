from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))

from local_store import LocalStore
from youtube_publisher import publish_video


def main() -> int:
    parser = argparse.ArgumentParser(description='Publish one exact pre-rendered Xiangqi asset.')
    parser.add_argument('--video', required=True)
    parser.add_argument('--job-json', required=True)
    parser.add_argument('--thumbnail', required=False)
    parser.add_argument('--db-path', default=os.getenv('LOCAL_DB_PATH', 'data/chinese_cheese_video.db'))
    args = parser.parse_args()

    video_path = Path(args.video).resolve()
    job_path = Path(args.job_json).resolve()
    job = json.loads(job_path.read_text(encoding='utf-8'))
    job['content_type'] = 'board_setup'
    job['playlist_key'] = 'en-board-setup'
    job['title'] = 'The 9×10 Point Board'
    job['hook'] = 'A Xiangqi board has nine files, ten ranks, and ninety intersections where every move begins and ends.'
    job['source_kind'] = 'curriculum'
    job['curriculum_lesson_key'] = 'en-005-the-9x10-point-board'
    job['curriculum_sequence'] = 3
    if args.thumbnail:
        job.setdefault('thumbnailAssets', {})['default'] = str(Path(args.thumbnail).resolve())
        job['thumbnailAssets']['english'] = str(Path(args.thumbnail).resolve())

    result = publish_video(
        video_path,
        job,
        localization_dir=video_path.parent / 'localization',
    )

    store = LocalStore(args.db_path)
    publication = result if isinstance(result, dict) else {}
    status = str(publication.get('status') or 'failed')
    store.upsert_youtube_publication(
        str(job['id']),
        str(job.get('language') or 'en'),
        str(job.get('content_type') or 'board_setup'),
        status,
        video_id=publication.get('video_id'),
        video_url=publication.get('video_url'),
        playlist_id=publication.get('playlist_id'),
        playlist_url=publication.get('playlist_url'),
        metadata=publication.get('metadata') or {},
        error_message=publication.get('error_message'),
    )
    lesson_key = str(job.get('curriculum_lesson_key') or '')
    if lesson_key:
        if status == 'published':
            store.update_curriculum_episode(lesson_key, 'en', 'published', candidate_id='curriculum-en-005-the-9x10-point-board', job_id=str(job['id']), error_message=None)
        elif status in {'published_localization_pending', 'published_thumbnail_pending', 'uploaded_playlist_pending'}:
            store.update_curriculum_episode(lesson_key, 'en', 'retry', candidate_id='curriculum-en-005-the-9x10-point-board', job_id=str(job['id']), error_message=str(publication.get('error_message') or status))
        else:
            store.update_curriculum_episode(lesson_key, 'en', 'retry', candidate_id='curriculum-en-005-the-9x10-point-board', job_id=str(job['id']), error_message=str(publication.get('error_message') or status))
    store.checkpoint()
    print(json.dumps({'publication': publication, 'lesson_key': lesson_key, 'catalog_db': str(Path(args.db_path).resolve())}, ensure_ascii=False, indent=2))
    return 0 if status in {'published', 'published_localization_pending', 'published_thumbnail_pending', 'uploaded_playlist_pending'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
