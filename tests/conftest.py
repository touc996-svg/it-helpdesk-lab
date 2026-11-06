from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from it_helpdesk.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HELPDESK_DB_PATH", str(tmp_path / "helpdesk-test.db"))
    with TestClient(app) as test_client:
        yield test_client
