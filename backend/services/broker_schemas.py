"""Broker field schemas — what each broker needs to authenticate.

The frontend renders a dynamic form using this schema. Backend accepts
a flat dict `credentials` and stores it encrypted.
"""

# field def:
#   name      — backend key
#   label     — UI label
#   type      — text / password / number
#   required  — bool
#   help      — short hint (markdown allowed)
BROKER_SCHEMAS = {
    "zerodha": {
        "name": "Zerodha Kite Connect",
        "docs": "https://developers.kite.trade",
        "redirect_required": True,
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "text", "required": True,
             "help": "From kite.trade → Create App → API Key."},
            {"name": "api_secret", "label": "API Secret", "type": "password", "required": True,
             "help": "Pair with the API key. Shown once when you create the app."},
        ],
        "post_save_action": "kite_oauth",
    },
    "breeze": {
        "name": "ICICI Breeze",
        "docs": "https://api.icicidirect.com/breezeapi/documents",
        "fields": [
            {"name": "api_key", "label": "App Key", "type": "text", "required": True,
             "help": "Generated from the Breeze dashboard."},
            {"name": "api_secret", "label": "Secret Key", "type": "password", "required": True},
            {"name": "session_token", "label": "Session Token", "type": "password", "required": True,
             "help": "Generated daily via the Breeze customer-login flow."},
        ],
    },
    "angel": {
        "name": "Angel One SmartAPI",
        "docs": "https://smartapi.angelbroking.com",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "text", "required": True},
            {"name": "client_code", "label": "Client Code", "type": "text", "required": True,
             "help": "Your Angel client ID, e.g. A123456."},
            {"name": "pin", "label": "MPIN", "type": "password", "required": True},
            {"name": "totp_secret", "label": "TOTP Secret", "type": "password", "required": True,
             "help": "Base32 TOTP seed from the Angel SmartAPI portal."},
        ],
    },
    "fyers": {
        "name": "Fyers API v3",
        "docs": "https://myapi.fyers.in",
        "redirect_required": True,
        "fields": [
            {"name": "api_key", "label": "App ID", "type": "text", "required": True},
            {"name": "api_secret", "label": "Secret ID", "type": "password", "required": True},
        ],
    },
    "upstox": {
        "name": "Upstox API",
        "docs": "https://upstox.com/developer",
        "redirect_required": True,
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "text", "required": True},
            {"name": "api_secret", "label": "API Secret", "type": "password", "required": True},
        ],
    },
    "dhan": {
        "name": "Dhan HQ",
        "docs": "https://dhanhq.co/docs",
        "fields": [
            {"name": "client_id", "label": "Client ID", "type": "text", "required": True},
            {"name": "access_token", "label": "Access Token", "type": "password", "required": True,
             "help": "Generated from the Dhan trader portal → API."},
        ],
    },
    "mock": {
        "name": "Mock (Paper trading)",
        "docs": "",
        "fields": [],
    },
}
