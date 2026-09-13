"""Small bounded HTTPS client. Never forwards credentials through redirects/proxies."""
import json
from urllib import request, error, parse

from .storage import SetupError


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, *, token="", header="Authorization", method="GET", body=None, timeout=20, missing_ok=False):
    parsed = parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise SetupError("A valid HTTPS service address is required.")
    headers = {"Accept": "application/json", "User-Agent": "orgo-onboarding/1"}
    if token:
        headers[header] = "Bearer " + token if header == "Authorization" else token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request.Request(url, headers=headers, data=data, method=method), timeout=timeout) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise SetupError("The service response exceeded the setup check limit.")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        status = exc.code
        exc.close()
        if status == 404 and missing_ok:
            return None
        if status in (401, 403):
            raise SetupError("The service rejected this credential or its access. Reconnect it to continue.") from None
        raise SetupError("The service check failed; retry or resume later.") from None
    except (OSError, ValueError):
        raise SetupError("The service did not return a usable response. Retry or resume later.") from None
