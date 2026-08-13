from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_store import LocalStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the normalized Chinese Cheese Video YouTube catalog")
    parser.add_argument("--output", default="youtube-catalog.json")
    parser.add_argument("--db-path", default=None)
    args = parser.parse_args()
    store = LocalStore(args.db_path)
    payload = store.get_youtube_catalog(limit=500)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: len(value) for key, value in payload.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
