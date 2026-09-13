"""Discover provider identities privately; setup AI resolves IDs for the owner."""
import json
import time
from urllib.parse import quote
from .http import fetch
from .storage import SetupError, private_write, read_json


def rows(value, key):
    if isinstance(value, list):
        return value
    return value.get(key, value.get('data', value.get('items', [])))


def inventory(runtime, service, options=None):
    options = options or {}
    env = {**runtime.env(), **options}
    if service == 'agentphone':
        agents = rows(fetch('https://api.agentphone.ai/v1/agents', token=env.get('AGENTPHONE_API_KEY', '')), 'agents')
        numbers = rows(fetch('https://api.agentphone.ai/v1/numbers', token=env.get('AGENTPHONE_API_KEY', '')), 'numbers')
        return {'agents': [{'id': x['id'], 'name': x.get('name', ''), 'voiceMode': x.get('voiceMode')} for x in agents],
                'numbers': [{'id': x['id'], 'number': x.get('phoneNumber', x.get('number')), 'agentId': x.get('agentId')} for x in numbers]}
    if service == 'agentmail':
        data = fetch('https://api.agentmail.to/v0/inboxes', token=env.get('AGENTMAIL_API_KEY', ''))
        return {'inboxes': [{k: x.get(k) for k in ('inbox_id', 'email', 'display_name', 'client_id')} for x in rows(data, 'inboxes')]}
    if service == 'onepassword':
        data = json.loads(runtime.command('op', 'vault', 'list', '--format=json', extra_env={'OP_SERVICE_ACCOUNT_TOKEN': env.get('OP_SERVICE_ACCOUNT_TOKEN', '')}).stdout)
        return {'vaults': [{'id': x['id'], 'name': x.get('name', '')} for x in data]}
    raise SetupError('Discovery is available for phone identities, inboxes and dedicated vaults.')


def select_inbox(runtime, options):
    identity = read_json(runtime.home / 'orgo-identity.json')
    existing = inventory(runtime, 'agentmail')['inboxes']
    chosen = options.get('inbox_id') or read_json(runtime.home / 'agentmail.json').get('inbox_id')
    client_id = 'orgo-' + identity.get('instance_id', '')
    if not chosen and options.get('create_inbox_selected') is True:
        matches = [x for x in existing if x.get('client_id') == client_id]
        if len(matches) == 1:
            chosen = matches[0]['inbox_id']
        elif matches:
            raise SetupError('Select the intended existing inbox; more than one matches this installation.')
        else:
            attempt = runtime.state.directory / 'inbox-creation.json'
            if attempt.exists():
                raise SetupError('The prior inbox request is unresolved. Recheck the provider account before creating another inbox.')
            private_write(attempt, json.dumps({'client_id': client_id, 'state': 'pending', 'started_at': time.time()}) + '\n')
            created = fetch('https://api.agentmail.to/v0/inboxes', token=runtime.env()['AGENTMAIL_API_KEY'], method='POST',
                            body={'display_name': identity.get('display_name', runtime.role['name']), 'client_id': client_id})
            if not created.get('inbox_id'):
                raise SetupError('Inbox creation needs provider reconciliation before retrying.')
            chosen = created['inbox_id']
            existing.append(created)
            private_write(attempt, json.dumps({'inbox_id': chosen, 'state': 'confirmed'}) + '\n')
    if not chosen or not any(x.get('inbox_id') == chosen for x in existing):
        raise SetupError('Select this agent’s dedicated inbox, or explicitly select creation of a new inbox.')
    # A real selected-resource read proves authorization, not just account discovery.
    fetch('https://api.agentmail.to/v0/inboxes/' + quote(chosen, safe=''), token=runtime.env()['AGENTMAIL_API_KEY'])
    return chosen


def choose(items, label, id_key='id', display_key='name'):
    if not items:
        raise SetupError('No ' + label + ' are available. The setup agent can create the selected resource after account authorization.')
    for n, value in enumerate(items, 1):
        print(str(n) + '. ' + str(value.get(display_key) or value[id_key]))
    answer = input('Select ' + label + ' by number, or leave blank to finish later: ').strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(items):
        raise SetupError('This selection was left unfinished.')
    return items[int(answer) - 1]
