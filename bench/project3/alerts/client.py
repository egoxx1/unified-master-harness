from alerts.format import format_alert
from alerts.settings import API_TOKEN, API_URL


def auth_headers():
    return {"Authorization": f"Bearer {API_TOKEN}"}


def build_request(level, text):
    return {"url": API_URL, "headers": auth_headers(), "body": {"text": format_alert(level, text)}}
