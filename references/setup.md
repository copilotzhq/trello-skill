# Setup and template installation

Read existing boards, lists, and labels first. Confirm workspace ID, scope, and board names; reuse only unambiguous matches. Do not bulk rename, relocate, or overwrite existing user content. Back up private state outside the repository if needed.

## Portable shared context

Initiative/project descriptions provide durable context for agents and collaborators. Use the default sections What it is; Purpose and audience; How it works; Context and relationships; and Resources. Keep progress, proposals, selected milestones, next steps, handoff notes and review details in linked milestone/task cards or dated comments. The project column records commitment state. Follow the [workflow](workflow.md) for portable-link rules. When rewriting an existing project description, preserve useful transient information in a concise dated comment and do not invent commitments.

Spaces are an optional fourth board for durable company, personal or collaboration context. A Space card is separate from a native Trello Workspace and does not imply legal or intellectual-property ownership. Projects link one primary Space. Every milestone has exactly one parent project and inherits that project's Space; standalone Space milestones are not used. Tasks inherit their parent project's Space unless they record explicit cross-space context; standalone tasks may link a Space directly.

Two setup paths are available:
1. **Automated configuration-driven setup** via `scripts/setup.py` (recommended for reproducible multi-board provisioning).
2. **Manual CLI / UI setup** using `scripts/trello.py` and Trello's web interface.

---

## 1. Automated Setup (`scripts/setup.py`)

`scripts/setup.py` provides an idempotent, configuration-driven setup that:
- Validates workspace ID and board definitions before making network calls.
- Runs in **preview mode** (read-only) by default to inspect planned additions.
- Requires explicit `--apply` to perform writes.
- Creates missing boards as `private` in the specified workspace.
- Supports the optional `spaces` role with `Active`, `Inactive`, and `Templates & Guide` lists.
- Preserves existing boards, lists, cards, and ordering (additive-only).
- Re-reads board state before writing lists, labels, cards, and checklists to avoid duplicate objects.
- Creates the dedicated `Templates & Guide` list, guide cards, and copyable template cards with native checklists.

### Usage

1. Copy the example configuration:
   ```sh
   cp config.example.json config.local.json
   ```
2. Edit `config.local.json` with your verified `workspaceId` (found via `python3 scripts/trello.py boards`) and desired board names/lists/labels.
3. Run preview mode (read-only):
   ```sh
   python3 scripts/setup.py --config config.local.json
   ```
4. Inspect the output plan. If satisfied, apply the changes:
   ```sh
   python3 scripts/setup.py --config config.local.json --apply
   ```
5. Rerunning with `--apply` is idempotent: if all objects exist, zero writes are made.

To preview or apply only the configured Spaces board, use `--only spaces`:
```sh
python3 scripts/setup.py --config config.local.json --only spaces
python3 scripts/setup.py --config config.local.json --only spaces --apply
```
The `--only` filter scopes planning and writes to the selected roles. Unknown roles fail before network activity, and `--only spaces` requires an explicit `spaces` entry in the config. Legacy configs that omit `spaces` continue to target the original three boards; `config.example.json` includes the opt-in Spaces role.

---

## 2. Manual CLI Setup (`scripts/trello.py`)

If creating boards manually or adapting existing boards in Trello's UI:
- **Spaces**: `Active`, `Inactive`.
- **My Projects**: `Ideas`, `Active`, `Maintaining`, `Paused`, `Retired`.
- **My Milestones**: `Planned`, `In Progress`, `In Review`, `Achieved`, `Paused`.
- **My Tasks**: `Backlog`, `To-Do`, `Doing`, `Blocked`, `In Review`, `Done 🎉`.

Names can differ; discover actual IDs first:
```sh
python3 scripts/trello.py boards
python3 scripts/trello.py lists BOARD_ID
```

Add `Templates & Guide` as the rightmost list on each board. Then create reusable template cards:
```sh
python3 scripts/trello.py create PROJECT_TEMPLATES_LIST_ID --name '[TEMPLATE] Initiative — Ongoing Overview (copy me)' --desc "$(cat templates/initiative.md)" --yes
python3 scripts/trello.py create MILESTONE_TEMPLATES_LIST_ID --name '[TEMPLATE] Milestone — Achieved State (copy me)' --desc "$(cat templates/milestone.md)" --yes
python3 scripts/trello.py create TASK_TEMPLATES_LIST_ID --name '[TEMPLATE] Task — Execution Brief (copy me)' --desc "$(cat templates/task.md)" --yes
python3 scripts/trello.py create SPACE_TEMPLATES_LIST_ID --name '[TEMPLATE] Space — Context & Purpose (copy me)' --desc "$(cat templates/space.md)" --yes

# Add native checklists to templates
python3 scripts/trello.py create-checklist TASK_TEMPLATE_CARD_ID --name 'To-dos' --yes
python3 scripts/trello.py add-checklist-item TASK_CHECKLIST_ID --name 'Clarify outcome and constraints' --yes
python3 scripts/trello.py add-checklist-item TASK_CHECKLIST_ID --name 'Execute the agreed work' --yes
python3 scripts/trello.py add-checklist-item TASK_CHECKLIST_ID --name 'Verify against Done when' --yes
python3 scripts/trello.py add-checklist-item TASK_CHECKLIST_ID --name 'Report result and evidence' --yes

python3 scripts/trello.py create-checklist MILESTONE_TEMPLATE_CARD_ID --name 'Success evidence' --yes
python3 scripts/trello.py add-checklist-item MILESTONE_CHECKLIST_ID --name 'Define success evidence before committing' --yes
```

### Copyable Cards vs Native Badges
These cards are clearly titled `[TEMPLATE] ... (copy me)` and designed to be copied directly in Trello. The REST API does not provide a reliable programmatic `isTemplate` badge setter. Users who prefer Trello's native template badge can click **Make template** in the card's action menu in the Trello UI.

## Safety, matching and recovery limits

Preview is a fresh read-only plan, not a saved transaction. Apply recomputes the plan and checks for remaining additions afterward. New-board privacy must read back as private. Existing board privacy, descriptions, positions and label colors are not normalized or overwritten.

Exact names identify managed objects; existing guide/template cards with the expected titles are reused even elsewhere on the board. Confirm these matches before applying. Renaming a managed object can make a later run propose a replacement. Archived objects are excluded. Changing template files does not overwrite existing card descriptions. Custom columns do not rewrite the generic guide's status explanations; adapt guides manually.

A failed write may have succeeded. Inspect state, then preview again: missing template checklists/items are included in recovery plans without recreating completed objects. There is no rollback, server-side lock, or concurrency guarantee; run one setup writer at a time. Do not run automatically as a background retry job.

Reads are not a certified exhaustive export. Label collections reaching the 100-item limit stop setup for manual review; other collections depend on API-returned scope. Offline fake-API tests cover fresh creation, repeat-run zero writes, partial-write recovery and validation. This generic setup has not been live-tested end-to-end and was not run against the user's existing boards during development.
