from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from it_helpdesk.auth import Principal, get_current_principal
from it_helpdesk.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HELPDESK_DB_PATH", str(tmp_path / "helpdesk-test.db"))
    principal = Principal(
        subject="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        username="test.operator@example.test",
        display_name="Test Operator",
        roles=frozenset({
            "Helpdesk.Requester", "Helpdesk.Technician", "Asset.Manager",
            "Auditor", "Administrator",
        }),
    )
    app.dependency_overrides[get_current_principal] = lambda: principal
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
