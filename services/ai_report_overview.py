"""Read-only overview statistics from complete, server-owned answer events."""

from collections import Counter

from services.class_lesson4_report import SKILL_NAMES

OUTCOMES = ("correct", "wrong", "partial")


def event_counts(events):
    counts = Counter(event.get("outcome") for event in events)
    result = {key: counts[key] for key in OUTCOMES}
    result["total"] = sum(result.values())
    result["correct_percent"] = round(result["correct"] * 100 / result["total"], 1) if result["total"] else None
    result["submission_count"] = len({event.get("submission_id") for event in events if event.get("submission_id")})
    return result


def build_overview(observed, *, student_id=None, skill="", source="", question_type=""):
    """Never calculate a class denominator from the truncated external AI copy."""
    rows, all_events = [], []
    for student in observed.get("students", []):
        if student_id is not None and student.get("student_id") != student_id:
            continue
        events = []
        seen = set()
        for original in student.get("observed_events", []):
            ref = original.get("event_ref")
            if ref and ref in seen:
                continue
            seen.add(ref)
            if skill and original.get("curriculum_code") != skill:
                continue
            if source and original.get("assessment_source") != source:
                continue
            if question_type and original.get("question_type") != question_type:
                continue
            if original.get("outcome") not in OUTCOMES:
                continue
            event = {**original, "student_id": student.get("student_id"), "display_name": student.get("display_name", "Học sinh")}
            events.append(event)
        wrong_skills = Counter(event.get("curriculum_code") or "unknown"
                               for event in events if event.get("outcome") == "wrong")
        focus_skill = min(wrong_skills, key=lambda code: (-wrong_skills[code], code)) if wrong_skills else None
        rows.append({
            "student_id": student.get("student_id"), "student_ref": student.get("student_ref"),
            "display_name": student.get("display_name", "Học sinh"), **event_counts(events),
            "focus_skill": focus_skill,
        })
        all_events.extend(events)
    names = {**SKILL_NAMES, **observed.get("skill_names", {})}
    codes = sorted(set(names) | {event.get("curriculum_code") or "unknown" for event in all_events})
    by_skill = [
        {"code": code, "name": names.get(code, "Chưa phân loại"),
         **event_counts([event for event in all_events if (event.get("curriculum_code") or "unknown") == code])}
        for code in codes if not skill or code == skill
    ]
    return {
        "counts": event_counts(all_events), "by_skill": by_skill,
        "students": sorted(rows, key=lambda row: (row["display_name"], row["student_id"] or 0)),
        "students_with_data": sum(bool(row["total"]) for row in rows), "roster_count": len(rows),
        "events": all_events, "unit": "lượt trả lời câu hỏi",
        "filters": {"skill": skill, "source": source, "question_type": question_type},
    }


def report_sections(report, *, student_id=None):
    """Adapt persisted class output; absent new fields stay absent on old runs."""
    if not report:
        return None
    if student_id is None:
        section = report.get("class_summary") or {}
    else:
        section = next((row for row in report.get("students", []) if row.get("student_id") == student_id), {})
    return {
        "summary": section.get("ai_summary", []),
        "causes": section.get("cause_hypotheses", []),
        "risks": section.get("next_risk_hypotheses", []),
        "recommendations": [row if isinstance(row, dict) else {"text": str(row), "basis_evidence_refs": []}
                            for row in section.get("recommendations", [])],
        "progress": section.get("observed_progress_recovery", []),
    }


def personal_archive_sections(report):
    """Keep the earlier per-paper diagnostic readable without merging its scope."""
    if not report.get("overall_diagnosis") and report.get("schema_version") != "lesson4-diagnostic-report-v1":
        return None
    return {
        "summary": report.get("overall_diagnosis", ""),
        "target_submission_id": report.get("target_submission_id"),
        "errors": [{"hypothesis": row.get("cause_hypothesis", ""),
                    "statement_label": row.get("statement_label"), "evidence": row.get("evidence", {})}
                   for row in report.get("error_analysis", [])],
        "risks": [row for row in report.get("future_risks", report.get("future_error_risks", []))
                  if row.get("hypothesis")], "recommendations": report.get("interventions", []),
    }
