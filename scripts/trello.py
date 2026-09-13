"""Dependency-free, on-demand Trello REST CLI for agents and humans.

Provides read and write operations with strict validation, JSON output,
explicit write confirmation, no automatic retries, and sanitized errors.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://api.trello.com/1'
ID_RE = re.compile(r'^[A-Za-z0-9]{1,64}$')


class ClientError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ClientError('Redirect refused; credentials will not be forwarded.')


class Client:
    def __init__(self, key=None, token=None, opener=None):
        key = (key if key is not None else os.environ.get('TRELLO_API_KEY', '')).strip()
        token = (token if token is not None else os.environ.get('TRELLO_TOKEN', '')).strip()
        if not key or not token:
            raise ClientError('Set TRELLO_API_KEY and TRELLO_TOKEN in the process environment.')
        self.auth = 'OAuth oauth_consumer_key="{}", oauth_token="{}"'.format(
            urllib.parse.quote(key, safe=''), urllib.parse.quote(token, safe=''))
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def request(self, method, path, params=None):
        headers = {'Authorization': self.auth, 'Accept': 'application/json'}
        url = BASE + path
        data = None
        params = params or {}
        if method == 'GET':
            if params:
                url += '?' + urllib.parse.urlencode(params)
        else:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(params).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise ClientError('Trello HTTP {}. No automatic retry. For writes, inspect state before retrying.'.format(status)) from None
        except ClientError:
            raise
        except Exception:
            raise ClientError('Network or response error. No automatic retry. For writes, inspect state before retrying.') from None


def identifier(value):
    val = str(value).strip()
    if not ID_RE.fullmatch(val):
        raise argparse.ArgumentTypeError('Use a valid Trello alphanumeric ID, not a URL or compound string.')
    return val


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ClientError('Invalid arguments. Use --help for command syntax.')


def build_parser():
    p = Parser(description='Trello CLI: Dependency-free REST client for agents.')
    sub = p.add_subparsers(dest='command', required=True, parser_class=Parser)

    # boards
    sub.add_parser('boards', help='List accessible open boards')

    # lists BOARD
    s = sub.add_parser('lists', help='List open lists on a board')
    s.add_argument('board', type=identifier, help='Board ID')

    # cards LIST
    s = sub.add_parser('cards', help='List cards in a list')
    s.add_argument('list', type=identifier, help='List ID')

    # card CARD
    s = sub.add_parser('card', help='Get card details')
    s.add_argument('card', type=identifier, help='Card ID')

    # create LIST --name NAME [--desc DESC]
    s = sub.add_parser('create', help='Create a new card in a list')
    s.add_argument('list', type=identifier, help='Destination list ID')
    s.add_argument('--name', required=True, help='Card title')
    s.add_argument('--desc', default='', help='Card description')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # update CARD [--name NAME] [--desc DESC]
    s = sub.add_parser('update', help='Update a card title or description')
    s.add_argument('card', type=identifier, help='Card ID')
    s.add_argument('--name', help='Updated title')
    s.add_argument('--desc', help='Updated description')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # move CARD LIST
    s = sub.add_parser('move', help='Move a card to another list')
    s.add_argument('card', type=identifier, help='Card ID')
    s.add_argument('list', type=identifier, help='Destination list ID')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # comment CARD --text TEXT
    s = sub.add_parser('comment', help='Add a comment to a card')
    s.add_argument('card', type=identifier, help='Card ID')
    s.add_argument('--text', required=True, help='Comment body')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # copy CARD LIST [--name NAME] [--keep KEEP]
    s = sub.add_parser('copy', help='Copy an existing card to a destination list')
    s.add_argument('card', type=identifier, help='Source card ID')
    s.add_argument('list', type=identifier, help='Destination list ID')
    s.add_argument('--name', help='New card name (defaults to source name)')
    s.add_argument('--keep', default='checklists', choices=['all', 'checklists', 'none'], help='Attributes to keep; default checklists (review source before copying)')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # labels BOARD
    s = sub.add_parser('labels', help='List labels defined on a board')
    s.add_argument('board', type=identifier, help='Board ID')

    # create-label BOARD --name NAME --color COLOR
    s = sub.add_parser('create-label', help='Create a label on a board')
    s.add_argument('board', type=identifier, help='Board ID')
    s.add_argument('--name', required=True, help='Label name')
    s.add_argument('--color', required=True, help='Label color (e.g. green, yellow, orange, red, purple, blue, blue_dark)')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # assign-label CARD LABEL
    s = sub.add_parser('assign-label', help='Assign an existing label to a card')
    s.add_argument('card', type=identifier, help='Card ID')
    s.add_argument('label', type=identifier, help='Label ID')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # checklists CARD
    s = sub.add_parser('checklists', help='List checklists on a card')
    s.add_argument('card', type=identifier, help='Card ID')

    # create-checklist CARD --name NAME
    s = sub.add_parser('create-checklist', help='Create a checklist on a card')
    s.add_argument('card', type=identifier, help='Card ID')
    s.add_argument('--name', required=True, help='Checklist title')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # add-checklist-item CHECKLIST --name NAME
    s = sub.add_parser('add-checklist-item', help='Add an item to a checklist')
    s.add_argument('checklist', type=identifier, help='Checklist ID')
    s.add_argument('--name', required=True, help='Item text')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    # set-checklist-item CARD ITEM --state STATE
    s = sub.add_parser('set-checklist-item', help='Update state of a checklist item')
    s.add_argument('card', type=identifier, help='Card ID')
    s.add_argument('item', type=identifier, help='CheckItem ID')
    s.add_argument('--state', required=True, choices=['complete', 'incomplete'], help='Target state')
    s.add_argument('--yes', action='store_true', help='Required confirmation for writes')

    return p


def plan(a):
    cmd = a.command
    # Read commands
    if cmd == 'boards':
        return 'GET', '/members/me/boards', {'filter': 'open', 'fields': 'name,url,closed,idOrganization'}
    if cmd == 'lists':
        return 'GET', f'/boards/{a.board}/lists', {'filter': 'open', 'fields': 'name,pos,closed,idBoard'}
    if cmd == 'cards':
        return 'GET', f'/lists/{a.list}/cards', {'filter': 'open', 'fields': 'name,desc,idList,url,idLabels,closed'}
    if cmd == 'card':
        return 'GET', f'/cards/{a.card}', {'fields': 'name,desc,idList,url,idLabels,closed,idBoard'}
    if cmd == 'labels':
        return 'GET', f'/boards/{a.board}/labels', {'limit': 100}
    if cmd == 'checklists':
        return 'GET', f'/cards/{a.card}/checklists', {'fields': 'name,pos,checkItems'}

    # Write commands require --yes
    if not getattr(a, 'yes', False):
        raise ClientError('Write not executed: supply --yes to confirm.')

    if cmd == 'create':
        if not a.name.strip():
            raise ClientError('Card name cannot be empty.')
        return 'POST', '/cards', {'idList': a.list, 'name': a.name.strip(), 'desc': a.desc}

    if cmd == 'update':
        params = {}
        if a.name is not None:
            if not a.name.strip():
                raise ClientError('Card name cannot be blank.')
            params['name'] = a.name.strip()
        if a.desc is not None:
            params['desc'] = a.desc
        if not params:
            raise ClientError('Supply --name and/or --desc to update.')
        return 'PUT', f'/cards/{a.card}', params

    if cmd == 'move':
        return 'PUT', f'/cards/{a.card}', {'idList': a.list}

    if cmd == 'comment':
        if not a.text.strip():
            raise ClientError('Comment text cannot be empty.')
        return 'POST', f'/cards/{a.card}/actions/comments', {'text': a.text}

    if cmd == 'copy':
        params = {'idList': a.list, 'idCardSource': a.card}
        if a.name and a.name.strip():
            params['name'] = a.name.strip()
        if a.keep == 'all':
            params['keepFromSource'] = 'all'
        elif a.keep == 'checklists':
            params['keepFromSource'] = 'checklists'
        elif a.keep == 'none':
            params['keepFromSource'] = 'none'
        else:
            params['keepFromSource'] = a.keep
        return 'POST', '/cards', params

    if cmd == 'create-label':
        if not a.name.strip():
            raise ClientError('Label name cannot be empty.')
        return 'POST', '/labels', {'idBoard': a.board, 'name': a.name.strip(), 'color': a.color.strip()}

    if cmd == 'assign-label':
        return 'POST', f'/cards/{a.card}/idLabels', {'value': a.label}

    if cmd == 'create-checklist':
        if not a.name.strip():
            raise ClientError('Checklist title cannot be empty.')
        return 'POST', '/checklists', {'idCard': a.card, 'name': a.name.strip(), 'pos': 'bottom'}

    if cmd == 'add-checklist-item':
        if not a.name.strip():
            raise ClientError('Checklist item text cannot be empty.')
        return 'POST', f'/checklists/{a.checklist}/checkItems', {'name': a.name.strip(), 'pos': 'bottom'}

    if cmd == 'set-checklist-item':
        return 'PUT', f'/cards/{a.card}/checkItem/{a.item}', {'state': a.state}

    raise ClientError(f'Unknown command: {cmd}')


def main(argv=None):
    try:
        parser = build_parser()
        args = parser.parse_args(argv)
        method, path, params = plan(args)
        result = Client().request(method, path, params)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ClientError as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
