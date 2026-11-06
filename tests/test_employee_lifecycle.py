from it_helpdesk.auth import Principal, get_current_principal


def _joiner_payload():
    return {
        "action": "joiner",
        "employee_name": "Taylor Morgan",
        "employee_email": "taylor.morgan@example.test",
        "employee_number": "EMP-2048",
        "target_department": "Finance",
        "target_job_title": "Financial Analyst",
        "target_manager_email": "manager@example.test",
        "effective_date": "2026-12-01",
        "reason": "Approved new hire starting in the Finance department.",
    }


def _approver():
    return Principal(
        subject="99999999-9999-9999-9999-999999999999",
        tenant_id="22222222-2222-2222-2222-222222222222",
        username="lifecycle.approver@example.test",
        email="lifecycle.approver@example.test",
        display_name="Lifecycle Approver",
        roles=frozenset({"Administrator"}),
    )


def test_joiner_request_waits_for_approval_and_has_audit_event(client):
    response = client.post("/api/v1/lifecycle/requests", json=_joiner_payload())
    assert response.status_code == 201
    request = response.json()
    assert request["request_key"] == "JML-000001"
    assert request["status"] == "pending_approval"
    assert request["tasks"] == []
    assert request["events"][-1]["event_type"] == "request_created"


def test_request_creator_cannot_approve_own_lifecycle_request(client):
    created = client.post("/api/v1/lifecycle/requests", json=_joiner_payload())
    request_key = created.json()["request_key"]
    response = client.post(
        f"/api/v1/lifecycle/requests/{request_key}/approve",
        json={"comment": "Reviewed and approved by the administrator."},
    )
    assert response.status_code == 403
    assert "cannot approve" in response.json()["detail"]


def test_distinct_admin_approval_creates_simulation_only_tasks(client):
    created = client.post("/api/v1/lifecycle/requests", json=_joiner_payload())
    request_key = created.json()["request_key"]
    client.app.dependency_overrides[get_current_principal] = _approver
    response = client.post(
        f"/api/v1/lifecycle/requests/{request_key}/approve",
        json={"comment": "HR approval evidence reviewed and verified."},
    )
    assert response.status_code == 200
    request = response.json()
    assert request["status"] == "approved"
    assert len(request["tasks"]) == 4
    assert {task["execution_mode"] for task in request["tasks"]} == {"simulation"}
    assert request["events"][-1]["event_type"] == "approved"


def test_lifecycle_task_completion_closes_request_when_all_tasks_done(client):
    created = client.post("/api/v1/lifecycle/requests", json=_joiner_payload())
    request_key = created.json()["request_key"]
    client.app.dependency_overrides[get_current_principal] = _approver
    approved = client.post(
        f"/api/v1/lifecycle/requests/{request_key}/approve",
        json={"comment": "Second-person approval recorded for the test."},
    ).json()
    client.app.dependency_overrides[get_current_principal] = lambda: Principal(
        subject="88888888-8888-8888-8888-888888888888",
        tenant_id="22222222-2222-2222-2222-222222222222",
        username="helpdesk.tech@example.test",
        email="helpdesk.tech@example.test",
        display_name="Helpdesk Technician",
        roles=frozenset({"Helpdesk.Technician"}),
    )
    current = approved
    for task in current["tasks"]:
        response = client.patch(
            f"/api/v1/lifecycle/requests/{request_key}/tasks/{task['id']}",
            json={"status": "completed", "result": "Simulation reviewed; no external account or access changes were made."},
        )
        assert response.status_code == 200
        current = response.json()
    assert current["status"] == "completed"
    assert all(task["status"] == "completed" for task in current["tasks"])


def test_mover_requires_target_change_and_leaver_forbids_target_fields(client):
    invalid_mover = _joiner_payload() | {"action": "mover", "target_department": None, "target_job_title": None, "target_manager_email": None}
    assert client.post("/api/v1/lifecycle/requests", json=invalid_mover).status_code == 422
    invalid_leaver = _joiner_payload() | {"action": "leaver"}
    assert client.post("/api/v1/lifecycle/requests", json=invalid_leaver).status_code == 422
