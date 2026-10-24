"""Reproduce diagnostic creation on a disposable copy of the real database."""
from pathlib import Path
from tempfile import TemporaryDirectory
from collections import Counter
from random import Random
import argparse
import hashlib
import json
import os
import sqlite3
import sys



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    original = args.database.resolve()
    output = args.output.resolve()
    if output == original:
        parser.error('--output must differ from the source database')
    checksum = hashlib.sha256(original.read_bytes()).hexdigest()
    with TemporaryDirectory(prefix='fnweb-common-transfer-') as tmp:
        snapshot = Path(tmp) / 'snapshot.db'
        with sqlite3.connect(original.as_uri() + '?mode=ro', uri=True) as source, sqlite3.connect(snapshot) as target:
            source.backup(target)
        os.environ['DATABASE_URL'] = f'sqlite:///{snapshot}'
        os.environ.pop('POSTGRES_URL', None)
        sys.path.insert(0, str(project))
        import config
        config.load_local_environment = lambda *a, **kw: None
        import services.database_startup as startup
        startup.initialize_database = lambda: None
        from app import app
        from database import db
        from flask import g
        from models import Course, QuestionBank, Exam, DiagnosticAssignment, User, Enrollment
        from routes.diagnostics import _diagnostic_question_ready
        from services.diagnostic_service import (
            common_diagnostic_selection, common_item_hash, diagnostic_assignment_is_eligible,
            class_diagnostic_source, learner_profile_state,
        )
        from services.source_resolver import resolve_class_banks, resolve_class_questions, validate_exam_source
        from services.practice_blueprint import TYPE_QUOTAS, SKILLS
        from services.personalization_evidence import bank_question_content_hash
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        results = []
        def client_for(user_id):
            g.pop('_login_user', None)
            client = app.test_client()
            with client.session_transaction() as session:
                session['_user_id'] = str(user_id)
                session['_fresh'] = True
            return client
        with app.app_context():
            for index, course in enumerate(Course.query.filter_by(is_active=True).order_by(Course.id).all(), 1):
                banks = [bank for bank in QuestionBank.query.filter_by(is_active=True, subject=course.subject).all()
                         if resolve_class_banks(course, [bank.id])['valid']]
                for bank_index, bank in enumerate(banks, 1):
                    pool = [q for q in resolve_class_questions(course, [bank.id], bank.questions)['questions']
                            if _diagnostic_question_ready(q)]
                    seeds, targets = [], set()
                    for seed in range(10):
                        selection = common_diagnostic_selection(pool, rng=Random(seed))
                        assert selection['status'] == 'ready', (seed, selection['status'], selection['shortages'])
                        assert len(selection['questions']) == 22
                        assert Counter(q.difficulty_level for q in selection['questions']) == selection['level_targets']
                        assert Counter(q.question_type for q in selection['questions']) == TYPE_QUOTAS
                        assert len({q.content_hash or bank_question_content_hash(q) for q in selection['questions']}) == 22
                        targets.add(tuple(sorted(t['target_skill'] for t in selection['recovery']['skill_transfers'])))
                        seeds.append(dict(seed=seed, status=selection['status'], count=22,
                                          quota_changes=selection['recovery']['quota_changes']))
                    before = {exam.id for exam in Exam.query.all()}
                    teacher = client_for(course.teacher_id)
                    response = teacher.post('/diagnostics/new', data={
                        'course_id': course.id, 'question_bank_id': bank.id,
                    }, follow_redirects=True)
                    assert response.status_code == 200
                    exam = Exam.query.filter(~Exam.id.in_(before)).one()
                    assert exam.assessment_purpose == 'initial_diagnostic'
                    assert validate_exam_source(exam, require_live=True)['valid']
                    assignments = DiagnosticAssignment.query.filter_by(exam_id=exam.id).all()
                    assert assignments
                    assert {a.common_item_hash for a in assignments} == {common_item_hash(exam)}
                    student_checks = []
                    for assignment in assignments:
                        assert diagnostic_assignment_is_eligible(assignment, exam)
                        assert class_diagnostic_source(assignment.student_id, course)['status'] == 'ready'
                        # Existing learner history may already initialize a profile.
                        state = learner_profile_state(assignment.student_id, course.subject, course_id=course.id)
                        assert state['status'] in ('initialized', 'diagnostic_required')
                        student_response = client_for(assignment.student_id).get(f'/practice/{exam.id}/take')
                        assert student_response.status_code == 200
                        student_checks.append(dict(assignment_eligible=True, source_ready=True, take_http_status=200))
                    recovery = exam.get_adaptive_metadata()['diagnostic']['recovery']
                    results.append(dict(class_reference=f'class-{index:02d}', bank_reference=f'bank-{bank_index:02d}',
                        eligible_questions=len(pool), post_http_status=response.status_code,
                        selected_count=len(exam.questions), actual_levels=dict(Counter(q.difficulty_level for q in exam.questions)),
                        actual_types=dict(Counter(q.question_type for q in exam.questions)),
                        unavailable_skills=recovery['unavailable_skills'], covered_skill_count=recovery['covered_skill_count'],
                        quota_changes=recovery['quota_changes'], skill_transfers=recovery['skill_transfers'],
                        source_manifest_valid=True, cohort_has_identical_frozen_hash=True, students=student_checks,
                        seeded_runs=seeds, distinct_receiving_skill_combinations=len(targets)))
            db.session.remove()
            db.engine.dispose()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == checksum
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(production_database_unchanged=True, tested_on_disposable_database_copy=True,
        ai_called=False, results=results), ensure_ascii=False, indent=2))
    print(json.dumps(dict(production_database_unchanged=True, results=[{
        **{key: item[key] for key in ('class_reference', 'eligible_questions', 'selected_count', 'actual_levels',
           'actual_types', 'unavailable_skills', 'quota_changes', 'distinct_receiving_skill_combinations')},
        'students_opened':len(item['students']), 'seeded_runs_ready':len(item['seeded_runs'])} for item in results]), ensure_ascii=False))


if __name__ == "__main__":
    main()
