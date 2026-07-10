import re
import unicodedata
from datetime import datetime
from typing import Any

import pandas as pd


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace(".", " ")
    text = re.sub(r"[^A-Z0-9&\-\s]", " ", text)
    text = re.sub(r"\bS\s*A\b", "SA", text)
    text = re.sub(r"\bS\s*R\s*L\b", "SRL", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_remito(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    text = re.sub(r"^0{4}\s*-\s*", "", text)
    digits = re.sub(r"\D", "", text)
    normalized = digits.lstrip("0")
    # TODO: Confirmar la normalizacion exacta entre Nro remito app y REMITO NOVEDADES con un caso real.
    return normalized or "0"


def normalize_guia(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s*-\s*", "-", str(value).strip())


def is_blank_or_transito(value: Any) -> bool:
    text = "" if value is None else str(value).strip()
    return text == "" or text.upper() == "TRANSITO"


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def only_date(value: Any) -> str:
    parsed = parse_date_value(value)
    return parsed.strftime("%d/%m/%Y") if parsed is not None else ""


def parse_date_value(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
    text = str(value).strip()
    if not text:
        return None

    iso_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:\s+.*)?$", text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return datetime(year, month, day)

    dmy_match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+.*)?$", text)
    if dmy_match:
        day, month, year = map(int, dmy_match.groups())
        return datetime(year, month, day)

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def first_six_digits(value: Any) -> str:
    match = re.search(r"\d{6}", "" if value is None else str(value))
    return match.group(0) if match else ""


def same_first_six_digits(left: Any, right: Any) -> bool:
    left_digits = first_six_digits(left)
    right_digits = first_six_digits(right)
    return bool(left_digits and right_digits and left_digits == right_digits)
