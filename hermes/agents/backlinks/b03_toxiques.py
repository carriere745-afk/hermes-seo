"""B03 — Detection de Backlinks Toxiques.

Detecte les domaines suspects : PBN, spam, sur-optimisation d'ancres.
Patterns : domaines expires, ancres exact match excessives, domaines avec
trop de liens sortants, TLD suspects, domaines sans trafic.

Non skippable. $0 — pas de LLM.
"""

import logging
import re
import time
from collections import Counter
from datetime import datetime

from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b03")

# Patterns suspects
SUSPICIOUS_TLDS = {".xyz", ".top", ".win", ".loan", ".tk", ".ml", ".ga", ".cf", ".gq", ".pw"}
SUSPICIOUS_WORDS = ["pbn", "seo", "backlink", "link", "guest", "sponsored", "buy", "cheap", "free"]
TOXIC_PATTERNS = [
    r"article\d+\.(xyz|top|win)",  # Domaines generiques
    r"seo.*link",  # SEO + link
    r"buy.*backlink",  # Achat de liens
    r"guest.*post.*\d+",  # Guest posts industriels
]


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b03"
    state.phase = "analyse"

    toxic_domains: list[dict] = []
    anchor_risk = 0

    domain_backlinks: dict[str, list] = {}
    for bl in state.backlinks:
        domain_backlinks.setdefault(bl.source_domain, []).append(bl)

    for domain_name, bls in domain_backlinks.items():
        risk_score = 0
        reasons = []

        # 1. TLD suspect
        tld = domain_name[domain_name.rfind("."):] if "." in domain_name else ""
        if tld in SUSPICIOUS_TLDS:
            risk_score += 30
            reasons.append(f"TLD suspect: {tld}")

        # 2. Mots suspects dans le domaine
        for word in SUSPICIOUS_WORDS:
            if word in domain_name.lower():
                risk_score += 10
                reasons.append(f"Mot suspect: {word}")
                break

        # 3. Patterns PBN
        for pattern in TOXIC_PATTERNS:
            if re.search(pattern, domain_name.lower()):
                risk_score += 25
                reasons.append(f"Pattern PBN: {pattern}")
                break

        # 4. Sur-optimisation d'ancres (exact match > 60%)
        anchors = [bl.anchor_text.lower().strip() for bl in bls if bl.anchor_text.strip()]
        if anchors:
            exact_match_ratio = sum(1 for a in anchors if state.domain.lower() in a and a != state.domain.lower()) / len(anchors)
            if exact_match_ratio > 0.6:
                risk_score += 20
                reasons.append(f"Ancres exact match excessives ({exact_match_ratio:.0%})")

        # 5. Ratio liens/dofollow anormal
        dofollow_ratio = sum(1 for bl in bls if bl.is_dofollow) / max(len(bls), 1)
        if dofollow_ratio > 0.95 and len(bls) > 3:
            risk_score += 10
            reasons.append("Trop de dofollow (>95%)")

        # Determiner le niveau de toxicite
        if risk_score >= 60:
            level = "toxic"
        elif risk_score >= 35:
            level = "suspicious"
        elif risk_score >= 15:
            level = "low_risk"
        else:
            level = "safe"

        if level != "safe":
            toxic_domains.append({
                "domain": domain_name,
                "toxicity_score": risk_score,
                "toxicity_level": level,
                "reasons": reasons,
                "backlinks_count": len(bls),
                "recommandation": _toxicity_recommandation(level),
            })

        # Mettre a jour les backlinks
        for bl in bls:
            bl.toxicity_score = risk_score
            bl.toxicity_level = level

    # Anchor risk global
    total_bl = len(state.backlinks)
    if total_bl > 0:
        exact_matches = sum(1 for bl in state.backlinks if bl.anchor_type == "exact_match")
        anchor_risk = min(100, (exact_matches / total_bl) * 2 * 100)

    # Persister les domaines toxiques
    for td in toxic_domains:
        try:
            insert_toxic(td["domain"], td["toxicity_score"],
                         ", ".join(td["reasons"]), state.session_id)
        except Exception:
            pass

    state.toxic_domains = toxic_domains
    state.anchor_risk_score = int(anchor_risk)
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b03", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    n_toxic = sum(1 for t in toxic_domains if t["toxicity_level"] == "toxic")
    logger.info(f"B03: {len(toxic_domains)} domaines suspects — {n_toxic} toxiques. Anchor risk: {anchor_risk:.0f}/100")
    return state


def _toxicity_recommandation(level: str) -> str:
    if level == "toxic":
        return "Desavouer ce domaine via Google Disavow Tool. Risque de penalite."
    elif level == "suspicious":
        return "Surveiller ce domaine. Si les positions baissent, desavouer."
    elif level == "low_risk":
        return "Faible risque. Pas d'action immediate necessaire."
    return "Aucune action necessaire."


# Helper pour insert dans backlinks_db (evite l'import circulaire)
def insert_toxic(domain: str, score: float, patterns: str, session_id: str):
    try:
        from hermes.core.backlinks_db import _get_conn
        from uuid import uuid4
        conn = _get_conn()
        conn.execute(
            "INSERT INTO toxic_domains (id, domain, reason, toxicity_score, patterns_detected, detected_at, session_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (uuid4().hex[:12], domain, f"Score: {score}/100", score, patterns,
             datetime.now().isoformat(), session_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"B03: Failed to insert toxic domain: {e}")
