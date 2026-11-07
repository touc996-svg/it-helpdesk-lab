from __future__ import annotations

from it_helpdesk.database import initialize_database
from it_helpdesk.schemas import KnowledgeArticleCreate
from it_helpdesk.service import create_knowledge_article, list_knowledge_articles


ARTICLES = [
    {
        "slug": "outlook-credential-prompts",
        "title": "Troubleshoot repeated Outlook credential prompts",
        "category": "email",
        "symptoms": "Outlook desktop repeatedly requests credentials or a password after a password reset. Email sending or receiving may fail.",
        "resolution_steps": (
            "Confirm the account is active; verify webmail sign-in; check device date and time; "
            "review saved credential entries under approved policy; test Outlook after approved remediation. "
            "Never collect a user's password or MFA code."
        ),
    },
    {
        "slug": "vpn-connection-troubleshooting",
        "title": "Troubleshoot corporate VPN connection failures",
        "category": "network",
        "symptoms": "VPN cannot connect, remote access fails, or the network connection drops after sign-in.",
        "resolution_steps": (
            "Confirm internet connectivity; verify the approved VPN profile and client version; "
            "record the exact connection error; check whether other users are affected; "
            "escalate suspected gateway outages to the network team."
        ),
    },
    {
        "slug": "account-lockout-and-mfa",
        "title": "Troubleshoot account lockout and MFA sign-in issues",
        "category": "account_access",
        "symptoms": "User cannot log in, account is locked, password is rejected, or MFA prompts fail.",
        "resolution_steps": (
            "Verify the user's identity using the organization's approved process; check account status "
            "and sign-in logs; review MFA registration and recent authentication changes; "
            "use approved unlock or recovery procedures. Never request passwords or MFA codes."
        ),
    },
    {
        "slug": "laptop-hardware-diagnostics",
        "title": "Basic laptop and workstation hardware diagnostics",
        "category": "hardware",
        "symptoms": "Laptop will not power on, battery drains quickly, monitor is blank, or keyboard and dock fail.",
        "resolution_steps": (
            "Record the asset tag; check power adapter, outlet, dock, and cable connections; "
            "note diagnostic lights or error codes; inspect warranty and repair status; "
            "escalate suspected hardware failure before replacing components."
        ),
    },
    {
        "slug": "application-crash-troubleshooting",
        "title": "Troubleshoot application crashes and software errors",
        "category": "software",
        "symptoms": "Application crashes, will not launch, freezes, or reports an error after an update or installation.",
        "resolution_steps": (
            "Record application name, version, and exact error; check scope and recent changes; "
            "review application logs; verify approved updates; test the documented repair procedure "
            "before reinstalling software."
        ),
    },
    {
        "slug": "report-suspicious-email",
        "title": "Report suspicious email and potential phishing",
        "category": "security",
        "symptoms": "Unexpected email, suspicious link, phishing attempt, unexpected MFA request, or suspected compromised account.",
        "resolution_steps": (
            "Do not click links or open attachments; preserve the original message and headers; "
            "record the time and affected account; report through the approved security channel; "
            "follow incident response procedures. Do not label an event confirmed without evidence."
        ),
    },
]


def main() -> None:
    initialize_database()
    existing = {
        item["slug"]
        for item in list_knowledge_articles(published_only=False)
    }

    inserted = 0
    skipped = 0
    for article in ARTICLES:
        if article["slug"] in existing:
            skipped += 1
            continue
        payload = KnowledgeArticleCreate(
            **article,
            owner="IT Support",
            published=True,
        )
        create_knowledge_article(payload)
        inserted += 1

    print(f"Knowledge base seed complete: {inserted} inserted, {skipped} already existed.")
    print("No existing tickets or knowledge articles were modified.")


if __name__ == "__main__":
    main()
