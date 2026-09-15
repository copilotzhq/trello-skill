"""Idempotent, configuration-driven Trello board setup.

Reads a JSON configuration specifying workspace and board definitions,
previews or applies additions, creates private boards when absent, adds missing
lists, labels, guide cards, and copyable template cards with native checklists.

Supports partial-failure rerun recovery: checks existing cards for missing
checklists and missing checklist items before executing additions.

Default mode is preview (read-only). Pass --apply to perform writes.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# Ensure scripts/ is in import path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trello import Client, ClientError, identifier

GUIDE_LIST_NAME = "Templates & Guide"
ID_RE = re.compile(r'^[A-Za-z0-9]{1,64}$')


def load_template_file(rel_path):
    p = REPO_DIR / rel_path
    if not p.exists():
        raise ClientError(f'Required template file missing: {rel_path}')
    return p.read_text(encoding='utf-8')


PROJECT_GUIDE = """# Using the Initiatives Board

This board holds continuous initiatives, products or projects.
Use each project description as durable shared context that another agent can understand without chat history.

## Project description
- What it is: identity and durable scope.
- Purpose and audience: why it matters and who benefits or uses it.
- How it works: durable architecture, workflow or operating model.
- Context and relationships: stakeholders, boundaries, dependencies and stable relationships to related initiatives or projects.
- Resources: verified canonical remote links, relevant durable milestone/task cards and other durable sources.

Link each project to one primary Space. Keep progress, proposals, selected milestones, next steps and handoff notes in linked milestone/task cards or dated comments. The project column is the commitment state; do not duplicate it in the description.

For shared resources, verify the repository URL and ref. Use branch/tag links for navigation, immutable commit links for evidence, and PR/issue/artifact/live-product links where useful. Do not use local filesystem paths or invent links for unpublished work; note when remote evidence is unavailable.

## Columns
- Ideas: Uncommitted possibilities.
- Active: Receiving deliberate investment toward a current outcome.
- Maintaining: Supported and kept healthy; upkeep rather than active feature work.
- Paused: Intentionally not receiving work; record any resume proposal in a milestone/task card or dated comment.
- Retired: Concluded or replaced; kept for reference.

When rewriting an existing project description, preserve useful transient information in a concise dated comment. Do not invent progress, commitments, dates or evidence.
"""

MILESTONE_GUIDE = """# Using the Milestones Board

A milestone is a meaningful achieved state, not a task checklist.

Every milestone has exactly one parent project/initiative. It inherits that project's sole parent
Space; do not create a standalone Space milestone.

## Required description
- Parent project: link exactly one project/initiative card.
- Target state to be achieved: describe the well-specified, observable state the milestone will achieve.
- Target date: include a required `## Target date` as `YYYY-MM-DD` in the description.
- Success evidence: state the verifiable evidence that proves the target state was achieved.

Set the native Trello due date as the canonical target time. The human-readable `## Target date`
in the description is required and must agree with that native due date.

## Columns
- Planned: Target state agreed, not yet started.
- In Progress: Actively being pursued.
- In Review: Target state reached, verification/evidence being evaluated.
- Achieved: Target state and success evidence verified.
- Paused: Deferred; record the reason on the milestone card or in a dated comment.

Keep execution tasks centralized on the My Tasks board; milestone cards do not maintain task links or task status. Use verified remote links for success evidence where available.
"""

TASK_GUIDE = """# Using the Tasks Board

This board holds bounded, independently manageable task assignments for humans or agents.

## Columns
- Backlog: Captured work, not yet prioritized or clarified.
- To-Do: Ready to start; outcome, context, and done-when criteria defined.
- Doing: Actively being executed.
- Blocked: Cannot proceed; record waiting-on dependency and unblock action.
- In Review: Work delivered, verification/acceptance underway.
- Done 🎉: Acceptance criteria verified with recorded evidence.

Link the parent project and milestone when present; a standalone task may link a Space directly. Tasks inherit the parent project's Space unless explicit cross-space context is recorded. Use the native To-dos checklist on the card for editable execution steps. Link canonical remote evidence when available.
"""

SPACE_GUIDE = """# Using the Spaces Board

