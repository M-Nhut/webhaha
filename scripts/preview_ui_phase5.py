"""Phase 5 preview using disposable database/files and synthetic accounts.

python3 scripts/preview_ui_phase5.py --port 8767
qa_teacher / qa_admin / qa_student, password Academy123!
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_ui_phase4 import isolate_environment, isolate_storage, seed_data as seed_banks

GENERAL_SOURCE = r'''% @grade: 10
\section*{Phương trình và phép tính}
\begin{ex}%[10C4Ni-1T]
Cho $a=1$. Giá trị $a+1$ là
\choice{\True $2$}{$3$}{$4$}{$5$}
\loigiai{Vì $a=1$ nên $a+1=2$.}
\end{ex}
\begin{ex}%[10C4Hi-2D]
Cho $x=2$. Xét các phát biểu sau.
\choiceTF{\True $x$ là số chẵn.}{$x=3$.}{\True $x^2=4$.}{$x<0$.}
\loigiai{Thay $x=2$ vào từng phát biểu.}
\end{ex}
\begin{ex}%[10C4Ni-3S]
Tính $2+3$.
\shortans{5}
\loigiai{$2+3=5$.}
\end{ex}'''

PAPER_SOURCE = r'''\section*{Phần I. Trắc nghiệm}
\begin{ex}Giá trị $1+1$ là\choice{\True $2$}{$3$}{$4$}{$5$}\loigiai{$1+1=2$.}\end{ex}
\begin{ex}Xét các ý sau.\choiceTF{\True Một cộng một bằng hai.}{Một cộng một bằng ba.}{\True Hai là số chẵn.}{Hai là số lẻ.}\end{ex}
\begin{ex}Điền kết quả $2+3$.\shortans{5}\end{ex}'''

RESEARCH_SOURCE = r'''\begin{ex}%[9C8Ni-1T]
Gieo một xúc xắc cân đối. Xác suất số chấm chẵn là
\choice{\True $1/2$}{$1/3$}{$1/4$}{$1$}
\loigiai{Có ba kết quả thuận lợi trong sáu kết quả.}
\end{ex}'''


def isolate_phase5(app, directory):
    isolate_storage(app, directory)
    from services import import_duplicates, latex_renderer
    latex_renderer.ASSET_DIR = Path(directory) / 'static/uploads/questions'
    import_duplicates.ROOT = Path(directory)
    # The source-download routes resolve from app.root_path. Copy only public
    # example documents, never configuration, uploads or production databases.
    for name in ('cautrucde.tex', 'docs/examples/de_kiem_tra_ex.tex', 'docs/examples/ngan_hang_nhieu_chu_de.tex'):
        target = Path(directory) / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)


def seed_data(db):
    from models import Course, QuestionBank, User
    from services.import_service import ImportService
    from services.import_scope import refresh_preview
    from services.id6_metadata import enrich_preview
    from services.assessment_bank import create_bank_draft
    from werkzeug.datastructures import FileStorage
    data = seed_banks(db)
    teacher = db.session.get(User, data['users']['teacher'])
    course = Course.query.filter_by(teacher_id=teacher.id).one()
    other_course = Course(course_name='Lớp thuộc giáo viên khác', subject='Toán', teacher_id=data['users']['other'])
    db.session.add(other_course)
    db.session.commit()
    data['courses'] = {'teacher': course.id, 'foreign': other_course.id}
    partial_bank = QuestionBank(name='Học liệu bổ sung · Kiểm tra nhập một phần', subject='Toán', grade='10',
        topic='Phương trình và phép tính', created_by=teacher.id, visibility='private', is_active=True)
    db.session.add(partial_bank)
    db.session.commit()
    data['banks']['partial'] = partial_bank.id
    sessions = {}

    def upload(key, source, *, bank=None, owner=None):
        session = ImportService.create_and_process_session(owner or teacher.id,
            FileStorage(stream=io.BytesIO(source.encode()), filename=key + '.tex'), key + '.tex', bank_id=bank)
        if (session.get_scope() or {}).get('document_kind') != 'assessment':
            enrich_preview(session, commit=False)
            refresh_preview(session)
            db.session.commit()
        sessions[key] = session.id
        return session

    # An exact pair and a new row exercise partial receipts and in-file choices.
    upload('general', GENERAL_SOURCE, bank=data['banks']['general'])
    upload('duplicates', GENERAL_SOURCE + '\n' + GENERAL_SOURCE, bank=data['banks']['general'])
    upload('research', RESEARCH_SOURCE, bank=data['banks']['research'])
    upload('paper', PAPER_SOURCE)
    upload('foreign', GENERAL_SOURCE, bank=data['banks']['foreign'], owner=data['users']['other'])
    incomplete = GENERAL_SOURCE.replace(r'\shortans{5}', r'\shortans{}')
    upload('incomplete', incomplete, bank=data['banks']['partial'])
    draft = create_bank_draft(teacher, course, [data['banks']['general']],
        selected_ids=[data['questions'][name] for name in ('general-single', 'general-tf', 'general-short')],
        budgets={'single': '4', 'true_false': '4', 'short_answer': '2'})
    sessions['bank-paper'] = draft.id
    data['sessions'] = sessions
    data['sources'] = {'general': GENERAL_SOURCE, 'paper': PAPER_SOURCE, 'research': RESEARCH_SOURCE}
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='linhedu-ui-phase5-') as directory:
        isolate_environment(directory)
        from app import app
        from database import db
        from flask import Response, jsonify, request, send_from_directory
        from whitenoise import WhiteNoise
        isolate_phase5(app, directory)
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
        app.wsgi_app = WhiteNoise(app.wsgi_app, root=str(ROOT / 'static'), prefix='static/', autorefresh=True, max_age=0)
        app.config.update(TESTING=False, WTF_CSRF_ENABLED=True, TEMPLATES_AUTO_RELOAD=True)
        app.jinja_env.auto_reload = True
        with app.app_context():
            data = seed_data(db)

        @app.before_request
        def preview_media():
            if request.path.startswith('/static/uploads/questions/'):
                path = Path(directory) / request.path.lstrip('/')
                if path.is_file() and path.resolve().is_relative_to(Path(directory).resolve()):
                    return send_from_directory(path.parent, path.name)

        @app.get('/qa/fixture')
        def fixture_info():
            return jsonify(data)

        @app.get('/qa/media/graph.svg')
        def graph():
            return Response('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="220" viewBox="0 0 480 220"><rect width="480" height="220" fill="white"/><path d="M40 185H440M60 200V20" stroke="#596579" stroke-width="2"/><path d="M90 45Q230 345 370 45" fill="none" stroke="#1d4ed8" stroke-width="3"/><text x="435" y="210" font-family="Arial" font-size="15">x</text><text x="40" y="24" font-family="Arial" font-size="15">y</text></svg>', mimetype='image/svg+xml')

        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        print(f'Synthetic Phase 5 preview: http://127.0.0.1:{args.port}/login', flush=True)
        app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False, threaded=False)


if __name__ == '__main__':
    main()
