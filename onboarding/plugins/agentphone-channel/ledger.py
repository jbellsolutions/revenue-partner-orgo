"""Private durable inbox/outbox. Ambiguous sends are held for reconciliation."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import time


def signed(raw, headers, secret, now=None):
    timestamp = headers.get("X-Webhook-Timestamp", "")
    signature = headers.get("X-Webhook-Signature", "")
    if not secret or not re.fullmatch(r"[0-9]{1,12}", timestamp):
        return False
    if abs((time.time() if now is None else now) - int(timestamp)) > 300:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), signature.encode())


def password_hash(passphrase, salt):
    return hashlib.scrypt(passphrase.strip().casefold().encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class Ledger:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(path.parent, 0o700)
        if path.is_symlink():
            raise ValueError("Phone ledger must not be a symlink")
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA journal_mode=DELETE;
          PRAGMA synchronous=FULL;
          CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, chat TEXT NOT NULL,
            channel TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
            reply TEXT, provider_id TEXT, created REAL NOT NULL, updated REAL NOT NULL
          );
          CREATE TABLE IF NOT EXISTS access (
            caller TEXT PRIMARY KEY, expires REAL NOT NULL DEFAULT 0,
            failures INTEGER NOT NULL DEFAULT 0, window REAL NOT NULL DEFAULT 0
          );
        ''')
        # A process may have died before computing a reply. Toolsets on this channel
        # cannot perform business mutations; it is safe to resume computation.
        self.db.execute("UPDATE events SET state='pending' WHERE state='processing' AND channel='sms'")
        # An HTTP timeout/crash can mean delivery succeeded. Do not blindly resend.
        self.db.execute("UPDATE events SET state='needs_attention' WHERE state='sending'")
        self.db.execute("UPDATE events SET state='expired' WHERE channel='voice' AND state IN ('pending','processing','ready')")
        self.db.commit()

    def add(self, event_id, payload):
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self.db.execute("SELECT 1 FROM events WHERE id=? OR digest=?", (event_id, digest)).fetchone():
            return False
        count = self.db.execute("SELECT COUNT(*) FROM events WHERE state IN ('pending','processing','ready')").fetchone()[0]
        if count >= 500:
            raise OverflowError("Phone queue is full")
        now = time.time()
        self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,'pending',NULL,NULL,?,?)",
                        (event_id, digest, payload["chat"], payload["channel"], json.dumps(payload), now, now))
        self.db.commit()
        return True

    def get(self, event_id):
        row = self.db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return dict(row) if row else None

    def update(self, event_id, state, *, reply=None, provider_id=None):
        if state not in {"pending", "processing", "ready", "sending", "sent", "needs_attention", "expired"}:
            raise ValueError("Invalid delivery state")
        self.db.execute("UPDATE events SET state=?, reply=COALESCE(?,reply), provider_id=COALESCE(?,provider_id), updated=? WHERE id=?",
                        (state, reply, provider_id, time.time(), event_id))
        self.db.commit()

    def pending(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM events WHERE channel='sms' AND state IN ('pending','ready') ORDER BY created")]

    def authenticate(self, caller, text, config, now=None):
        now = time.time() if now is None else now
        row = self.db.execute("SELECT * FROM access WHERE caller=?", (caller,)).fetchone()
        row = dict(row) if row else {"expires": 0, "failures": 0, "window": now}
        # Always remove a supplied secret before any persistence or model invocation.
        match = re.match(r"^access\s+(.+?)\.\s*(.*)$", text, re.I | re.S)
        if row["expires"] > now and not match:
            return text
        if row["window"] < now - 900:
            row.update(failures=0, window=now)
        if row["failures"] >= 5:
            return None
        valid = bool(match and hmac.compare_digest(password_hash(match[1], config["salt"]), config["hash"]))
        self.db.execute("INSERT OR REPLACE INTO access VALUES (?,?,?,?)",
                        (caller, now + 900 if valid else 0, 0 if valid else row["failures"] + 1, row["window"]))
        self.db.commit()
        return (match[2] or "Hello.") if valid else None

    def expire_access(self, caller):
        self.db.execute("DELETE FROM access WHERE caller=?", (caller,))
        self.db.commit()

    def prune(self):
        self.db.execute("DELETE FROM access WHERE expires < ? AND window < ?", (time.time() - 900, time.time() - 900))
        self.db.execute("DELETE FROM events WHERE state IN ('sent','expired') AND updated < ?", (time.time() - 7 * 86400,))
        self.db.commit()
