"""Rule-based, auditable adaptive-learning engine."""

import datetime as dt
import json
from collections import Counter, defaultdict

from database import db
from models import (
    BankQuestion,
    ExamSubmission,
    LearningHistory,
    MasterySnapshot,
    StudentErrorProfile,
    StudentMastery,
    StudentPerformance,
)
from services.personalization_evidence import (
    answer_status,
    content_hash,
    evidence_ref,
    is_finalized,
    is_legacy_unknown_answer,
    rebuild_error_observations,
)
from services.question_policy import bank_question_ready

COGNITIVE_LEVELS = ("nhan_biet", "thong_hieu", "van_dung", "van_dung_cao")
COGNITIVE_LABELS = {
    "nhan_biet": "Nhận biết", "thong_hieu": "Thông hiểu",
    "van_dung": "Vận dụng", "van_dung_cao": "Vận dụng cao",
}


class AdaptiveEngine:
    COLD_START_MIN_ANSWERS = 20
    MASTERY_THRESHOLDS = {"weak": .40, "middle": .60, "good": .80}
    SCORE_WEIGHTS = {"weakness": .40, "difficulty": .25, "cognitive": .20, "variety": .10, "teacher": .05}
    REVIEW_MIX = {"weak": .60, "middle": .25, "strong": .15}
    COGNITIVE_WEIGHT = {"nhan_biet": 1.0, "thong_hieu": 1.15, "van_dung": 1.4, "van_dung_cao": 1.7}
    DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.15, "hard": 1.4, "challenge": 1.7}

    @staticmethod
    def interpretation(value):
        value = max(0., min(1., float(value or 0)))
        if value < AdaptiveEngine.MASTERY_THRESHOLDS["weak"]:
            return "Yếu"
        if value < AdaptiveEngine.MASTERY_THRESHOLDS["middle"]:
            return "Trung bình"
        if value < AdaptiveEngine.MASTERY_THRESHOLDS["good"]:
            return "Khá"
        return "Tốt"

    @staticmethod
    def _difficulty_band(question):
        bank_question = question.bank_question
        if bank_question and bank_question.difficulty_band in ("easy", "medium", "hard", "challenge"):
            return bank_question.difficulty_band
        return {"nhan_biet": "easy", "thong_hieu": "medium", "van_dung": "hard", "van_dung_cao": "challenge"}.get(
            question.difficulty_level, "medium"
        )

    @staticmethod
    def _question_topic(question):
        bank_question = question.bank_question
        if not bank_question:
            return "Chưa xác định"
        if bank_question.topic:
            return bank_question.topic.strip()
        node = bank_question.curriculum_node
        return ((node.topic_name or node.category_name) if node else "Chưa xác định").strip()

    @staticmethod
    def _classification_reliability(bank_question):
        if not bank_question:
            return .80
        if bank_question.classification_status == "teacher_confirmed":
            return 1.
        try:
            data = json.loads(bank_question.classification_data or "{}")
            confidence = float(data.get("confidence", data.get("overall_confidence", .8)))
            confidence = confidence / 100 if confidence > 1 else confidence
            return max(.5, min(1., confidence))
        except (TypeError, ValueError, json.JSONDecodeError):
            return .80

    @classmethod
    def _attempt_weight(cls, question):
        cognitive = question.difficulty_level or "nhan_biet"
        return round(
            cls.COGNITIVE_WEIGHT.get(cognitive, 1.)
            * cls.DIFFICULTY_WEIGHT.get(cls._difficulty_band(question), 1.)
            * cls._classification_reliability(question.bank_question), 4
        )

    @classmethod
    def record_submission(cls, student_id, submission):
        """Store one fact per answer; a later regrade updates that same fact."""
        if not submission or not submission.exam or not submission.exam.course or not is_finalized(submission) or submission.exam.assessment_purpose == "standalone":
            return []
        answers = [
            answer for answer in submission.answers
            if answer.question and (
                answer_status(answer) not in ("unanswered", "pending_review")
                or is_legacy_unknown_answer(submission, answer)
            )
        ]
        fallback_time = int((submission.time_spent_seconds or 0) / len(answers)) if answers else 0
        rows = []
        for answer in answers:
            question = answer.question
            max_points = max(float(question.points or 0), .0001)
            topic = cls._question_topic(question)
            difficulty_band = cls._difficulty_band(question)
            cognitive_level = question.difficulty_level or "nhan_biet"
            normalized_score = round(max(0., min(1., float(answer.points_earned or 0) / max_points)), 6)
            weight = cls._attempt_weight(question)
            row = LearningHistory.query.filter_by(
                submission_id=submission.id, exam_question_id=question.id
            ).first()
            if not row:
                row = LearningHistory(
                    student_id=student_id, submission_id=submission.id, exam_question_id=question.id,
                    subject=submission.exam.course.subject, topic=topic, difficulty_band=difficulty_band,
                    cognitive_level=cognitive_level, is_correct=bool(answer.is_correct),
                    normalized_score=normalized_score,
                    curriculum_code=question.curriculum_code,
                )
                db.session.add(row)
            row.bank_question_id = question.bank_question_id
            row.subject = submission.exam.course.subject
            row.curriculum_code = question.curriculum_code
            row.topic = topic
            row.difficulty_band = difficulty_band
            row.cognitive_level = cognitive_level
            row.is_correct = bool(answer.is_correct)
            row.normalized_score = normalized_score
            row.points_earned = float(answer.points_earned or 0)
            row.max_points = max_points
            row.weight = weight
            row.time_spent_seconds = max(0, int(answer.time_spent_seconds or fallback_time))
            row.occurred_at = submission.submitted_at or dt.datetime.utcnow()
            row.submission_answer_id = answer.id
            row.answer_status = "legacy_unknown" if is_legacy_unknown_answer(submission, answer) else answer_status(answer)
            row.grading_revision = int(submission.grading_revision or 0)
            row.question_content_hash = question.source_content_hash
            row.evidence_ref = evidence_ref(submission.id, answer.id, submission.grading_revision or 0)
            rows.append(row)
        db.session.flush()
        return rows

    @classmethod
    def _aggregate(cls, rows, key_getter):
        buckets = defaultdict(lambda: {"weighted_score": 0., "total_weight": 0., "sample_count": 0})
        for row in rows:
            key = key_getter(row)
            weight = max(float(row.weight or 0), .0001)
            buckets[key]["weighted_score"] += weight * max(0., min(1., float(row.normalized_score or 0)))
            buckets[key]["total_weight"] += weight
            buckets[key]["sample_count"] += 1
        output = {}
        for key, data in buckets.items():
            mastery = data["weighted_score"] / data["total_weight"] if data["total_weight"] else 0
            output[key] = {
                "mastery": round(mastery, 4), "interpretation": cls.interpretation(mastery),
                "sample_count": data["sample_count"], "weighted_score": round(data["weighted_score"], 6),
                "total_weight": round(data["total_weight"], 6),
            }
        return output

    @classmethod
    def recompute_mastery(cls, student_id, subject, submission_id=None):
        rows = [row for row in LearningHistory.query.filter_by(student_id=student_id, subject=subject).all()
                if row.answer_status not in ("unanswered", "pending_review")]
        overall = cls._aggregate(rows, lambda _row: "all").get("all", {}).get("mastery", .50)
        topic = cls._aggregate(rows, lambda row: row.topic)
        skill = cls._aggregate(rows, lambda row: row.curriculum_code or row.topic)
        cognitive = cls._aggregate(rows, lambda row: row.cognitive_level)
        intersections = cls._aggregate(rows, lambda row: f"{row.topic}||{row.cognitive_level}")
        for dimension, values in (("topic", topic), ("skill", skill), ("cognitive", cognitive), ("topic_cognitive", intersections)):
            existing = {item.dimension_key: item for item in StudentMastery.query.filter_by(
                student_id=student_id, subject=subject, dimension=dimension
            ).all()}
            for key, data in values.items():
                item = existing.get(key)
                if not item:
                    item = StudentMastery(student_id=student_id, subject=subject, dimension=dimension, dimension_key=key)
                    db.session.add(item)
                for field in ("mastery", "interpretation", "sample_count", "weighted_score", "total_weight"):
                    setattr(item, field, data[field])
                item.evidence_count = data["sample_count"]
                item.insufficient_data = data["sample_count"] < 3
                item.last_evidence_at = max((row.occurred_at for row in rows), default=None)
                item.updated_at = dt.datetime.utcnow()
        weak_regions = []
        for key, data in intersections.items():
            if data["mastery"] < cls.MASTERY_THRESHOLDS["middle"]:
                topic_name, level = key.split("||", 1)
                weak_regions.append({"topic": topic_name, "cognitive_level": level, **data})
        weak_regions.sort(key=lambda item: (item["mastery"], -item["sample_count"]))
        profile = {
            "student_id": student_id, "subject": subject, "answer_count": len(rows),
            "cold_start": len(rows) < cls.COLD_START_MIN_ANSWERS,
            "cold_start_min_answers": cls.COLD_START_MIN_ANSWERS,
            "overall_mastery": round(overall, 4), "overall_interpretation": cls.interpretation(overall),
            "topic_mastery": topic, "skill_mastery": skill, "cognitive_mastery": cognitive,
            "topic_cognitive_mastery": intersections, "weak_regions": weak_regions,
            "insufficient_data": len(rows) < 3,
        }
        if submission_id:
            from services.practice_evidence import learning_rows, practice_skill_matrix
            finalized_sources = [s for s in ExamSubmission.query.filter_by(student_id=student_id).all()
                                 if s.exam and s.exam.course and s.exam.course.subject == subject
                                 and is_finalized(s)]
            profile['practice_skill_mastery'] = practice_skill_matrix(learning_rows(finalized_sources))
            profile['practice_evidence_policy'] = 'atomic_repeat_discount_v2'
            snapshot = MasterySnapshot.query.filter_by(
                student_id=student_id, subject=subject, submission_id=submission_id
            ).first()
            if not snapshot:
                snapshot = MasterySnapshot(student_id=student_id, subject=subject, submission_id=submission_id)
                db.session.add(snapshot)
            snapshot.profile_data = json.dumps(profile, ensure_ascii=False)
            snapshot.profile_revision = int(snapshot.profile_revision or 0) + 1
            snapshot.input_hash = content_hash({
                "student_id": student_id,
                "subject": subject,
                "practice_evidence_policy": "atomic_repeat_discount_v2",
                "evidence": [row.evidence_ref for row in rows if row.evidence_ref],
            })
            snapshot.trigger = "grading"
            snapshot.created_at = dt.datetime.utcnow()
        db.session.flush()
        return profile

    @classmethod
    def analyze_performance(cls, student_id, subject, topic=None):
        perf = StudentPerformance.query.filter_by(student_id=student_id, subject=subject).first()
        submissions = [item for item in ExamSubmission.query.filter_by(student_id=student_id)
                       .order_by(ExamSubmission.submitted_at.desc()).all()
                       if item.exam and item.exam.course and item.exam.course.subject == subject and item.exam.assessment_purpose != "standalone" and is_finalized(item)]
        rows = [row for row in LearningHistory.query.filter_by(student_id=student_id, subject=subject).all()
                if row.answer_status not in ("unanswered", "pending_review")]
        mastery_profile = cls.recompute_mastery(student_id, subject) if rows else {
            "student_id": student_id, "subject": subject, "answer_count": 0, "cold_start": True,
            "cold_start_min_answers": cls.COLD_START_MIN_ANSWERS, "topic_mastery": {},
            "skill_mastery": {},
            "cognitive_mastery": {}, "topic_cognitive_mastery": {}, "weak_regions": [],
        }
        scores = [item.percentage / 10 for item in submissions]
        recency_weights = [.7 ** index for index in range(len(scores))]
        avg_score = sum(score * weight for score, weight in zip(scores, recency_weights)) / sum(recency_weights) if recency_weights else 0
        if len(scores) >= 3:
            recent = sum(scores[:3]) / 3
            older = sum(scores[3:]) / len(scores[3:]) if len(scores) > 3 else recent
            trend = "improving" if recent - older >= .8 else "declining" if older - recent >= .8 else "stable"
        else:
            trend = "stable"
        overall = cls._aggregate(rows, lambda _row: "all").get("all", {}).get("mastery", .50)
        cognitive = mastery_profile["cognitive_mastery"]
        topics = mastery_profile["topic_mastery"]
        result = {
            **mastery_profile, "total_attempts": len(submissions), "avg_score": round(avg_score, 1),
            "latest_score": round(scores[0], 1) if scores else 0., "best_score": round(max(scores), 1) if scores else 0.,
            "score_trend": trend, "overall_mastery": round(overall, 4),
            "overall_interpretation": cls.interpretation(overall),
            "adaptive_difficulty": "reinforce" if overall < cls.MASTERY_THRESHOLDS["weak"] else "challenge" if overall >= cls.MASTERY_THRESHOLDS["good"] else "standard",
            "single_accuracy": perf.single_accuracy if perf else 50.,
            "truefalse_accuracy": perf.truefalse_accuracy if perf else 50.,
            "short_answer_accuracy": perf.short_answer_accuracy if perf else 50.,
            "weak_topics": [key for key, value in topics.items() if value["mastery"] < cls.MASTERY_THRESHOLDS["weak"]],
            "strong_topics": [key for key, value in topics.items() if value["mastery"] >= cls.MASTERY_THRESHOLDS["good"]],
        }
        error_profiles = StudentErrorProfile.query.filter_by(
            student_id=student_id, subject=subject, status="observed"
        ).filter(StudentErrorProfile.evidence_count > 0).order_by(
            StudentErrorProfile.evidence_count.desc()
        ).all()
        result["error_targets"] = [
            {
                "curriculum_code": row.curriculum_code,
                "error_code": row.error_code,
                "evidence_count": row.evidence_count,
                "confidence": row.confidence,
            }
            for row in error_profiles
        ]
        for level in COGNITIVE_LEVELS:
            result[f"{level}_accuracy"] = round(cognitive.get(level, {}).get("mastery", .50) * 100, 1)
        if topic and topic in topics:
            result["selected_topic"] = topics[topic]
        from services.practice_evidence import learning_rows, practice_skill_matrix
        result["practice_skill_mastery"] = practice_skill_matrix(learning_rows(submissions))
        return result

    @classmethod
    def recommend_difficulty(cls, profile):
        mastery = float(profile.get("overall_mastery", .50))
        if profile.get("cold_start"):
            diff, level, target = ({"nhan_biet": 25, "thong_hieu": 50, "van_dung": 20, "van_dung_cao": 5}, "cold_start", "Đánh giá đầu vào cân bằng")
        elif mastery < cls.MASTERY_THRESHOLDS["weak"]:
            diff, level, target = ({"nhan_biet": 55, "thong_hieu": 30, "van_dung": 10, "van_dung_cao": 5}, "reinforce", "Chủ yếu câu dễ")
        elif mastery < cls.MASTERY_THRESHOLDS["middle"]:
            diff, level, target = ({"nhan_biet": 35, "thong_hieu": 40, "van_dung": 20, "van_dung_cao": 5}, "standard", "Câu dễ và trung bình")
        elif mastery < cls.MASTERY_THRESHOLDS["good"]:
            diff, level, target = ({"nhan_biet": 15, "thong_hieu": 35, "van_dung": 35, "van_dung_cao": 15}, "standard", "Câu trung bình và khó")
        else:
            diff, level, target = ({"nhan_biet": 10, "thong_hieu": 20, "van_dung": 40, "van_dung_cao": 30}, "challenge", "Câu khó và vận dụng cao")
        types = {"single": 50, "truefalse": 30, "short_answer": 20}
        if profile.get("truefalse_accuracy", 50) < 40:
            types.update({"single": 40, "truefalse": 40})
        if profile.get("short_answer_accuracy", 50) < 40:
            types["short_answer"] += 10
            types["single"] -= 10
        return {"level": level, "diff_config": diff, "type_config": types, "target_score": target}

    @classmethod
    def score_question(cls, question, profile, recent_question_ids=None):
        topic = question.topic or (question.curriculum_node.topic_name if question.curriculum_node else "Chưa xác định") or "Chưa xác định"
        topic_mastery = profile.get("topic_mastery", {}).get(topic, {}).get("mastery", .50)
        level = question.difficulty_level or "nhan_biet"
        cognitive_data = profile.get("topic_cognitive_mastery", {}).get(f"{topic}||{level}") or profile.get("cognitive_mastery", {}).get(level) or {"mastery": .50}
        distribution = cls.recommend_difficulty(profile)["diff_config"]
        max_distribution = max(distribution.values()) or 1
        target_codes = {item.get("curriculum_code") for item in profile.get("error_targets", [])}
        question_code = question.curriculum_node.canonical_code if question.curriculum_node else None
        targeted = bool(question_code and question_code in target_codes)
        parts = {
            # Error evidence is intentionally a bounded boost to weakness; it
            # never overrides teacher constraints or deterministic grading.
            "weakness": min(1., 1 - topic_mastery + (.20 if targeted else 0.)),
            "difficulty": distribution.get(level, 0) / max_distribution,
            "cognitive": 1 - cognitive_data["mastery"],
            "variety": 0. if question.id in set(recent_question_ids or []) else 1.,
            "teacher": max(0., min(1., float(question.adaptive_priority or 0) / 100)),
        }
        return round(sum(cls.SCORE_WEIGHTS[key] * value for key, value in parts.items()), 6), {key: round(value, 4) for key, value in parts.items()}

    @staticmethod
    def _topic_bucket(question, profile):
        topic = question.topic or (question.curriculum_node.topic_name if question.curriculum_node else "Chưa xác định") or "Chưa xác định"
        mastery = profile.get("topic_mastery", {}).get(topic, {}).get("mastery", .50)
        return "weak" if mastery < AdaptiveEngine.MASTERY_THRESHOLDS["weak"] else "strong" if mastery >= AdaptiveEngine.MASTERY_THRESHOLDS["good"] else "middle"

    @staticmethod
    def _allocate_quotas(total, ratios):
        normalized = {key: (float(value) / 100 if float(value) > 1 else float(value)) for key, value in ratios.items()}
        raw = {key: total * max(0., value) for key, value in normalized.items()}
        quotas = {key: int(value) for key, value in raw.items()}
        remaining = max(0, total - sum(quotas.values()))
        order = sorted(raw, key=lambda key: (-(raw[key] - quotas[key]), -normalized[key], key))
        for key in order[:remaining]:
            quotas[key] += 1
        return quotas

    @classmethod
    def select_questions(cls, student_id, subject, bank_ids, total, constraints=None):
        constraints, total = constraints or {}, max(1, min(100, int(total)))
        from services import practice_blueprint as blueprint
        fixed = constraints.get("blueprint") == blueprint.VERSION
        if fixed:
            total = blueprint.TOTAL
        candidates = [question for question in BankQuestion.query.filter(
            BankQuestion.bank_id.in_(bank_ids), BankQuestion.adaptive_excluded.is_(False)
        ).all() if bank_question_ready(question)]
        # Overlay authoring must not expose another teacher's private rows
        # through a bank-wide candidate query. Routes supply server-resolved
        # class context; this does not change ranking or paper allocation.
        from models import Course
        from services.source_resolver import resolve_class_questions
        course_id = constraints.get("course_id")
        if course_id is not None:
            course = db.session.get(Course, course_id)
            # The route-level source resolver uses the strict Grade-9 check.
            # This lower-level API keeps NULL-grade legacy fixtures usable;
            # explicit non-9 grades are still rejected by production routes.
            source = resolve_class_questions(
                course, bank_ids, candidates, require_grade=False
            ) if course else {"valid": False, "questions": []}
            candidates = [question for question in source["questions"]
                          if course.subject == subject]
        else:
            # Compatibility for offline callers without a class: never make
            # an explicit private supplement available without its principal.
            candidates = [question for question in candidates
                          if question.scope is None and question.private_owner_id is None
                          and question.bank and question.bank.visibility != "shared"]
        for field in ("chapter", "section", "topic"):
            allowed = set(constraints.get(field) or [])
            if allowed:
                candidates = [question for question in candidates if str(getattr(question, field, "") or "") in allowed]
        levels = set(constraints.get("cognitive_levels") or [])
        if levels:
            candidates = [question for question in candidates if question.difficulty_level in levels]
        excluded = set(constraints.get("excluded_question_ids") or [])
        candidates = [question for question in candidates if question.id not in excluded]
        from services import aptga
        history = LearningHistory.query.filter_by(student_id=student_id, subject=subject).all()
        # Recheck current grading state: stale facts from a pending regrade are
        # not eligible evidence. Historical unknown skill labels are not guessed.
        submissions = {s.id: s for s in ExamSubmission.query.filter_by(student_id=student_id).all()
                       if s.exam and s.exam.assessment_purpose != "standalone"}
        eligible = [r for r in history if r.answer_status == "answered"
                    and r.curriculum_code in {f"9C8-i-{i}" for i in range(1, 9)}
                    and is_finalized(submissions.get(r.submission_id))]
        if fixed:
            from services.practice_evidence import learning_rows
            eligible = learning_rows([s for s in submissions.values() if s.exam and s.exam.course
                                      and s.exam.course.subject == subject])
        cells = aptga.matrix(eligible)
        by_level = {level: aptga.summarize([r for r in eligible if r.cognitive_level == level])
                    for level in COGNITIVE_LEVELS}
        quotas, warnings = aptga.allocate(total, by_level, levels or None)
        promotion_moves = []
        if fixed:
            from services.practice_selector import progression
            # Fixed papers retain all four levels; teacher exclusions are candidate
            # filters, never permission to silently replace the paper blueprint.
            quotas, warnings = aptga.allocate(total, by_level)
            quotas, promotion_moves = progression(eligible, quotas)
        profile = cls.analyze_performance(student_id, subject)
        profile["skill_cognitive_mastery"] = cells
        exposure_submissions = sorted(
            [s for s in submissions.values()
             if s.submitted_at and s.exam and s.exam.course
             and s.exam.course.subject == subject],
            key=lambda s: (s.submitted_at, s.id), reverse=True)
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=5)
        cooldown_submissions = [
            s for index, s in enumerate(exposure_submissions)
            if index < 3 or s.submitted_at >= cutoff
        ]
        recent_sessions = {s.id for s in cooldown_submissions}
        blocked_ids = {
            question.bank_question_id
            for submission in cooldown_submissions
            for question in submission.exam.questions
            if question.bank_question_id is not None
        }
        blocked_hashes = {
            question.source_content_hash
            for submission in cooldown_submissions
            for question in submission.exam.questions
            if question.source_content_hash
        }
        # Retain recorded facts as a migration-safe fallback when a legacy exam
        # no longer has a complete question snapshot.
        blocked_ids.update(r.bank_question_id for r in history
                           if r.bank_question_id is not None and
                           (r.submission_id in recent_sessions or r.occurred_at >= cutoff))
        blocked_hashes.update(r.question_content_hash for r in history
                              if r.question_content_hash and
                              (r.submission_id in recent_sessions or r.occurred_at >= cutoff))
        if not fixed:
            candidates = [q for q in candidates if q.id not in blocked_ids
                          and getattr(q, "content_hash", None) not in blocked_hashes]
        exposure_ids, exposure_hashes = defaultdict(set), defaultdict(set)
        for age, submission in enumerate(exposure_submissions):
            for question in submission.exam.questions:
                if question.bank_question_id:
                    exposure_ids[question.bank_question_id].add(age)
                if question.source_content_hash:
                    exposure_hashes[question.source_content_hash].add(age)
        ranked = []
        rejected = Counter() if fixed else None
        for question in candidates:
            node = question.curriculum_node
            code = node.canonical_code if node else None
            # Unclassified legacy questions can only be probes; do not assign
            # them a made-up skill. Explicit outside-scope metadata is rejected.
            if code and code not in {f"9C8-i-{i}" for i in range(1, 9)}:
                continue
            if question.chapter not in (None, "", "8") or question.section not in (None, "", "i"):
                continue
            if fixed:
                reason = blueprint.readiness_error(question)
                if reason:
                    rejected[reason] += 1
                    continue
            cell = cells.get(f"{code}||{question.difficulty_level}", aptga.summarize([]))
            score, components = aptga.priority(cell)
            if fixed and any(move["skill"] == code and move["target"] == question.difficulty_level for move in promotion_moves):
                score += .15
                components["next_level_probe"] = .15
            components["teacher"] = max(0., min(1., float(question.adaptive_priority or 0) / 100))
            from services.personalization_evidence import bank_question_content_hash
            fingerprint = question.content_hash or bank_question_content_hash(question)
            ages = exposure_ids[question.id] | exposure_hashes[fingerprint]
            cooling = question.id in blocked_ids or fingerprint in blocked_hashes
            tier = (3 if 0 in ages else 2 if ages and min(ages) < 3 else 1) if cooling else 0
            role = "probe" if not cell["sufficient"] else "remedial" if cell["mastery"] < .7 else "maintenance"
            ranked.append(dict(question=question, score=round(score, 6), components=components,
                               fingerprint=fingerprint, exposure_tier=tier,
                               exposure_count=len(ages), last_seen_sessions=min(ages) if ages else None,
                               role=role, skill=code, state=cell["state"],
                               bucket={"probe": "middle", "remedial": "weak", "maintenance": "strong"}[role]))
        ranked.sort(key=lambda item: (-item["score"], -item["components"]["teacher"], item["question"].id))
        selected = []
        actual = {}
        role_targets = cls._allocate_quotas(total, constraints.get("review_mix") or cls.REVIEW_MIX)
        role_counts = defaultdict(int)
        for level, quota in ({} if fixed else quotas).items():
            pool = [item for item in ranked if item["question"].difficulty_level == level]
            for _ in range(min(quota, len(pool))):
                # Soft role mix never overrides level quotas or exclusions.
                preferred = [item for item in pool if role_counts[item["bucket"]] < role_targets.get(item["bucket"], 0)]
                item = (preferred or pool)[0]
                selected.append(item)
                pool.remove(item)
                role_counts[item["bucket"]] += 1
            actual[level] = sum(item["question"].difficulty_level == level for item in selected)
        fixed_audit = {}
        if fixed:
            from services.practice_selector import skill_targets
            from services.practice_recovery import select_resilient
            from services.personalization_evidence import bank_question_content_hash
            for item in ranked:
                item["fingerprint"] = item["question"].content_hash or bank_question_content_hash(item["question"])
            knowledge = skill_targets(cells, offset=len(exposure_submissions))
            from services.practice_source_inventory import build_source_inventory
            source_inventory = build_source_inventory(
                ranked, level_targets=quotas, skill_targets=knowledge)
            from random import SystemRandom
            selected, shortages, status, recovery = select_resilient(
                ranked, quotas, knowledge, cells=cells, rng=SystemRandom())
            role_counts = Counter(item["bucket"] for item in selected)
            actual = {level: sum(item["question"].difficulty_level == level for item in selected) for level in quotas}
            fixed_audit = dict(version=blueprint.VERSION, status=status, type_targets=blueprint.TYPE_QUOTAS,
                               actual_types=dict(Counter(item["question"].question_type for item in selected)),
                               skill_targets=knowledge, actual_skills=dict(Counter(item["skill"] for item in selected)),
                               shortages=shortages, rejected=dict(rejected), promotion_moves=promotion_moves,
                               scoring=dict(points=blueprint.POINTS, true_false=list(blueprint.TF_POINTS)),
                               source_inventory=source_inventory,
                               evidence_policy="atomic_repeat_discount_v2", **recovery)
            if selected and recovery["repeated_count"]:
                warnings.append(f"Ôn lại {recovery['repeated_count']}/22 câu đã gặp; ưu tiên câu ít lặp và cách xa lượt trước. Không lặp nội dung trong cùng đề.")
            if selected and recovery["quota_changes"]:
                warnings.append(f"Chuyển {recovery['quota_changes']} vị trí sang dạng khác; giữ nguyên số câu từng mức nhận thức, ba hình thức và thang điểm.")
                transfer_counts = Counter((t["source_skill"], t["target_skill"], t["level"],
                                           t["question_type"], t["reason"]) for t in recovery["skill_transfers"])
                for (source, target, level, kind, reason), count in transfer_counts.items():
                    cause = ("dạng nguồn không có câu hợp lệ ở ô này" if reason == "source_cell_empty"
                             else "phân bổ dạng ban đầu chưa ghép được trong lượt tìm kiếm theo mức và hình thức yêu cầu")
                    warnings.append(f"Chuyển {count} câu {COGNITIVE_LABELS[level]} ({blueprint.TYPE_LABELS[kind]}) từ dạng {source.rsplit('-', 1)[-1]} sang dạng {target.rsplit('-', 1)[-1]}: {cause}.")
            if selected and recovery["unavailable_skills"]:
                missing = ", ".join(s.rsplit("-", 1)[-1] for s in recovery["unavailable_skills"])
                warnings.append(f"Nguồn hợp lệ hoàn toàn thiếu dạng {missing}; đề phủ {recovery['covered_skill_count']}/8 dạng, không đổi nhãn kiến thức của câu thay thế.")
            if status != "ready":
                warnings.append("Không tạo đề: chưa thể ghép đủ 22 câu theo cấu trúc 12–4–6, đúng quota mức và độ phủ các dạng có nguồn hợp lệ.")
                warnings.extend(f"Thiếu {s['missing']} câu {s['dimension']} {s['key']} (cần {s['required']}, có {s['available']})." for s in shortages)
                warnings.extend(f"{reason}: {count} câu." for reason, count in rejected.items())
                if status == "search_limit":
                    warnings.append("Đã đạt giới hạn tìm kiếm; chưa kết luận ngân hàng không có phương án phù hợp.")
                elif status == "incompatible_intersections":
                    warnings.append("Số lượng từng nhóm riêng lẻ đủ nhưng giao giữa dạng câu, mức và kiến thức không đáp ứng.")
        shortfall = {level: quotas[level] - actual[level] for level in quotas if actual[level] < quotas[level]}
        if shortfall and not fixed:
            warnings.append("Ngân hàng/cooldown không đủ câu đúng mức; đề ngắn hơn yêu cầu, không tự đổi quota.")
        recommendation = cls.recommend_difficulty(profile)
        recommendation["diff_config"] = {l: quotas.get(l, 0) * 100 / total for l in COGNITIVE_LEVELS}
        recommendation["level"] = "aptga"
        if fixed:
            recommendation["type_config"] = {key: count * 100 / total for key, count in blueprint.TYPE_QUOTAS.items()}
        explanation = (
            f"Chọn {len(selected)}/{total} câu theo dạng kiến thức và mức nhận thức. "
            "Hồ sơ dựa trên câu trả lời đã chấm, có nhãn kiến thức; "
            "lịch sử các lượt đã nộp giúp ưu tiên câu ít gặp."
        )
        if warnings:
            explanation += " " + " ".join(warnings)
        return {
            "questions": [item["question"] for item in selected],
            "ranked": [dict(question_id=item["question"].id, score=item["score"],
                            components=item["components"], bucket=item["bucket"],
                            exposure_count=item.get("exposure_count", 0),
                            exposure_tier=item.get("exposure_tier", 0),
                            last_seen_sessions=item.get("last_seen_sessions"),
                            role=item["role"], skill=item["skill"], state=item["state"]) for item in selected],
            "profile": profile, "recommendation": recommendation, "explanation": explanation,
            "requested_count": total, "selected_count": len(selected),
            "mix": {key: role_counts[key] for key in cls.REVIEW_MIX},
            "error_targets": profile.get("error_targets", []),
            "aptga": dict(version=aptga.VERSION, desired_quotas=quotas, actual_quotas=actual,
                          shortfall=shortfall, warnings=warnings, skill_cognitive_mastery=cells,
                          parameters=dict(recency=.8, min_distinct=5, min_sessions=2,
                                          adaptive_cap=.2, cooldown_days=5, cooldown_sessions=3,
                                          priority_weights=[.6, .25, .15]),
                          prerequisite_transfer="disabled_pending_expert_validation",
                          ai_influence=0, role_targets=role_targets) | fixed_audit,
        }
    @classmethod
    def update_performance(cls, student_id, submission, *, commit=True):
        if not submission or not submission.exam or not submission.exam.course or not is_finalized(submission) or submission.exam.assessment_purpose == "standalone":
            return None
        subject = submission.exam.course.subject
        cls.record_submission(student_id, submission)
        rebuild_error_observations(submission)
        profile = cls.recompute_mastery(student_id, subject, submission.id)
        perf = StudentPerformance.query.filter_by(student_id=student_id, subject=subject).first()
        if not perf:
            perf = StudentPerformance(student_id=student_id, subject=subject)
            db.session.add(perf)
        submissions = [item for item in ExamSubmission.query.filter_by(student_id=student_id).all()
                       if item.exam and item.exam.course and item.exam.course.subject == subject and item.exam.assessment_purpose != "standalone" and is_finalized(item)]
        scores = [item.percentage / 10 for item in submissions]
        perf.total_attempts = len(submissions)
        perf.latest_score = round(submission.percentage / 10, 1)
        perf.avg_score = round(sum(scores) / len(scores), 1) if scores else 0
        perf.best_score = round(max(scores), 1) if scores else 0
        perf.worst_score = round(min(scores), 1) if scores else 0
        for level in COGNITIVE_LEVELS:
            setattr(perf, f"{level}_accuracy", round(profile["cognitive_mastery"].get(level, {}).get("mastery", .50) * 100, 1))
        type_rows = defaultdict(list)
        for answer in submission.answers:
            if answer.question and (
                answer_status(answer) not in ("unanswered", "pending_review")
                or is_legacy_unknown_answer(submission, answer)
            ):
                qtype = "truefalse" if answer.question.question_type == "true_false" else answer.question.question_type
                type_rows[qtype].append(1. if answer.is_correct else 0.)
        for qtype in ("single", "truefalse", "short_answer"):
            if type_rows[qtype]:
                setattr(perf, f"{qtype}_accuracy", round(sum(type_rows[qtype]) / len(type_rows[qtype]) * 100, 1))
        perf.weak_topics = json.dumps([key for key, value in profile["topic_mastery"].items() if value["mastery"] < cls.MASTERY_THRESHOLDS["weak"]], ensure_ascii=False)
        perf.strong_topics = json.dumps([key for key, value in profile["topic_mastery"].items() if value["mastery"] >= cls.MASTERY_THRESHOLDS["good"]], ensure_ascii=False)
        all_rows = [row for row in LearningHistory.query.filter_by(student_id=student_id, subject=subject).all()
                    if row.answer_status not in ("unanswered", "pending_review")]
        overall = cls._aggregate(all_rows, lambda _row: "all").get("all", {}).get("mastery", .5)
        perf.adaptive_difficulty = cls.recommend_difficulty({**profile, "overall_mastery": overall})["level"]
        perf.updated_at = dt.datetime.utcnow()
        if commit:
            db.session.commit()
        else:
            db.session.flush()
        return perf
