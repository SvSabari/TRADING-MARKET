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
    "aliceblue": {
        "name": "Alice Blue",
        "docs": "https://ant.aliceblueonline.com/",
        "redirect_required": True,
        "fields": [
            {"name": "user_id", "label": "Client ID", "type": "text", "required": True,
             "help": "Your Alice Blue Client Code."},
            {"name": "api_key", "label": "API Key", "type": "text", "required": True,
             "help": "App Code from Alice Blue Developer Portal."},
            {"name": "api_secret", "label": "API Secret", "type": "password", "required": True,
             "help": "App Secret from Alice Blue Developer Portal."},
        ],
        "post_save_action": "aliceblue_oauth",
    },
    "mock": {
        "name": "Mock (Paper trading)",
        "docs": "",
        "fields": [],
    },
}
