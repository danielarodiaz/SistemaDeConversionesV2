import argparse
import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[4]))

from backend.database import SessionLocal, init_db

from .config import load_config, validate_config
from .extractor_app_interna import export_from_app, filter_logistica_rows, read_logistica_excel
from .extractor_novedades import read_novedades_rows
from .matcher import match_and_prepare_updates
from .notificador import build_summary, send_summary
from .resolver_proveedor import ProveedorResolver
from .writer_novedades import apply_updates


def run_sync(
    *,
    dry_run: bool = True,
    excel_path: str | None = None,
    send_email: bool = False,
) -> dict:
    config = load_config()
    validate_config(config, need_app=excel_path is None, need_sheets=True, need_email=send_email)

    init_db()
    db = SessionLocal()
    try:
        if excel_path:
            exported_path = Path(excel_path)
        else:
            exported_path = export_from_app(config)

        raw_df = read_logistica_excel(exported_path)
        filtered_df, filtered_out = filter_logistica_rows(raw_df)

        worksheet, novedades_rows, headers = read_novedades_rows(config)
        resolver = ProveedorResolver(db, threshold=config.fuzzy_threshold)
        report = match_and_prepare_updates(filtered_df, novedades_rows, resolver, dry_run=dry_run)
        report.filtered_out = filtered_out

        if not dry_run:
            apply_updates(worksheet, headers, report.updates)

        db.commit()

        if send_email:
            send_summary(config, report)

        return report.as_dict() | {"summary": build_summary(report), "excel_path": str(exported_path)}
    except Exception as exc:
        db.rollback()
        error = f"{type(exc).__name__}: {exc}"
        try:
            from .modelos import SyncReport

            report = SyncReport(dry_run=dry_run, technical_errors=[error])
            if send_email:
                send_summary(config, report)
        except Exception:
            traceback.print_exc()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza NOVEDADES desde la app interna de logistica")
    parser.add_argument("--excel-path", help="Usa un Excel ya exportado en lugar de Playwright")
    parser.add_argument("--write", action="store_true", help="Escribe cambios en Google Sheets. Default: dry-run")
    parser.add_argument("--email", action="store_true", help="Envia mail de resumen")
    args = parser.parse_args()

    result = run_sync(
        dry_run=not args.write,
        excel_path=args.excel_path,
        send_email=args.email,
    )
    print(result["summary"])


if __name__ == "__main__":
    main()