A Space card is durable company, personal or collaboration context. It is separate from a native Trello Workspace and is organizational context, not a claim of legal or intellectual-property ownership.

## Relationships
- Link each project to one primary Space.
- Every milestone has exactly one parent project and inherits that project's Space; standalone Space milestones are not used.
- A task inherits its parent project's Space unless it explicitly records cross-space context; a standalone task may link a Space directly.

Keep the Space description durable: identity, purpose, people and relationships, associated projects and resources. Put changing progress, proposals, next steps and handoffs in milestone/task cards or dated comments.

## Columns
- Active: Context currently in use.
- Inactive: Context retained for reference or not currently in use.

Use verified canonical remote links for resources. Do not use local filesystem paths or invent links for unpublished work; note when remote evidence is unavailable.
"""

ROLE_ORDER = ['spaces', 'projects', 'milestones', 'tasks']

BOARD_SPECS = {
    'spaces': {
        'default_name': 'Spaces',
        'default_lists': ['Active', 'Inactive'],
        'guide_title': '[GUIDE] Using Spaces Board',
        'guide_desc': SPACE_GUIDE,
        'template_title': '[TEMPLATE] Space — Context & Purpose (copy me)',
        'template_rel': 'templates/space.md',
        'checklist_name': None,
        'checklist_items': []
    },
    'projects': {
        'default_name': 'My Projects',
        'default_lists': ['Ideas', 'Active', 'Maintaining', 'Paused', 'Retired'],
        'guide_title': '[GUIDE] Using Initiatives Board',
        'guide_desc': PROJECT_GUIDE,
        'template_title': '[TEMPLATE] Initiative — Ongoing Overview (copy me)',
        'template_rel': 'templates/initiative.md',
        'checklist_name': None,
        'checklist_items': []
    },
    'milestones': {
        'default_name': 'My Milestones',
        'default_lists': ['Planned', 'In Progress', 'In Review', 'Achieved', 'Paused'],
        'guide_title': '[GUIDE] Using Milestones Board',
        'guide_desc': MILESTONE_GUIDE,
        'template_title': '[TEMPLATE] Milestone — Achieved State (copy me)',
        'template_rel': 'templates/milestone.md',
        'checklist_name': 'Success evidence',
        'checklist_items': ['Define success evidence before committing']
    },
    'tasks': {
        'default_name': 'My Tasks',
        'default_lists': ['Backlog', 'To-Do', 'Doing', 'Blocked', 'In Review', 'Done 🎉'],
        'guide_title': '[GUIDE] Using Tasks Board',
        'guide_desc': TASK_GUIDE,
        'template_title': '[TEMPLATE] Task — Execution Brief (copy me)',
        'template_rel': 'templates/task.md',
        'checklist_name': 'To-dos',
        'checklist_items': [
            'Clarify outcome and constraints',
            'Execute the agreed work',
            'Verify against Done when',
            'Report result and evidence'
        ]
    }
}


def unique_names(items):
    names = [x.get('name') for x in items if x.get('name')]
    if len(names) != len(set(names)):
        raise ClientError('Ambiguous duplicate names; inspect manually.')


def resolve_roles(cfg, selected_roles=None):
    boards_cfg = cfg.get('boards', {})
    if selected_roles is None:
        return [role for role in ROLE_ORDER
                if role != 'spaces' or 'spaces' in boards_cfg]

    if isinstance(selected_roles, str):
        selected_roles = [selected_roles]
    else:
        selected_roles = list(selected_roles)
    if not selected_roles:
        raise ClientError('--only requires at least one board role.')

    requested = []
    for value in selected_roles:
        if not isinstance(value, str):
            raise ClientError('Selected board roles must be strings.')
        for role in value.split(','):
            role = role.strip()
            if not role:
                raise ClientError('--only contains an empty board role.')
            if role not in BOARD_SPECS:
                raise ClientError(f'Unknown board role selected with --only: "{role}".')
            if role == 'spaces' and 'spaces' not in boards_cfg:
                raise ClientError('The "spaces" role requires an explicit spaces configuration.')
            if role in requested:
                raise ClientError(f'Duplicate board role selected with --only: "{role}".')
            requested.append(role)

    return [role for role in ROLE_ORDER if role in requested]


def validate_config(cfg, selected_roles=None):
    if not isinstance(cfg, dict):
        raise ClientError('Config must be a JSON object.')

    workspace_id = cfg.get('workspaceId')
    if not workspace_id or not isinstance(workspace_id, str):
        raise ClientError('Config must specify a valid "workspaceId" string.')
    workspace_id = workspace_id.strip()
    if 'YOUR_' in workspace_id or not ID_RE.fullmatch(workspace_id):
        raise ClientError('Config "workspaceId" contains an invalid or placeholder value.')

    boards_cfg = cfg.get('boards', {})
    if not isinstance(boards_cfg, dict):
        raise ClientError('"boards" in config must be an object.')

    if set(boards_cfg) - set(BOARD_SPECS):
        raise ClientError('Unknown board role.')
    roles = resolve_roles(cfg, selected_roles)

    # Check for duplicate board target IDs or names across the selected roles.
    seen_ids = set()
    seen_names = set()
    for role in roles:
        b = boards_cfg.get(role, {})
        if not isinstance(b, dict):
            raise ClientError(f'Config for board "{role}" must be an object.')
        bid = b.get('id')
        if bid is not None:
            if not isinstance(bid, str) or not ID_RE.fullmatch(bid.strip()):
                raise ClientError(f'Invalid board id format for role "{role}".')
            clean_bid = bid.strip()
            if clean_bid in seen_ids:
                raise ClientError(f'Duplicate board id across roles: "{role}" targets already used board.')
            seen_ids.add(clean_bid)
        name = b.get('name')
        if name is not None and not isinstance(name, str):
            raise ClientError('Board name must be a string.')
        effective_name = str(name).strip() if name is not None else BOARD_SPECS[role]['default_name']
        if not effective_name:
            raise ClientError(f'Board name for "{role}" cannot be empty.')
        if effective_name in seen_names:
            raise ClientError(f'Duplicate board name across roles: "{role}" uses "{effective_name}" already targeted.')
        seen_names.add(effective_name)

        # Validate lists schema if present
        if 'lists' in b:
            if not isinstance(b['lists'], list) or not b['lists']:
                raise ClientError(f'"lists" for role "{role}" must be a non-empty list of strings.')
            seen_list_names = set()
            for item in b['lists']:
                if not isinstance(item, str) or not item.strip():
                    raise ClientError(f'List names in "{role}" must be non-empty strings.')
                clean_item = item.strip()
                if clean_item == GUIDE_LIST_NAME or clean_item != item:
                    raise ClientError('List name is reserved or has surrounding whitespace.')
                if clean_item in seen_list_names:
                    raise ClientError(f'Duplicate list name "{clean_item}" in board "{role}".')
                seen_list_names.add(clean_item)

        # Validate labels schema if present
        if 'labels' in b:
            if not isinstance(b['labels'], list):
                raise ClientError(f'"labels" for role "{role}" must be a list of objects.')
            seen_label_names = set()
            for item in b['labels']:
                if not isinstance(item, dict):
                    raise ClientError(f'Label entries in "{role}" must be objects with "name" and "color".')
                lname = item.get('name')
                lcolor = item.get('color')
                if not isinstance(lname, str) or not lname.strip():
                    raise ClientError(f'Label name in "{role}" must be a non-empty string.')
                if not isinstance(lcolor, str) or not lcolor.strip():
                    raise ClientError(f'Label color in "{role}" must be a non-empty string.')
                clean_lname = lname.strip()
                if clean_lname in seen_label_names:
                    raise ClientError(f'Duplicate label name "{clean_lname}" in board "{role}".')
                seen_label_names.add(clean_lname)

    # Validate that required template files exist on disk before network activity
    for role in roles:
        rel = BOARD_SPECS[role]['template_rel']
        load_template_file(rel)


def inspect_target_board(client, role, b_cfg, workspace_id, all_boards):
    explicit_id = b_cfg.get('id')
    target_name = (b_cfg.get('name') or BOARD_SPECS[role]['default_name']).strip()

    if explicit_id:
        bid = explicit_id.strip()
        board_data = client.request('GET', f'/boards/{bid}', {'fields': 'name,closed,idOrganization,prefs'})
        if board_data.get('closed'):
            raise ClientError(f'Target board for "{role}" is closed.')
        if board_data.get('idOrganization') != workspace_id:
            raise ClientError(f'Target board for "{role}" belongs to another workspace, not expected workspace.')
        return board_data, False

    # Lookup by name within workspace
    matching = [
        b for b in all_boards
        if not b.get('closed') and b.get('idOrganization') == workspace_id and b.get('name') == target_name
    ]
    if len(matching) > 1:
        raise ClientError(f'Multiple open boards named "{target_name}" found in workspace. Specify explicit "id" in config.')
    if len(matching) == 1:
        bid = matching[0]['id']
        board_data = client.request('GET', f'/boards/{bid}', {'fields': 'name,closed,idOrganization,prefs'})
        return board_data, False

    # Does not exist -> needs creation
    return {'name': target_name, 'idOrganization': workspace_id, 'is_new': True}, True


def build_plan(client, cfg, workspace_id, selected_roles=None):
    validate_config(cfg, selected_roles)
    roles = resolve_roles(cfg, selected_roles)
    all_boards = client.request('GET', '/members/me/boards', {'filter': 'open', 'fields': 'name,closed,idOrganization'})
    boards_cfg = cfg.get('boards', {})

    actions = []
    board_targets = {}

    for role in roles:
        b_cfg = boards_cfg.get(role, {})
        spec = BOARD_SPECS[role]
        board_info, is_new = inspect_target_board(client, role, b_cfg, workspace_id, all_boards)
        if not is_new:
            if board_info.get('closed') or board_info.get('idOrganization') != workspace_id:
                raise ClientError('Target board changed workspace or closed.')
            if any(v[0].get('id') == board_info['id'] for v in board_targets.values()):
                raise ClientError('Multiple roles resolve to the same board.')
        board_targets[role] = (board_info, is_new)

        if is_new:
            actions.append({
                'type': 'create_board',
                'role': role,
                'name': board_info['name'],
                'workspaceId': workspace_id,
                'permissionLevel': 'private'
            })
            desired_lists = b_cfg.get('lists', spec['default_lists'])
            for lname in desired_lists:
                actions.append({'type': 'create_list', 'role': role, 'board': board_info['name'], 'name': lname})
            actions.append({'type': 'create_list', 'role': role, 'board': board_info['name'], 'name': GUIDE_LIST_NAME})

            labels = b_cfg.get('labels', [])
            for lbl in labels:
                actions.append({'type': 'create_label', 'role': role, 'board': board_info['name'], 'name': lbl['name'], 'color': lbl['color']})

            actions.append({'type': 'create_card', 'role': role, 'board': board_info['name'], 'list': GUIDE_LIST_NAME, 'name': spec['guide_title']})
            actions.append({
                'type': 'create_card',
                'role': role,
                'board': board_info['name'],
                'list': GUIDE_LIST_NAME,
                'name': spec['template_title'],
                'checklist': spec['checklist_name'],
                'items': spec['checklist_items']
            })
        else:
            bid = board_info['id']
            curr_lists = client.request('GET', f'/boards/{bid}/lists', {'filter': 'open', 'fields': 'name,pos,closed'})
            unique_names(curr_lists)
            curr_list_names = {l['name'] for l in curr_lists}

            desired_lists = b_cfg.get('lists', spec['default_lists'])
            for lname in desired_lists:
                if lname not in curr_list_names:
                    actions.append({'type': 'create_list', 'role': role, 'boardId': bid, 'board': board_info['name'], 'name': lname})
            if GUIDE_LIST_NAME not in curr_list_names:
                actions.append({'type': 'create_list', 'role': role, 'boardId': bid, 'board': board_info['name'], 'name': GUIDE_LIST_NAME})

            curr_labels = client.request('GET', f'/boards/{bid}/labels', {'limit': 100})
            if len(curr_labels) >= 100:
                raise ClientError('Label listing may be truncated; inspect manually.')
            unique_names(curr_labels)
            curr_label_names = {l['name'] for l in curr_labels if l.get('name')}
            labels = b_cfg.get('labels', [])
            for lbl in labels:
                if lbl['name'] not in curr_label_names:
                    actions.append({'type': 'create_label', 'role': role, 'boardId': bid, 'board': board_info['name'], 'name': lbl['name'], 'color': lbl['color']})

            curr_cards = client.request('GET', f'/boards/{bid}/cards', {'filter': 'open', 'fields': 'name,idList'})
            matching_guide_cards = [c for c in curr_cards if c['name'] == spec['guide_title']]
            if len(matching_guide_cards) > 1:
                raise ClientError(f'Ambiguity: multiple open cards named "{spec["guide_title"]}" on board.')
            if not matching_guide_cards:
                actions.append({
                    'type': 'create_card',
                    'role': role,
                    'boardId': bid,
                    'board': board_info['name'],
                    'list': GUIDE_LIST_NAME,
                    'name': spec['guide_title']
                })

            matching_template_cards = [c for c in curr_cards if c['name'] == spec['template_title']]
            if len(matching_template_cards) > 1:
                raise ClientError(f'Ambiguity: multiple open cards named "{spec["template_title"]}" on board.')
            if not matching_template_cards:
                actions.append({
                    'type': 'create_card',
                    'role': role,
                    'boardId': bid,
                    'board': board_info['name'],
                    'list': GUIDE_LIST_NAME,
                    'name': spec['template_title'],
                    'checklist': spec['checklist_name'],
                    'items': spec['checklist_items']
                })
            else:
                # Card exists: check if checklist or checklist items are missing (partial failure recovery)
                chk_name = spec['checklist_name']
                if chk_name:
                    cid = matching_template_cards[0]['id']
                    card_checklists = client.request('GET', f'/cards/{cid}/checklists', {'fields': 'name,checkItems'})
                    unique_names(card_checklists)
                    matching_checklists = [chk for chk in card_checklists if chk.get('name') == chk_name]
                    if len(matching_checklists) > 1:
                        raise ClientError(f'Ambiguity: multiple checklists named "{chk_name}" on template card.')
                    if not matching_checklists:
                        actions.append({
                            'type': 'create_checklist',
                            'role': role,
                            'boardId': bid,
                            'board': board_info['name'],
                            'cardId': cid,
                            'cardName': spec['template_title'],
                            'name': chk_name,
                            'items': spec['checklist_items']
                        })
                    else:
                        # Checklist exists: check for missing items
                        chk_obj = matching_checklists[0]
                        unique_names(chk_obj.get('checkItems', []))
                        existing_items = {item.get('name') for item in chk_obj.get('checkItems', [])}
                        missing_items = [i for i in spec['checklist_items'] if i not in existing_items]
                        for m_item in missing_items:
                            actions.append({
                                'type': 'create_checklist_item',
                                'role': role,
                                'boardId': bid,
                                'board': board_info['name'],
                                'cardId': cid,
                                'checklistId': chk_obj['id'],
                                'checklistName': chk_name,
                                'name': m_item
                            })

    return actions, board_targets


def execute_plan(client, actions, board_targets, workspace_id):
    created_boards = {}
    results = []

    # Step 1: Create boards if needed
    for act in [a for a in actions if a['type'] == 'create_board']:
        role = act['role']
        name = act['name']
        existing_boards = client.request('GET', '/members/me/boards', {'filter': 'open', 'fields': 'name,closed,idOrganization'})
        if any(b.get('name') == name and b.get('idOrganization') == workspace_id for b in existing_boards):
            raise ClientError('Board appeared since planning; rerun preview.')
        res = client.request('POST', '/boards', {
            'name': name,
            'idOrganization': workspace_id,
            'defaultLists': False,
            'prefs_permissionLevel': 'private'
        })
        bid = res['id']
        # Post-write verification: ensure board was created with private permissionLevel and correct workspace
        fresh_board = client.request('GET', f'/boards/{bid}', {'fields': 'name,closed,idOrganization,prefs'})
        if fresh_board.get('closed'):
            raise ClientError(f'Verification failed: newly created board "{name}" is closed.')
        if fresh_board.get('idOrganization') != workspace_id:
            raise ClientError(f'Verification failed: newly created board "{name}" has unexpected workspace.')
        if fresh_board.get('prefs', {}).get('permissionLevel') != 'private':
            raise ClientError(f'Verification failed: newly created board "{name}" is not private.')

        created_boards[role] = bid
        results.append(f"Created private board '{name}' (id: {bid})")

    def resolve_board_id(role):
        if role in created_boards:
            return created_boards[role]
        return board_targets[role][0]['id']

    # Step 2: Lists
    for act in [a for a in actions if a['type'] == 'create_list']:
        role = act['role']
        bid = resolve_board_id(role)
        lname = act['name']
        existing = client.request('GET', f'/boards/{bid}/lists', {'filter': 'open', 'fields': 'name'})
        matching = [l for l in existing if l['name'] == lname]
        if len(matching) > 1:
            raise ClientError(f'Ambiguity: multiple lists named "{lname}" on board.')
        if matching:
            continue
        res = client.request('POST', '/lists', {'idBoard': bid, 'name': lname, 'pos': 'bottom'})
        results.append(f"Created list '{lname}' on board {bid}")

    # Step 3: Labels
    for act in [a for a in actions if a['type'] == 'create_label']:
        role = act['role']
        bid = resolve_board_id(role)
        lname = act['name']
        color = act['color']
        existing = client.request('GET', f'/boards/{bid}/labels', {'limit': 100})
        matching = [l for l in existing if l.get('name') == lname]
        if len(matching) > 1:
            raise ClientError(f'Ambiguity: multiple labels named "{lname}" on board.')
        if matching:
            continue
        res = client.request('POST', '/labels', {'idBoard': bid, 'name': lname, 'color': color})
        results.append(f"Created label '{lname}' ({color}) on board {bid}")

    # Step 4: Cards
    for act in [a for a in actions if a['type'] == 'create_card']:
        role = act['role']
        bid = resolve_board_id(role)
        cname = act['name']

        lists = client.request('GET', f'/boards/{bid}/lists', {'filter': 'open', 'fields': 'name'})
        matching_lists = [l for l in lists if l['name'] == act['list']]
        if not matching_lists:
            raise ClientError(f"Cannot find destination list '{act['list']}' on board.")
        if len(matching_lists) > 1:
            raise ClientError(f"Ambiguity: multiple destination lists named '{act['list']}' on board.")
        lid = matching_lists[0]['id']

        cards = client.request('GET', f'/lists/{lid}/cards', {'filter': 'open', 'fields': 'name'})
        matching_cards = [c for c in cards if c['name'] == cname]
        if len(matching_cards) > 1:
            raise ClientError(f"Ambiguity: multiple cards named '{cname}' in destination list.")
        if matching_cards:
            cid = matching_cards[0]['id']
        else:
            spec = BOARD_SPECS[role]
            if cname == spec['guide_title']:
                desc = spec['guide_desc']
            else:
                desc = load_template_file(spec['template_rel'])

            card_res = client.request('POST', '/cards', {
                'idList': lid,
                'name': cname,
                'desc': desc,
                'pos': 'bottom'
            })
            cid = card_res['id']
            results.append(f"Created card '{cname}' in list '{act['list']}' (id: {cid})")

        chk_name = act.get('checklist')
        if chk_name:
            checklists = client.request('GET', f'/cards/{cid}/checklists', {'fields': 'name,checkItems'})
            matching_chks = [chk for chk in checklists if chk.get('name') == chk_name]
            if len(matching_chks) > 1:
                raise ClientError(f"Ambiguity: multiple checklists named '{chk_name}' on card.")
            if matching_chks:
                chkid = matching_chks[0]['id']
                existing_item_names = {i.get('name') for i in matching_chks[0].get('checkItems', [])}
            else:
                chk_res = client.request('POST', '/checklists', {
                    'idCard': cid,
                    'name': chk_name,
                    'pos': 'bottom'
                })
                chkid = chk_res['id']
                existing_item_names = set()
                results.append(f"Added checklist '{chk_name}' to card {cid}")

            for item_text in act.get('items', []):
                if item_text not in existing_item_names:
                    client.request('POST', f'/checklists/{chkid}/checkItems', {
                        'name': item_text,
                        'pos': 'bottom'
                    })
                    results.append(f"Added item '{item_text}' to checklist '{chk_name}'")

    # Step 5: Isolated Checklists on existing cards (partial-failure recovery)
    for act in [a for a in actions if a['type'] == 'create_checklist']:
        cid = act['cardId']
        chk_name = act['name']
        checklists = client.request('GET', f'/cards/{cid}/checklists', {'fields': 'name,checkItems'})
        matching_chks = [chk for chk in checklists if chk.get('name') == chk_name]
        if len(matching_chks) > 1:
            raise ClientError(f"Ambiguity: multiple checklists named '{chk_name}' on card.")
        if matching_chks:
            chkid = matching_chks[0]['id']
            existing_item_names = {i.get('name') for i in matching_chks[0].get('checkItems', [])}
        else:
            chk_res = client.request('POST', '/checklists', {
                'idCard': cid,
                'name': chk_name,
                'pos': 'bottom'
            })
            chkid = chk_res['id']
            existing_item_names = set()
            results.append(f"Added checklist '{chk_name}' to card {cid}")

        for item_text in act.get('items', []):
            if item_text not in existing_item_names:
                client.request('POST', f'/checklists/{chkid}/checkItems', {
                    'name': item_text,
                    'pos': 'bottom'
                })
                results.append(f"Added item '{item_text}' to checklist '{chk_name}'")

    # Step 6: Isolated Checklist Items on existing checklist (partial-failure recovery)
    for act in [a for a in actions if a['type'] == 'create_checklist_item']:
        cid = act['cardId']
        chkid = act['checklistId']
        item_name = act['name']
        checklists = client.request('GET', f'/cards/{cid}/checklists', {'fields': 'name,checkItems'})
        target_chk = next((chk for chk in checklists if chk.get('id') == chkid), None)
        if not target_chk:
            raise ClientError(f"Checklist {chkid} not found on card during item creation.")
        existing_item_names = {i.get('name') for i in target_chk.get('checkItems', [])}
        if item_name not in existing_item_names:
            client.request('POST', f'/checklists/{chkid}/checkItems', {
                'name': item_name,
                'pos': 'bottom'
            })
            results.append(f"Added item '{item_name}' to checklist {chkid}")

    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description='Automated Trello board setup.')
    parser.add_argument('--config', default='config.local.json', help='Path to configuration JSON file (default: config.local.json)')
    parser.add_argument('--apply', action='store_true', help='Apply additions to Trello (default: preview read-only)')
    parser.add_argument('--only', nargs='+', dest='only_roles', metavar='ROLE',
                        help='Select one or more board roles (for example: --only spaces)')
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(json.dumps({'error': 'Config file not found.'}), file=sys.stderr)
        return 2

    try:
        cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        validate_config(cfg, args.only_roles)
    except Exception as exc:
        print(json.dumps({'error': f'Config error: {str(exc)}'}), file=sys.stderr)
        return 2

    try:
        client = Client()
        workspace_id = cfg['workspaceId'].strip()
        actions, board_targets = build_plan(client, cfg, workspace_id, args.only_roles)

        if not args.apply:
            summary = {
                'mode': 'preview',
                'actions_count': len(actions),
                'actions': actions,
                'note': 'Pass --apply to execute these additions. Existing cards and lists will be preserved.'
            }
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0

        results = execute_plan(client, actions, board_targets, workspace_id)
        remaining, _ = build_plan(client, cfg, workspace_id, args.only_roles)
        if remaining:
            raise ClientError('Verification found remaining additions; inspect before rerunning.')
        print(json.dumps({'mode': 'applied', 'results': results}, indent=2, ensure_ascii=False))
        return 0

    except ClientError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
