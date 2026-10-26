import datetime as dt
import json
import uuid
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db

# ──────────────────────── MODELS ────────────────────────

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # Verified email from a social provider, if any. Local accounts created
    # before social sign-in keep NULL here; it is never a password substitute.
    email = db.Column(db.String(255), unique=True, nullable=True, index=True)
    fullname = db.Column(db.String(100), nullable=False)
    user_code = db.Column(db.String(20), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    phone = db.Column(db.String(20))
    birth_date = db.Column(db.Date)
    position = db.Column(db.String(100))
    password_hash = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    avatar = db.Column(db.String(100), default="default.jpg")

    courses_taught = db.relationship("Course", back_populates="teacher", foreign_keys="Course.teacher_id")
    enrollments = db.relationship("Enrollment", back_populates="student", foreign_keys="Enrollment.student_id")
    ai_key_groups = db.relationship("TeacherAIKeyGroup", back_populates="owner", foreign_keys="TeacherAIKeyGroup.owner_id")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash or "", password)

    @property
    def is_admin(self):
        return self.role == "admin"

class SocialAccount(db.Model):
    """One external identity linked to one local account.

    The provider's user id is the stable key; the email is the verified
    address returned by the provider at link time.  A second provider
    (Facebook, later) is another row, never a second local account.
    """

    __tablename__ = "social_account"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    provider = db.Column(db.String(30), nullable=False, index=True)
    provider_user_id = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)

    user = db.relationship("User", backref="social_accounts")

    __table_args__ = (
        db.UniqueConstraint("provider", "provider_user_id", name="uq_social_provider_user"),
    )


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(80), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    # An explicit group is optional.  When empty, the course may use its
    # teacher's configured default group; it never searches another teacher.
    ai_key_group_id = db.Column(db.Integer, db.ForeignKey("teacher_ai_key_group.id"), nullable=True, index=True)
    classroom = db.Column(db.String(40))
    # Short code a teacher shares so students can join by code or link.
    # NULL on legacy rows until the teacher first opens the class.
    join_code = db.Column(db.String(12), unique=True, nullable=True, index=True)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)

    teacher = db.relationship("User", back_populates="courses_taught", foreign_keys=[teacher_id])
    ai_key_group = db.relationship("TeacherAIKeyGroup", back_populates="courses", foreign_keys=[ai_key_group_id])
    enrollments = db.relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class TeacherAIKeyGroup(db.Model):
    """A teacher-owned, selectable Gemini credential group.

    The group contains only encrypted key material.  ``config_revision`` is
    incremented whenever a configuration change can affect a report, making
    old completed/fallback reports ineligible for the new setting.
    """

    __tablename__ = "teacher_ai_key_group"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    # Teacher routing is server-owned in Phase 5.  Existing rows may retain a
    # historical value until the reviewed migration runs, but new groups use
    # the one supported model and the gateway enforces it at the boundary.
    model_name = db.Column(db.String(120), nullable=False, default="gemini-3.8-flash")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    config_revision = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    owner = db.relationship("User", back_populates="ai_key_groups", foreign_keys=[owner_id])
    keys = db.relationship(
        "TeacherAIKey", back_populates="group", cascade="all, delete-orphan",
        order_by="TeacherAIKey.sort_order.asc(), TeacherAIKey.id.asc()",
    )
    courses = db.relationship("Course", back_populates="ai_key_group", foreign_keys="Course.ai_key_group_id")

    __table_args__ = (db.UniqueConstraint("owner_id", "name", name="uq_teacher_ai_key_group_owner_name"),)

    def touch_configuration(self):
        self.config_revision = max(1, int(self.config_revision or 0) + 1)


