from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

from .modelos import FieldUpdate, SheetRow, SyncIssue, SyncReport
from .normalizacion import (
    is_blank,
    is_blank_or_transito,
    normalize_guia,
    normalize_remito,
    only_date,
    parse_date_value,
    same_first_six_digits,
)
from .resolver_proveedor import ProveedorResolver


DEPOSITO_PRINCIPAL = "240001 - TUC -DEPOSITO"


def build_sheet_index(rows: list[SheetRow]) -> dict[tuple[str, str], list[SheetRow]]:
    index = defaultdict(list)
    for row in rows:
        remito = normalize_remito(row.values.get("REMITO", ""))
        cod_prov = str(row.values.get("COD. PROV.", "")).strip()
        if remito and cod_prov:
            index[(remito, cod_prov)].append(row)
    return index


def build_remito_index(rows: list[SheetRow]) -> dict[str, list[SheetRow]]:
    index = defaultdict(list)
    for row in rows:
        remito = normalize_remito(row.values.get("REMITO", ""))
        if remito:
            index[remito].append(row)
    return index


def calculate_desired_values(log_row: pd.Series) -> dict[str, str]:
    sucursal = _clean(log_row.get("Sucursal acuse", ""))
    desired = {
        "PUESTA": only_date(log_row.get("Fecha emision", "")),
        "RECIBIDA": only_date(log_row.get("Fecha acuse", "")),
        "TRANSPORTE": "SEVIL",
        "GUIA": normalize_guia(log_row.get("Nro factura", "")),
        "VD": _format_valor_declarado(log_row.get("Valor declarado", "")),
    }
    if sucursal and sucursal != DEPOSITO_PRINCIPAL:
        desired["OBSERVACIONES"] = sucursal
    return desired


def match_and_prepare_updates(
    logistica_df: pd.DataFrame,
    novedades_rows: list[SheetRow],
    resolver: ProveedorResolver,
    *,
    dry_run: bool,
) -> SyncReport:
    report = SyncReport(processed=len(logistica_df), dry_run=dry_run)
    sheet_index = build_sheet_index(novedades_rows)
    remito_index = build_remito_index(novedades_rows)

    for _, log_row in logistica_df.iterrows():
        remito_original = _clean(log_row.get("Nro remito", ""))
        remito = normalize_remito(remito_original)
        origen = _clean(log_row.get("Origen", ""))

        proveedor, resolver_info = resolver.resolve(origen)
        if resolver_info and resolver_info.get("score") is not None and resolver_info.get("cod_prov"):
            report.fuzzy_matches.append(resolver_info)

        if proveedor is None:
            report.unresolved_providers.append(SyncIssue(
                remito=remito_original,
                proveedor=origen,
                reason="proveedor_sin_resolver",
                detail=(resolver_info or {}).get("detail", "No se encontro match exacto ni fuzzy confiable en proveedores"),
            ))
            continue

        candidates = sheet_index.get((remito, proveedor.cod_prov), [])
        desired_values = calculate_desired_values(log_row)
        date_issue = _validate_dates(log_row, remito_original, proveedor.cod_prov)
        if date_issue:
            report.inconsistencies.append(date_issue)
            continue

        if len(candidates) > 1 and _duplicate_rows_can_be_updated(candidates, desired_values):
            duplicate_updates = []
            duplicate_conflicts = []
            for sheet_row in candidates:
                row_updates, row_conflicts = _prepare_row_updates(
                    sheet_row,
                    desired_values,
                    remito_original,
                    proveedor.cod_prov,
                )
                duplicate_updates.extend(row_updates)
                duplicate_conflicts.extend(row_conflicts)
            report.updates.extend(duplicate_updates)
            report.conflicts.extend(duplicate_conflicts)
            report.matched_rows += len(candidates)
            if not duplicate_conflicts:
                report.completed_ok += len(candidates)
            continue

        if len(candidates) != 1:
            if len(candidates) > 1:
                reason = "match_duplicado"
                detail = f"{len(candidates)} filas NOVEDADES para remito {remito} y proveedor {proveedor.cod_prov}"
            elif remito in remito_index:
                reason = "remito_con_otro_proveedor"
                codigos = sorted({str(r.values.get("COD. PROV.", "")).strip() for r in remito_index[remito]})
                detail = "El remito existe en NOVEDADES pero con COD. PROV.: " + ", ".join(codigos)
            else:
                reason = "sin_fila_novedades"
                detail = "No se encontro fila NOVEDADES para remito normalizado y proveedor"
            report.inconsistencies.append(SyncIssue(
                remito=remito_original,
                proveedor=f"{proveedor.cod_prov} - {origen}",
                reason=reason,
                detail=detail,
            ))
            continue

        sheet_row = candidates[0]
        row_updates, row_conflicts = _prepare_row_updates(sheet_row, desired_values, remito_original, proveedor.cod_prov)
        report.updates.extend(row_updates)
        report.conflicts.extend(row_conflicts)
        report.matched_rows += 1
        if not row_conflicts:
            report.completed_ok += 1

    return report


