"""Public Flask route contract for the supported application surface."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

# Keep this test isolated from a developer's local database when it is the
# first test module to import the application.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.pop("POSTGRES_URL", None)
os.environ["FLASK_SECRET_KEY"] = "route-contract-isolated-test-session"
os.environ["AI_CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

import config
config.load_local_environment = lambda *args, **kwargs: None

_storage = tempfile.TemporaryDirectory(prefix="route-contract-tests-")
with patch.object(config, "upload_directories", return_value={
    "UPLOAD_FOLDER_AVATARS": f"{_storage.name}/avatars",
    "UPLOAD_FOLDER_COURSES": f"{_storage.name}/courses",
}):
    from app import app


CONTRACT_PATH = Path(__file__).with_name("fixtures") / "route_contract.json"


def current_route_contract() -> list[dict[str, object]]:
    """Return stable route data; implicit HEAD/OPTIONS are Flask internals."""
    return sorted(
        (
            {
                "endpoint": rule.endpoint,
                "methods": sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"}),
                "rule": rule.rule,
            }
            for rule in app.url_map.iter_rules()
            if rule.endpoint != "static"
        ),
        key=lambda item: (str(item["rule"]), str(item["endpoint"])),
    )


class RouteContractTests(unittest.TestCase):
    def test_public_routes_match_the_supported_contract(self):
        expected = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(current_route_contract(), expected)
