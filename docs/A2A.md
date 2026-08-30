# Private agent-to-agent connection

Revenue Partner and Head of Ops use Hermes' A2A 1.0 support over a private
Tailscale network. No public A2A port is required.

Each direction has its own long random token. Each computer trusts exactly the
other agent's name, logs exchanges to `~/.hermes/a2a_audit.jsonl`, rate-limits
requests, and stops ping-pong loops after three turns. The `a2a` toolset is
enabled for the owner's CLI, Slack, and Telegram sessions. It is deliberately
not enabled for inbound A2A sessions, so one incoming peer request cannot chain
into another agent call.

On each computer, connect Tailscale, then run:

```bash
./orgo/connect-a2a.sh
```

Enter the other computer's Tailscale address and the two one-direction tokens.
After both sides are configured, ask Revenue Partner:

```text
Discover Head of Ops and ask it for a one-sentence readiness check. Do not take
any external action.
```

Then inspect the audit log and confirm the request was attributed to the named
peer. External sends, calendar changes, proposals, spending, publishing, and
customer-record changes remain behind the same human approval rules whether a
request starts in Slack or arrives through A2A.
