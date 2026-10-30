LEVELS = ("info", "warning", "critical")


def format_alert(level, text):
    if level not in LEVELS:
        raise ValueError(f"unknown level: {level}")
    return f"[{level.upper()}] {text.strip()}"
