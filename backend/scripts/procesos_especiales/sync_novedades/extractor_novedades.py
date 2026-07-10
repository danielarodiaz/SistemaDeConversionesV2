from .config import SyncNovedadesConfig
from .modelos import SheetRow


def get_worksheet(config: SyncNovedadesConfig):
    try:
        import gspread
    except ImportError as exc:
        raise RuntimeError("gspread no esta instalado para leer Google Sheets") from exc

    client = gspread.service_account(filename=config.google_service_account_file)
    spreadsheet = client.open_by_key(config.google_spreadsheet_id)
    return spreadsheet.worksheet(config.google_worksheet_name)


def read_novedades_rows(config: SyncNovedadesConfig) -> tuple[object, list[SheetRow], list[str]]:
    worksheet = get_worksheet(config)
    values = worksheet.get_all_values()
    if not values:
        return worksheet, [], []

    headers = [h.strip() for h in values[0]]
    rows = []
    for index, row in enumerate(values[1:], start=2):
        data = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        rows.append(SheetRow(row_number=index, values=data))
    return worksheet, rows, headers
