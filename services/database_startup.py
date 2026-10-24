"""Database startup lifecycle, extracted without changing migration SQL or commit order.

Call initialize_database inside an application context. Importing this module
alone never creates tables or runs migrations.
"""

from database import db
from models import (
    User, Course, Enrollment, BankQuestion, ExamQuestion,
    ImportSession, ExamSubmission, SubmissionAnswer, LearningHistory, MasterySnapshot,
)
from helpers import parse_date
from adaptive_engine import AdaptiveEngine
from services.curriculum_service import seed_math9_catalog
from services.id6_service import migrate_id6_metadata, parse_id6_for_record

def seed_sample_data():
    if User.query.count():
        return

    users = [
        ("admin", "Nguyễn Văn Admin", "ADMIN001", "admin", "0912345678", "Giám đốc"),
        ("gv001", "Thầy Minh - Anh", "GV001", "teacher", "0978123456", "Giáo viên Anh"),
        ("hs001", "Nguyễn Thị Hoa", "HS001", "student", "0123456789", "Lớp 9"),
    ]
    created = {}
    for username, fullname, code, role, phone, position in users:
        user = User(
            username=username,
            fullname=fullname,
            user_code=code,
            role=role,
            phone=phone,
            position=position,
            is_active=True,
        )
        user.set_password("123456")
        db.session.add(user)
        created[username] = user
    db.session.flush()
    courses_data = [
        ("Toán 9 nâng cao", "Toán", created["gv001"], "P101", "2026-06-01", "2026-12-31"),
        ("Anh văn 10 giao tiếp", "Anh văn", created["gv001"], "P102", "2026-06-15", "2026-10-15"),
    ]
    courses_created = []
    for name, subject, teacher, room, start, end in courses_data:
        course = Course(
            course_name=name,
            subject=subject,
            teacher_id=teacher.id,
            classroom=room,
            description=f"Chương trình {name} tại trung tâm.",
            start_date=parse_date(start),
            end_date=parse_date(end),
            is_active=True,
        )
        db.session.add(course)
        courses_created.append(course)
    db.session.flush()

    db.session.add(Enrollment(student_id=created["hs001"].id, course_id=courses_created[0].id))
    db.session.add(Enrollment(student_id=created.get("hs002", created["hs001"]).id, course_id=courses_created[1].id))
    db.session.commit()


def table_columns(table_name):
    try:
        inspector = db.inspect(db.engine)
        columns = inspector.get_columns(table_name)
        return {col['name'] for col in columns}
    except Exception as e:
        print(f"Error inspecting table {table_name}: {e}")
        return set()


def add_column_if_missing(table_name, column_name, ddl):
    if column_name not in table_columns(table_name):
        # Quote table name to prevent conflicts with reserved keywords (like "user" in Postgres)
        db.session.execute(db.text(f'ALTER TABLE "{table_name}" ADD COLUMN {column_name} {ddl}'))
        db.session.commit()


