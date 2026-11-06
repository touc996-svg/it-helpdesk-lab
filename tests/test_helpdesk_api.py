def create_sample_ticket(client):
    response = client.post("/api/v1/tickets", json={
        "title": "Cannot access company email",
        "description": "Outlook prompts for credentials repeatedly after password reset.",
        "requester_name": "Jordan Lee",
        "requester_email": "jordan.lee@example.test",
        "category": "email",
        "priority": "P2",
    })
    assert response.status_code == 201
    return response.json()


def test_health_and_empty_summary(client):
    assert client.get("/health").json()["status"] == "healthy"
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["total_tickets"] == 0
    assert summary["open_tickets"] == 0


def test_create_ticket_sets_key_sla_and_initial_audit_event(client):
    ticket = create_sample_ticket(client)
    assert ticket["ticket_key"] == "HD-000001"
    assert ticket["status"] == "new"
    assert ticket["priority"] == "P2"
    events = client.get(f"/api/v1/tickets/{ticket['ticket_key']}/events").json()
    assert len(events) == 1
    assert events[0]["event_type"] == "ticket_created"


def test_ticket_status_workflow_and_invalid_transition(client):
    ticket = create_sample_ticket(client)
    key = ticket["ticket_key"]

    updated = client.patch(
        f"/api/v1/tickets/{key}",
        json={"status": "in_progress", "assigned_to": "helpdesk.agent"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    invalid = client.patch(
        f"/api/v1/tickets/{key}",
        json={"status": "closed"},
    )
    assert invalid.status_code == 409
    assert "Invalid status transition" in invalid.json()["detail"]


def test_ticket_comment_is_audited(client):
    ticket = create_sample_ticket(client)
    key = ticket["ticket_key"]
    response = client.post(f"/api/v1/tickets/{key}/comments", json={
        "comment": "Asked the requester to test Outlook on the web.",
    })
    assert response.status_code == 200
    events = client.get(f"/api/v1/tickets/{key}/events").json()
    assert events[-1]["event_type"] == "comment"
    assert "Outlook on the web" in events[-1]["details"]


def test_ticket_filters_and_priority_validation(client):
    create_sample_ticket(client)
    assert len(client.get("/api/v1/tickets?priority=P2").json()) == 1
    assert client.get("/api/v1/tickets?priority=urgent").status_code == 422


def test_asset_inventory_rejects_duplicate_hostnames(client):
    payload = {
        "asset_tag": "LAP-1001",
        "hostname": "NYC-LT-1001",
        "device_type": "laptop",
        "operating_system": "Windows 11",
        "assigned_to": "Jordan Lee",
        "location": "New York",
    }
    assert client.post("/api/v1/assets", json=payload).status_code == 201
    duplicate = {**payload, "asset_tag": "LAP-1002"}
    assert client.post("/api/v1/assets", json=duplicate).status_code == 409


def test_knowledge_base_published_filter(client):
    draft = {
        "slug": "outlook-credential-loop",
        "title": "Resolve Outlook credential prompts",
        "category": "email",
        "symptoms": "Outlook repeatedly requests credentials.",
        "resolution_steps": "Verify account status, confirm modern authentication, and test webmail.",
        "owner": "IT Support",
        "published": False,
    }
    assert client.post("/api/v1/knowledge", json=draft).status_code == 201
    assert client.get("/api/v1/knowledge").json() == []
    assert len(client.get("/api/v1/knowledge?include_unpublished=true").json()) == 1
