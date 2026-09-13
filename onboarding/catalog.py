"""Owner-facing choices, also consumed by setup agents via `catalog --json`."""

SERVICES = {
    "honcho": {
        "name": "Honcho memory", "recommended": True,
        "benefit": "Remember preferences and useful context across conversations.",
        "account": "A Honcho account and API key.",
        "charges": "Honcho usage may require a paid plan.",
        "access": "Selected conversations and identity mappings are sent to Honcho. Each installation gets a distinct agent identity.",
        "url": "https://app.honcho.dev", "keys": ["HONCHO_API_KEY"],
        "proof": "Write a harmless test fact, recall it in a new session, and check another agent cannot recall it.",
    },
    "latitude": {
        "name": "Latitude monitoring", "recommended": True,
        "benefit": "See traces, failures, timing, and usage to help evaluate improvements. Monitoring does not automatically optimize the agent.",
        "account": "A Latitude account, project, and API key.",
        "charges": "Trace storage and usage may require a paid plan.",
        "access": "Metadata by default. Sanitized conversation capture is a separate optional choice; redaction cannot guarantee all private information is removed.",
        "url": "https://app.latitude.so", "keys": ["LATITUDE_API_KEY", "LATITUDE_PROJECT_SLUG"],
        "proof": "An actual Hermes turn must produce an accepted trace under the selected privacy mode.",
    },
    "agentphone": {
        "name": "This agent's phone", "recommended": True,
        "benefit": "Approved business calls and texts, plus direct SMS and voice conversations with this running agent.",
        "account": "A separate AgentPhone provider identity, assigned number and credentials, plus an authorized Tailscale account for HTTPS.",
        "charges": "Phone numbers, calling, texting, and subscriptions may cost money. No number is purchased during basic setup.",
        "access": "AgentPhone processes phone numbers, messages and call transcripts. Only the signed phone webhook is public. Owner access requires an additional private passphrase; caller ID alone is insufficient.",
        "url": "https://agentphone.ai", "keys": ["AGENTPHONE_API_KEY"],
        "proof": "Approved inbound and outbound SMS and voice tests, with separate identities and delivery evidence.",
    },
    "agentmail": {
        "name": "This agent's inbox", "recommended": True,
        "benefit": "Give this installation its own email address for approved business communication.",
        "account": "An AgentMail account and dedicated inbox credentials.",
        "charges": "Inboxes and email volume may require a paid plan.",
        "access": "This agent can access its selected inbox. Worker profiles do not inherit the credential. Sending remains subject to approval.",
        "url": "https://agentmail.to", "keys": ["AGENTMAIL_API_KEY"],
        "mcp": "https://mcp.agentmail.to/mcp", "header": "x-api-key",
        "proof": "List this agent's inbox and read a harmless test message.",
    },
    "composio": {
        "name": "Calendar, inbox, Drive, and CRM", "benefit": "Work with the business apps you already use.",
        "account": "Composio and authorization for each selected app.",
        "charges": "Composio and connected apps may have subscription or usage charges.",
        "access": "Only the app accounts and scopes you approve. Start with read-only access and connect each app separately.",
        "url": "https://platform.composio.dev", "keys": ["COMPOSIO_API_KEY"],
        "proof": "Read a harmless record from every selected app; never send or modify records as an automatic test.",
    },
    "pandadoc": {
        "name": "PandaDoc proposals", "benefit": "Prepare proposals and agreements as private drafts.",
        "account": "A PandaDoc account and OAuth authorization for the correct region.",
        "charges": "PandaDoc may require a paid subscription.",
        "access": "Approved documents and templates. Sending a proposal requires separate approval.",
        "url": "https://app.pandadoc.com", "keys": [],
        "proof": "Read templates and create one explicitly selected unsent test draft.",
    },
    "super-browser": {
        "name": "Super Browser", "benefit": "Add browser automation and research capabilities.",
        "account": "A Super Browser account and its authenticated MCP connection.",
        "charges": "Browser sessions, research, and usage may incur charges.",
        "access": "Selected browsing activity, page content and authorized account sessions. External actions still need approval.",
        "url": "https://github.com/jbellsolutions/super-browser", "keys": [], "optional_keys": ["SUPER_BROWSER_TOKEN"],
        "proof": "Open a public page and extract its title using the connected service.",
    },
    "scrapecreators": {
        "name": "ScrapeCreators research", "benefit": "Research supported public social content.",
        "account": "A ScrapeCreators account and API key.",
        "charges": "Research requests consume paid credits where applicable.",
        "access": "Public profile and content queries are sent to ScrapeCreators.",
        "url": "https://scrapecreators.com", "keys": ["SCRAPECREATORS_API_KEY"],
        "proof": "Run a selected public-content lookup and inspect the returned record.",
    },
    "onepassword": {
        "name": "1Password", "benefit": "Keep authorized integration secrets in a dedicated vault.",
        "account": "1Password and an authorized service account with a narrowly scoped vault.",
        "charges": "A 1Password subscription may be required.",
        "access": "Only the vaults granted to this installation. Do not grant a personal vault by default.",
        "url": "https://1password.com", "keys": ["OP_SERVICE_ACCOUNT_TOKEN"],
        "proof": "Read metadata for the selected vault without displaying secret values.",
    },
    "a2a": {
        "name": "Private agent collaboration", "benefit": "Coordinate with individually approved teammates.",
        "account": "A working private network and a named agent at both ends.",
        "charges": "Network or hosting plans may have charges.",
        "access": "Only messages shared with approved peers. Peer messages cannot approve spending, permissions or private credential access.",
        "url": "https://tailscale.com", "keys": [],
        "proof": "An authenticated round trip to the selected private peer, with an unknown peer rejected.",
    },
    "agentcard": {
        "name": "AgentCard", "benefit": "A separate, optional way to prepare controlled purchasing workflows.",
        "account": "An AgentCard account with a TEST environment.",
        "charges": "Production transactions spend real money and require a later explicit decision.",
        "access": "TEST account metadata only; purchasing tools remain disabled. Never inherits phone or inbox approval.",
        "url": "https://agentcard.sh", "keys": ["AGENTCARD_API_KEY"],
        "proof": "Read back the provider's TEST mode before enabling any card tools.",
    },
}

CORE = ("identity", "runtime", "model", "channel")


def describe(service):
    item = SERVICES[service]
    return "\n".join((item["name"], item["benefit"], "Account: " + item["account"],
                      "Possible charges: " + item["charges"], "Data access: " + item["access"],
                      "Account link: " + item["url"], "Verification: " + item["proof"]))
