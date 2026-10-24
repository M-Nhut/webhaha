"""Read-only summaries of the teacher-authorized, finalized class attempts."""
from models import LearningHistory
from services.personalization_evidence import is_finalized
from services.practice_blueprint import LEVELS


def summarize_learning(submissions, subject):
    from adaptive_engine import AdaptiveEngine
    attempts = [item for item in submissions if is_finalized(item) and item.exam.course.subject == subject
                and item.exam.assessment_purpose != 'standalone']
    ids = [item.id for item in attempts]
    rows = LearningHistory.query.filter(LearningHistory.submission_id.in_(ids)).all() if ids else []
    rows = [row for row in rows if row.answer_status in ('answered', 'graded')]
    overall = AdaptiveEngine._aggregate(rows, lambda _: 'all').get('all', {})
    cognitive = AdaptiveEngine._aggregate(rows, lambda row: row.cognitive_level)
    topics = AdaptiveEngine._aggregate(rows, lambda row: row.topic)
    from services.practice_evidence import learning_rows, practice_skill_matrix
    result = dict(overall_mastery=overall.get('mastery', 0), overall_interpretation='Kết quả từ các bài đã chấm' if rows else 'Chưa có dữ liệu',
                  answer_count=len(rows), cold_start=len(rows)<3, cold_start_min_answers=3,
                  total_attempts=len(attempts), topic_mastery=topics, cognitive_mastery=cognitive,
                  weak_regions=[], practice_skill_mastery=practice_skill_matrix(learning_rows(attempts)))
    for level in LEVELS:
        result[level + '_accuracy'] = round(cognitive[level]['mastery']*100,1) if level in cognitive else None
    return result
