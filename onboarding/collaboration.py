"""Pair and prove an explicitly selected private Tailscale A2A peer."""
import ipaddress
import json
import secrets
from urllib import request, error
from .http import NoRedirect
from .storage import SetupError, private_write, read_json


def private_ip(value):
    try:
        address = ipaddress.ip_address(value)
        if address not in ipaddress.ip_network('100.64.0.0/10'):
            raise ValueError()
        return str(address)
    except ValueError:
        raise SetupError('Use the intended peer’s private Tailscale IPv4 address.') from None


def configure(runtime, options):
    import re
    name = options.get('peer_name', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', name):
        raise SetupError('Select the named peer to pair.')
    ip = private_ip(options.get('peer_ip', ''))
    local = private_ip(runtime.run(['tailscale', 'ip', '-4']).stdout.strip().splitlines()[0])
    incoming, outgoing = options.get('incoming_token', ''), options.get('outgoing_token', '')
    if any(len(x) < 32 or any(c in x for c in ',:\n\r') for x in (incoming, outgoing)):
        raise SetupError('Pair both intended agents with separate private tokens of at least 32 characters.')
    env = runtime.env()
    peers = dict(part.split(':', 1) for part in env.get('A2A_PEER_TOKENS', '').split(',') if ':' in part)
    peers[name] = incoming
    trusted = set(filter(None, env.get('A2A_TRUSTED_PEERS', '').split(','))) | {name}
    runtime.save_env({'A2A_PEER_TOKENS': ','.join(k + ':' + v for k, v in peers.items()),
                      'A2A_TRUSTED_PEERS': ','.join(sorted(trusted)), 'A2A_ALLOW_ALL_USERS': 'false',
                      'A2A_HOST': '0.0.0.0' if runtime.kind == 'compose' else local,
                      'A2A_BIND_ADDRESS': local, 'A2A_PORT': '9900',
                      'A2A_PUBLIC_URL': 'http://' + local + ':9900'})
    runtime.set('a2a_agents.' + name, {'url': 'http://' + ip + ':9900', 'auth': {'type': 'bearer', 'token': outgoing}, 'timeout': 120})
    runtime.set('gateway.platforms.a2a.enabled', True)
    private_write(runtime.home / 'a2a.json', json.dumps({'peer_name': name, 'peer_ip': ip}) + '\n')


def verify(runtime):
    saved = read_json(runtime.home / 'a2a.json')
    peer = runtime.get('a2a_agents.' + saved.get('peer_name', '')) or {}
    url = 'http://' + private_ip(saved.get('peer_ip', '')) + ':9900'
    if peer.get('url') != url:
        raise SetupError('The saved private peer and running configuration disagree.')
    nonce = 'orgo-peer-check-' + secrets.token_hex(8)
    body = {'jsonrpc': '2.0', 'id': secrets.token_hex(8), 'method': 'SendMessage',
            'params': {'message': {'role': 'ROLE_USER', 'messageId': secrets.token_hex(16),
                                   'parts': [{'text': 'Harmless authorized setup check. Reply with exactly ' + nonce, 'mediaType': 'text/plain'}]}}}
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    def call(token):
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'A2A-Version': '1.0'}
        with opener.open(request.Request(url, data=json.dumps(body).encode(), headers=headers), timeout=120) as response:
            return json.loads(response.read(1_000_000))
    try:
        try:
            call(secrets.token_urlsafe(32))
        except error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code not in (401, 403):
                raise SetupError('The peer did not explicitly reject unknown credentials.')
        else:
            raise SetupError('The private peer accepted an unknown credential.')
        response = call(peer.get('auth', {}).get('token', ''))
        payload = response.get('result', {})
        payload = payload.get('task', payload.get('message', payload))
        messages = payload.get('artifacts', []) or [payload.get('status', {}).get('message', payload)]
        texts = [part.get('text', '') for message in messages for part in message.get('parts', [])]
        if response.get('error') or not any(nonce in text for text in texts):
            raise SetupError('The approved peer did not complete the harmless round trip.')
    except (OSError, ValueError):
        raise SetupError('The private peer could not complete its live connection check.') from None