def migrate_existing_sqlite_schema():
    inspector = db.inspect(db.engine)
    tables = set(inspector.get_table_names())

    # 1. SQLite specific table recreation to fix NOT NULL constraint mismatches
    if db.engine.dialect.name == "sqlite":
        # Rebuild course table if it contains the old 'name' column or 'image_file'
        if "course" in tables:
            columns = table_columns("course")
            if "name" in columns or "image_file" in columns:
                try:
                    db.session.execute(db.text("PRAGMA foreign_keys=OFF;"))
                    db.session.execute(db.text("""
                        CREATE TABLE course_new (
                            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                            course_name VARCHAR(120) NOT NULL,
                            subject VARCHAR(80) NOT NULL,
                            teacher_id INTEGER,
                            classroom VARCHAR(40),
                            description TEXT,
                            start_date DATE,
                            end_date DATE,
                            is_active BOOLEAN DEFAULT 1,
                            FOREIGN KEY(teacher_id) REFERENCES user (id)
                        );
                    """))
                    db.session.execute(db.text("""
                        INSERT INTO course_new (id, course_name, subject, teacher_id, classroom, description, start_date, end_date, is_active)
                        SELECT 
                            id, 
                            COALESCE(course_name, name, ''), 
                            COALESCE(subject, ''), 
                            teacher_id, 
                            classroom, 
                            COALESCE(description, summary),
                            start_date, 
                            end_date, 
                            COALESCE(is_active, 1)
                        FROM course;
                    """))
                    db.session.execute(db.text("DROP TABLE course;"))
                    db.session.execute(db.text("ALTER TABLE course_new RENAME TO course;"))
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Error rebuilding SQLite course table: {e}")
                finally:
                    db.session.execute(db.text("PRAGMA foreign_keys=ON;"))

    # 2. General check & alter DDL for added/missing columns (DB agnostic)
    if "course" in tables:
        add_column_if_missing("course", "course_name", "VARCHAR(120) DEFAULT ''")
        add_column_if_missing("course", "classroom", "VARCHAR(40)")
        add_column_if_missing("course", "description", "TEXT")
        add_column_if_missing("course", "start_date", "DATE")
        add_column_if_missing("course", "end_date", "DATE")
        add_column_if_missing("course", "is_active", "BOOLEAN DEFAULT TRUE")
        columns = table_columns("course")
        if "name" in columns:
            db.session.execute(db.text("UPDATE course SET course_name = name WHERE course_name IS NULL OR course_name = ''"))
        if "summary" in columns:
            db.session.execute(db.text("UPDATE course SET description = summary WHERE description IS NULL"))
        db.session.commit()

    if "bank_question" in tables:
        add_column_if_missing("bank_question", "context", "TEXT")
        add_column_if_missing("bank_question", "image_url", "VARCHAR(500)")
        add_column_if_missing("bank_question", "confidence_scores", "TEXT")
        add_column_if_missing("bank_question", "source_id", "VARCHAR(50)")
        add_column_if_missing("bank_question", "chapter", "VARCHAR(20)")
        add_column_if_missing("bank_question", "section", "VARCHAR(20)")
        add_column_if_missing("bank_question", "question_category", "VARCHAR(20)")
        add_column_if_missing("bank_question", "curriculum_node_id", "INTEGER REFERENCES curriculum_node(id)")
        add_column_if_missing("bank_question", "id6_scope", "VARCHAR(80)")
        add_column_if_missing("bank_question", "id6_sequence", "INTEGER")
        add_column_if_missing("bank_question", "classification_status", "VARCHAR(30)")
        add_column_if_missing("bank_question", "classification_data", "TEXT")
        add_column_if_missing("bank_question", "learning_metadata", "TEXT")
        add_column_if_missing("bank_question", "difficulty_band", "VARCHAR(20)")
        add_column_if_missing("bank_question", "adaptive_priority", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("bank_question", "adaptive_excluded", "BOOLEAN NOT NULL DEFAULT FALSE")
        add_column_if_missing("bank_question", "content_revision", "INTEGER NOT NULL DEFAULT 1")
        add_column_if_missing("bank_question", "content_hash", "VARCHAR(64)")
        add_column_if_missing("bank_question", "catalog_version", "VARCHAR(30)")
        # Question scope is an additive, nullable rollout.  Existing rows are
        # deliberately left NULL until an audited migration can classify
        # them; policy code must fail closed when that classification is not
        # safe.  ``private_owner_id`` is separate from ``created_by`` because
        # an administrator may create/import a teacher's private supplement
        # in a shared bank in a later phase.
        add_column_if_missing("bank_question", "scope", "VARCHAR(20)")
        add_column_if_missing("bank_question", "private_owner_id", "INTEGER REFERENCES \"user\"(id)")
        db.session.execute(db.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_bank_question_id6_sequence ON bank_question (id6_scope, id6_sequence)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_bank_question_content_hash ON bank_question (content_hash)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_bank_question_scope ON bank_question (scope)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_bank_question_private_owner_id ON bank_question (private_owner_id)"))
        db.session.commit()

    if "question_bank" in tables:
        # Additive only: existing rows stay NULL until the reviewed bank
        # visibility backfill.  The authorization policy treats NULL
        # teacher-owned rows as private and does not infer shared access from
        # an admin creator, so adding this column cannot widen visibility.
        add_column_if_missing("question_bank", "visibility", "VARCHAR(20)")
        db.session.execute(db.text(
            "CREATE INDEX IF NOT EXISTS ix_question_bank_visibility "
            "ON question_bank (visibility)"
        ))
        db.session.commit()

    if "import_session" in tables:
        add_column_if_missing("import_session", "scope_data", "TEXT")
        for column in ("duplicate_decisions", "duplicate_report", "result_data"):
            add_column_if_missing("import_session", column, "TEXT")

    if "curriculum_node" in tables:
        add_column_if_missing("curriculum_node", "topic_code", "VARCHAR(40)")
        add_column_if_missing("curriculum_node", "topic_name", "VARCHAR(100)")

    if "formula_asset" in tables:
        add_column_if_missing("formula_asset", "source_text", "TEXT")
        add_column_if_missing("formula_asset", "source_preamble", "TEXT")
        add_column_if_missing("formula_asset", "render_method", "VARCHAR(40)")
        add_column_if_missing("formula_asset", "render_error", "TEXT")

    # Migrate Exam tables — add new columns for question bank integration
    if "exam" in tables:
        add_column_if_missing("exam", "question_bank_id", "INTEGER")
        add_column_if_missing("exam", "exam_type", "VARCHAR(20) DEFAULT 'exam'")
        add_column_if_missing("exam", "exam_category", "VARCHAR(50) DEFAULT 'Kiểm tra thường kỳ'")
        add_column_if_missing("exam", "total_questions", "INTEGER")
        add_column_if_missing("exam", "difficulty_config", "TEXT")
        add_column_if_missing("exam", "question_type_config", "TEXT")
        add_column_if_missing("exam", "adaptive_metadata", "TEXT")
        add_column_if_missing("exam", "assessment_purpose", "VARCHAR(30) DEFAULT 'summative'")
        add_column_if_missing("exam", "diagnostic_coverage", "TEXT")
        add_column_if_missing("exam", "source_manifest", "TEXT")

    if "exam_question" in tables:
        add_column_if_missing("exam_question", "learning_metadata", "TEXT")
        add_column_if_missing("exam_question", "bank_question_id", "INTEGER")
        add_column_if_missing("exam_question", "difficulty_level", "VARCHAR(20)")
        add_column_if_missing("exam_question", "explanation", "TEXT")
        add_column_if_missing("exam_question", "context", "TEXT")
        add_column_if_missing("exam_question", "image_url", "VARCHAR(500)")
        add_column_if_missing("exam_question", "source_id6", "VARCHAR(50)")
        add_column_if_missing("exam_question", "source_content_revision", "INTEGER")
        add_column_if_missing("exam_question", "source_content_hash", "VARCHAR(64)")
        add_column_if_missing("exam_question", "curriculum_code", "VARCHAR(80)")
        add_column_if_missing("exam_question", "curriculum_catalog_version", "VARCHAR(30)")
        add_column_if_missing("exam_question", "topic_snapshot", "VARCHAR(200)")
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_exam_question_source_content_hash ON exam_question (source_content_hash)"))

    if "exam_submission" in tables:
        add_column_if_missing("exam_submission", "exam_type", "VARCHAR(20) DEFAULT 'exam'")
        add_column_if_missing("exam_submission", "time_spent_seconds", "INTEGER")
        add_column_if_missing("exam_submission", "correct_count", "INTEGER DEFAULT 0")
        add_column_if_missing("exam_submission", "wrong_count", "INTEGER DEFAULT 0")
        add_column_if_missing("exam_submission", "status", "VARCHAR(20) NOT NULL DEFAULT 'draft'")
        add_column_if_missing("exam_submission", "grading_revision", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("exam_submission", "finalized_at", "DATETIME")
        add_column_if_missing("exam_submission", "idempotency_key", "VARCHAR(100)")
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_exam_submission_status ON exam_submission (status)"))
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_exam_submission_idempotency_key ON exam_submission (idempotency_key)"))

    if "submission_answer" in tables:
        add_column_if_missing("submission_answer", "answer_text", "TEXT")
        add_column_if_missing("submission_answer", "time_spent_seconds", "INTEGER")
        add_column_if_missing("submission_answer", "answer_status", "VARCHAR(20) NOT NULL DEFAULT 'unanswered'")
        add_column_if_missing("submission_answer", "grading_revision", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("submission_answer", "answer_snapshot", "TEXT")
        add_column_if_missing("submission_answer", "evidence_hash", "VARCHAR(64)")
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_submission_answer_answer_status ON submission_answer (answer_status)"))
        # Legacy rows cannot be promoted to a confident answered/pending state
        # without an old event log.  Mark non-blank payloads explicitly as
        # unknown so mastery may remain auditable while misconception claims
        # stay excluded.
        for answer in SubmissionAnswer.query.filter_by(answer_status="unanswered").all():
            has_selected = bool(answer.selected_answer_ids and answer.selected_answer_ids not in ("", "[]"))
            has_payload = bool(answer.answer_text and answer.answer_text not in ("", "{}", "null"))
            if has_selected or has_payload:
                answer.answer_status = "legacy_unknown"
        db.session.commit()

    if "learning_history" in tables:
        add_column_if_missing("learning_history", "submission_answer_id", "INTEGER")
        add_column_if_missing("learning_history", "curriculum_code", "VARCHAR(80)")
        add_column_if_missing("learning_history", "answer_status", "VARCHAR(20)")
        add_column_if_missing("learning_history", "grading_revision", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("learning_history", "question_content_hash", "VARCHAR(64)")
        add_column_if_missing("learning_history", "evidence_ref", "VARCHAR(160)")
        db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_learning_history_evidence_ref ON learning_history (evidence_ref)"))

    if "student_mastery" in tables:
        add_column_if_missing("student_mastery", "evidence_count", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing("student_mastery", "insufficient_data", "BOOLEAN NOT NULL DEFAULT TRUE")
        add_column_if_missing("student_mastery", "last_evidence_at", "DATETIME")

    if "mastery_snapshot" in tables:
        add_column_if_missing("mastery_snapshot", "profile_revision", "INTEGER NOT NULL DEFAULT 1")
        add_column_if_missing("mastery_snapshot", "input_hash", "VARCHAR(64)")
        add_column_if_missing("mastery_snapshot", "trigger", "VARCHAR(30) DEFAULT 'grading'")

    if "ai_analysis_run" in tables:
        add_column_if_missing("ai_analysis_run", "course_id", "INTEGER")
        add_column_if_missing("ai_analysis_run", "ai_key_group_id", "INTEGER")
        add_column_if_missing("ai_analysis_run", "ai_config_revision", "INTEGER")
        add_column_if_missing("ai_analysis_run", "ai_credential_source", "VARCHAR(30)")
        add_column_if_missing("ai_analysis_run", "schema_version", "VARCHAR(40) DEFAULT 'chapter6-analysis-v1'")
        add_column_if_missing("ai_analysis_run", "review_status", "VARCHAR(20) NOT NULL DEFAULT 'unreviewed'")
        add_column_if_missing("ai_analysis_run", "reviewed_by", "INTEGER")
        add_column_if_missing("ai_analysis_run", "review_note", "TEXT")
        add_column_if_missing("ai_analysis_run", "reviewed_at", "DATETIME")

    if "class_ai_analysis_run" in tables:
        add_column_if_missing("class_ai_analysis_run", "ai_key_group_id", "INTEGER")
        add_column_if_missing("class_ai_analysis_run", "ai_config_revision", "INTEGER")
        add_column_if_missing("class_ai_analysis_run", "ai_credential_source", "VARCHAR(30)")
        add_column_if_missing("class_ai_analysis_run", "retry_after", "DATETIME")
        add_column_if_missing("class_ai_analysis_run", "review_status", "VARCHAR(20) NOT NULL DEFAULT 'unreviewed'")
        add_column_if_missing("class_ai_analysis_run", "reviewed_by", "INTEGER")
        add_column_if_missing("class_ai_analysis_run", "review_note", "TEXT")
        add_column_if_missing("class_ai_analysis_run", "reviewed_at", "DATETIME")

    if "course" in tables:
        add_column_if_missing("course", "ai_key_group_id", "INTEGER")

    # SQLite does not enforce VARCHAR length, while an older PostgreSQL schema
    # did.  The current diagnostic prompt version is longer than VARCHAR(30),
    # so widen it in place without rewriting any audit rows.
    if "ai_analysis_run" in tables and db.engine.dialect.name == "postgresql":
        try:
            db.session.execute(db.text(
                "ALTER TABLE ai_analysis_run ALTER COLUMN prompt_version TYPE VARCHAR(80)"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

    if "student_performance" in tables:
        add_column_if_missing("student_performance", "thong_hieu_accuracy", "FLOAT DEFAULT 0")

    if "enrollment" in tables:
        # Clean up string student_ids stored in the database to use integer IDs
        rows = db.session.execute(db.text("SELECT id, student_id FROM enrollment")).all()
        for r_id, s_id in rows:
            if isinstance(s_id, str) and not str(s_id).isdigit():
                # Look up the user by username or user_code
                user = User.query.filter(
                    (User.role == "student") &
                    ((User.username == s_id.lower()) | (User.user_code == s_id.upper()) | (User.username == s_id) | (User.user_code == s_id))
                ).first()
                if user:
                    db.session.execute(db.text("UPDATE enrollment SET student_id = :uid WHERE id = :eid"), {"uid": user.id, "eid": r_id})
        db.session.commit()

def backfill_adaptive_learning_history():
    """Build adaptive facts and chronological snapshots for submissions created before this feature."""
    submissions = [submission for submission in ExamSubmission.query.filter(
        ExamSubmission.submitted_at.is_not(None)
    ).order_by(ExamSubmission.submitted_at.asc(), ExamSubmission.id.asc()).all()
                  if submission.is_graded or (
                      submission.status in (None, "draft") and submission.exam_type == "practice"
                  )]
    latest_by_student_subject = {}
    changed = False
    for submission in submissions:
        if not submission.exam or not submission.exam.course or not submission.answers:
            continue
        answer_count = len([
            answer for answer in submission.answers
            if answer.question and (
                answer.answer_status not in ("unanswered", "pending_review")
                or (submission.status in (None, "draft") and submission.exam_type == "practice")
            )
        ])
        history_count = LearningHistory.query.filter_by(submission_id=submission.id).count()
        snapshot = MasterySnapshot.query.filter_by(
            student_id=submission.student_id,
            subject=submission.exam.course.subject,
            submission_id=submission.id,
        ).first()
        if history_count != answer_count or not snapshot:
            AdaptiveEngine.record_submission(submission.student_id, submission)
            AdaptiveEngine.recompute_mastery(
                submission.student_id, submission.exam.course.subject, submission.id
            )
            changed = True
        latest_by_student_subject[(submission.student_id, submission.exam.course.subject)] = submission
    if changed:
        db.session.commit()
        for submission in latest_by_student_subject.values():
            AdaptiveEngine.update_performance(submission.student_id, submission)


def disable_removed_roles():
    """Deactivate accounts for roles removed from the product.

    Historical rows remain intact for reporting and foreign-key references, but
    these accounts cannot log in or be promoted to another role implicitly.
    """
    removed = User.query.filter(User.role.in_(["manager", "parent"]), User.is_active.is_(True)).all()
    if not removed:
        return
    for user in removed:
        user.is_active = False
    db.session.commit()


def migrate_legacy_question_types():
    """Convert legacy essay labels to the supported short-answer type."""
    changed = False
    bank_questions = BankQuestion.query.filter(BankQuestion.question_type.in_(["essay", "tu_luan", "tự luận"])).all()
    for question in bank_questions:
        question.question_type = "short_answer"
        changed = True
    exam_questions = ExamQuestion.query.filter(ExamQuestion.question_type.in_(["essay", "tu_luan", "tự luận"])).all()
    for question in exam_questions:
        question.question_type = "short_answer"
        changed = True
    if changed:
        db.session.commit()


def ensure_bank_read_indexes():
    """Add only the two bank-read indexes to existing/new deployments."""
    from models import BankQuestionOption
    names = {'ix_bank_question_bank_id', 'ix_bank_question_option_question_id'}
    for table in (BankQuestion.__table__, BankQuestionOption.__table__):
        for index in table.indexes:
            if index.name in names:
                index.create(bind=db.engine, checkfirst=True)


def initialize_database():
    db.create_all()
    migrate_existing_sqlite_schema()
    ensure_bank_read_indexes()
    disable_removed_roles()
    migrate_legacy_question_types()
    seed_math9_catalog()
    migrate_id6_metadata()
    backfill_adaptive_learning_history()
    seed_sample_data()
