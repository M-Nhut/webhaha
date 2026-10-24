"""Chapter 6 release and migration tests on isolated databases only."""

import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
from sqlalchemy import inspect, select, text

from database import db
from models import (
    BankQuestion, CurriculumCatalogMigration, CurriculumNode, ID6Counter,
    ImportSession, QuestionBank, User,
)
from services.curriculum_data import CHAPTER6_MIGRATION, CHAPTER6_VERSION, load_chapter6_bundle, load_math9_catalog
from services.curriculum_migration import (
    CatalogMigrationBlocked, apply_chapter6_migration, inspect_chapter6_migration,
    rollback_chapter6_migration,
)
from services.curriculum_service import normalize_curriculum_payload, seed_math9_catalog


class TestChapter6Migration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(Path(self.temp.name) / "test.db")
        db.init_app(self.app)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        with db.engine.begin() as connection:
            connection.execute(User.__table__.insert().values(
                id=1, username="catalog-test", fullname="Catalog Test", user_code="C6", role="teacher"))
            connection.execute(QuestionBank.__table__.insert().values(
                id=1, name="Catalog Test", subject="Toán", created_by=1))
        self.bundle = load_chapter6_bundle()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()
        self.temp.cleanup()

    def seed_legacy(self):
        with db.engine.begin() as connection:
            for row in self.bundle["legacy"]:
                code = f"9C6-{row['lesson_code']}-{row['category_code']}"
                connection.execute(CurriculumNode.__table__.insert().values(**row, canonical_code=code))

    def node_id(self, code="9C6-4-2"):
        with db.engine.connect() as connection:
            return connection.execute(select(CurriculumNode.id).where(CurriculumNode.canonical_code == code)).scalar_one()

    def add_question(self, **values):
        with db.engine.begin() as connection:
            connection.execute(BankQuestion.__table__.insert().values(
                id=1, bank_id=1, created_by=1, question_text="Nội dung cũ $x^{-2}<0$", **values))

    def nodes(self):
        with db.engine.connect() as connection:
            return [dict(row) for row in connection.execute(select(CurriculumNode.__table__).order_by(CurriculumNode.id)).mappings()]

    def assert_blocked_without_writes(self, kind):
        before = self.nodes()
        with self.assertRaises(CatalogMigrationBlocked) as caught:
            apply_chapter6_migration(db.engine)
        self.assertIn(kind, {b["kind"] for b in caught.exception.report["blockers"]})
        self.assertEqual(self.nodes(), before)
        with db.engine.connect() as connection:
            self.assertEqual(connection.execute(select(CurriculumCatalogMigration)).all(), [])

    def test_release_has_exact_codes_topics_and_rubric_without_default_level(self):
        rows = self.bundle["rows"]
        self.assertEqual(len(rows), 8)
        for lesson, size in {"4": 8}.items():
            subset = [r for r in rows if r["lesson_code"] == lesson]
            self.assertEqual({r["category_code"] for r in subset}, {str(n) for n in range(1, size + 1)})
            self.assertEqual({r["topic_code"] for r in subset}, {"thong_ke_xac_suat"})
        lookup = {(r["lesson_code"], r["category_code"]): r["category_name"] for r in rows}
        self.assertEqual(lookup["4", "1"], "Viết tập hợp không gian mẫu của một phép thử")
        self.assertEqual(lookup["4", "4"], "Tính xác suất của biến cố trong trò chơi Gieo xúc sắc")
        self.assertTrue(lookup["4", "8"].endswith("một nhóm đối tượng"))
        rules = self.bundle["rules"]
        self.assertEqual(rules["topics"], [{"code": "thong_ke_xac_suat", "name": "Thống kê và xác suất",
                                           "lesson_codes": ["4"]}])
        self.assertIsNone(rules["policies"]["default_difficulty"])
        self.assertEqual([v["label"] for v in rules["difficulty_rubric"].values()], ["NB", "TH", "VD", "VDC"])
        self.assertTrue(all(e["action"] == "needs_review" for e in self.bundle["transition"]["entries"]))

    def test_fresh_seed_and_catalog_options_preserve_later_edits(self):
        from services.id6_service import catalog_options
        seed_math9_catalog()
        self.assertEqual(len(self.nodes()), 8)
        node = db.session.get(CurriculumNode, self.node_id())
        self.assertEqual(node.catalog_version, CHAPTER6_VERSION)
        node.category_name = "Tên giáo viên đã chỉnh"
        node.topic_name = "Chủ đề tùy chỉnh"
        db.session.commit()
        seed_math9_catalog()
        option = next(row for row in catalog_options() if row["id"] == node.id)
        self.assertEqual(option["category_name"], "Tên giáo viên đã chỉnh")
        self.assertEqual(option["topic_name"], "Chủ đề tùy chỉnh")

    def test_startup_seed_does_not_reinterpret_partial_legacy_chapter(self):
        row = self.bundle["legacy"][5]
        with db.engine.begin() as connection:
            connection.execute(CurriculumNode.__table__.insert().values(**row, canonical_code="9C6-4-6"))
        seed_math9_catalog()
        chapter = [n for n in self.nodes() if n["chapter_code"] == "6"]
        self.assertEqual(len(chapter), 1)
        self.assertEqual(chapter[0]["category_name"], "Luật số lớn (trực giác)")

    def test_dry_run_is_read_only_and_apply_is_idempotent(self):
        self.seed_legacy()
        before = self.nodes()
        report = inspect_chapter6_migration(db.engine)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["counts"]["update"], 8)
        self.assertEqual(self.nodes(), before)
        result = apply_chapter6_migration(db.engine, report["plan_fingerprint"])
        self.assertEqual(result["status"], "applied")
        after = self.nodes()
        self.assertEqual([n["id"] for n in after], [n["id"] for n in before])
        self.assertEqual({n["catalog_version"] for n in after}, {CHAPTER6_VERSION})
        self.assertEqual(apply_chapter6_migration(db.engine)["status"], "already_applied")
        self.assertEqual(self.nodes(), after)
        receipt = db.session.get(CurriculumCatalogMigration, CHAPTER6_MIGRATION)
        snapshot = json.loads(receipt.snapshot_json)
        self.assertEqual(len(snapshot["before"]["nodes"]), 8)
        self.assertIn("transition", snapshot)

    def test_seed_does_not_bind_old_tags_when_catalog_is_missing(self):
        self.add_question(source_id="9C6H2-2D.4")
        seed_math9_catalog()
        self.assertEqual(len([n for n in self.nodes() if n["chapter_code"] == "6"]), 8)
        self.assertEqual(db.session.get(BankQuestion, 1).source_id, "9C6H2-2D.4")

    def test_merge_v3_topics_preserves_prior_receipt_and_category_identity(self):
        with db.engine.begin() as connection:
            for row in self.bundle["rows"]:
                previous = {**row, "catalog_version": "math9-c6-v3",
                            "topic_code": "xac_suat" if row["lesson_code"] == "4" else "thong_ke",
                            "topic_name": "Xác suất" if row["lesson_code"] == "4" else "Thống kê"}
                connection.execute(CurriculumNode.__table__.insert().values(
                    **previous, canonical_code=f"9C6-{row['lesson_code']}-{row['category_code']}"))
            connection.execute(CurriculumCatalogMigration.__table__.insert().values(
                migration_key="math9-chapter6-v3", catalog_version="math9-c6-v3", status="applied",
                applied_at=dt.datetime(2026, 9, 5), snapshot_json='{"original":"preserved"}',
                after_fingerprint="previous-snapshot"))
        before = self.nodes()
        self.assertEqual(apply_chapter6_migration(db.engine)["status"], "applied")
        after = self.nodes()
        self.assertEqual({n["topic_code"] for n in after}, {"thong_ke_xac_suat"})
        for old, new in zip(before, after):
            for key in ("id", "canonical_code", "chapter_name", "lesson_name", "category_name"):
                self.assertEqual(old[key], new[key])
        receipt = db.session.get(CurriculumCatalogMigration, "math9-chapter6-v3")
        self.assertEqual(receipt.snapshot_json, '{"original":"preserved"}')
        self.assertEqual(rollback_chapter6_migration(db.engine)["status"], "rolled_back")
        self.assertEqual(self.nodes(), before)

    def test_other_chapters_questions_and_high_water_marks_are_untouched(self):
        self.seed_legacy()
        other = {
            **self.bundle["rows"][0],
            "chapter_code": "1",
            "lesson_code": "1",
            "category_code": "1",
            "canonical_code": "9C1-1-1",
        }
        with db.engine.begin() as connection:
            connection.execute(CurriculumNode.__table__.insert().values(**other))
            connection.execute(ID6Counter.__table__.insert().values(scope="9C6-4-2", last_sequence=81))
        self.add_question(grade="Lớp 9", chapter="1", source_id="9C1N1-1D.7")
        other_before = [n for n in self.nodes() if n["chapter_code"] == "1"]
        apply_chapter6_migration(db.engine)
        self.assertEqual([n for n in self.nodes() if n["chapter_code"] == "1"], other_before)
        self.assertEqual(db.session.get(ID6Counter, "9C6-4-2").last_sequence, 81)
        q = db.session.get(BankQuestion, 1)
        self.assertEqual(q.source_id, "9C1N1-1D.7")
        self.assertEqual(q.question_text, "Nội dung cũ $x^{-2}<0$")

    def test_referenced_node_blocks_without_changing_question_meaning(self):
        self.seed_legacy()
        self.add_question(curriculum_node_id=self.node_id(), difficulty_level="thong_hieu")
        self.assert_blocked_without_writes("referenced_questions")
        self.assertEqual(db.session.get(BankQuestion, 1).difficulty_level, "thong_hieu")

    def test_old_source_id_without_fk_is_detected(self):
        self.seed_legacy()
        self.add_question(source_id="%[9C6H4-2D.4]")
        self.assert_blocked_without_writes("referenced_questions")

    def test_legacy_mapping_is_detected(self):
        self.seed_legacy()
        self.add_question()
        with db.engine.begin() as connection:
            connection.execute(text("CREATE TABLE question_skill (id INTEGER PRIMARY KEY, question_id INTEGER, curriculum_node_id INTEGER, is_primary BOOLEAN)"))
            connection.execute(text("INSERT INTO question_skill VALUES (1, 1, :node, 1)"), {"node": self.node_id()})
        self.assert_blocked_without_writes("legacy_mappings")

    def test_custom_catalog_is_not_overwritten(self):
        self.seed_legacy()
        with db.engine.begin() as connection:
            connection.execute(CurriculumNode.__table__.update().where(CurriculumNode.canonical_code == "9C6-4-2").values(category_name="Nội dung riêng"))
        self.assert_blocked_without_writes("custom_catalog")

    def test_active_import_blocks_but_expired_session_does_not(self):
        self.seed_legacy()
        with db.engine.begin() as connection:
            connection.execute(ImportSession.__table__.insert().values(
                id="pending", user_id=1, filename="old.tex", file_type="tex", status="preview",
                expires_at=dt.datetime.utcnow() + dt.timedelta(hours=1)))
        self.assert_blocked_without_writes("active_imports")
        with db.engine.begin() as connection:
            connection.execute(ImportSession.__table__.update().values(expires_at=dt.datetime.utcnow() - dt.timedelta(hours=1)))
        self.assertEqual(apply_chapter6_migration(db.engine)["status"], "applied")

    def test_stale_dry_run_is_rejected(self):
        self.seed_legacy()
        fingerprint = inspect_chapter6_migration(db.engine)["plan_fingerprint"]
        with db.engine.begin() as connection:
            connection.execute(ID6Counter.__table__.insert().values(scope="9C6-4-2", last_sequence=1))
        with self.assertRaises(CatalogMigrationBlocked) as caught:
            apply_chapter6_migration(db.engine, fingerprint)
        self.assertIn("stale_plan", {b["kind"] for b in caught.exception.report["blockers"]})

    def test_restore_is_exact_and_repeatable(self):
        self.seed_legacy()
        before = self.nodes()
        apply_chapter6_migration(db.engine)
        self.assertEqual(rollback_chapter6_migration(db.engine)["status"], "rolled_back")
        self.assertEqual(self.nodes(), before)
        self.assertEqual(rollback_chapter6_migration(db.engine)["status"], "already_rolled_back")
        with self.assertRaises(CatalogMigrationBlocked):
            apply_chapter6_migration(db.engine)

    def test_restore_does_not_overwrite_edits_or_new_references(self):
        self.seed_legacy()
        apply_chapter6_migration(db.engine)
        self.add_question(curriculum_node_id=self.node_id())
        with self.assertRaises(CatalogMigrationBlocked):
            rollback_chapter6_migration(db.engine)
        with db.engine.begin() as connection:
            connection.execute(BankQuestion.__table__.delete())
            connection.execute(CurriculumNode.__table__.update().where(CurriculumNode.canonical_code == "9C6-4-2").values(category_name="Sửa sau migration"))
        with self.assertRaises(CatalogMigrationBlocked):
            rollback_chapter6_migration(db.engine)
        self.assertEqual(db.session.get(CurriculumNode, self.node_id()).category_name, "Sửa sau migration")

    def test_apply_failure_rolls_back_catalog_and_schema_changes(self):
        self.seed_legacy()
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE curriculum_catalog_migration"))
            connection.execute(text("ALTER TABLE curriculum_node DROP COLUMN topic_code"))
            connection.execute(text("ALTER TABLE curriculum_node DROP COLUMN topic_name"))
        before = inspect_chapter6_migration(db.engine)["before"]
        with patch("services.curriculum_migration._audit_table", side_effect=RuntimeError("injected failure")):
            with self.assertRaisesRegex(RuntimeError, "injected failure"):
                apply_chapter6_migration(db.engine)
        self.assertEqual(inspect_chapter6_migration(db.engine)["before"], before)
        self.assertNotIn("topic_code", {c["name"] for c in inspect(db.engine).get_columns("curriculum_node")})

    def test_pre_topic_schema_migrates_and_restores_without_touching_other_tables(self):
        self.seed_legacy()
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE curriculum_node DROP COLUMN topic_code"))
            connection.execute(text("ALTER TABLE curriculum_node DROP COLUMN topic_name"))
        before = inspect_chapter6_migration(db.engine)["before"]["nodes"]
        self.assertEqual(apply_chapter6_migration(db.engine)["status"], "applied")
        self.assertEqual(rollback_chapter6_migration(db.engine)["status"], "rolled_back")
        restored = [{k: v for k, v in n.items() if k not in {"topic_code", "topic_name"}} for n in self.nodes()]
        self.assertEqual(restored, before)

    def test_topic_payload_does_not_erase_existing_metadata_when_absent(self):
        payload = self.bundle["rows"][0]
        normalized = normalize_curriculum_payload(payload)
        self.assertEqual(normalized["topic_code"], "thong_ke_xac_suat")
        without = {k: v for k, v in payload.items() if not k.startswith("topic_")}
        self.assertEqual(normalize_curriculum_payload(without)["topic_code"], "thong_ke_xac_suat")
        self.assertEqual(
            normalize_curriculum_payload({**payload, "topic_code": ""})["topic_code"],
            "thong_ke_xac_suat",
        )


if __name__ == "__main__":
    unittest.main()
