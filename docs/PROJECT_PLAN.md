# Advanced IT Help Desk Lab — Build Plan

## Phase 1 — Service desk foundation (this release)
- Ticket intake and lifecycle transitions.
- Priority-based target response windows (training defaults, not contractual SLAs).
- Assignment, comments, and immutable-style event history (append-only application events).
- Asset inventory and knowledge article catalog.
- API documentation and automated tests.

## Phase 2 — Service desk operator experience
- Streamlit operator console and requester intake form.
- Search, queues, ticket aging, SLA-at-risk reporting, and CSV export.
- Role-aware operator actions; authentication before exposing the service to a network.

## Phase 3 — Windows endpoint support
- Windows 11 ARM workstation or a cloud-hosted Windows client.
- Endpoint diagnostics, event logs, service health, network troubleshooting, and evidence capture.
- Test scenarios for DNS, DHCP, VPN, disk pressure, update failures, and account lockouts.

## Phase 4 — Identity operations
- Active Directory lab domain hosted on an appropriate Windows Server environment.
- Organizational units, security groups, Group Policy, joiner/mover/leaver procedures.
- PowerShell account provisioning with `-WhatIf`, approvals, and audit evidence.

## Phase 5 — Security operations handoff
- MFA and least-privilege checks, endpoint protection, BitLocker status evidence.
- Incident escalation playbooks and mapping of security tickets to a future Microsoft Sentinel SOC lab.

## Hardware and cost guardrails
- The local application is designed to run on a Mac with 8 GB RAM using SQLite.
- Do not run multiple heavyweight VMs locally on the 8 GB machine.
- Use cloud Windows infrastructure only for the AD and Windows Server exercises, start it only for lab sessions, and remove resources when the exercise is over.
- Never use real employee data, production credentials, or real corporate domains in the lab.
