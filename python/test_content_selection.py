from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_runner import select_diverse_candidates
from director import _fallback
from local_store import LocalStore, normalize_topic_key


class ContentSelectionTests(unittest.TestCase):
    def test_topic_key_normalizes_source_suffixes(self) -> None:
        first = normalize_topic_key("Trending Xiangqi: Xu Xiangyu and Yan Tianqi are 2026 Chinese chess champions - Chess News | ChessBase")
        second = normalize_topic_key("Xu Xiangyu and Yan Tianqi are 2026 Chinese chess champions - another news source")
        self.assertEqual(first, second)

    def test_published_topic_is_not_selected_again_from_another_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / "selection.db")
            store.add_candidate({
                "id": "published-topic",
                "topic_key": "same xiangqi championship story",
                "content_type": "trend_breakdown",
                "title": "Trending Xiangqi: Same Xiangqi Championship Story - Source A",
                "language": "en",
                "source_kind": "rss",
                "status": "published",
                "payload": {"topic_key": "same xiangqi championship story", "moves": ["0,6-0,5"]},
            })
            store.add_candidate({
                "id": "duplicate-topic",
                "topic_key": "same xiangqi championship story",
                "content_type": "trend_breakdown",
                "title": "Trending Xiangqi: Same Xiangqi Championship Story - Source B",
                "language": "en",
                "source_kind": "rss",
                "status": "discovered",
                "payload": {"topic_key": "same xiangqi championship story", "moves": ["0,6-0,5"]},
            })
            store.add_candidate({
                "id": "fresh-opening",
                "topic_key": "fresh opening lesson",
                "content_type": "opening",
                "title": "A Fresh Opening Lesson",
                "language": "en",
                "source_kind": "generated_evergreen",
                "status": "discovered",
                "priority_score": 3.0,
                "payload": {"topic_key": "fresh opening lesson", "moves": ["1,9-2,7"]},
            })
            selected = select_diverse_candidates(store, language="en", limit=1)
            self.assertEqual([item["id"] for item in selected], ["fresh-opening"])

    def test_fallback_changes_topic_narration_and_move_variant(self) -> None:
        first = _fallback({
            "title": "Trending Xiangqi: Story Alpha",
            "trend_title": "Story Alpha",
            "source_kind": "rss",
            "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
            "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
        }, "en")
        second = _fallback({
            "title": "Trending Xiangqi: Story Beta",
            "trend_title": "Story Beta",
            "source_kind": "rss",
            "moves": ["0,6-0,5", "0,3-0,4", "1,7-1,4"],
            "fen": "rheakaehr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RHEAKAEHR r",
        }, "en")
        self.assertNotEqual(first["narration"], second["narration"])
        self.assertNotEqual(first["moves"], second["moves"])


if __name__ == "__main__":
    unittest.main()
