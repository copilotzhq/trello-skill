# Spaces, projects, milestones and tasks

## Spaces: durable context
Spaces are durable company, personal or collaboration context cards. A Space is distinct from a native Trello Workspace; it is organizational context, not a claim of legal or intellectual-property ownership.

Use the hierarchy `Space → Project → Milestone → Task → native checklist to-dos` when those levels add useful context. A project links one primary Space. Milestones inherit that Space through their sole parent project; tasks inherit it unless they explicitly record cross-space context. A standalone task may link a Space directly. Spaces do not need health, current-focus, milestone, next-action or other transient fields; keep changing progress and handoffs on milestone/task cards or in dated comments.

Space descriptions should cover What it is, Purpose, People and relationships, Projects and Resources. Use verified canonical remote links and the portable-link rules below.

## Projects: continuous initiatives
Ideas → Active → Maintaining → Paused → Retired.
Use the project description as durable shared context for another agent, with these default sections: What it is, Purpose and audience, How it works, Context and relationships, and Resources. Link one primary Space from the project context. Keep progress, proposals, selected milestones, next steps and handoff notes in linked milestone/task cards or dated comments. The project column is its commitment state; do not duplicate that state in the description.
Active means deliberate investment, Maintaining means support/upkeep, Paused means intentionally not receiving work, Retired means no longer pursued. These are commitment states, not a mandatory sequence. A paused or maintaining project does not need a resume condition or health field in its description.

Use canonical remote Git links in shared cards. Verify the repository URL and ref before linking; use branch or tag URLs for navigation, immutable commit URLs for evidence, and PR, issue, artifact or live-product URLs when useful. Do not put absolute or repo-relative filesystem paths in shared cards. Private repository links are fine for authorized collaborators; never change access or expose secrets. If work exists only locally or has not been published, record that remote evidence is unavailable rather than inventing a link.

## Milestones: meaningful achieved states
Planned → In Progress → In Review → Achieved; Paused for deferred outcomes.
Title: `[Project] Achieved state`. Every milestone has exactly one parent project/initiative and inherits that project's sole parent Space; standalone Space milestones are not used. The description must include `## Parent project`, a well-specified `## Target state` to be achieved, a mandatory `## Target date`, and `## Success evidence`. Set the native Trello due date as the canonical target time; the human-readable target date must agree with it. Keep execution tasks centralized on My Tasks; milestone cards do not maintain task links. Link verified remote evidence where available, including immutable commits or review/artifact links. No arbitrary percent-complete claims based on card counts.

## Tasks: independently manageable assignments
Backlog → To-Do → Doing → Blocked → In Review → Done.
Backlog is uncommitted; To-Do is executable; Doing is actual work; Blocked names dependency, next unblock action and review date; In Review awaits verification; Done meets acceptance with evidence. Blocking is an exception, not a required stage. Use modest per-executor work-in-progress limits; list ordering expresses initial priority.

Title: `[Project or Space] Verb + concrete outcome`. A task is an execution brief, not every agent action. Inherit the parent project's Space; a standalone task may link a Space directly. To-dos are native checklist steps. Split a step into a card only when independent ownership, approval, priority, deadline or substantial scope warrants it. Checklists may change; task done-when criteria do not silently change.

## Labels and other fields
- Projects/Milestones: organizational or product-family labels, e.g. Business A, Business B (user-defined).
- Tasks: functional labels, e.g. DEV, FIN, SALES, MKT, CS; clarify meanings with the user.
- Columns encode status. Do not duplicate status with labels or project-description fields. Put health and review notes in dated comments or the relevant milestone/task card. Urgent is optional and rare.
- Labels are board-local IDs even when names match. Preserve existing meanings/colors; do not silently correct ambiguous acronyms.
- Members identify accountable humans; executor text can identify an agent. Dates are real commitments, not priority substitutes. Configure members/dates in UI where CLI lacks support.
- Link the parent project and relevant context without copying task status. Keep task records centralized on My Tasks. Comments hold dated decisions and evidence. Archive older records natively in UI; an Archived column is not native archival.

Example: an ongoing Service initiative has milestone `Read/write integration verified`; task `Implement and verify the integration`; checklist steps build, test, inspect, document. Do not create duplicate task and milestone objects when one level adds no useful management.
