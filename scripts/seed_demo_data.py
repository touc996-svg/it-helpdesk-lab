from __future__ import annotations

from it_helpdesk.database import initialize_database
from it_helpdesk.schemas import AssetCreate, KnowledgeArticleCreate, TicketCreate
from it_helpdesk.service import create_asset, create_knowledge_article, create_ticket, dashboard_summary


def main() -> None:
    initialize_database()
    summary = dashboard_summary()
    if summary["total_tickets"] or summary["tracked_assets"] or summary["published_articles"]:
        print("Demo data not inserted: this database already contains records.")
        print("Use a fresh HELPDESK_DB_PATH to create a clean demo dataset.")
        return

    samples = [
        TicketCreate(
            title="VPN connection fails after password reset",
            description="Requester can sign in locally but the corporate VPN rejects the new credentials.",
            requester_name="Jordan Lee", requester_email="jlee@example.test",
            category="network", priority="P2",
        ),
        TicketCreate(
            title="Outlook repeatedly prompts for credentials",
            description="Outlook desktop requests credentials every few minutes; webmail remains accessible.",
            requester_name="Morgan Diaz", requester_email="mdiaz@example.test",
            category="email", priority="P3",
        ),
        TicketCreate(
            title="Request access to finance shared folder",
            description="New team member needs read-only access to the finance project share.",
            requester_name="Taylor Chen", requester_email="tchen@example.test",
            category="account_access", priority="P4",
        ),
        TicketCreate(
            title="Suspected account compromise",
            description="Requester reports an unexpected MFA prompt and a sign-in notification they do not recognize.",
            requester_name="Jordan Lee", requester_email="jlee@example.test",
            category="security", priority="P1",
        ),
    ]
    for ticket in samples:
        create_ticket(ticket)

    create_asset(AssetCreate(
        asset_tag="LAP-1001", hostname="NYC-LT-1001", device_type="laptop",
        operating_system="Windows 11", assigned_to="Jordan Lee", location="New York",
    ))
    create_asset(AssetCreate(
        asset_tag="LAP-1002", hostname="NYC-LT-1002", device_type="laptop",
        operating_system="Windows 11", assigned_to="Morgan Diaz", location="New York",
    ))
    create_knowledge_article(KnowledgeArticleCreate(
        slug="outlook-credential-prompts", title="Troubleshoot repeated Outlook credential prompts",
        category="email", symptoms="Outlook desktop repeatedly requests a password.",
        resolution_steps=(
            "Confirm the account is active; verify that the user can sign in to webmail; "
            "check device date and time; review credential manager entries under approved policy; "
            "test Outlook after the approved remediation. Never collect the user's password or MFA code."
        ), owner="IT Support", published=True,
    ))

    print("Inserted synthetic ATLAS Help Desk demo records.")
    print(dashboard_summary())


if __name__ == "__main__":
    main()
