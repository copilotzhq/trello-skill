# Setup and template installation

Read existing boards, lists and labels first. Confirm workspace, scope and names; reuse only unambiguous matches. Do not bulk rename, relocate or overwrite user content. Back up private state outside the repository if needed.

This CLI does not create boards/lists. In Trello's UI, create or adapt:
- My Projects: Ideas, Active, Maintaining, Paused, Retired.
- My Milestones: Planned, In Progress, In Review, Achieved, Paused.
- My Tasks: Backlog, To-Do, Doing, Blocked, In Review, Done.

Names can differ; discover actual IDs. Make new boards private by default unless the user requests otherwise and inspect visibility afterward. Add `Templates & Guide` to each. Put a guide card there summarizing the corresponding section of workflow.md and linking the other boards. Preserve existing initiative statuses; populate unknown values as To define rather than guessing commitments.

Create reusable cards (commands run from repository root, credentials already injected):

```sh
python3 scripts/trello.py create PROJECTTEMPLATELIST --name '[TEMPLATE] Initiative — copy me' --desc "$(cat templates/initiative.md)" --yes
python3 scripts/trello.py create MILESTONETEMPLATELIST --name '[TEMPLATE] Milestone — copy me' --desc "$(cat templates/milestone.md)" --yes
python3 scripts/trello.py create TASKTEMPLATELIST --name '[TEMPLATE] Task — copy me' --desc "$(cat templates/task.md)" --yes
python3 scripts/trello.py create-checklist TASKTEMPLATEID --name 'To-dos' --yes
python3 scripts/trello.py add-checklist-item CHECKLISTID --name 'Clarify outcome and constraints' --yes
python3 scripts/trello.py add-checklist-item CHECKLISTID --name 'Execute the agreed work' --yes
python3 scripts/trello.py add-checklist-item CHECKLISTID --name 'Verify acceptance criteria' --yes
python3 scripts/trello.py add-checklist-item CHECKLISTID --name 'Report result and evidence' --yes
python3 scripts/trello.py create-checklist MILESTONETEMPLATEID --name 'Acceptance criteria' --yes
```

Replace every placeholder ID with values discovered from reads or returned by creation. Inspect for existing objects before repeating commands: these POSTs are not idempotent. Fill milestone criteria per milestone, not a generic box that implies achievement.

These are copyable cards, not native template badges. Convert via Make template in Trello's UI if desired. For a new assignment, copy the approved card, inspect it, fill acceptance/boundaries, link parents and select labels. Never execute the template placeholders as actual work.
