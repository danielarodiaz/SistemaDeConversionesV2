import smtplib
from email.message import EmailMessage

from .config import SyncNovedadesConfig
from .modelos import SyncIssue, SyncReport


def build_summary(report: SyncReport) -> str:
    lines = [
        "Resumen sync NOVEDADES - App Logistica",
        "",
        f"Modo dry-run: {'SI' if report.dry_run else 'NO'}",
        f"Filas procesadas: {report.processed}",
        f"Filas filtradas/descartadas: {report.filtered_out}",
        f"Filas con match NOVEDADES: {report.matched_rows}",
        f"Filas completadas OK: {report.completed_ok}",
        f"Celdas a actualizar/actualizadas: {len(report.updates)}",
        "",
    ]

    if report.unresolved_providers:
        lines.extend(_section("Proveedores sin resolver", report.unresolved_providers))
    if report.inconsistencies:
        lines.extend(_section("Inconsistencias de cruce", report.inconsistencies))
    if report.conflicts:
        lines.extend(_section("Datos previos distintos no sobreescritos", report.conflicts))
    if report.fuzzy_matches:
        lines.append("Matches fuzzy auditados:")
        for item in report.fuzzy_matches:
            lines.append(
                f"- Origen: {item.get('origen_original')} | Proveedor: {item.get('cod_prov')} "
                f"({item.get('razon_social')}) | Score: {item.get('score')}"
            )
        lines.append("")
    if report.technical_errors:
        lines.append("Errores tecnicos:")
        for error in report.technical_errors:
            lines.append(f"- {error}")
        lines.append("")

    if not any([report.unresolved_providers, report.inconsistencies, report.conflicts, report.technical_errors]):
        lines.append("No se registraron casos pendientes de revision.")

    return "\n".join(lines)


def send_summary(config: SyncNovedadesConfig, report: SyncReport) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Sync NOVEDADES - resumen de corrida"
    msg["From"] = config.smtp_from
    msg["To"] = config.notify_to
    msg.set_content(build_summary(report))

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(msg)


def _section(title: str, issues: list[SyncIssue]) -> list[str]:
    lines = [f"{title}:"]
    for item in issues:
        extra = ""
        if item.field:
            extra = f" | Campo: {item.field} | Viejo: {item.old_value} | Nuevo: {item.new_value}"
        lines.append(
            f"- Remito: {item.remito} | Proveedor/Origen: {item.proveedor} | "
            f"Motivo: {item.reason} | {item.detail}{extra}"
        )
    lines.append("")
    return lines
