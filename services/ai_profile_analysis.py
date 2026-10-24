"""AI API integration for auditable Chapter 8 learner diagnosis."""

import datetime as dt
import hashlib
import json
import os
import time
from copy import deepcopy

import requests

from database import db
from models import AIAnalysisRun
from services.ai_gateway import (
    AICooldownError,
    AIConfigurationError,
    AIGatewayError,
    GeminiAIGateway,
    TEACHER_GEMINI_MODEL,
    teacher_default_group,
)
from services.chapter8_profile_service import COGNITIVE_LEVELS, build_chapter8_profile
from services.personalization_evidence import evidence_packet
from services import diagnostic_report_contract as diagnostic


PROMPT_VERSION = "c8-i-diagnosis-v6-stable-evidence"
SYSTEM_PROMPT = diagnostic.SYSTEM_PROMPT


def _env_int(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _canonical_hash(payload):
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _bounded_number(value, low=0., high=1.):
    number = float(value)
    if number < low or number > high:
        raise ValueError(f"Giá trị {number} nằm ngoài khoảng {low}–{high}.")
    return number


def _known_pairs(profile):
    pairs = {(str(row["lesson"]), str(row["exercise_type"])) for row in profile.get("available_taxonomy", [])}
    pairs |= {(str(row["lesson"]), str(row["exercise_type"])) for row in profile.get("skill_results", [])}
    return pairs


def validate_analysis(data, profile):
    if not isinstance(data, dict):
        raise ValueError("AI phải trả về một JSON object.")
    diagnosis = str(data.get("overall_diagnosis") or "").strip()
    explanation = str(data.get("student_explanation") or "").strip()
    if not diagnosis or not explanation:
        raise ValueError("Kết quả AI thiếu chẩn đoán hoặc giải thích cho học sinh.")
    confidence = _bounded_number(data.get("confidence", 0))
    observed = {
        (str(row["lesson"]), str(row["exercise_type"]), row["cognitive_level"])
        for row in profile.get("skill_results", [])
    }
    known_pairs = _known_pairs(profile)

    def validate_observation_list(name, severity_name=None):
        output = []
        rows = data.get(name, [])
        if not isinstance(rows, list):
            raise ValueError(f"{name} phải là danh sách.")
        for row in rows[:8]:
            if not isinstance(row, dict):
                raise ValueError(f"Phần tử {name} không hợp lệ.")
            lesson, exercise_type = str(row.get("lesson", "")), str(row.get("exercise_type", ""))
            cognitive = row.get("cognitive_level")
            if (lesson, exercise_type, cognitive) not in observed:
                raise ValueError(f"AI dẫn chiếu vùng chưa được quan sát: bài {lesson}, dạng {exercise_type}, {cognitive}.")
            evidence = str(row.get("evidence") or "").strip()
            if not evidence:
                raise ValueError(f"Nhận định {name} thiếu bằng chứng.")
            clean = {
                "lesson": lesson, "exercise_type": exercise_type, "cognitive_level": cognitive,
                "evidence": evidence[:500],
            }
            if severity_name:
                clean[severity_name] = round(_bounded_number(row.get(severity_name, 0)), 4)
            output.append(clean)
        return output

    strengths = validate_observation_list("strengths")
    weaknesses = validate_observation_list("weaknesses", "severity")
    objectives = []
    raw_objectives = data.get("next_objectives", [])
    if not isinstance(raw_objectives, list):
        raise ValueError("next_objectives phải là danh sách.")
    for row in raw_objectives[:8]:
        if not isinstance(row, dict):
            raise ValueError("Mục tiêu tiếp theo không hợp lệ.")
        lesson, exercise_type = str(row.get("lesson", "")), str(row.get("exercise_type", ""))
        cognitive = row.get("target_cognitive_level")
        if (lesson, exercise_type) not in known_pairs or cognitive not in COGNITIVE_LEVELS:
            raise ValueError(f"Mục tiêu ngoài danh mục Chương 8: bài {lesson}, dạng {exercise_type}.")
        count = int(row.get("recommended_question_count", 1))
        if not 1 <= count <= 50:
            raise ValueError("Số câu đề xuất phải từ 1 đến 50.")
        objectives.append({
            "lesson": lesson, "exercise_type": exercise_type,
            "target_cognitive_level": cognitive,
            "priority": round(_bounded_number(row.get("priority", 0)), 4),
            "recommended_question_count": count,
            "reason": str(row.get("reason") or "").strip()[:500],
        })
    mix = data.get("difficulty_mix")
    if not isinstance(mix, dict):
        raise ValueError("Thiếu phân phối độ khó.")
    difficulty_mix = {}
    for level in ("nhan_biet", "thong_hieu", "van_dung", "van_dung_cao"):
        if level not in mix:
            raise ValueError(f"Phân phối độ khó thiếu mức {level}.")
        difficulty_mix[level] = round(_bounded_number(mix.get(level, 0), 0, 100), 2)
    if abs(sum(difficulty_mix.values()) - 100) > .5:
        raise ValueError("Tổng phân phối độ khó phải bằng 100%.")
    return {
        "schema_version": "chapter6-analysis-v1",
        "overall_diagnosis": diagnosis[:1500], "confidence": round(confidence, 4),
        "strengths": strengths, "weaknesses": weaknesses, "next_objectives": objectives,
        "difficulty_mix": difficulty_mix, "student_explanation": explanation[:1000],
    }


def validate_evidence_analysis(data, profile):
    """Validate answer-level references before displaying an AI claim.

    A model may explain a recorded wrong answer, but it may not invent an item
    or turn a risk signal into a fact.  The legacy v1 validator remains public
    for old cached runs and is intentionally not used as proof of answer-level
    evidence.
    """
    if not isinstance(data, dict):
        raise ValueError("AI phải trả về một JSON object.")
    known_refs = {str(row.get("evidence_ref")) for row in profile.get("observed_error_evidence", [])}
    observed = data.get("observed_errors", [])
    if not isinstance(observed, list):
        raise ValueError("observed_errors phải là danh sách.")
    clean_observed = []
    for row in observed[:30]:
        if not isinstance(row, dict):
            raise ValueError("observed_errors chứa phần tử không hợp lệ.")
        refs = row.get("evidence_refs", [])
        if not isinstance(refs, list) or not refs or any(str(ref) not in known_refs for ref in refs):
            raise ValueError("AI dẫn chiếu bằng chứng không tồn tại hoặc không được cung cấp.")
        confidence = _bounded_number(row.get("confidence", 0), 0, 1)
        if not str(row.get("curriculum_code") or "").strip() or not str(row.get("error_code") or "").strip() or not str(row.get("claim") or "").strip():
            raise ValueError("observed_errors thiếu kỹ năng, mã lỗi hoặc claim.")
        clean_observed.append({
            "curriculum_code": str(row.get("curriculum_code") or "")[:80],
            "error_code": str(row.get("error_code") or "")[:60],
            "claim": str(row.get("claim") or "").strip()[:800],
            "evidence_refs": [str(ref) for ref in refs[:10]],
            "evidence_count": len(refs),
            "confidence": round(confidence, 4),
            "status": "observed",
        })
    risks = data.get("future_error_risks", [])
    if not isinstance(risks, list):
        raise ValueError("future_error_risks phải là danh sách.")
    clean_risks = []
    for row in risks[:20]:
        if not isinstance(row, dict):
            raise ValueError("future_error_risks chứa phần tử không hợp lệ.")
        refs = row.get("basis_evidence_refs", [])
        if not isinstance(refs, list) or not refs or any(str(ref) not in known_refs for ref in refs):
            raise ValueError("future_error_risks dẫn chiếu bằng chứng không tồn tại.")
        validation = str(row.get("validation") or "not_validated")
        if validation != "not_validated":
            raise ValueError("Rủi ro tương lai phải được đánh dấu chưa kiểm chứng.")
        clean_risks.append({
            "skill": str(row.get("skill") or "")[:80],
            "basis_evidence_refs": [str(ref) for ref in refs[:10]],
            "confidence": round(_bounded_number(row.get("confidence", 0), 0, 1), 4),
            "validation": "not_validated",
        })
    diagnosis = str(data.get("overall_diagnosis") or "").strip()
    explanation = str(data.get("student_explanation") or "").strip()
    if not diagnosis or not explanation:
        raise ValueError("Kết quả AI thiếu chẩn đoán hoặc giải thích cho học sinh.")
    mix = data.get("difficulty_mix")
    if not isinstance(mix, dict):
        raise ValueError("Thiếu phân phối độ khó.")
    clean_mix = {}
    for level in ("nhan_biet", "thong_hieu", "van_dung", "van_dung_cao"):
        if level not in mix:
            raise ValueError(f"Phân phối độ khó thiếu mức {level}.")
        clean_mix[level] = round(_bounded_number(mix[level], 0, 100), 2)
    if abs(sum(clean_mix.values()) - 100) > .5:
        raise ValueError("Tổng phân phối độ khó phải bằng 100%.")
    return {
        "schema_version": "chapter6-analysis-v2",
        "overall_diagnosis": diagnosis[:1500],
        "confidence": round(_bounded_number(data.get("confidence", 0), 0, 1), 4),
        "strengths": data.get("strengths", [])[:8] if isinstance(data.get("strengths", []), list) else [],
        "weaknesses": data.get("weaknesses", [])[:8] if isinstance(data.get("weaknesses", []), list) else [],
        "next_objectives": data.get("next_objectives", [])[:8] if isinstance(data.get("next_objectives", []), list) else [],
        "difficulty_mix": clean_mix,
        "student_explanation": explanation[:1000],
        "observed_errors": clean_observed,
        "future_error_risks": clean_risks,
    }


def with_evidence_contract(result, profile):
    """Attach deterministic evidence links to a legacy/fallback diagnosis."""
    rows = profile.get("observed_error_evidence", [])
    observed = []
    by_key = {}
    for row in rows:
        key = (row.get("curriculum_code") or row.get("topic") or "unknown", row.get("error_code") or "observed_error")
        by_key.setdefault(key, []).append(row["evidence_ref"])
    for (skill, code), refs in by_key.items():
        observed.append({
            "curriculum_code": skill,
            "error_code": code,
            "claim": "Quan sát lỗi trên các câu trả lời cụ thể; chưa kết luận misconception ổn định.",
            "evidence_refs": refs[:10],
            "evidence_count": len(refs),
            "confidence": min(.75, .35 + len(refs) * .1),
            "status": "observed",
        })
    result = dict(result)
    result.update({
        "schema_version": "chapter6-analysis-v2",
        "observed_errors": observed,
        "future_error_risks": [
            {
                "skill": skill,
                "basis_evidence_refs": refs[:10],
                "confidence": min(.75, .25 + len(refs) * .1),
                "validation": "not_validated",
            }
            for (skill, _code), refs in by_key.items()
        ],
    })
    return result


def deterministic_fallback(profile):
    skills = profile.get("skill_results", [])
    ordered = sorted(skills, key=lambda row: (row["mastery"], -row["attempts"]))
    weak = [row for row in ordered if row["mastery"] < .60][:5]
    strong = [row for row in reversed(ordered) if row["mastery"] >= .80][:3]
    if not weak and ordered:
        weak = ordered[:2]
    evidence = lambda row: f"Đạt {row['normalized_score']:.0%} qua {row['attempts']} câu; xu hướng {row['recent_trend']}."
    weaknesses = [{
        "lesson": row["lesson"], "exercise_type": row["exercise_type"],
        "cognitive_level": row["cognitive_level"], "severity": round(1 - row["mastery"], 4),
        "evidence": evidence(row),
    } for row in weak]
    strengths = [{
        "lesson": row["lesson"], "exercise_type": row["exercise_type"],
        "cognitive_level": row["cognitive_level"], "evidence": evidence(row),
    } for row in strong]
    objectives = [{
        "lesson": row["lesson"], "exercise_type": row["exercise_type"],
        "target_cognitive_level": row["cognitive_level"], "priority": round(1 - row["mastery"], 4),
        "recommended_question_count": 4 if index == 0 else 2,
        "reason": f"Mức thành thạo hiện tại {row['mastery']:.0%}.",
    } for index, row in enumerate(weak[:3])]
    mastery = float(profile.get("overall_mastery", .5))
    if not skills:
        mix = {"nhan_biet": 25, "thong_hieu": 50, "van_dung": 20, "van_dung_cao": 5}
        diagnosis = "Chưa có đủ dữ liệu Chương 8 để xác định dạng bài mạnh hoặc yếu."
        explanation = "Em sẽ bắt đầu bằng bài luyện cân bằng để hệ thống hiểu rõ năng lực hiện tại."
    elif mastery < .40:
        mix = {"nhan_biet": 55, "thong_hieu": 30, "van_dung": 10, "van_dung_cao": 5}
        diagnosis = "Kết quả gần đây cho thấy học sinh cần củng cố các kỹ năng nền tảng của Chương 8."
        explanation = "Bài tiếp theo ưu tiên kiến thức nền và tăng dần độ khó theo kết quả của em."
    elif mastery < .60:
        mix = {"nhan_biet": 35, "thong_hieu": 40, "van_dung": 20, "van_dung_cao": 5}
        diagnosis = "Học sinh đang hình thành kiến thức Chương 8 nhưng một số dạng bài chưa ổn định."
        explanation = "Bài tiếp theo củng cố các dạng chưa ổn định bằng câu dễ và trung bình."
    elif mastery < .80:
        mix = {"nhan_biet": 15, "thong_hieu": 35, "van_dung": 35, "van_dung_cao": 15}
        diagnosis = "Học sinh có nền tảng khá và cần tăng luyện tập ở các vùng vận dụng còn yếu."
        explanation = "Bài tiếp theo tăng câu Thông hiểu và Vận dụng, đồng thời vẫn có phần ôn tập."
    else:
        mix = {"nhan_biet": 10, "thong_hieu": 20, "van_dung": 40, "van_dung_cao": 30}
        diagnosis = "Học sinh làm tốt phần lớn nội dung đã quan sát và phù hợp với thử thách cao hơn."
        explanation = "Bài tiếp theo tăng câu Vận dụng và Vận dụng cao nhưng vẫn duy trì kiến thức cũ."
    confidence = min(.90, .30 + profile.get("recent_window", {}).get("answer_count", 0) / 50 * .60)
    return validate_analysis({
        "overall_diagnosis": diagnosis, "confidence": confidence, "strengths": strengths,
        "weaknesses": weaknesses, "next_objectives": objectives,
        "difficulty_mix": mix, "student_explanation": explanation,
    }, profile)


class AIProfileAnalyzer:
    def __init__(self, http_session=None, sleep_fn=None):
        self.session = http_session or requests.Session()
        self.sleep = sleep_fn or time.sleep
        self.url = os.environ.get("AI_ANALYSIS_API_URL", "").strip()
        self.api_key = os.environ.get("AI_ANALYSIS_API_KEY", "").strip()
        self.model = (os.environ.get("AI_ANALYSIS_MODEL", "").strip() or "configured-model")[:120]
        self.provider = (os.environ.get("AI_ANALYSIS_PROVIDER", "openai-compatible").strip() or "openai-compatible")[:80]
        self.timeout = _env_int("AI_ANALYSIS_TIMEOUT_SECONDS", 20, 3, 60)
        self.retries = _env_int("AI_ANALYSIS_RETRIES", 2, 0, 3)
        self.cache_hours = _env_int("AI_ANALYSIS_CACHE_HOURS", 24, 1, 168)
        self.gateway = GeminiAIGateway(http_session=self.session, sleep_fn=self.sleep)

    @property
    def configured(self):
        return bool(self.url)

    @staticmethod
    def _user_prompt(profile):
        return diagnostic.user_prompt(profile)

    def _call_api(self, profile, configuration=None):
        configuration = configuration or self.gateway.legacy_configuration()
        return self.gateway.complete(
            configuration,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": self._user_prompt(profile)},
            ],
            temperature=0, response_format={"type": "json_object"},
        )

    @staticmethod
    def _unavailable_course_identity(course):
        owner_id = getattr(course, "teacher_id", None)
        # Use the current owner's default only.  A retained legacy course
        # mapping can belong to a former teacher and must not identify a new
        # fallback/cache snapshot.
        group = teacher_default_group(owner_id)
        revision = getattr(group, "config_revision", None) if group else None
        if revision is None:
            # No schema change is needed to distinguish unavailable snapshots
            # after course reassignment: negative owner markers occupy the
            # existing revision field and old rows remain untouched.
            revision = -int(owner_id) if owner_id else 0
        return {
            "source": "unavailable",
            "group_id": getattr(group, "id", None),
            "revision": revision,
            "owner_id": owner_id,
            "provider": "gemini-openai-compatible",
            # Teacher routes and their unavailable fallback must share the
            # immutable gateway model identity; the stored legacy group value
            # remains untouched for historical audit rows.
            "model": TEACHER_GEMINI_MODEL if group else "not-configured",
        }

    @staticmethod
    def _safe_error(exc):
        # Validation and configuration messages are local and bounded.  Do
        # not serialize arbitrary exception strings: an unexpected adapter or
        # proxy may echo an upstream body, request headers, or credentials.
        if isinstance(exc, (ValueError, AIConfigurationError, AICooldownError, AIGatewayError)):
            return str(exc or "AI không khả dụng.").replace("\n", " ")[:500]
        return "AI không khả dụng hoặc phản hồi không hợp lệ."

    def analyze(self, student_id, subject="Toán", requested_by=None, force=False, *, course=None, allow_legacy=True):
        profile = build_chapter8_profile(student_id, subject, course_id=course.id if course is not None else None)
        # The packet is populated only for this explicit teacher-triggered run;
        # no background job transmits answer text to an external provider.
        profile["observed_error_evidence"] = [
            row for row in evidence_packet(student_id, subject, course_id=course.id if course is not None else None)
            if str(row.get("curriculum_code") or "").startswith("9C8-i-")
        ]
        def external_error_copy(row):
            statements = [
                {
                    "label": item.get("label"),
                    "curriculum_code": item.get("curriculum_code"),
                    "cognitive_level": item.get("cognitive_level"),
                    "actual": item.get("actual"),
                    "status": "answered",
                    "correct": False,
                }
                for item in row.get("statement_results", [])
                if item.get("status") == "answered" and item.get("correct") is False
            ]
            copied = {
                key: deepcopy(row.get(key)) for key in (
                    "observation_id", "evidence_ref", "submission_id", "answer_id",
                    "question_id", "question_content_hash", "curriculum_code", "topic",
                    "cognitive_level", "error_code", "error_label", "claim",
                    "question_text", "grading_revision",
                )
            }
            if statements:
                copied["wrong_statement_results"] = statements
            else:
                copied["actual_answer"] = deepcopy(row.get("actual_answer"))
            return copied
        error_copy = {
            "schema_version": "chapter6-error-profile-copy-v1",
            "scope": {"course_id": course.id if course is not None else None, "subject": subject, "grade": "9", "chapter_code": "8", "lesson_code": "i", "scope_code": "9C8-i"},
            "observed_error_evidence": [external_error_copy(row) for row in profile["observed_error_evidence"]],
            "limitations": [
                "Chỉ gồm lỗi từ câu đã trả lời và đã chấm.",
                "Không chứa mastery, quota hoặc quyết định chọn câu hỏi.",
                "Rủi ro tương lai là giả thuyết chưa kiểm chứng.",
            ],
        }
        error_copy = diagnostic.enrich_packet(error_copy, student_id, subject, course_id=course.id if course is not None else None)
        configuration = None
        configuration_error = None
        if course is not None:
            try:
                configuration = self.gateway.resolve_course(course, allow_legacy=allow_legacy)
            except AIConfigurationError as exc:
                configuration_error = exc
        else:
            try:
                configuration = self.gateway.legacy_configuration()
            except AIConfigurationError as exc:
                configuration_error = exc
        if configuration is not None:
            identity = {
                "source": configuration.source, "group_id": configuration.group_id,
                "revision": configuration.config_revision, "provider": configuration.provider,
                "model": configuration.model_name, "owner_id": configuration.owner_id,
            }
        elif course is not None:
            identity = self._unavailable_course_identity(course)
        else:
            identity = {"source": "legacy_unavailable", "group_id": None, "revision": None, "provider": self.provider, "model": self.model}
        # Preserve the input-only hash used by legacy direct calls.  Course
        # runs include the group revision so an old fallback cannot survive a
        # later key/model/pause change.
        input_hash = _canonical_hash({"input": error_copy, "ai_configuration": identity}) if course is not None else _canonical_hash(error_copy)
        now = dt.datetime.utcnow()
        cache_query = AIAnalysisRun.query.filter(
            AIAnalysisRun.student_id == student_id,
            AIAnalysisRun.subject == subject,
            AIAnalysisRun.chapter_code == "8",
            AIAnalysisRun.input_hash == input_hash,
            AIAnalysisRun.provider == identity["provider"],
            AIAnalysisRun.model_name == identity["model"],
            AIAnalysisRun.prompt_version == PROMPT_VERSION,
            AIAnalysisRun.status == "completed",
        )
        if course is not None:
            cache_query = cache_query.filter(
                AIAnalysisRun.course_id == course.id,
                AIAnalysisRun.ai_key_group_id == identity["group_id"],
                AIAnalysisRun.ai_config_revision == identity["revision"],
                AIAnalysisRun.ai_credential_source == identity["source"],
            )
        cached = cache_query.order_by(AIAnalysisRun.created_at.desc()).first()
        if cached:
            return cached, True
        status, error = "completed", None
        result = None
        try:
            if configuration_error:
                raise configuration_error
            if not configuration:
                raise RuntimeError("Chưa cấu hình AI cho khóa học này.")
            raw_result = self._call_api(error_copy, configuration)
            result = diagnostic.validate_report(raw_result, error_copy)
            from services.class_lesson4_report import SKILL_NAMES
            if isinstance(result, dict):
                result["skill_names"] = SKILL_NAMES
                for err in result.get("error_analysis", []):
                    ev = err.get("evidence", {})
                    cc = ev.get("curriculum_code")
                    if cc and cc in SKILL_NAMES:
                        ev["skill_name"] = SKILL_NAMES[cc]
        except Exception as exc:
            status, error = "failed", self._safe_error(exc)
            result = None
        run = AIAnalysisRun(
            student_id=student_id, requested_by=requested_by, subject=subject, chapter_code="8",
            course_id=course.id if course is not None else None,
            ai_key_group_id=identity["group_id"], ai_config_revision=identity["revision"],
            ai_credential_source=identity["source"],
            input_hash=input_hash, provider=identity["provider"], model_name=identity["model"],
            prompt_version=PROMPT_VERSION, status=status,
            request_data=json.dumps(error_copy, ensure_ascii=False),
            response_data=json.dumps(result or {}, ensure_ascii=False),
            confidence=(result.get("confidence", 0.0) if isinstance(result, dict) else 0.0),
            schema_version=(result.get("schema_version", "lesson4-diagnostic-report-v1") if isinstance(result, dict) else "lesson4-diagnostic-report-v1"),
            error_message=error, created_at=now,
            expires_at=now + dt.timedelta(hours=self.cache_hours),
        )
        db.session.add(run)
        db.session.commit()
        return run, False
