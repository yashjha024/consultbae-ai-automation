"""Deterministic, non-destructive normalizers used by ingestion and matching."""
from __future__ import annotations

import re
import unicodedata


def _text(value: object) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def normalize_email(value: object) -> str | None:
    value = _text(value)
    if not value:
        return None
    value = value.casefold()
    # This deliberately validates only basic address shape; it does not alter aliases.
    return value if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value) else None


def normalize_phone(value: object) -> str | None:
    value = _text(value)
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    # Dataset is Indian phone data. Accept local 10 digits or 91-prefixed numbers.
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return f"+91{digits}" if len(digits) == 10 and digits[0] in "6789" else None


def normalize_name(value: object) -> str | None:
    value = _text(value)
    if not value:
        return None
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-zA-Z ]", " ", value).casefold()
    value = " ".join(value.split())
    return value or None


_CITIES = {
    "bangalore": "bengaluru", "bengaluru": "bengaluru",
    "gurgaon": "gurugram", "gurugram": "gurugram",
    "new delhi": "delhi ncr", "delhi ncr": "delhi ncr", "delhi": "delhi ncr",
    "noida": "noida", "pune": "pune",
}


def normalize_city(value: object) -> str | None:
    value = _text(value)
    return _CITIES.get(" ".join(value.casefold().split())) if value else None


def normalize_status(value: object) -> str | None:
    value = _text(value)
    if not value:
        return None
    value = value.casefold()
    return {"y": "verified", "yes": "verified", "n": "not_verified", "no": "not_verified"}.get(value, value)


def normalize_skills(value: object) -> list[str]:
    value = _text(value)
    if not value:
        return []
    return sorted({" ".join(x.casefold().split()) for x in value.split(",") if x.strip()})
