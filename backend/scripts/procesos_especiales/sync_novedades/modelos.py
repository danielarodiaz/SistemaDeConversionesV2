from dataclasses import dataclass, field
from typing import Any


LOGISTICA_COLUMNS = [
    "Nro remito", "Nro factura", "Fecha emision", "Origen", "Destino", "Bultos", "Kilos", "Tarifa",
    "Valor declarado", "Seguro", "Creado por", "Creado en", "Transporte", "Usuario transporte interno",
    "Estado", "Acusado por", "Sucursal acuse", "Fecha acuse", "Motivo",
]

NOVEDADES_COLUMNS = [
    "SISTEMA", "C", "EMPRESA", "PIVOT", "COD. PROV.", "MARCA", "TIPO", "FACTURA/NC", "EMISION",
    "SUBTOTAL", "TOTAL", "PUESTA", "RECIBIDA", "VTO.", "PRONTO", "DESC FINAN.", "ESTADO", "FECHA PAGO",
    "OBSERVACIONES", "nota", "TRANSPORTE", "GUIA", "REMITO", "VD", "DIF",
]

WRITABLE_FIELDS = ("PUESTA", "RECIBIDA", "OBSERVACIONES", "TRANSPORTE", "GUIA", "VD")


@dataclass
class ProveedorResuelto:
    id: int
    cod_prov: str
    razon_social: str
    marca: str
    pivot: str
    tipo: str
    metodo: str
    score: float


@dataclass
class SheetRow:
    row_number: int
    values: dict[str, Any]


@dataclass
class FieldUpdate:
    row_number: int
    column_name: str
    old_value: str
    new_value: str
    remito: str = ""


@dataclass
class SyncIssue:
    remito: str
    proveedor: str
    reason: str
    detail: str = ""
    field: str = ""
    old_value: str = ""
    new_value: str = ""


@dataclass
class SyncReport:
    processed: int = 0
    filtered_out: int = 0
    matched_rows: int = 0
    completed_ok: int = 0
    updates: list[FieldUpdate] = field(default_factory=list)
    unresolved_providers: list[SyncIssue] = field(default_factory=list)
    inconsistencies: list[SyncIssue] = field(default_factory=list)
    conflicts: list[SyncIssue] = field(default_factory=list)
    technical_errors: list[str] = field(default_factory=list)
    fuzzy_matches: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "filtered_out": self.filtered_out,
            "matched_rows": self.matched_rows,
            "completed_ok": self.completed_ok,
            "updates": [
                {
                    "remito": u.remito,
                    "column_name": u.column_name,
                    "old_value": u.old_value,
                    "new_value": u.new_value,
                }
                for u in self.updates
            ],
            "unresolved_providers": [i.__dict__ for i in self.unresolved_providers],
            "inconsistencies": [i.__dict__ for i in self.inconsistencies],
            "conflicts": [i.__dict__ for i in self.conflicts],
            "technical_errors": self.technical_errors,
            "fuzzy_matches": self.fuzzy_matches,
            "dry_run": self.dry_run,
        }
