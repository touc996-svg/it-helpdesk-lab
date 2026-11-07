from __future__ import annotations

import re
from typing import Any


CATEGORY_KEYWORDS = {
    "security": {
        "phishing", "malware", "ransomware", "virus", "compromised",
        "breach", "suspicious", "unauthorized", "hacked", "security",
    },
    "account_access": {
        "login", "log in", "signin", "sign in", "password", "mfa",
        "locked", "access denied", "authentication", "credential",
    },
    "hardware": {
        "laptop", "desktop", "monitor", "keyboard", "mouse", "printer",
        "battery", "dock", "screen", "hardware", "device",
    },
    "software": {
        "application", "software", "install", "crash", "update",
        "license", "error message", "program",
    },
    "network": {
        "network", "wifi", "wi-fi", "vpn", "internet", "connection",
        "router", "ethernet", "wireless",
    },
    "email": {
        "email", "outlook", "mailbox", "mail", "smtp", "send message",
        "receive message",
    },
}

PRIORITY_RULES = {
    "P1": {
        "ransomware", "data breach", "production down", "entire company",
        "all users", "critical outage", "malware spreading",
        "account compromised", "administrator compromised",
    },
    "P2": {
        "multiple users", "many users", "several users", "several employees", "multiple employees", "business critical",
        "cannot work", "can't work", "unable to work",
        "work is blocked", "major service disruption",
    },
    "P4": {
        "how do i", "how to", "general question", "non-urgent",
        "when convenient", "information request",
    },
}

TROUBLESHOOTING = {
    "security": [
        "Do not click suspicious links or open unexpected attachments.",
        "Preserve relevant emails, timestamps, and security alerts.",
        "Escalate suspected compromise to the security team immediately.",
        "Follow the organization's incident response process; do not declare an incident without evidence.",
    ],
    "account_access": [
        "Confirm the affected username and exact sign-in error.",
        "Check account status and whether the account is locked.",
        "Verify MFA registration and recent password changes.",
        "Review sign-in logs before resetting credentials or changing access.",
    ],
    "hardware": [
        "Confirm the device asset tag and affected hardware component.",
        "Check power, cable, docking, and peripheral connections.",
        "Record any diagnostic error codes and recent changes.",
        "Check warranty or repair status before replacing equipment.",
    ],
    "software": [
        "Record the application name, version, and exact error message.",
        "Check whether the issue affects one user or multiple users.",
        "Review recent updates, installation changes, and application logs.",
        "Test the approved repair or update procedure before reinstalling.",
    ],
    "network": [
        "Confirm whether the issue affects one device, one location, or multiple users.",
        "Check network connection status and approved VPN configuration.",
        "Capture relevant error messages and connection test results.",
        "Escalate suspected infrastructure outages to the network team.",
    ],
    "email": [
        "Confirm whether webmail and the desktop email client are both affected.",
        "Check mailbox access, service status, and the exact error message.",
        "Review recent password or MFA changes if authentication is involved.",
        "Test sending and receiving with a controlled test message.",
    ],
    "other": [
        "Clarify the expected behavior and the actual result.",
        "Record the exact error message and when the issue began.",
        "Check whether other users or devices are affected.",
        "Document troubleshooting steps and the result of each test.",
    ],
}

STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have",
    "has", "been", "after", "before", "when", "what", "where",
    "user", "users", "please", "help", "issue", "problem", "unable",
    "cannot", "into", "your", "their", "they", "them", "our",
}


def _terms(value: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]{3,}", value.lower()))
    return words - STOP_WORDS


def _suggest_category(ticket: dict[str, Any]) -> tuple[str, str, list[str]]:
    text = f"{ticket.get('title', '')} {ticket.get('description', '')}".lower()
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sorted(word for word in keywords if word in text)
        if hits:
            scores[category] = len(hits)
            matched[category] = hits

    if not scores:
        return ticket.get("category", "other"), "low", []

    selected = max(scores, key=scores.get)
    confidence = "high" if scores[selected] >= 3 else "moderate"
    return selected, confidence, matched[selected]


def _suggest_priority(ticket: dict[str, Any]) -> tuple[str, str]:
    text = f"{ticket.get('title', '')} {ticket.get('description', '')}".lower()

    for priority in ("P1", "P2", "P4"):
        matches = [phrase for phrase in PRIORITY_RULES[priority] if phrase in text]
        if matches:
            return priority, (
                f"Matched impact indicators: {', '.join(sorted(matches))}."
            )

    return "P3", (
        "No explicit critical outage, broad business impact, or informational-only "
        "indicator was detected. Review the impact with the requester."
    )


def _find_knowledge_matches(
    ticket: dict[str, Any],
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ticket_terms = _terms(
        f"{ticket.get('title', '')} {ticket.get('description', '')}"
    )
    ticket_category = ticket.get("category")
    ranked = []

    for article in articles:
        if not article.get("published"):
            continue

        article_terms = _terms(
            f"{article.get('title', '')} "
            f"{article.get('symptoms', '')} "
            f"{article.get('resolution_steps', '')}"
        )
        overlap = sorted(ticket_terms & article_terms)
        score = len(overlap)
        if article.get("category") == ticket_category:
            score += 3

        if score > 0:
            ranked.append({
                "slug": article.get("slug"),
                "title": article.get("title"),
                "category": article.get("category"),
                "relevance_score": score,
                "matching_terms": overlap[:8],
                "resolution_steps": article.get("resolution_steps", ""),
            })

    ranked.sort(key=lambda item: item["relevance_score"], reverse=True)
    return ranked[:3]


def analyze_ticket(
    ticket: dict[str, Any],
    articles: list[dict[str, Any]],
) -> dict[str, Any]:
    suggested_category, category_confidence, category_signals = (
        _suggest_category(ticket)
    )
    suggested_priority, priority_reason = _suggest_priority(ticket)

    original_text = (
        f"{ticket.get('title', '')} {ticket.get('description', '')}"
    ).strip()
    summary = original_text[:300]
    if len(original_text) > 300:
        summary += "..."

    category_matches = _find_knowledge_matches(
        {**ticket, "category": suggested_category},
        articles,
    )

    return {
        "ticket_key": ticket.get("ticket_key"),
        "summary": summary,
        "suggested_category": suggested_category,
        "category_confidence": category_confidence,
        "category_signals": category_signals,
        "suggested_priority": suggested_priority,
        "priority_reason": priority_reason,
        "troubleshooting_steps": TROUBLESHOOTING[suggested_category],
        "knowledge_matches": category_matches,
        "engine": "explainable_rules_and_knowledge_retrieval",
        "requires_technician_review": True,
        "ticket_modified": False,
    }
