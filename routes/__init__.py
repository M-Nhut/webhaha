"""Route-registration modules.

The application retains Flask's existing endpoint names while route groups are
moved out of the bootstrap module incrementally.
"""

from routes.auth import register_auth_routes
from routes.main import register_main_routes
from routes.academic import register_academic_routes
from routes.curriculum import register_curriculum_routes
from routes.question_bank import register_question_bank_routes
from routes.imports import register_imports_routes
from routes.diagnostics import register_diagnostic_routes
from routes.practice import register_practice_routes
from routes.practice_runtime import register_practice_runtime_routes
from routes.ai_settings import register_ai_settings_routes
from routes.errors import register_error_handlers
from routes.assessments import register_assessment_routes
from routes.ai_reports import register_ai_report_routes


def register_all_routes(app, project_root, is_vercel: bool) -> None:
    """Register route domains while preserving their legacy endpoint names."""
    register_main_routes(app, project_root, is_vercel)
    register_auth_routes(app)
    register_academic_routes(app)
    register_curriculum_routes(app)
    register_question_bank_routes(app)
    register_imports_routes(app)
    register_diagnostic_routes(app)
    register_practice_routes(app)
    register_practice_runtime_routes(app)
    register_assessment_routes(app)
    register_ai_settings_routes(app)
    register_ai_report_routes(app)
    register_error_handlers(app)
