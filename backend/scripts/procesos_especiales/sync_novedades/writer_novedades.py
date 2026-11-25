from .modelos import FieldUpdate


def column_letters(headers: list[str]) -> dict[str, str]:
    return {header: _letter(index + 1) for index, header in enumerate(headers)}


def apply_updates(worksheet, headers: list[str], updates: list[FieldUpdate]) -> None:
    if not updates:
        return
    letters = column_letters(headers)
    missing = sorted({u.column_name for u in updates if u.column_name not in letters})
    if missing:
        raise ValueError("NOVEDADES no contiene columnas requeridas: " + ", ".join(missing))

    payload = []
    for update in updates:
        cell = f"{letters[update.column_name]}{update.row_number}"
        payload.append({"range": cell, "values": [[update.new_value]]})
    worksheet.batch_update(payload, value_input_option="USER_ENTERED")


def _letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result
