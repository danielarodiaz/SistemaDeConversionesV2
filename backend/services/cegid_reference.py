from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional


@dataclass(frozen=True)
class CegidDocumentRef:
    fecha: Optional[str]
    naturaleza: str
    souche: str
    numero: str
    indice: str
    linea: Optional[str] = None

    @property
    def document_key(self) -> str:
        return build_document_key(self.naturaleza, self.souche, self.numero, self.indice)

    @property
    def line_key(self) -> Optional[str]:
        if not self.linea:
            return None
        return f"{self.document_key}:{self.linea}"


def normalize_code(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_nature(value) -> str:
    return normalize_code(value).upper()


def build_document_key(naturaleza, souche, numero, indice=0) -> str:
    return "|".join([
        normalize_nature(naturaleza),
        normalize_code(souche),
        normalize_code(numero),
        normalize_code(indice or 0),
    ])


def parse_document_ref(value) -> Optional[CegidDocumentRef]:
    """
    CEGID guarda referencias como:
      15052026;ALF;002;7879;0;;
      14052026;CF;002;7944;0;2;

    Los primeros 5 campos identifican el documento y el sexto, si existe,
    identifica la linea original/predecesora.
    """
    raw = normalize_code(value)
    if not raw or raw.lower() == "nan":
        return None

    parts = raw.split(";")
    if len(parts) < 5:
        return None

    linea = parts[5].strip() if len(parts) > 5 and parts[5].strip() else None
    return CegidDocumentRef(
        fecha=parts[0].strip() or None,
        naturaleza=normalize_nature(parts[1]),
        souche=normalize_code(parts[2]),
        numero=normalize_code(parts[3]),
        indice=normalize_code(parts[4]) or "0",
        linea=linea,
    )


def parse_cegid_date(value):
    raw = normalize_code(value)
    if not raw or raw.startswith("1900-01-01") or raw.startswith("1899-12-30"):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", ""))
    except ValueError:
        return None


def parse_cegid_decimal(value, scale=None) -> Decimal:
    raw = normalize_code(value)
    if not raw or raw.lower() == "nan":
        return Decimal("0")
    try:
        parsed = Decimal(raw)
    except InvalidOperation:
        return Decimal("0")
    return parsed / Decimal(scale) if scale else parsed
