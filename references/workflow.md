# Three boards, four levels

## Projects: continuous initiatives
Ideas → Active → Maintaining → Paused → Retired.
Active means deliberate investment, Maintaining means support/upkeep, Paused means intentionally not receiving work, Retired means no longer pursued. These are commitment states, not a mandatory sequence. Keep purpose stable and current focus explicit. Review weekly; do not invent deadlines or health assessments.

## Milestones: meaningful achieved states
Planned → In Progress → In Review → Achieved; Paused for deferred outcomes.
Title: `[Initiative] Achieved state`. Require observable evidence. A milestone can remain unmet even after all contributing tasks complete. Link parent initiative and contributing tasks. No arbitrary percent-complete claims based on card counts.

## Tasks: independently manageable assignments
Backlog → To-Do → Doing → Blocked → In Review → Done.
Backlog is uncommitted; To-Do is executable; Doing is actual work; Blocked names dependency, next unblock action and review date; In Review awaits verification; Done meets acceptance with evidence. Blocking is an exception, not a required stage. Use modest per-executor work-in-progress limits; list ordering expresses initial priority.

Title: `[Initiative] Verb + concrete outcome`. A task is an execution brief, not every agent action. To-dos are native checklist steps. Split a step into a card only when independent ownership, approval, priority, deadline or substantial scope warrants it. Checklists may change; acceptance criteria do not silently change.

## Labels and other fields
- Projects/Milestones: organizational or product-family labels, e.g. Business A, Business B (user-defined).
- Tasks: functional labels, e.g. DEV, FIN, SALES, MKT, CS; clarify meanings with the user.
- Columns encode status. Do not duplicate status with labels. Health is a brief evidence-backed note, not a family label. Urgent is optional and rare.
- Labels are board-local IDs even when names match. Preserve existing meanings/colors; do not silently correct ambiguous acronyms.
- Members identify accountable humans; executor text can identify an agent. Dates are real commitments, not priority substitutes. Configure members/dates in UI where CLI lacks support.
- Link related cards both ways without copying task status. Comments hold dated decisions and evidence. Archive older records natively in UI; an Archived column is not native archival.

Example: an ongoing Service initiative has milestone `Read/write integration verified`; task `Implement and verify the integration`; checklist steps build, test, inspect, document. Do not create duplicate task and milestone objects when one level adds no useful management.
