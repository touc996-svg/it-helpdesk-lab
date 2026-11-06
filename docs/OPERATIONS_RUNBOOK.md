# Operator Runbook

## Ticket priority training targets

| Priority | Example | Target elapsed time |
|---|---|---:|
| P1 | Suspected account compromise or business-wide outage | 4 hours |
| P2 | A user cannot work due to a core service failure | 8 hours |
| P3 | Standard individual incident | 24 hours |
| P4 | Low-impact request or information request | 72 hours |

These are demonstration targets for this lab only. They are not real-world contractual SLAs, and this first version measures elapsed hours rather than business hours.

## Ticket lifecycle

`new → in_progress → waiting_on_user → in_progress → resolved → closed`

A resolved or closed ticket can be moved back to `in_progress` when a requester reports that the issue persists. Cancelled tickets are terminal in this version.

## Required evidence in a ticket

- Impact and scope: one user, one team, site-wide, or organization-wide.
- Start time and relevant error text.
- Troubleshooting actions attempted and their outcomes.
- Device/asset tag when hardware is involved.
- User confirmation before closing a resolved incident.
- Escalation owner and reason when support cannot safely resolve the issue.

## Safety rules

- Never ask for or record passwords, MFA codes, recovery codes, or API keys.
- Confirm identity using an approved process before account changes.
- Do not disable accounts, remove group membership, or wipe devices without documented authorization.
- Keep all sample identities fictional (`example.test`).
