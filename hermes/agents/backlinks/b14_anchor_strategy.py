"""B14 — Anchor Strategy Engine.

Analyse le profil d'ancres actuel vs cible, genere des suggestions concretes
de textes d'ancre, alerte sur le ratio follow/nofollow.
Non skippable (MVP). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b14")

ANCHOR_TARGETS = {
    "blog": {"brand": 40, "partial_match": 20, "long_tail": 15, "url_naked": 10, "generic": 10, "exact_match": 5},
    "ecommerce": {"brand": 40, "partial_match": 15, "long_tail": 15, "url_naked": 10, "generic": 10, "exact_match": 10},
    "saas": {"brand": 45, "partial_match": 20, "long_tail": 15, "url_naked": 8, "generic": 7, "exact_match": 5},
    "local": {"brand": 35, "partial_match": 20, "long_tail": 15, "url_naked": 10, "generic": 10, "exact_match": 10},
    "corporate": {"brand": 50, "partial_match": 15, "long_tail": 10, "url_naked": 10, "generic": 10, "exact_match": 5},
    "agressif": {"brand": 25, "partial_match": 25, "long_tail": 20, "url_naked": 10, "generic": 5, "exact_match": 15},
    "defensif": {"brand": 55, "partial_match": 15, "long_tail": 10, "url_naked": 10, "generic": 5, "exact_match": 5},
}

# Templates d'ancres par type — remplit {domain}, {brand}, {keyword}, {city}
ANCHOR_TEMPLATES = {
    "brand": [
        "{brand}", "{brand}.fr", "le site {brand}", "{brand} - site officiel",
    ],
    "partial_match": [
        "{keyword} par {brand}", "{brand} : {keyword}", "{keyword} avec {brand}",
        "decouvrez {keyword} chez {brand}",
    ],
    "long_tail": [
        "ou trouver {keyword} a {city}", "comment choisir {keyword} pour {sector}",
        "guide complet {keyword} {city}", "pourquoi {keyword} est important pour votre {sector}",
        "les avantages de {keyword} professionnel a {city}",
    ],
    "exact_match": [
        "{keyword}", "{keyword} a {city}", "{keyword} {city}",
        "{keyword} professionnel",
    ],
    "url_naked": [
        "https://www.{domain}", "www.{domain}", "{domain}/page",
    ],
    "generic": [
        "cliquez ici", "en savoir plus", "site web", "voir le site",
        "decouvrir", "plus d'infos",
    ],
}


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b14"
    state.phase = "analyse"

    target = ANCHOR_TARGETS.get(state.profile, ANCHOR_TARGETS["blog"])
    current = state.anchor_profile.get("current", {})

    # Ecart actuel vs cible
    deviations = {}
    for anchor_type, target_pct in target.items():
        current_pct = current.get(anchor_type, 0)
        deviation = current_pct - target_pct
        deviations[anchor_type] = {
            "current": round(current_pct, 1),
            "target": target_pct,
            "deviation": round(deviation, 1),
            "status": "ok" if abs(deviation) < 10 else ("sur-represente" if deviation > 0 else "sous-represente"),
        }

    # Alertes + suggestions concretes d'ancres
    alerts = []
    anchor_suggestions: dict[str, list[str]] = {}
    domain = state.domain
    brand_name = domain.replace(".fr", "").replace(".com", "").replace(".pro", "").replace("www.", "")
    # Nettoyer pour un nom de marque lisible
    if "-" in brand_name:
        brand_display = " ".join(w.capitalize() for w in brand_name.split("-"))
    else:
        brand_display = brand_name.upper() if len(brand_name) <= 6 else brand_name.capitalize()

    primary_kw = state.keywords_cibles[0] if state.keywords_cibles else "service"
    city = "Tours"  # Fallback — a enrichir avec geo-detection

    for atype, dev in deviations.items():
        if dev["status"] != "ok":
            alerts.append(f"{dev['status'].title()}: {atype} ({dev['current']}% vs {dev['target']}% cible)")

        # Generer 5 suggestions concretes pour chaque type
        suggestions = []
        for tpl in ANCHOR_TEMPLATES.get(atype, [atype]):
            text = tpl.format(
                brand=brand_display,
                domain=domain,
                keyword=primary_kw,
                city=city,
                sector="professionnel" if state.profile == "local" else state.profile,
            )
            suggestions.append(text)
        anchor_suggestions[atype] = suggestions[:5]

    # Generer les suggestions prioritaires (types sous-representes)
    priority_suggestions = []
    for atype in sorted(deviations, key=lambda a: deviations[a]["deviation"]):
        dev = deviations[atype]
        if dev["deviation"] < -5:  # Sous-represente
            for tpl in ANCHOR_TEMPLATES.get(atype, [atype])[:3]:
                text = tpl.format(
                    brand=brand_display, domain=domain,
                    keyword=primary_kw, city=city,
                    sector="professionnel" if state.profile == "local" else state.profile,
                )
                priority_suggestions.append({"type": atype, "text": text})

    # Alertes follow/nofollow
    dofollow_ratio = state.anchor_profile.get("dofollow_ratio", 100)
    follow_alert = state.anchor_profile.get("follow_alert", "")
    if follow_alert and "OK" not in follow_alert:
        alerts.append(f"Ratio follow/nofollow: {dofollow_ratio:.0f}% dofollow — {follow_alert}")

    # Score de sante
    max_deviation = max(abs(d["deviation"]) for d in deviations.values()) if deviations else 0
    # Penalite follow/nofollow si desequilibre
    follow_penalty = 10 if dofollow_ratio > 95 else (5 if dofollow_ratio < 50 else 0)
    anchor_health = max(0, 100 - max_deviation * 2 - follow_penalty)

    state.anchor_profile = {
        **state.anchor_profile,
        "target": target,
        "deviations": deviations,
        "alerts": alerts,
        "health_score": round(anchor_health, 1),
        "anchor_suggestions": anchor_suggestions,
        "priority_suggestions": priority_suggestions,
        "brand_display": brand_display,
    }
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b14", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    logger.info(f"B14: Profil ancres — sante {anchor_health:.0f}/100, {len(alerts)} alertes, "
                f"{len(priority_suggestions)} suggestions concretes, dofollow={dofollow_ratio:.0f}%")
    return state
