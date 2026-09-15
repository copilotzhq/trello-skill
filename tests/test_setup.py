"""Unit tests for configuration-driven setup.py.

All tests mock Client transport, perform zero live network calls, and verify:
- Config validation (placeholders, bad types, missing keys)
- Preview mode (zero writes)
- Fresh setup (creates boards, lists, labels, cards, checklists)
- Idempotent rerun (zero writes when up to date)
- Error handling (ambiguous board names, wrong workspace, closed boards)
- Preserving existing board content and lists
"""
import json
import os
import sys
import unittest
import copy
from pathlib import Path
from unittest.mock import MagicMock, patch

TEST_DIR = Path(__file__).resolve().parent
REPO_DIR = TEST_DIR.parent
SCRIPTS_DIR = REPO_DIR / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import setup
from trello import ClientError


class FakeTrelloClient:
    def __init__(self):
        self.requests = []
        # In-memory mock database
        self.boards = []
        self.lists = {}
        self.labels = {}
        self.cards = {}
        self.checklists = {}
        self._id_counter = 100

    def _next_id(self):
        self._id_counter += 1
        return f'id{self._id_counter}'

    def request(self, method, path, params=None):
        params = params or {}
        self.requests.append((method, path, params))

        # Boards routes
        if method == 'GET' and path == '/members/me/boards':
            return [
                {'id': b['id'], 'name': b['name'], 'closed': b.get('closed', False), 'idOrganization': b.get('idOrganization')}
                for b in self.boards if not b.get('closed', False)
            ]

        if method == 'GET' and path.startswith('/boards/') and path.endswith('/lists'):
            bid = path.split('/')[2]
            return [
                {'id': l['id'], 'name': l['name'], 'closed': l.get('closed', False), 'pos': l.get('pos', 1000)}
                for l in self.lists.get(bid, []) if not l.get('closed', False)
            ]

        if method == 'GET' and path.startswith('/boards/') and path.endswith('/labels'):
            bid = path.split('/')[2]
            return self.labels.get(bid, [])

        if method == 'GET' and path.startswith('/boards/') and path.endswith('/cards'):
            bid = path.split('/')[2]
            b_cards = []
            for l in self.lists.get(bid, []):
                lid = l['id']
                for c in self.cards.get(lid, []):
                    if not c.get('closed', False):
                        b_cards.append({'id': c['id'], 'name': c['name'], 'idList': lid})
            return b_cards

        if method == 'GET' and path.startswith('/boards/'):
            bid = path.split('/')[2]
            for b in self.boards:
                if b['id'] == bid:
                    return b
            raise ClientError(f'Board not found: {bid}')

        if method == 'GET' and path.startswith('/lists/') and path.endswith('/cards'):
            lid = path.split('/')[2]
            return [
                {'id': c['id'], 'name': c['name'], 'desc': c.get('desc', ''), 'closed': c.get('closed', False)}
                for c in self.cards.get(lid, []) if not c.get('closed', False)
            ]

        if method == 'GET' and path.startswith('/cards/') and path.endswith('/checklists'):
            return self.checklists.get(path.split('/')[2], [])

        # Writes
        if method == 'POST' and path == '/boards':
            new_id = self._next_id()
            b = {
                'id': new_id,
                'name': params['name'],
                'idOrganization': params.get('idOrganization'),
                'closed': False,
                'prefs': {'permissionLevel': params.get('prefs_permissionLevel', 'private')}
            }
            self.boards.append(b)
            self.lists[new_id] = []
            self.labels[new_id] = []
            return b

        if method == 'POST' and path == '/lists':
            bid = params['idBoard']
            new_id = self._next_id()
            l = {'id': new_id, 'name': params['name'], 'idBoard': bid, 'closed': False, 'pos': params.get('pos', 1000)}
            self.lists.setdefault(bid, []).append(l)
            self.cards[new_id] = []
            return l

        if method == 'POST' and path == '/labels':
            bid = params['idBoard']
            new_id = self._next_id()
            lbl = {'id': new_id, 'name': params['name'], 'color': params['color']}
            self.labels.setdefault(bid, []).append(lbl)
            return lbl

        if method == 'POST' and path == '/cards':
            lid = params['idList']
            new_id = self._next_id()
            c = {'id': new_id, 'name': params['name'], 'desc': params.get('desc', ''), 'idList': lid, 'closed': False}
            self.cards.setdefault(lid, []).append(c)
            return c

        if method == 'POST' and path == '/checklists':
            cid = params['idCard']
            new_id = self._next_id()
            chk = {'id': new_id, 'idCard': cid, 'name': params['name'], 'checkItems': []}
            self.checklists.setdefault(cid, []).append(chk)
            return chk

        if method == 'POST' and '/checklists/' in path and path.endswith('/checkItems'):
            chkid = path.split('/')[2]
            new_id = self._next_id()
            item = {'id': new_id, 'name': params['name']}
            for clist in self.checklists.values():
                for chk in clist:
                    if chk['id'] == chkid:
                        chk['checkItems'].append(item)
                        return item
            return item

        raise ClientError(f'Unhandled fake request: {method} {path}')


