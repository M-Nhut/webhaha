"""Read-only real-class source checks on a temporary SQLite snapshot.

No learner profile, provider credentials, AI calls or production writes.
Neutral skill/level targets test source feasibility, not learning effectiveness.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import os
import sqlite3
import sys
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project, original = args.project.resolve(), args.database.resolve()
    if args.output.resolve() == original:
        parser.error('--output must differ from the source database')
    checksum = hashlib.sha256(original.read_bytes()).hexdigest()
    with TemporaryDirectory(prefix='fnweb-source-phase3-') as tmp:
        snapshot = Path(tmp)/'snapshot.db'
        with sqlite3.connect(original.as_uri()+'?mode=ro', uri=True) as source, sqlite3.connect(snapshot) as target:
            source.backup(target)
        os.environ['DATABASE_URL'] = f'sqlite:///{snapshot}'
        os.environ.pop('POSTGRES_URL', None)
        sys.path.insert(0, str(project))
        import config
        config.load_local_environment = lambda *a, **kw: None
        # Inspect the actual snapshot as-is: do not seed, backfill or migrate it.
        import services.database_startup as startup
        startup.initialize_database = lambda: None
        from app import app
        from models import Course, QuestionBank
        from services.source_resolver import resolve_class_banks, resolve_class_questions
        from services.practice_blueprint import LEVELS, SKILLS, TYPE_QUOTAS, readiness_error
        from services.question_policy import bank_question_ready
        from services.personalization_evidence import bank_question_content_hash
        from services.practice_recovery import select_resilient
        from services.practice_selector import select_fixed, skill_targets
        from services.practice_source_inventory import build_source_inventory
        from services import aptga
        result = []
        with app.app_context():
            for index, course in enumerate(Course.query.filter_by(is_active=True).order_by(Course.id).all(), 1):
                ids = [b.id for b in QuestionBank.query.filter_by(is_active=True, subject=course.subject).all()
                       if resolve_class_banks(course, [b.id])['valid']]
                resolved = resolve_class_questions(course, ids) if ids else {'valid': False, 'questions': []}
                rejected, ranked = Counter(), []
                for q in resolved['questions']:
                    if q.adaptive_excluded or not bank_question_ready(q):
                        rejected['excluded_or_not_ready'] += 1
                        continue
                    reason = readiness_error(q)
                    if reason:
                        rejected[reason] += 1
                        continue
                    if q.chapter not in (None, '', '8') or q.section not in (None, '', 'i'):
                        rejected['outside_scope'] += 1
                        continue
                    ranked.append(dict(question=q, skill=q.curriculum_node.canonical_code,
                                       fingerprint=q.content_hash or bank_question_content_hash(q),
                                       score=0, exposure_tier=0, exposure_count=0))
                levels = aptga.allocate(22, {})[0]
                skills = skill_targets({})
                cases = [('actual_source_neutral_profile', ranked),
                         ('simulated_missing_first_skill', [x for x in ranked if x['skill'] != SKILLS[0]]),
                         ('simulated_missing_vdc', [x for x in ranked if x['question'].difficulty_level != LEVELS[-1]]),
                         ('simulated_missing_true_false', [x for x in ranked if x['question'].question_type != 'true_false']),
                         ('simulated_duplicate_content', [{**x, 'fingerprint':'same'} for x in ranked])]
                outcomes = []
                for name, pool in cases:
                    strict, _, strict_status = select_fixed(pool, levels, skills)
                    selected, shortages, status, audit = select_resilient(pool, levels, skills)
                    if selected:
                        assert Counter(x['question'].difficulty_level for x in selected) == levels
                        assert Counter(x['question'].question_type for x in selected) == TYPE_QUOTAS
                        assert len({x['fingerprint'] for x in selected}) == 22
                        actual_skills = Counter(x['skill'] for x in selected)
                        assert all(1 <= actual_skills[skill] <= 5 for skill in {x['skill'] for x in pool})
                    assert audit['effective_level_targets'] == levels
                    outcomes.append(dict(case=name, candidate_count=len(pool), status=status,
                                         strict_status=strict_status, strict_count=len(strict),
                                         selected_count=len(selected), actual_levels=dict(Counter(x['question'].difficulty_level for x in selected)),
                                         actual_types=dict(Counter(x['question'].question_type for x in selected)),
                                         effective_levels=audit['effective_level_targets'],
                                         level_targets_preserved=audit['level_targets_preserved'],
                                         quota_changes=audit['quota_changes'], covered_skills=audit['covered_skill_count'],
                                         unavailable_skills=audit['unavailable_skills'],
                                         skill_transfers=audit['skill_transfers'], exposure_stage=audit['exposure_stage'],
                                         shortages=shortages))
                result.append(dict(class_reference=f'class-{index:02d}', authorized_bank_count=len(ids),
                                   scoped_question_count=len(resolved['questions']), approved_count=len(ranked),
                                   rejection_counts=dict(rejected), inventory=build_source_inventory(ranked),
                                   outcomes=outcomes))
        assert hashlib.sha256(original.read_bytes()).hexdigest() == checksum
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(kind='real_class_sources_neutral_profile_and_simulated_stress',
        production_database_unchanged=True, snapshot_seeded_or_migrated=False,
        learner_profiles_used=False, ai_called=False, classes=result), ensure_ascii=False, indent=2))
    print(json.dumps([dict(class_reference=c['class_reference'], approved=c['approved_count'],
        outcomes=[dict(case=x['case'],status=x['status'],count=x['selected_count']) for x in c['outcomes']])
        for c in result], ensure_ascii=False))


if __name__ == '__main__':
    main()
