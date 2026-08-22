import re


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()
