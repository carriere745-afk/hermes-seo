"""S07 — Alertes.

Centralise toutes les alertes generees par S02 et S02b.
Deduplique, priorise et dispatch vers les canaux (UI, Email, Webhook).

En cas de Core Update detecte : les alertes individuelles sont inhibees
pendant 7 jours. Les donnees continuent d'etre collectees.

Non skippable.

$0 — deterministe.
"""

import logging
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState, AlertEntry

logger = logging.getLogger("hermes.serp.sv07")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv07"

    # 1. Dedupliquer les alertes (meme type + meme keyword)
    seen = set()
    deduped = []
    for alert in state.alerts:
        key = (alert.type, alert.keyword, alert.url)
        if key not in seen:
            seen.add(key)
            deduped.append(alert)

    # 2. Inhiber les alertes individuelles si Core Update
    if state.core_update_detected:
        deduped = [a for a in deduped if a.type == "core_update"]
        logger.info("S07: Core Update actif — seules les alertes Core Update sont conservees")

    state.alerts = deduped

    # 3. Logger et stocker dans SQLite
    try:
        from hermes.core.serp_db import insert_alert
        for alert in state.alerts:
            insert_alert({
                "type": alert.type, "keyword": alert.keyword,
                "url": alert.url, "valeur_avant": alert.valeur_avant,
                "valeur_apres": alert.valeur_apres, "priorite": alert.priorite,
                "canal": alert.canal, "statut": alert.statut,
                "date": alert.date.isoformat(), "note": alert.note,
            })
    except Exception as e:
        logger.debug(f"S07: SQLite alert store failed ({e})")

    # 4. Notifications P0 (email)
    p0_alerts = [a for a in state.alerts if a.priorite == "P0"]
    if p0_alerts:
        _send_email_alerts(p0_alerts, state.site_url)

    logger.info(f"S07: {len(state.alerts)} alertes actives ({len(p0_alerts)} P0)")
    state.updated_at = datetime.now()
    return state


def _send_email_alerts(alerts: list[AlertEntry], site_url: str):
    """Envoie les alertes P0 par email (si SMTP configure)."""
    try:
        from hermes import config
        smtp_host = getattr(config, "SMTP_HOST", "")
        if not smtp_host:
            logger.debug("S07: SMTP non configure — skip email")
            return

        import smtplib
        from email.mime.text import MIMEText

        body = f"Hermes SEO — Alertes P0 pour {site_url}\n\n"
        for a in alerts:
            body += f"[{a.type}] {a.keyword}: {a.valeur_avant} → {a.valeur_apres}\n"
            body += f"  {a.note}\n\n"

        msg = MIMEText(body)
        msg["Subject"] = f"Hermes SEO — {len(alerts)} alerte(s) P0 pour {site_url}"
        msg["From"] = getattr(config, "SMTP_FROM", "hermes@localhost")

        smtp_to = getattr(config, "SMTP_TO", "")
        if smtp_to:
            msg["To"] = smtp_to
            with smtplib.SMTP(smtp_host, int(getattr(config, "SMTP_PORT", 587))) as server:
                if getattr(config, "SMTP_TLS", True):
                    server.starttls()
                user = getattr(config, "SMTP_USER", "")
                pwd = getattr(config, "SMTP_PASSWORD", "")
                if user:
                    server.login(user, pwd)
                server.send_message(msg)
            logger.info(f"S07: {len(alerts)} alertes P0 envoyees par email")
    except Exception as e:
        logger.warning(f"S07: email notification failed ({e})")
