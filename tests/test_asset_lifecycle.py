def asset_payload(tag="LAB-TEST-001"):
    return {
        "asset_tag": tag,
        "hostname": f"{tag.lower()}.example.test",
        "device_type": "laptop",
        "operating_system": "Windows 11",
        "assigned_to": "Demo User",
        "location": "Brooklyn Lab",
        "status": "in_service",
    }


def test_asset_registration_and_audit_history(client):
    response = client.post("/api/v1/assets", json=asset_payload())
    assert response.status_code == 201
    assert response.json()["asset_tag"] == "LAB-TEST-001"

    updated = client.patch(
        "/api/v1/assets/LAB-TEST-001",
        json={
            "assigned_to": "IT Support",
            "location": "Brooklyn Repair Bench",
            "status": "in_repair",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_repair"
    assert updated.json()["assigned_to"] == "IT Support"

    history = client.get("/api/v1/assets/LAB-TEST-001/events")
    assert history.status_code == 200

    event_types = {event["event_type"] for event in history.json()}
    assert event_types == {
        "asset_created",
        "assigned_to_updated",
        "location_updated",
        "status_updated",
    }


def test_retired_asset_cannot_return_to_service(client):
    created = client.post(
        "/api/v1/assets",
        json=asset_payload("LAB-TEST-002"),
    )
    assert created.status_code == 201

    retired = client.patch(
        "/api/v1/assets/LAB-TEST-002",
        json={"status": "retired"},
    )
    assert retired.status_code == 200

    invalid_transition = client.patch(
        "/api/v1/assets/LAB-TEST-002",
        json={"status": "in_service"},
    )
    assert invalid_transition.status_code == 409


def test_duplicate_asset_tag_is_rejected(client):
    payload = asset_payload("LAB-TEST-003")

    assert client.post("/api/v1/assets", json=payload).status_code == 201
    assert client.post("/api/v1/assets", json=payload).status_code == 409


def test_asset_history_returns_404_for_unknown_asset(client):
    response = client.get("/api/v1/assets/DOES-NOT-EXIST/events")
    assert response.status_code == 404


def test_asset_management_page_loads(client):
    response = client.get("/asset-management")
    assert response.status_code == 200
    assert "IT Asset Management" in response.text
    assert "Register device" in response.text