class TeacherAIKey(db.Model):
    """One encrypted Gemini key; plaintext exists only for an outbound call."""

    __tablename__ = "teacher_ai_key"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("teacher_ai_key_group.id"), nullable=False, index=True)
    # Fernet token, never a raw key.  Do not add a plaintext accessor/property.
    encrypted_key = db.Column(db.Text, nullable=False)
    key_fingerprint = db.Column(db.String(64), nullable=False, index=True)
    key_hint = db.Column(db.String(8), nullable=False, default="")
    project_ref = db.Column(db.String(160), nullable=False, default="default")
    label = db.Column(db.String(120), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_paused = db.Column(db.Boolean, nullable=False, default=False, index=True)
    last_tested_at = db.Column(db.DateTime, nullable=True)
    last_test_status = db.Column(db.String(30), nullable=True)
    last_error_code = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    group = db.relationship("TeacherAIKeyGroup", back_populates="keys", foreign_keys=[group_id])

    __table_args__ = (db.UniqueConstraint("group_id", "key_fingerprint", name="uq_teacher_ai_key_group_fingerprint"),)

    @property
    def masked_key(self):
        return "••••" + (self.key_hint or "")


class AIProjectCooldown(db.Model):
    """Persistent quota cooldown shared by all keys tagged to one project."""

    __tablename__ = "ai_project_cooldown"

    id = db.Column(db.Integer, primary_key=True)
    scope_key = db.Column(db.String(64), nullable=False, unique=True, index=True)
    provider = db.Column(db.String(40), nullable=False, default="gemini")
    cooldown_until = db.Column(db.DateTime, nullable=False, index=True)
    reason_code = db.Column(db.String(80), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    status = db.Column(db.String(20), default="active")
    enrolled_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    student = db.relationship("User", back_populates="enrollments", foreign_keys=[student_id])
    course = db.relationship("Course", back_populates="enrollments")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    __table_args__ = (db.UniqueConstraint("student_id", "course_id", name="uq_student_course"),)


# ──────────────────────── QUESTION BANK MODELS ────────────────────────

class QuestionBank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.String(80), nullable=False)
    grade = db.Column(db.String(40))
    topic = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # Server-owned access scope.  NULL is retained for legacy rows until the
    # reviewed backfill; authorization treats it conservatively (teacher-owned
    # legacy rows remain private, admin-created legacy rows are not promoted to
    # shared for teachers).
    visibility = db.Column(db.String(20), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    creator = db.relationship("User", foreign_keys=[created_by])
    questions = db.relationship("BankQuestion", back_populates="bank", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def question_count(self):
        return len(self.questions)

    def stats_by_difficulty(self):
        counts = {"nhan_biet": 0, "thong_hieu": 0, "van_dung": 0, "van_dung_cao": 0}
        for q in self.questions:
            if q.difficulty_level in counts:
                counts[q.difficulty_level] += 1
        return counts

    def stats_by_type(self):
        from services.question_policy import TYPE_CODES
        counts = {kind: 0 for kind in TYPE_CODES}
        for q in self.questions:
            qtype = "true_false" if q.question_type == "truefalse" else q.question_type
            if qtype in counts:
                counts[qtype] += 1
        return counts


class BankQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bank_id = db.Column(db.Integer, db.ForeignKey("question_bank.id"), nullable=False, index=True)
    question_text = db.Column(db.Text, nullable=False)
    context = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    question_type = db.Column(db.String(30), nullable=False, default="single")  # single, multiple_choice, true_false, short_answer, essay
    difficulty_level = db.Column(db.String(20), nullable=False, default="nhan_biet")  # nhan_biet, thong_hieu, van_dung, van_dung_cao
    points = db.Column(db.Float, default=1.0)
    explanation = db.Column(db.Text)
    subject = db.Column(db.String(80))
    grade = db.Column(db.String(40))
    topic = db.Column(db.String(200))
    source_id = db.Column(db.String(50), nullable=True)
    chapter = db.Column(db.String(20), nullable=True)
    section = db.Column(db.String(20), nullable=True)
    question_category = db.Column(db.String(20), nullable=True)
    confidence_scores = db.Column(db.Text, nullable=True)  # JSON string
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # Question-level access is intentionally independent from ``created_by``.
    # A shared administrator bank may later contain teacher-owned private
    # supplements, while the account that imported/created the row can still
    # be an administrator.  These columns remain nullable for legacy rows;
    # authorization handles NULL conservatively and does not backfill it at
    # startup.
    scope = db.Column(db.String(20), nullable=True, index=True)
    private_owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    bank = db.relationship("QuestionBank", back_populates="questions")
    creator = db.relationship("User", foreign_keys=[created_by])
    private_owner = db.relationship("User", foreign_keys=[private_owner_id])
    options = db.relationship("BankQuestionOption", back_populates="question", cascade="all, delete-orphan", order_by="BankQuestionOption.order_index")
    curriculum_node_id = db.Column(db.Integer, db.ForeignKey("curriculum_node.id"), nullable=True, index=True)
    curriculum_node = db.relationship("CurriculumNode")
    id6_scope = db.Column(db.String(80), nullable=True)
    id6_sequence = db.Column(db.Integer, nullable=True)
    classification_status = db.Column(db.String(30), nullable=True)
    classification_data = db.Column(db.Text, nullable=True)
    learning_metadata = db.Column(db.Text, nullable=True)
    difficulty_band = db.Column(db.String(20), nullable=True)
    adaptive_priority = db.Column(db.Integer, nullable=False, default=0)
    adaptive_excluded = db.Column(db.Boolean, nullable=False, default=False)
    # Additive provenance fields.  Existing imports may not have these values;
    # ``unknown`` is intentionally preserved instead of inventing history.
    content_revision = db.Column(db.Integer, nullable=False, default=1)
    content_hash = db.Column(db.String(64), nullable=True, index=True)
    catalog_version = db.Column(db.String(30), nullable=True)

    __table_args__ = (
        db.Index("uq_bank_question_id6_sequence", "id6_scope", "id6_sequence", unique=True),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        opts = [opt.to_dict() for opt in self.options]
        stmts = []
        if self.question_type in ("true_false", "truefalse"):
            for opt in self.options:
                text = opt.option_text
                stmt_id = text[:1].lower() if text and len(text) > 1 and text[1] in (")", ".", ":") else ""
                stmt_body = text[2:].strip() if stmt_id else text
                stmts.append({
                    "id": stmt_id,
                    "text": stmt_body,
                    "full_text": text,
                    "answer": opt.is_correct
                })
        return {
            "id": self.id,
            "bank_id": self.bank_id,
            "question_text": self.question_text,
            "context": self.context or "",
            "image_url": self.image_url or "",
            "question_type": "true_false" if self.question_type == "truefalse" else self.question_type,
            "difficulty_level": self.difficulty_level,
            "grade": self.grade or "",
            "topic": self.topic or "",
            "source_id": self.source_id or "",
            "curriculum_node_id": self.curriculum_node_id,
            "id6_sequence": self.id6_sequence,
            "id6_scope": self.id6_scope,
            "catalog_version": self.catalog_version,
            "chapter": self.chapter or "",
            "section": self.section or "",
            "question_category": self.question_category or "",
            "points": self.points,
            "explanation": self.explanation or "",
            "classification_status": self.classification_status,
            "classification": json.loads(self.classification_data) if self.classification_data else None,
            "learning_metadata": json.loads(self.learning_metadata) if self.learning_metadata else {},
            "difficulty_band": self.difficulty_band,
            "adaptive_priority": self.adaptive_priority,
            "adaptive_excluded": self.adaptive_excluded,
            "options": opts,
            "statements": stmts
        }


class BankQuestionOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("bank_question.id"), nullable=False, index=True)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order_index = db.Column(db.Integer, default=0)

    question = db.relationship("BankQuestion", back_populates="options")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "option_text": self.option_text,
            "is_correct": self.is_correct,
            "order_index": self.order_index
        }


# ──────────────────────── CURRICULUM / ID6 CLASSIFICATION ────────────────────────

class CurriculumNode(db.Model):
    """Canonical curriculum skill, independent from all file-import formats."""

    id = db.Column(db.Integer, primary_key=True)
    grade = db.Column(db.String(10), nullable=False, index=True)
    chapter_code = db.Column(db.String(10), nullable=False, index=True)
    chapter_name = db.Column(db.String(200), nullable=False)
    lesson_code = db.Column(db.String(20), nullable=False)
    lesson_name = db.Column(db.String(250), nullable=False)
    category_code = db.Column(db.String(20), nullable=False)
    category_name = db.Column(db.String(250), nullable=False)
    topic_code = db.Column(db.String(40), nullable=True)
    topic_name = db.Column(db.String(100), nullable=True)
    canonical_code = db.Column(db.String(80), nullable=False, unique=True, index=True)
    is_advanced = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    catalog_version = db.Column(db.String(30), default="math9-v1", nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])

    @staticmethod
    def make_canonical_code(grade, chapter_code, lesson_code, category_code):
        grade = str(grade).strip().upper().removeprefix("LỚP ")
        chapter = str(chapter_code).strip().upper()
        lesson = str(lesson_code).strip()
        # ``i`` is the literal combined lesson marker for the corrected
        # Chapter 8 scope.  Do not normalize it to ``I``: the lower-case
        # character is part of the canonical source-ID grammar.
        lesson = "i" if lesson.lower() == "i" else lesson.upper()
        category = str(category_code).strip().upper()
        return f"{grade}C{chapter}-{lesson}-{category}"

    def __init__(self, **kwargs):
        if not kwargs.get("canonical_code"):
            kwargs["canonical_code"] = self.make_canonical_code(
                kwargs.get("grade", ""),
                kwargs.get("chapter_code", ""),
                kwargs.get("lesson_code", ""),
                kwargs.get("category_code", ""),
            )
        super().__init__(**kwargs)


class CurriculumCatalogMigration(db.Model):
    """Transactional catalog snapshots; historical questions are never rewritten."""
    migration_key = db.Column(db.String(80), primary_key=True)
    catalog_version = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    applied_at = db.Column(db.DateTime, nullable=False)
    rolled_back_at = db.Column(db.DateTime, nullable=True)
    snapshot_json = db.Column(db.Text, nullable=False)
    after_fingerprint = db.Column(db.String(64), nullable=False)


class ID6Counter(db.Model):
    """Atomic high-water mark shared by all types/levels in one exercise category."""
    scope = db.Column(db.String(80), primary_key=True)
    last_sequence = db.Column(db.Integer, nullable=False)





# ──────────────────────── IMPORT SESSION ────────────────────────

class ImportSession(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey("question_bank.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # tex, latex (legacy values remain readable)
    file_path = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="uploaded")  # uploaded, processing, preview, confirmed, cancelled, failed
    parsed_data = db.Column(db.Text)  # JSON: list of normalized questions
    duplicate_decisions = db.Column(db.Text, nullable=True)
    duplicate_report = db.Column(db.Text, nullable=True)
    result_data = db.Column(db.Text, nullable=True)
    scope_data = db.Column(db.Text, nullable=True)  # Validated file curriculum scope
    valid_count = db.Column(db.Integer, default=0)
    warning_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    total_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    user = db.relationship("User", foreign_keys=[user_id])
    bank = db.relationship("QuestionBank", foreign_keys=[bank_id])

    def __init__(self, **kwargs):
        if "expires_at" not in kwargs:
            kwargs["expires_at"] = dt.datetime.utcnow() + dt.timedelta(hours=2)
        super().__init__(**kwargs)

    def get_duplicate_decisions(self):
        return json.loads(self.duplicate_decisions or '{}')

    def get_duplicate_report(self):
        return json.loads(self.duplicate_report or '{}')

    def get_results(self):
        return json.loads(self.result_data or '{}')

    def get_scope(self):
        try:
            value = json.loads(self.scope_data or "null")
            return value if isinstance(value, dict) else None
        except (ValueError, TypeError):
            return None

    def get_parsed_questions(self):
        try:
            return json.loads(self.parsed_data or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_parsed_questions(self, questions):
        self.parsed_data = json.dumps(questions, ensure_ascii=False)


# ──────────────────────── EXAM MODELS ────────────────────────

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    is_active = db.Column(db.Boolean, default=True)
    shuffle_questions = db.Column(db.Boolean, default=True)
    shuffle_answers = db.Column(db.Boolean, default=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    # New fields for question bank integration
    question_bank_id = db.Column(db.Integer, db.ForeignKey("question_bank.id"), nullable=True)
    exam_type = db.Column(db.String(20), default="exam")  # exam, practice
    exam_category = db.Column(db.String(50), default="Kiểm tra thường kỳ")  # Kiểm tra thường kỳ, Kiểm tra giữa kỳ, Kiểm tra cuối kỳ
    total_questions = db.Column(db.Integer, nullable=True)
    difficulty_config = db.Column(db.Text, nullable=True)  # JSON percentages for N/H/V/C
    question_type_config = db.Column(db.Text, nullable=True)  # JSON: {"single":10,"truefalse":5,"short_answer":5}
    adaptive_metadata = db.Column(db.Text, nullable=True)  # profile, score components and human-readable reasons
    # summative, initial_diagnostic, practice.  Legacy rows are treated as
    # summative/practice by the route layer when this field is NULL.
    assessment_purpose = db.Column(db.String(30), nullable=True, default="summative", index=True)
    diagnostic_coverage = db.Column(db.Text, nullable=True)
    # Immutable source/audience manifest for newly generated papers.  The
    # manifest records the class teacher and every bank/question source at
    # creation time; old exams remain readable with a legacy compatibility
    # path when this field is NULL.
    source_manifest = db.Column(db.Text, nullable=True)

    course = db.relationship("Course")
    creator = db.relationship("User", foreign_keys=[created_by])
    question_bank = db.relationship("QuestionBank", foreign_keys=[question_bank_id])
    questions = db.relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.order_index")
    submissions = db.relationship("ExamSubmission", back_populates="exam", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def total_points(self):
        return sum(q.points for q in self.questions)

    @property
    def question_count(self):
        return len(self.questions)

    @property
    def status_label(self):
        now = dt.datetime.now()
        if not self.is_active:
            return "closed"
        if self.start_time and now < self.start_time:
            return "upcoming"
        if self.end_time and now > self.end_time:
            return "closed"
        return "open"

    def get_difficulty_config(self):
        try:
            return json.loads(self.difficulty_config or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_question_type_config(self):
        try:
            return json.loads(self.question_type_config or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_adaptive_metadata(self):
        try:
            value = json.loads(self.adaptive_metadata or "{}")
            return value if isinstance(value, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_diagnostic_coverage(self):
        try:
            value = json.loads(self.diagnostic_coverage or "{}")
            return value if isinstance(value, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_source_manifest(self):
        """Return the immutable generation-source manifest, if present."""
        try:
            value = json.loads(self.source_manifest or "{}")
            return value if isinstance(value, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}


class ExamQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    context = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    question_type = db.Column(db.String(30), nullable=False, default="single")  # single, multiple_choice, true_false, short_answer, essay
    points = db.Column(db.Float, default=1.0)
    order_index = db.Column(db.Integer, default=0)
    # New fields
    bank_question_id = db.Column(db.Integer, db.ForeignKey("bank_question.id"), nullable=True)
    difficulty_level = db.Column(db.String(20), nullable=True)  # nhan_biet, thong_hieu, van_dung, van_dung_cao
    explanation = db.Column(db.Text, nullable=True)
    # Frozen source metadata copied when a bank question enters an exam.  The
    # rendered text and answer key are already snapshotted by ExamAnswer.
    source_id6 = db.Column(db.String(50), nullable=True)
    source_content_revision = db.Column(db.Integer, nullable=True)
    source_content_hash = db.Column(db.String(64), nullable=True, index=True)
    curriculum_code = db.Column(db.String(80), nullable=True, index=True)
    curriculum_catalog_version = db.Column(db.String(30), nullable=True)
    topic_snapshot = db.Column(db.String(200), nullable=True)
    learning_metadata = db.Column(db.Text, nullable=True)

    exam = db.relationship("Exam", back_populates="questions")
    answers = db.relationship("ExamAnswer", back_populates="question", cascade="all, delete-orphan", order_by="ExamAnswer.id")
    bank_question = db.relationship("BankQuestion", foreign_keys=[bank_question_id])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ExamAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("exam_question.id"), nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

    question = db.relationship("ExamQuestion", back_populates="answers")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class ExamSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exam.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    submitted_at = db.Column(db.DateTime, nullable=True)
    total_score = db.Column(db.Float, default=0)
    max_score = db.Column(db.Float, default=0)
    is_graded = db.Column(db.Boolean, default=False)
    # New fields
    exam_type = db.Column(db.String(20), default="exam")  # exam, practice
    time_spent_seconds = db.Column(db.Integer, nullable=True)
    correct_count = db.Column(db.Integer, default=0)
    wrong_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    grading_revision = db.Column(db.Integer, nullable=False, default=0)
    finalized_at = db.Column(db.DateTime, nullable=True)
    idempotency_key = db.Column(db.String(100), nullable=True, index=True)

    exam = db.relationship("Exam", back_populates="submissions")
    student = db.relationship("User", foreign_keys=[student_id])
    answers = db.relationship("SubmissionAnswer", back_populates="submission", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def percentage(self):
        if self.max_score == 0:
            return 0
        return round(self.total_score / self.max_score * 100, 1)

    @property
    def score_on_ten(self):
        """Display legacy and current results on one scale without rewriting evidence."""
        from decimal import Decimal, ROUND_HALF_UP
        if not self.max_score:
            return None
        value = Decimal(str(self.total_score or 0)) * 10 / Decimal(str(self.max_score))
        return float(min(Decimal(10), max(Decimal(0), value)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))




class SubmissionAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("exam_submission.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("exam_question.id"), nullable=False)
    selected_answer_ids = db.Column(db.Text, default="[]")  # JSON array of answer IDs
    is_correct = db.Column(db.Boolean, default=False)
    points_earned = db.Column(db.Float, default=0)
    # New fields
    answer_text = db.Column(db.Text, nullable=True)  # For short_answer type
    time_spent_seconds = db.Column(db.Integer, nullable=True)
    # answered/unanswered/pending_review/graded.  This is deliberately
    # separate from ``is_correct`` so a blank answer is never treated as an
    # observed misconception.
    answer_status = db.Column(db.String(20), nullable=False, default="unanswered", index=True)
    grading_revision = db.Column(db.Integer, nullable=False, default=0)
    answer_snapshot = db.Column(db.Text, nullable=True)
    evidence_hash = db.Column(db.String(64), nullable=True, index=True)

    submission = db.relationship("ExamSubmission", back_populates="answers")
    question = db.relationship("ExamQuestion")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_selected_ids(self):
        try:
            return json.loads(self.selected_answer_ids or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def get_answer_payload(self):
        try:
            val = json.loads(self.answer_text or "{}")
            if isinstance(val, dict):
                return val
            return {"text": str(val)}
        except (json.JSONDecodeError, TypeError):
            return {"text": self.answer_text or ""}

    @property
    def is_answered(self):
        """Whether the learner supplied a non-blank answer payload."""
        if self.answer_status in ("answered", "pending_review", "graded"):
            return True
        payload = self.get_answer_payload()
        if any(value is not None and str(value).strip() for value in payload.values()):
            return True
        return bool(self.get_selected_ids())


# ──────────────────────── STUDENT PERFORMANCE ────────────────────────

class StudentPerformance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(80), nullable=False)
    topic = db.Column(db.String(200), nullable=True)
    total_attempts = db.Column(db.Integer, default=0)
    avg_score = db.Column(db.Float, default=0)
    best_score = db.Column(db.Float, default=0)
    worst_score = db.Column(db.Float, default=10)
    latest_score = db.Column(db.Float, default=0)
    score_trend = db.Column(db.String(20), default="stable")  # improving, declining, stable
    accuracy_rate = db.Column(db.Float, default=0)
    nhan_biet_accuracy = db.Column(db.Float, default=0)
    thong_hieu_accuracy = db.Column(db.Float, default=0)
    van_dung_accuracy = db.Column(db.Float, default=0)
    van_dung_cao_accuracy = db.Column(db.Float, default=0)
    single_accuracy = db.Column(db.Float, default=0)
    truefalse_accuracy = db.Column(db.Float, default=0)
    short_answer_accuracy = db.Column(db.Float, default=0)
    weak_topics = db.Column(db.Text, default="[]")  # JSON array
    strong_topics = db.Column(db.Text, default="[]")  # JSON array
    adaptive_difficulty = db.Column(db.String(20), default="standard")  # reinforce, standard, challenge
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    student = db.relationship("User", foreign_keys=[student_id])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_weak_topics(self):
        try:
            return json.loads(self.weak_topics or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def get_strong_topics(self):
        try:
            return json.loads(self.strong_topics or "[]")
        except (json.JSONDecodeError, TypeError):
            return []


class LearningHistory(db.Model):
    """Immutable question-attempt facts, except regrading the same answer."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('exam_submission.id'), nullable=False, index=True)
    exam_question_id = db.Column(db.Integer, db.ForeignKey('exam_question.id'), nullable=False)
    bank_question_id = db.Column(db.Integer, db.ForeignKey('bank_question.id'), nullable=True, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    curriculum_code = db.Column(db.String(80), nullable=True, index=True)
    topic = db.Column(db.String(200), nullable=False, default='Chưa xác định', index=True)
    difficulty_band = db.Column(db.String(20), nullable=False)
    cognitive_level = db.Column(db.String(20), nullable=False, index=True)
    is_correct = db.Column(db.Boolean, nullable=False)
    normalized_score = db.Column(db.Float, nullable=False)
    points_earned = db.Column(db.Float, nullable=False, default=0)
    max_points = db.Column(db.Float, nullable=False, default=1)
    weight = db.Column(db.Float, nullable=False, default=1)
    time_spent_seconds = db.Column(db.Integer, nullable=False, default=0)
    occurred_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, index=True)
    submission_answer_id = db.Column(db.Integer, db.ForeignKey('submission_answer.id'), nullable=True, index=True)
    answer_status = db.Column(db.String(20), nullable=True, index=True)
    grading_revision = db.Column(db.Integer, nullable=False, default=0)
    question_content_hash = db.Column(db.String(64), nullable=True)
    evidence_ref = db.Column(db.String(160), nullable=True, index=True)
    __table_args__ = (db.UniqueConstraint('submission_id', 'exam_question_id', name='uq_learning_answer'),)


class StudentMastery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    dimension = db.Column(db.String(30), nullable=False)  # topic, cognitive, topic_cognitive
    dimension_key = db.Column(db.String(260), nullable=False)
    mastery = db.Column(db.Float, nullable=False)
    interpretation = db.Column(db.String(20), nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    weighted_score = db.Column(db.Float, nullable=False)
    total_weight = db.Column(db.Float, nullable=False)
    evidence_count = db.Column(db.Integer, nullable=False, default=0)
    insufficient_data = db.Column(db.Boolean, nullable=False, default=True)
    last_evidence_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'subject', 'dimension', 'dimension_key', name='uq_student_mastery_dimension'),)


class MasterySnapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('exam_submission.id'), nullable=True)
    profile_data = db.Column(db.Text, nullable=False)
    profile_revision = db.Column(db.Integer, nullable=False, default=1)
    input_hash = db.Column(db.String(64), nullable=True, index=True)
    trigger = db.Column(db.String(30), nullable=True, default="grading")
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, index=True)
    __table_args__ = (db.UniqueConstraint('student_id', 'subject', 'submission_id', name='uq_mastery_snapshot_submission'),)


class AIAnalysisRun(db.Model):
    """Auditable Chapter 6 AI diagnosis request, response, cache and fallback."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    # Nullable keeps historical rows readable. New teacher-initiated runs
    # record their course/configuration to prevent cross-course cache reuse.
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=True, index=True)
    ai_key_group_id = db.Column(db.Integer, db.ForeignKey('teacher_ai_key_group.id'), nullable=True, index=True)
    ai_config_revision = db.Column(db.Integer, nullable=True)
    ai_credential_source = db.Column(db.String(30), nullable=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    chapter_code = db.Column(db.String(10), nullable=False, default='8', index=True)
    input_hash = db.Column(db.String(64), nullable=False, index=True)
    provider = db.Column(db.String(80), nullable=False)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(30), nullable=False)  # completed, fallback, failed
    request_data = db.Column(db.Text, nullable=False)
    response_data = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    schema_version = db.Column(db.String(40), nullable=True, default="chapter6-analysis-v1")
    review_status = db.Column(db.String(20), nullable=False, default="unreviewed", index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    def get_request_data(self):
        try:
            value = json.loads(self.request_data or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def get_response_data(self):
        try:
            value = json.loads(self.response_data or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}


class ClassAIAnalysisRun(db.Model):
    """Versioned, auditable class report for the retained Lesson 4 scope.

    A row is a complete input/output snapshot.  ``active_key`` is populated
    only while a request is being generated, which gives concurrent HTTP
    requests a database-backed idempotency guard without replacing older
    snapshots when a teacher explicitly refreshes the report.
    """

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    ai_key_group_id = db.Column(db.Integer, db.ForeignKey('teacher_ai_key_group.id'), nullable=True, index=True)
    ai_config_revision = db.Column(db.Integer, nullable=True)
    ai_credential_source = db.Column(db.String(30), nullable=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    scope_code = db.Column(db.String(30), nullable=False, default='9C8-i', index=True)
    input_hash = db.Column(db.String(64), nullable=False, index=True)
    provider = db.Column(db.String(80), nullable=False)
    model_name = db.Column(db.String(120), nullable=True)
    prompt_version = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='processing', index=True)
    analysis_source = db.Column(db.String(50), nullable=False, default='observed_data_fallback')
    request_data = db.Column(db.Text, nullable=False, default='{}')
    response_data = db.Column(db.Text, nullable=False, default='{}')
    source_cutoff = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    roster_count = db.Column(db.Integer, nullable=False, default=0)
    event_count = db.Column(db.Integer, nullable=False, default=0)
    omitted_event_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
    schema_version = db.Column(db.String(50), nullable=False, default='class-lesson4-report-v1')
    active_key = db.Column(db.String(130), nullable=True, unique=True, index=True)
    # Review is an annotation on the report snapshot.  It is deliberately
    # separate from learning facts/mastery and never feeds question selection.
    review_status = db.Column(db.String(20), nullable=False, default="unreviewed", index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    # Fallback reports are cacheable only briefly.  This avoids a tight retry
    # loop while allowing a healthy provider/configuration to recover without
    # teachers having to force-refresh unchanged evidence.
    retry_after = db.Column(db.DateTime, nullable=True, index=True)

    course = db.relationship('Course', foreign_keys=[course_id])
    requester = db.relationship('User', foreign_keys=[requested_by])

    def get_request_data(self):
        try:
            value = json.loads(self.request_data or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def get_response_data(self):
        try:
            value = json.loads(self.response_data or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}


# Keep the shorter name available to integrations that describe this artifact
# as a class lesson report rather than an AI run.
ClassLesson4Report = ClassAIAnalysisRun


class DiagnosticAssignment(db.Model):
    """Cohort assignment for a frozen common initial diagnostic exam."""

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    common_item_hash = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="assigned", index=True)
    assigned_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    __table_args__ = (db.UniqueConstraint('exam_id', 'student_id', name='uq_diagnostic_exam_student'),)


class PracticeSession(db.Model):
    """Persisted learner decision loop for fixed Lesson 4 practice papers."""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    scope_code = db.Column(db.String(30), nullable=False, default='9C8-i', index=True)
    status = db.Column(db.String(30), nullable=False, default='active', index=True)
    bank_ids = db.Column(db.Text, nullable=False, default='[]')
    last_exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=True)
    last_submission_id = db.Column(db.Integer, db.ForeignKey('exam_submission.id'), nullable=True)
    started_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)

    def get_bank_ids(self):
        try:
            values = json.loads(self.bank_ids or '[]')
            return [int(value) for value in values] if isinstance(values, list) else []
        except (TypeError, ValueError, json.JSONDecodeError):
            return []


class ErrorObservation(db.Model):
    """A conservative, reviewable observation tied to one wrong answer."""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    submission_id = db.Column(db.Integer, db.ForeignKey('exam_submission.id'), nullable=False, index=True)
    submission_answer_id = db.Column(db.Integer, db.ForeignKey('submission_answer.id'), nullable=False, index=True)
    exam_question_id = db.Column(db.Integer, db.ForeignKey('exam_question.id'), nullable=False)
    bank_question_id = db.Column(db.Integer, db.ForeignKey('bank_question.id'), nullable=True, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    curriculum_code = db.Column(db.String(80), nullable=True, index=True)
    topic = db.Column(db.String(200), nullable=True)
    cognitive_level = db.Column(db.String(20), nullable=True)
    error_code = db.Column(db.String(60), nullable=False)
    error_label = db.Column(db.String(160), nullable=False)
    observed_claim = db.Column(db.Text, nullable=False)
    evidence_ref = db.Column(db.String(160), nullable=False, index=True)
    confidence = db.Column(db.Float, nullable=False, default=0.5)
    status = db.Column(db.String(20), nullable=False, default="observed", index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    teacher_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('submission_answer_id', 'error_code', name='uq_error_observation_answer_code'),)

    answer = db.relationship("SubmissionAnswer", foreign_keys=[submission_answer_id])
    question = db.relationship("ExamQuestion", foreign_keys=[exam_question_id])


class StudentErrorProfile(db.Model):
    """Aggregate counts for observed errors; never a claim about future errors."""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    curriculum_code = db.Column(db.String(80), nullable=True, index=True)
    error_code = db.Column(db.String(60), nullable=False)
    evidence_count = db.Column(db.Integer, nullable=False, default=0)
    confidence = db.Column(db.Float, nullable=False, default=0.5)
    status = db.Column(db.String(20), nullable=False, default="observed")
    first_observed_at = db.Column(db.DateTime, nullable=True)
    last_observed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'subject', 'curriculum_code', 'error_code', name='uq_student_error_profile'),)


class TeacherLearningReport(db.Model):
    """In-app, auditable report artifact with teacher review/correction state."""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    report_type = db.Column(db.String(40), nullable=False, default="learning_profile")
    source_revision = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="generated", index=True)
    payload = db.Column(db.Text, nullable=False)
    correction_payload = db.Column(db.Text, nullable=True)
    generated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    review_note = db.Column(db.Text, nullable=True)
    generated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('student_id', 'subject', 'report_type', 'source_revision', name='uq_teacher_report_revision'),)

    def get_payload(self):
        try:
            value = json.loads(self.payload or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def get_correction_payload(self):
        try:
            value = json.loads(self.correction_payload or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}


# ──────────────────────── FORMULA ASSETS ────────────────────────

class FormulaAsset(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mathml = db.Column(db.Text, nullable=True)
    latex = db.Column(db.Text, nullable=True)
    # Original non-MathJax LaTeX block and its sanitized preamble.  Keeping
    # these fields makes failed TikZ/table renders retryable without requiring
    # the teacher to upload the whole question bank again.
    source_text = db.Column(db.Text, nullable=True)
    source_preamble = db.Column(db.Text, nullable=True)
    # Preserve source labels for auditing existing formula records.
    source_format = db.Column(db.String(20), nullable=True)
    converter_name = db.Column(db.String(100), nullable=True)
    converter_version = db.Column(db.String(50), nullable=True)
    content_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)  # SHA-256
    parse_confidence = db.Column(db.Float, default=1.0)
    conversion_status = db.Column(db.String(20), default="pending")  # pending, converted, fallback_svg, failed
    verification_status = db.Column(db.String(20), default="needs_review")  # verified, needs_review, failed
    svg_cache_key = db.Column(db.String(100), nullable=True)  # filesystem/object storage key, no SVG binary in DB
    render_method = db.Column(db.String(40), nullable=True)  # remote_tex, local_tex, approximate_svg
    render_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_api_dict(self):
        """Return formula metadata suitable for API responses."""
        from services.formula_display import display_asset
        return display_asset({
            "id": self.id,
            "mathml": self.mathml,
            "latex": self.latex,
            "source_text": self.source_text,
            "source_preamble": self.source_preamble,
            "source_format": self.source_format,
            "conversion_status": self.conversion_status,
            "verification_status": self.verification_status,
            "svg_cache_key": self.svg_cache_key,
            "render_method": self.render_method,
            "render_error": self.render_error,
        })
