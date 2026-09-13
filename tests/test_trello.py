"""Unit tests for standalone dependency-free trello.py CLI.

All tests mock transport, require zero network access, and test auth,
routes, validation, error sanitization, and redirect refusal.
"""
import json
import os
import unittest
from unittest.mock import MagicMock

import scripts.trello as trello


class DummyResponse:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def read(self):
        return json.dumps(self.data).encode('utf-8')


class TestTrelloCLI(unittest.TestCase):
    def setUp(self):
        self.env_patcher = unittest.mock.patch.dict(os.environ, {
            'TRELLO_API_KEY': 'test_key_123',
            'TRELLO_TOKEN': 'test_token_xyz'
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_missing_credentials_raises(self):
        with unittest.mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(trello.ClientError) as ctx:
                trello.Client()
            self.assertIn('Set TRELLO_API_KEY and TRELLO_TOKEN', str(ctx.exception))

    def test_auth_header_format(self):
        client = trello.Client(key='mykey', token='mytoken')
        self.assertEqual(
            client.auth,
            'OAuth oauth_consumer_key="mykey", oauth_token="mytoken"'
        )

    def test_redirect_refused(self):
        handler = trello.NoRedirect()
        with self.assertRaises(trello.ClientError) as ctx:
            handler.redirect_request(None, None, 302, 'Found', {}, 'https://malicious.com')
        self.assertIn('Redirect refused', str(ctx.exception))

    def test_identifier_validation(self):
        self.assertEqual(trello.identifier('ExampleBoardID123'), 'ExampleBoardID123')
        self.assertEqual(trello.identifier('card123'), 'card123')
        with self.assertRaises(Exception):
            trello.identifier('https://trello.com/c/1234')
        with self.assertRaises(Exception):
            trello.identifier('id with spaces')
        with self.assertRaises(Exception):
            trello.identifier('../../path')

    def test_writes_require_yes_confirmation(self):
        parser = trello.build_parser()
        write_commands = [
            ['create', 'list1', '--name', 'Card Title'],
            ['update', 'card1', '--name', 'New Title'],
            ['move', 'card1', 'list2'],
            ['comment', 'card1', '--text', 'Hello'],
            ['copy', 'card1', 'list2'],
            ['create-label', 'board1', '--name', 'Bug', '--color', 'red'],
            ['assign-label', 'card1', 'label1'],
            ['create-checklist', 'card1', '--name', 'Todo'],
            ['add-checklist-item', 'check1', '--name', 'Item 1'],
            ['set-checklist-item', 'card1', 'item1', '--state', 'complete'],
        ]
        for cmd in write_commands:
            args = parser.parse_args(cmd)
            with self.assertRaises(trello.ClientError, msg=f'Failed for {cmd}') as ctx:
                trello.plan(args)
            self.assertIn('supply --yes to confirm', str(ctx.exception))

    def test_routes_read(self):
        parser = trello.build_parser()
        # boards
        m, p, q = trello.plan(parser.parse_args(['boards']))
        self.assertEqual((m, p), ('GET', '/members/me/boards'))

        # lists
        m, p, q = trello.plan(parser.parse_args(['lists', 'b1']))
        self.assertEqual((m, p), ('GET', '/boards/b1/lists'))

        # cards
        m, p, q = trello.plan(parser.parse_args(['cards', 'l1']))
        self.assertEqual((m, p), ('GET', '/lists/l1/cards'))

        # card
        m, p, q = trello.plan(parser.parse_args(['card', 'c1']))
        self.assertEqual((m, p), ('GET', '/cards/c1'))

        # labels
        m, p, q = trello.plan(parser.parse_args(['labels', 'b1']))
        self.assertEqual((m, p), ('GET', '/boards/b1/labels'))

        # checklists
        m, p, q = trello.plan(parser.parse_args(['checklists', 'c1']))
        self.assertEqual((m, p), ('GET', '/cards/c1/checklists'))

    def test_routes_write(self):
        parser = trello.build_parser()
        # create
        m, p, q = trello.plan(parser.parse_args(['create', 'l1', '--name', 'T1', '--desc', 'D1', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/cards', {'idList': 'l1', 'name': 'T1', 'desc': 'D1'}))

        # update
        m, p, q = trello.plan(parser.parse_args(['update', 'c1', '--name', 'T2', '--desc', 'D2', '--yes']))
        self.assertEqual((m, p, q), ('PUT', '/cards/c1', {'name': 'T2', 'desc': 'D2'}))

        # move
        m, p, q = trello.plan(parser.parse_args(['move', 'c1', 'l2', '--yes']))
        self.assertEqual((m, p, q), ('PUT', '/cards/c1', {'idList': 'l2'}))

        # comment
        m, p, q = trello.plan(parser.parse_args(['comment', 'c1', '--text', 'Note', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/cards/c1/actions/comments', {'text': 'Note'}))

        # copy
        m, p, q = trello.plan(parser.parse_args(['copy', 'c1', 'l2', '--name', 'Copy', '--keep', 'all', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/cards', {'idList': 'l2', 'idCardSource': 'c1', 'name': 'Copy', 'keepFromSource': 'all'}))

        # create-label
        m, p, q = trello.plan(parser.parse_args(['create-label', 'b1', '--name', 'Dev', '--color', 'green', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/labels', {'idBoard': 'b1', 'name': 'Dev', 'color': 'green'}))

        # assign-label
        m, p, q = trello.plan(parser.parse_args(['assign-label', 'c1', 'lbl1', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/cards/c1/idLabels', {'value': 'lbl1'}))

        # create-checklist
        m, p, q = trello.plan(parser.parse_args(['create-checklist', 'c1', '--name', 'Steps', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/checklists', {'idCard': 'c1', 'name': 'Steps', 'pos': 'bottom'}))

        # add-checklist-item
        m, p, q = trello.plan(parser.parse_args(['add-checklist-item', 'chk1', '--name', 'Do this', '--yes']))
        self.assertEqual((m, p, q), ('POST', '/checklists/chk1/checkItems', {'name': 'Do this', 'pos': 'bottom'}))

        # set-checklist-item
        m, p, q = trello.plan(parser.parse_args(['set-checklist-item', 'c1', 'itm1', '--state', 'complete', '--yes']))
        self.assertEqual((m, p, q), ('PUT', '/cards/c1/checkItem/itm1', {'state': 'complete'}))

    def test_http_error_sanitized_no_retry(self):
        mock_opener = MagicMock()
        import urllib.error
        mock_opener.open.side_effect = urllib.error.HTTPError(
            'https://api.trello.com/1/cards', 401, 'Unauthorized', {}, None
        )
        client = trello.Client(key='secret_key_123', token='secret_token_999', opener=mock_opener)
        with self.assertRaises(trello.ClientError) as ctx:
            client.request('GET', '/members/me/boards')
        self.assertIn('Trello HTTP 401', str(ctx.exception))
        self.assertIn('No automatic retry', str(ctx.exception))
        self.assertNotIn('secret_key_123', str(ctx.exception))
        self.assertNotIn('secret_token_999', str(ctx.exception))

    def test_network_error_sanitized(self):
        mock_opener = MagicMock()
        mock_opener.open.side_effect = ConnectionResetError('socket closed')
        client = trello.Client(key='secret_key_123', token='secret_token_999', opener=mock_opener)
        with self.assertRaises(trello.ClientError) as ctx:
            client.request('POST', '/cards', {'name': 'test'})
        self.assertIn('Network or response error', str(ctx.exception))
        self.assertIn('No automatic retry', str(ctx.exception))
        self.assertNotIn('socket closed', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
