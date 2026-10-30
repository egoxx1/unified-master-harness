import os

API_URL = "https://alerts.example.invalid/v1/messages"


def api_token():
    token = os.environ.get("ALERTS_API_TOKEN")
    if not token:
        raise RuntimeError("ALERTS_API_TOKEN is not set; see README.md")
    return token