class TestSetup(unittest.TestCase):
    def setUp(self):
        self.valid_cfg = {
            'workspaceId': 'ws1234567890',
            'boards': {
                'projects': {'name': 'My Projects'},
                'milestones': {'name': 'My Milestones'},
                'tasks': {'name': 'My Tasks'}
            }
        }

    def spaces_cfg(self):
        cfg = copy.deepcopy(self.valid_cfg)
        cfg['boards']['spaces'] = {'name': 'Spaces'}
        return cfg

    def test_spaces_only_preview_is_read_only_and_scoped(self):
        client = FakeTrelloClient()
        cfg = self.spaces_cfg()

        actions, targets = setup.build_plan(client, cfg, 'ws1234567890', ['spaces'])

        self.assertEqual(set(targets), {'spaces'})
        self.assertEqual(len(actions), 6)
        self.assertTrue(all(action['role'] == 'spaces' for action in actions))
        self.assertFalse(any(action['type'].startswith('create_checklist') for action in actions))
        self.assertTrue(all(method == 'GET' for method, _, _ in client.requests))

    def test_spaces_only_apply_creates_expected_board_and_reruns_cleanly(self):
        client = FakeTrelloClient()
        cfg = self.spaces_cfg()
        actions, targets = setup.build_plan(client, cfg, 'ws1234567890', ['spaces'])

        setup.execute_plan(client, actions, targets, 'ws1234567890')

        self.assertEqual([board['name'] for board in client.boards], ['Spaces'])
        space_board_id = client.boards[0]['id']
        self.assertEqual(
            [item['name'] for item in client.lists[space_board_id]],
            ['Active', 'Inactive', setup.GUIDE_LIST_NAME]
        )
        card_names = [
            card['name']
            for cards in client.cards.values()
            for card in cards
        ]
        self.assertEqual(set(card_names), {
            setup.BOARD_SPECS['spaces']['guide_title'],
            setup.BOARD_SPECS['spaces']['template_title']
        })
        self.assertEqual(client.checklists, {})

        client.requests.clear()
        rerun_actions, rerun_targets = setup.build_plan(client, cfg, 'ws1234567890', ['spaces'])
        self.assertEqual(rerun_actions, [])
        self.assertEqual(set(rerun_targets), {'spaces'})
        setup.execute_plan(client, rerun_actions, rerun_targets, 'ws1234567890')
        self.assertTrue(all(method == 'GET' for method, _, _ in client.requests))

    def test_legacy_config_still_targets_three_boards(self):
        client = FakeTrelloClient()
        actions, targets = setup.build_plan(client, self.valid_cfg, 'ws1234567890')

        self.assertEqual(set(targets), {'projects', 'milestones', 'tasks'})
        self.assertEqual(
            {action['role'] for action in actions if action['type'] == 'create_board'},
            {'projects', 'milestones', 'tasks'}
        )

    def test_spaces_opt_in_targets_four_boards(self):
        client = FakeTrelloClient()
        cfg = self.spaces_cfg()
        actions, targets = setup.build_plan(client, cfg, 'ws1234567890')

        self.assertEqual(set(targets), {'spaces', 'projects', 'milestones', 'tasks'})
        self.assertEqual(
            {action['role'] for action in actions if action['type'] == 'create_board'},
            {'spaces', 'projects', 'milestones', 'tasks'}
        )

    def test_selected_role_validation_happens_before_reads(self):
        client = FakeTrelloClient()
        with self.assertRaises(ClientError):
            setup.build_plan(client, self.valid_cfg, 'ws1234567890', ['spaces'])
        self.assertEqual(client.requests, [])

        with self.assertRaises(ClientError):
            setup.build_plan(client, self.valid_cfg, 'ws1234567890', ['unknown'])
        self.assertEqual(client.requests, [])

        cfg = self.spaces_cfg()
        with self.assertRaises(ClientError):
            setup.validate_config(cfg, ['spaces', 'spaces'])
        cfg['boards']['spaces']['name'] = 'My Projects'
        with self.assertRaises(ClientError):
            setup.validate_config(cfg)

    def test_partial_write_recovery(self):
        client = FakeTrelloClient()
        original = client.request
        failed = [False]
        def interrupted(method, path, params=None):
            result = original(method, path, params)
            if method == 'POST' and path.endswith('/checkItems') and not failed[0]:
                failed[0] = True
                raise ClientError('Simulated lost response after successful write')
            return result
        client.request = interrupted
        actions, targets = setup.build_plan(client, self.valid_cfg, 'ws1234567890')
        with self.assertRaises(ClientError):
            setup.execute_plan(client, actions, targets, 'ws1234567890')
        client.request = original
        actions, targets = setup.build_plan(client, self.valid_cfg, 'ws1234567890')
        setup.execute_plan(client, actions, targets, 'ws1234567890')
        remaining, _ = setup.build_plan(client, self.valid_cfg, 'ws1234567890')
        self.assertEqual(remaining, [])
        for checklists in client.checklists.values():
            for checklist in checklists:
                names = [x['name'] for x in checklist['checkItems']]
                self.assertEqual(len(names), len(set(names)))

    def test_missing_privacy_fails(self):
        client = FakeTrelloClient()
        original = client.request
        def request(method, path, params=None):
            result = original(method, path, params)
            if method == 'POST' and path == '/boards':
                result['prefs'] = {}
            return result
        client.request = request
        actions, targets = setup.build_plan(client, self.valid_cfg, 'ws1234567890')
        with self.assertRaises(ClientError):
            setup.execute_plan(client, actions, targets, 'ws1234567890')

    def test_schema_and_duplicate_rejections(self):
        import copy
        for override in [{'lists': 'not a list'}, {'labels': [{}]}, {'name': 123},
                         {'lists': ['Active', 'Active']}, {'name': 'My Projects'}]:
            cfg = copy.deepcopy(self.valid_cfg)
            cfg['boards']['tasks'] = override
            with self.assertRaises(ClientError):
                setup.validate_config(cfg)
        with self.assertRaises(ClientError):
            setup.unique_names([{'name': 'Repeated'}, {'name': 'Repeated'}])

    def test_config_validation(self):
        # Not dict
        with self.assertRaises(ClientError):
            setup.validate_config('not a dict')

        # Missing workspaceId
        with self.assertRaises(ClientError):
            setup.validate_config({'boards': {}})

        # Placeholder workspaceId
        with self.assertRaises(ClientError):
            setup.validate_config({'workspaceId': 'YOUR_WORKSPACE_ID'})

        # Invalid characters in workspaceId
        with self.assertRaises(ClientError):
            setup.validate_config({'workspaceId': 'invalid workspace id with spaces'})

        # Invalid board ID
        with self.assertRaises(ClientError):
            setup.validate_config({'workspaceId': 'ws123', 'boards': {'tasks': {'id': 'not a valid id!'}}})

        # Valid config passes
        setup.validate_config(self.valid_cfg)

    def test_preview_mode_zero_writes(self):
        fake_client = FakeTrelloClient()
        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')

        # Verify actions planned
        self.assertTrue(len(actions) > 0)
        # Verify only GET requests were made
        for m, p, q in fake_client.requests:
            self.assertEqual(m, 'GET')

    def test_fresh_setup_creates_boards_and_content(self):
        fake_client = FakeTrelloClient()
        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        results = setup.execute_plan(fake_client, actions, targets, 'ws1234567890')

        self.assertTrue(len(results) > 0)
        # 3 boards created
        self.assertEqual(len(fake_client.boards), 3)
        for b in fake_client.boards:
            self.assertEqual(b['idOrganization'], 'ws1234567890')
            self.assertEqual(b['prefs']['permissionLevel'], 'private')
            bid = b['id']
            # Verify Templates & Guide list exists
            list_names = [l['name'] for l in fake_client.lists[bid]]
            self.assertIn(setup.GUIDE_LIST_NAME, list_names)

    def test_milestone_template_and_guide_use_success_evidence(self):
        fake_client = FakeTrelloClient()
        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        setup.execute_plan(fake_client, actions, targets, 'ws1234567890')

        milestone_board = next(b for b in fake_client.boards if b['name'] == 'My Milestones')
        milestone_cards = [
            card
            for cards in fake_client.cards.values()
            for card in cards
            if any(l['id'] == card['idList'] and l['idBoard'] == milestone_board['id']
                   for l in fake_client.lists[milestone_board['id']])
        ]
        guide = next(c for c in milestone_cards if c['name'] == setup.BOARD_SPECS['milestones']['guide_title'])
        template = next(c for c in milestone_cards if c['name'] == setup.BOARD_SPECS['milestones']['template_title'])
        for description in (guide['desc'], template['desc']):
            self.assertIn('Parent project', description)
            self.assertIn('Target state', description)
            self.assertIn('Target date', description)
            self.assertIn('Success evidence', description)
            self.assertNotIn('acceptance', description.lower())
            self.assertNotIn('scope / exclusions', description.lower())
            self.assertNotIn('contributing tasks', description.lower())

        checklists = fake_client.checklists[template['id']]
        self.assertEqual([checklist['name'] for checklist in checklists], ['Success evidence'])
        self.assertEqual(
            [item['name'] for item in checklists[0]['checkItems']],
            ['Define success evidence before committing']
        )

    def test_legacy_milestone_checklist_recovery_adds_new_checklist_idempotently(self):
        fake_client = FakeTrelloClient()
        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        setup.execute_plan(fake_client, actions, targets, 'ws1234567890')

        template = next(
            card for cards in fake_client.cards.values() for card in cards
            if card['name'] == setup.BOARD_SPECS['milestones']['template_title']
        )
        fake_client.checklists[template['id']] = [{
            'id': 'legacy-checklist',
            'idCard': template['id'],
            'name': 'Acceptance criteria',
            'checkItems': [{'id': 'legacy-item', 'name': 'Old wording'}],
        }]

        fake_client.requests.clear()
        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        self.assertEqual(
            [action['type'] for action in actions if action.get('role') == 'milestones'],
            ['create_checklist']
        )
        setup.execute_plan(fake_client, actions, targets, 'ws1234567890')
        self.assertEqual(
            {checklist['name'] for checklist in fake_client.checklists[template['id']]},
            {'Acceptance criteria', 'Success evidence'},
        )

        actions, _ = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        self.assertFalse(any(
            action.get('role') == 'milestones' and action['type'].startswith('create_checklist')
            for action in actions
        ))

    def test_idempotent_rerun_zero_writes(self):
        fake_client = FakeTrelloClient()
        # First run
        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        setup.execute_plan(fake_client, actions, targets, 'ws1234567890')

        # Clear recorded requests
        fake_client.requests.clear()

        # Second run
        actions2, targets2 = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        self.assertEqual(len(actions2), 0)

        # Execute plan with empty actions
        results2 = setup.execute_plan(fake_client, actions2, targets2, 'ws1234567890')
        self.assertEqual(len(results2), 0)

        # Verify no POST or PUT requests in second run
        for m, p, q in fake_client.requests:
            self.assertEqual(m, 'GET')

    def test_ambiguous_board_name_raises(self):
        fake_client = FakeTrelloClient()
        # Add two boards with same name in same workspace
        fake_client.boards.append({'id': 'b1', 'name': 'My Tasks', 'closed': False, 'idOrganization': 'ws1234567890'})
        fake_client.boards.append({'id': 'b2', 'name': 'My Tasks', 'closed': False, 'idOrganization': 'ws1234567890'})

        with self.assertRaises(ClientError) as ctx:
            setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        self.assertIn('Multiple open boards named', str(ctx.exception))

    def test_board_wrong_workspace_raises(self):
        fake_client = FakeTrelloClient()
        fake_client.boards.append({'id': 'b1', 'name': 'My Tasks', 'closed': False, 'idOrganization': 'other_ws'})
        cfg = {
            'workspaceId': 'ws1234567890',
            'boards': {
                'tasks': {'id': 'b1'}
            }
        }
        with self.assertRaises(ClientError) as ctx:
            setup.build_plan(fake_client, cfg, 'ws1234567890')
        self.assertIn('belongs to another workspace, not expected workspace', str(ctx.exception))

    def test_existing_board_content_preserved(self):
        fake_client = FakeTrelloClient()
        # Pre-populate an existing board with some custom lists and cards
        fake_client.boards.append({
            'id': 'b_tasks',
            'name': 'My Tasks',
            'closed': False,
            'idOrganization': 'ws1234567890'
        })
        fake_client.lists['b_tasks'] = [
            {'id': 'l_custom', 'name': 'Custom List', 'closed': False, 'idBoard': 'b_tasks', 'pos': 1000}
        ]
        fake_client.cards['l_custom'] = [
            {'id': 'c_existing', 'name': 'Existing Important Task', 'closed': False, 'idList': 'l_custom'}
        ]

        actions, targets = setup.build_plan(fake_client, self.valid_cfg, 'ws1234567890')
        setup.execute_plan(fake_client, actions, targets, 'ws1234567890')

        # Verify custom list and card still exist
        l_names = [l['name'] for l in fake_client.lists['b_tasks']]
        self.assertIn('Custom List', l_names)
        c_names = [c['name'] for c in fake_client.cards['l_custom']]
        self.assertIn('Existing Important Task', c_names)


if __name__ == '__main__':
    unittest.main()