def _prepare_row_updates(
    sheet_row: SheetRow,
    desired_values: dict[str, str],
    remito_original: str,
    cod_prov: str,
) -> tuple[list[FieldUpdate], list[SyncIssue]]:
    updates = []
    conflicts = []
    for field, new_value in desired_values.items():
        if not new_value:
            continue
        old_value = _clean(sheet_row.values.get(field, ""))
        if _same_effective_value(field, old_value, new_value):
            continue

        if field in {"PUESTA", "RECIBIDA"}:
            if is_blank_or_transito(old_value):
                updates.append(FieldUpdate(sheet_row.row_number, field, old_value, new_value, remito_original))
            elif old_value != new_value:
                conflicts.append(_conflict(remito_original, cod_prov, field, old_value, new_value))
            continue

        if field == "OBSERVACIONES":
            if is_blank(old_value) or same_first_six_digits(old_value, new_value):
                updates.append(FieldUpdate(sheet_row.row_number, field, old_value, new_value, remito_original))
            elif old_value != new_value:
                conflicts.append(_conflict(remito_original, cod_prov, field, old_value, new_value))
            continue

        if is_blank(old_value):
            updates.append(FieldUpdate(sheet_row.row_number, field, old_value, new_value, remito_original))
        elif old_value != new_value:
            conflicts.append(_conflict(remito_original, cod_prov, field, old_value, new_value))
    return updates, conflicts


def _validate_dates(log_row: pd.Series, remito_original: str, cod_prov: str) -> SyncIssue | None:
    puesta = parse_date_value(log_row.get("Fecha emision", ""))
    recibida = parse_date_value(log_row.get("Fecha acuse", ""))
    if puesta is not None and recibida is not None and recibida.date() < puesta.date():
        return SyncIssue(
            remito=remito_original,
            proveedor=cod_prov,
            reason="fecha_inconsistente",
            detail=(
                "RECIBIDA no puede ser menor que PUESTA "
                f"(PUESTA={puesta.strftime('%d/%m/%Y')}, RECIBIDA={recibida.strftime('%d/%m/%Y')})"
            ),
        )
    return None


def _duplicate_rows_can_be_updated(rows: list[SheetRow], desired_values: dict[str, str]) -> bool:
    desired_obs = desired_values.get("OBSERVACIONES", "")
    if not desired_obs:
        current_values = {_clean(row.values.get("OBSERVACIONES", "")) for row in rows}
        return len(current_values) <= 1
    return all(
        is_blank(row.values.get("OBSERVACIONES", ""))
        or _clean(row.values.get("OBSERVACIONES", "")) == desired_obs
        or same_first_six_digits(row.values.get("OBSERVACIONES", ""), desired_obs)
        for row in rows
    )


def _conflict(remito: str, proveedor: str, field: str, old_value: str, new_value: str) -> SyncIssue:
    return SyncIssue(
        remito=remito,
        proveedor=proveedor,
        reason="dato_previo_distinto",
        field=field,
        old_value=old_value,
        new_value=new_value,
        detail="No se sobreescribio el dato existente",
    )


def _same_effective_value(field: str, old_value: str, new_value: str) -> bool:
    if old_value == new_value:
        return True
    if field in {"PUESTA", "RECIBIDA"}:
        old_date = parse_date_value(old_value)
        new_date = parse_date_value(new_value)
        return old_date is not None and new_date is not None and old_date.date() == new_date.date()
    if field == "VD":
        old_amount = _parse_money_value(old_value)
        new_amount = _parse_money_value(new_value)
        return old_amount is not None and new_amount is not None and old_amount == new_amount
    return _canonical_text(old_value) == _canonical_text(new_value)


def _canonical_text(value: Any) -> str:
    return " ".join(_clean(value).upper().split())


def _format_valor_declarado(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (int, float)):
        return f"{value:.2f}".replace(".", ",")

    text = _clean(value)
    if not text:
        return ""

    if "," in text and "." in text:
        comma_pos = text.rfind(",")
        dot_pos = text.rfind(".")
        if dot_pos > comma_pos:
            return text.replace(",", "").replace(".", ",")
        return text

    if "." in text and "," not in text:
        return text.replace(".", ",")

    return text


def _parse_money_value(value: Any) -> Decimal | None:
    text = _clean(value)
    if not text:
        return None

    text = (
        text.replace("$", "")
        .replace("\u00a0", "")
        .replace(" ", "")
        .strip()
    )
    if not text:
        return None

    comma_pos = text.rfind(",")
    dot_pos = text.rfind(".")

    if comma_pos >= 0 and dot_pos >= 0:
        if comma_pos > dot_pos:
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif comma_pos >= 0:
        decimals = len(text) - comma_pos - 1
        normalized = text.replace(",", ".") if decimals in {1, 2} else text.replace(",", "")
    elif dot_pos >= 0:
        decimals = len(text) - dot_pos - 1
        normalized = text if decimals in {1, 2} else text.replace(".", "")
    else:
        normalized = text

    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null", "nat"} else text
