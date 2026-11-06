from pathlib import Path


def test_employee_lifecycle_dashboard_is_served(client):
    response = client.get("/employee-lifecycle")
    assert response.status_code == 200
    assert "Employee Lifecycle Operations" in response.text
    assert "Simulation mode" in response.text
    assert "/static/auth.bundle.js" in response.text
