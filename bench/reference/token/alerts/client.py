from alerts.format import format_alert
from alerts.settings import API_URL, api_token


def auth_headers():
    return {"Authorization": f"Bearer {api_token()}"}


def build_request(level, text):
    return {"url": API_URL, "headers": auth_headers(), "body": {"text": format_alert(level, text)}}
