# Trello Skill

A portable agent skill and dependency-free Python CLI for **Spaces → Initiatives → Milestones → Tasks → To-dos**. No vendor-specific runtime, account IDs, or credentials are bundled.

Initiative/project descriptions provide durable shared context with default sections for What it is, Purpose and audience, How it works, Context and relationships, and Resources. Keep progress, proposals, selected milestones, next steps and handoff notes in linked milestone/task cards or dated comments; the project column records commitment state. Follow the [workflow](references/workflow.md) for portable-link rules.

## Install

```sh
git clone https://github.com/copilotzhq/trello-skill.git
cd trello-skill
python3 scripts/trello.py --help
```

For an agent host supporting `SKILL.md`, place or register this entire directory in its skill location (installation paths vary by host). Otherwise instruct the agent to read `SKILL.md` and provide terminal access. Installing files does not automatically grant Trello access.

Supply `TRELLO_API_KEY` and `TRELLO_TOKEN` through your host's secret environment mechanism. See [authentication](references/authentication.md). Then:

```sh
python3 scripts/trello.py boards
python3 scripts/trello.py lists BOARDID
python3 scripts/trello.py cards LISTID
```

## Contents

- `SKILL.md`: agent operating instructions.
- `scripts/setup.py`: configuration-driven, read-only preview and explicit `--apply` provisioning.
- `scripts/trello.py`: JSON CLI for cards, labels, copies and checklists.
- `references/`: setup, workflow, authentication, command and safety guides.
- `templates/`: reusable Space, initiative, milestone and task descriptions.
- `tests/`: offline transport and command tests.

[Set up the configured boards](references/setup.md), then follow the [workflow](references/workflow.md). Boards and labels are configurable conventions, not hardcoded account resources.

## Tests and limits

```sh
python3 -m unittest discover -s tests -v
```

The setup script can create boards/lists, labels, guides and templates additively; it is not a migration tool.

Tests are offline mocks, not a certification of every Trello operation. This packaged CLI's expanded copy/label/checklist command set has not been live-tested as a whole. JSON output contains private board data. Lists are API-returned collections, not guaranteed exhaustive exports; labels return at most 100. No pagination loop, bulk migration, native template flag, member assignment, due-date editing, delete/archive command, webhooks or automatic execution is included. Configure those unsupported fields in Trello's UI. No third-party Python dependencies are required.
