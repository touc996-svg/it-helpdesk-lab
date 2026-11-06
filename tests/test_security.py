from it_helpdesk.auth import Principal, get_current_principal
from it_helpdesk.main import app


def principal_with(*roles):
    return Principal(
        subject="11111111-1111-1111-1111-111111111111",
        tenant_id="22222222-2222-2222-2222-222222222222",
        username="security.test@example.test",
        display_name="Security Test",
        roles=frozenset(roles),
    )


def test_health_is_public_but_api_requires_bearer(client):
    client.app.dependency_overrides.clear()
    assert client.get("/health").status_code == 200
    response = client.get("/api/v1/assets")
    assert response.status_code == 401


def test_requester_cannot_read_asset_inventory(client):
    client.app.dependency_overrides[get_current_principal] = lambda: principal_with("Helpdesk.Requester")
    response = client.get("/api/v1/assets")
    assert response.status_code == 403


def test_technician_cannot_register_asset(client):
    client.app.dependency_overrides[get_current_principal] = lambda: principal_with("Helpdesk.Technician")
    response = client.post("/api/v1/assets", json={
        "asset_tag": "SEC-1001",
        "hostname": "sec-1001.example.test",
        "device_type": "laptop",
        "operating_system": "macOS",
    })
    assert response.status_code == 403


def test_asset_manager_registration_uses_verified_identity_for_audit(client):
    client.app.dependency_overrides[get_current_principal] = lambda: principal_with("Asset.Manager")
    response = client.post("/api/v1/assets", json={
        "asset_tag": "SEC-1002",
        "hostname": "sec-1002.example.test",
        "device_type": "laptop",
        "operating_system": "macOS",
    })
    assert response.status_code == 201
    events = client.get("/api/v1/assets/SEC-1002/events")
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "asset_created"
    assert events.json()[0]["actor"] == "security.test@example.test [oid:11111111-1111-1111-1111-111111111111]"
