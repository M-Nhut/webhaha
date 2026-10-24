"""Whole-app acceptance preview: synthetic SQLite memory, temporary files, mock AI.

python3 scripts/preview_ui_phase9.py --port 8771
qa_admin / qa_teacher / qa_student / qa_resume: Academy123!
No .env, production DB, uploads or actual provider credentials are used.
"""
from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_ui_phase8 import isolate_phase8_environment, isolate_phase5, seed_data as seed_management, synthetic_providers


def seed_data(db):
    """Extend the retained learning/management fixture with import/editor states."""
    from models import Course, User, ImportSession
    from services.import_service import ImportService
    from services.import_scope import refresh_preview
    from services.id6_metadata import enrich_preview
    from services.assessment_bank import create_bank_draft
    from services.standalone_assessment import save_paper
    from werkzeug.datastructures import FileStorage
    from scripts.preview_ui_phase5 import GENERAL_SOURCE, PAPER_SOURCE, RESEARCH_SOURCE

    data = seed_management(db)
    teacher = db.session.get(User, data['users']['teacher'])
    sessions = {}

    def upload(key, text, bank=None, owner=None):
        session = ImportService.create_and_process_session(owner or teacher.id,
            FileStorage(stream=io.BytesIO(text.encode()), filename='qa-'+key+'.tex'),
            'qa-'+key+'.tex', bank_id=bank)
        if (session.get_scope() or {}).get('document_kind') != 'assessment':
            enrich_preview(session, commit=False)
            refresh_preview(session)
            db.session.commit()
        sessions[key] = session.id
        return session

    upload('general', GENERAL_SOURCE, data['banks']['general'])
    upload('duplicates', GENERAL_SOURCE+'\n'+GENERAL_SOURCE, data['banks']['general'])
    upload('research', RESEARCH_SOURCE, data['banks']['research'])
    paper = upload('paper', PAPER_SOURCE)
    draft = create_bank_draft(teacher, db.session.get(Course, data['courses']['teacher']),
        [data['banks']['general']], selected_ids=[data['questions'][key] for key in
        ('general-single', 'general-tf', 'general-short')],
        budgets={'single':'4', 'true_false':'4', 'short_answer':'2'})
    sessions['bank-paper'] = draft.id
    fields = {'title':'Đề kiểm tra · Bản nháp nghiệm thu giao diện', 'course_id':str(data['courses']['teacher']),
        'duration_minutes':'45', 'action':'draft', 'reviewed':'yes',
        'budget_single':'4', 'budget_true_false':'4', 'budget_short_answer':'2',
        'q0_correct':'0', 'q1_truth0':'1', 'q1_truth1':'0', 'q1_truth2':'1', 'q1_truth3':'0', 'q2_answer':'5'}
    editor = save_paper(db.session.get(ImportSession, paper.id), teacher, fields)
    data['exams']['editor'] = editor.id
    data['sessions'] = sessions
    db.session.commit()
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8771)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='linhedu-phase9-preview-') as directory:
        isolate_phase8_environment(directory)
        from app import app
        from database import db
        from flask import jsonify, Response, abort
        from whitenoise import WhiteNoise
        isolate_phase5(app, directory)
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
        app.config.update(TESTING=False, WTF_CSRF_ENABLED=True, TEMPLATES_AUTO_RELOAD=True)
        app.jinja_env.auto_reload = True
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=str(ROOT/'static'), prefix='static/', autorefresh=True, max_age=0)
        with synthetic_providers():
            with app.app_context(): data = seed_data(db)
            @app.get('/qa/fixture')
            def fixture(): return jsonify(data)
            @app.get('/qa/media/graph.svg')
            def graph():
                return Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="220"><rect width="480" height="220" fill="white"/><path d="M40 160H440M60 200V20" stroke="#596579"/><path d="M90 45Q230 300 370 45" fill="none" stroke="#1d4ed8" stroke-width="3"/></svg>', mimetype='image/svg+xml')
            @app.get('/qa/errors/<int:code>')
            def error_example(code):
                if code not in (400,403,404,405,429,500): abort(404)
                abort(code)
            logging.getLogger('werkzeug').setLevel(logging.ERROR)
            print(f'Synthetic Phase 9 preview http://127.0.0.1:{args.port}/login', flush=True)
            app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False, threaded=False)


if __name__ == '__main__': main()
