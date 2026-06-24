"""ST04 — Gap Concurrentiel Semantique et GEO.

Analyse les ecarts entre le site et ses concurrents :
- Contenu manquant
- Features SERP capturees par les concurrents
- Ecarts de position

Utilise Claude Haiku pour analyser les donnees P4 S04/S05.
Non skippable. Cout: ~$0.02.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from hermes.models.strategie import StrategieState, GapConcurrentiel
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st04")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st04"
    state.phase = "analyse"

    gaps: list[GapConcurrentiel] = []

    # Charger les donnees P4
    p4_data = _load_p4_competitor_data()

    if p4_data and state.competitors:
        # Avec Haiku pour analyse fine
        gaps = await _analyze_with_llm(state, p4_data)
    else:
        # Mode degrade sans LLM
        gaps = _analyze_static(state)

    state.gaps_concurrentiels = gaps
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st04", pipeline_id="strategie",
        model="claude-haiku-4-5" if p4_data else "none",
        tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST04: {len(gaps)} gaps concurrentiels identifies")
    return state


def _load_p4_competitor_data() -> dict:
    try:
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return {}
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM competitor_positions "
            "WHERE date >= date('now', '-30 days') "
            "ORDER BY date DESC LIMIT 200"
        ).fetchall()
        conn.close()
        return {"competitors": [dict(r) for r in rows]}
    except Exception:
        return {}


async def _analyze_with_llm(state: StrategieState, p4_data: dict) -> list[GapConcurrentiel]:
    """Utilise Haiku pour analyser les gaps concurrentiels."""
    competitors = {c.get("domain", "") for c in p4_data.get("competitors", [])}
    topics = [s.nom for s in state.sujets[:30]]

    prompt = f"""Analyse les gaps concurrentiels pour {state.domain}.

Concurrents identifies: {', '.join(list(competitors)[:5])}
Sujets du site: {', '.join(topics[:20])}
Mode: {state.mode}

Retourne un JSON avec ce format exact:
{{"gaps": [
  {{"domaine": "concurrent.com", "keyword": "mot-cle", "notre_position": 0.0, "leur_position": 1.0, "contenu_manquant": "description", "opportunite": "strategie", "score_gap": 80}}
]}}
Limite-toi a 10 gaps maximum. score_gap de 0-100. Soyez realiste et specifique."""

    try:
        from hermes.core.llm import LLMFactory
        from hermes.config import _cfg
        factory = LLMFactory(anthropic_api_key=_cfg._resolve("ANTHROPIC_API_KEY"))
        text, _, _, _ = await factory.route(
            system_prompt="Tu es un analyste SEO concurrentiel expert. Analyse les donnees et retourne du JSON valide uniquement.",
            user_message=prompt,
            agent_id="st04",
            max_tokens=2048,
        )

        from hermes.core.llm import _repair_json
        data = _repair_json(text)
        raw_gaps = data.get("gaps", []) if isinstance(data, dict) else []

        gaps = []
        for g in raw_gaps[:15]:
            gaps.append(GapConcurrentiel(
                domaine=g.get("domaine", ""),
                keyword=g.get("keyword", ""),
                notre_position=g.get("notre_position", 0),
                leur_position=g.get("leur_position", 0),
                contenu_manquant=g.get("contenu_manquant", ""),
                opportunite=g.get("opportunite", ""),
                score_gap=g.get("score_gap", 50),
            ))
        return gaps
    except Exception as e:
        logger.warning(f"ST04: LLM failed ({e}), fallback to static analysis")
        return _analyze_static(state)


def _analyze_static(state: StrategieState) -> list[GapConcurrentiel]:
    """Analyse sans LLM basee sur les opportunites non couvertes."""
    gaps = []
    for opp in state.opportunites[:15]:
        if opp.get("concurrents_top5"):
            gaps.append(GapConcurrentiel(
                domaine=opp["concurrents_top5"][0] if opp["concurrents_top5"] else "",
                keyword=opp.get("sujet", ""),
                notre_position=opp.get("position_moyenne", 100) if opp.get("position_moyenne", 100) < 100 else 0,
                leur_position=1.0,
                contenu_manquant=opp.get("sujet", ""),
                opportunite=f"Creer un {opp.get('type_page_recommande', 'article')}",
                score_gap=opp.get("opportunite_score", 50),
            ))
    return gaps
