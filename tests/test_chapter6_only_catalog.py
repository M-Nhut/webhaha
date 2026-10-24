"""Focused regression tests for the reduced Chapter-6 ID catalog."""

import unittest

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine

from services.curriculum_data import load_math9_catalog
from services.curriculum_migration import cleanup_non_chapter6_id6
from services.curriculum_service import normalize_curriculum_payload
from services.id6_service import make_id6, parse_id6


class TestChapter6OnlyCatalog(unittest.TestCase):
    def test_catalog_and_payload_are_chapter6_only(self):
        rows = load_math9_catalog()
        self.assertEqual(len(rows), 8)
        self.assertEqual({(row["grade"], row["chapter_code"]) for row in rows}, {("9", "6")})
        normalized = normalize_curriculum_payload({
            "grade": "9", "chapter_code": "6", "chapter_name": "Thống kê và xác suất",
            "lesson_code": "4", "lesson_name": "Phép thử ngẫu nhiên và không gian mẫu. Xác suất của biến cố",
            "category_code": "1", "category_name": "Viết tập hợp không gian mẫu của một phép thử",
        })
        self.assertEqual(normalized["topic_code"], "thong_ke_xac_suat")
        self.assertEqual(normalized["topic_name"], "Thống kê và xác suất")
        with self.assertRaises(ValueError):
            normalize_curriculum_payload({**normalized, "chapter_code": "1"})
        with self.assertRaises(ValueError):
            make_id6("9", "1", "1", "1", "nhan_biet", "single", 1)

    def test_non_lesson4_cleanup_deletes_outside_rows_and_keeps_retained_rows(self):
        engine = create_engine("sqlite:///:memory:")
        metadata = MetaData()
        nodes = Table(
            "curriculum_node", metadata,
            Column("id", Integer, primary_key=True), Column("grade", String),
            Column("chapter_code", String), Column("chapter_name", String),
            Column("lesson_code", String), Column("lesson_name", String),
            Column("category_code", String), Column("category_name", String),
        )
        questions = Table(
            "bank_question", metadata,
            Column("id", Integer, primary_key=True), Column("curriculum_node_id", Integer),
            Column("id6_scope", String), Column("id6_sequence", Integer),
            Column("source_id", String), Column("original_source_id", String),
            Column("chapter", String), Column("section", String),
            Column("question_category", String), Column("classification_status", String),
            Column("classification_data", Text),
        )
        counters = Table(
            "id6_counter", metadata,
            Column("scope", String, primary_key=True), Column("last_sequence", Integer),
        )
        metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(nodes.insert(), [
                {"id": 1, "grade": "9", "chapter_code": "6", "lesson_code": "4", "category_code": "1"},
                {"id": 2, "grade": "9", "chapter_code": "1", "chapter_name": "Chương 1",
                 "lesson_code": "1", "lesson_name": "Bài 1", "category_code": "1", "category_name": "Dạng 1"},
            ])
            connection.execute(questions.insert(), {
                "id": 7, "curriculum_node_id": 2, "id6_scope": "9C1-1-1",
                "id6_sequence": 4, "source_id": "9C1N1-1D.4", "chapter": "1",
                "section": "1", "question_category": "1", "classification_status": "suggested",
                "classification_data": "{}",
            })
            connection.execute(counters.insert(), [
                {"scope": "9C1-1-1", "last_sequence": 4},
                {"scope": "9C6-1-1", "last_sequence": 3},
            ])

        preview = cleanup_non_chapter6_id6(engine, dry_run=True)
        self.assertEqual(preview["counts"]["nodes_removed"], 1)
        self.assertEqual(preview["counts"]["questions_removed"], 1)
        report = cleanup_non_chapter6_id6(engine)
        self.assertEqual(report["status"], "applied")
        with engine.connect() as connection:
            self.assertEqual(connection.execute(questions.select()).fetchall(), [])
            self.assertEqual(connection.execute(nodes.select()).fetchall(), [(1, "9", "6", None, "4", None, "1", None)])
            self.assertEqual([row[0] for row in connection.execute(counters.select()).fetchall()], [])
        engine.dispose()

    def test_parser_reads_only_chapter6(self):
        self.assertIsNotNone(parse_id6("9C6N4-1D.1"))
        self.assertIsNone(parse_id6("9C6N1-1D.1"))
        self.assertIsNone(parse_id6("9C1N1-1D.1"))


if __name__ == "__main__":
    unittest.main()
