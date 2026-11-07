def create_ticket(client, description, category="other", priority="P3"):
    response = client.post("/api/v1/tickets", json={
        "title": "Support request for testing",
        "description": description,
        "requester_name": "Jordan Lee",
        "requester_email": "jordan.lee@example.test",
        "category": category,
        "priority": priority,
    })
    assert response.status_code == 201
    return response.json()


def test_ai_assist_suggests_category_and_finds_knowledge(client):
    ticket = create_ticket(
        client,
        "Outlook repeatedly asks for credentials after a password reset. Email cannot be sent.",
        category="other",
        priority="P3",
    )
    article = {
        "slug": "outlook-credential-prompts",
        "title": "Resolve Outlook credential prompts",
        "category": "email",
        "symptoms": "Outlook repeatedly requests credentials after a password reset.",
        "resolution_steps": "Check account status, modern authentication, and webmail access.",
        "owner": "IT Support",
        "published": True,
    }
    created_article = client.post("/api/v1/knowledge", json=article)
    assert created_article.status_code == 201

    response = client.post(
        f"/api/v1/tickets/{ticket['ticket_key']}/ai-assist"
    )
    assert response.status_code == 200
    result = response.json()

    assert result["suggested_category"] == "email"
    assert result["suggested_priority"] == "P3"
    assert result["requires_technician_review"] is True
    assert result["ticket_modified"] is False
    assert result["knowledge_matches"][0]["slug"] == article["slug"]
    assert result["troubleshooting_steps"]


def test_ai_assist_does_not_modify_ticket(client):
    ticket = create_ticket(
        client,
        "Several employees cannot connect to the corporate VPN network.",
        category="other",
        priority="P4",
    )
    response = client.post(
        f"/api/v1/tickets/{ticket['ticket_key']}/ai-assist"
    )
    assert response.status_code == 200

    stored = client.get(f"/api/v1/tickets/{ticket['ticket_key']}").json()
    assert stored["category"] == "other"
    assert stored["priority"] == "P4"
    assert stored["status"] == "new"
    assert response.json()["suggested_category"] == "network"
    assert response.json()["suggested_priority"] == "P2"


def test_ai_assist_returns_404_for_unknown_ticket(client):
    response = client.post("/api/v1/tickets/HD-999999/ai-assist")
    assert response.status_code == 404
