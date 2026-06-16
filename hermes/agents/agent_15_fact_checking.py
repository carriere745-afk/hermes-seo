"""Agent 15 — Fact-checking.

Verifie les chiffres, dates, citations, prix et sources dans le brouillon.
Non skippable — critique pour la fiabilite du contenu.

Double couche : patterns heuristiques + LLM pour verification approfondie.
"""

import json
import re
from datetime import datetime
from html.parser import HTMLParser

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import ErreurFactuelle, FactCheckData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# ─── Patterns d'extraction des affirmations factuelles ──────────────────

FACT_PATTERNS: list[tuple[str, str]] = [
    (r"\b\d{1,3}(?:\s?\d{3})*(?:,\d+)?\s?(?:%|pour\s?cent|euros?|€|dollars?|\$|millions?|milliards?)\b",
     "chiffre/montant"),
    (r"\b(?:19|20)\d{2}\b", "annee"),
    (r"\b\d{1,2}\s?(?:janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s?\d{4}\b",
     "date complete"),
    (r"\bselon\s+(?:l'|le\s|la\s|les\s)?([A-Z][a-zàâäéèêëîïôöùûüÿ]+(?:\s(?:de|du|des|l'|d')\s?[A-Z][a-z]+)?)",
     "attribution a une source"),
    (r"\b(?:taux|prix|cot|indice|pourcentage)\s+(?:de|du|des|moyen)?\s?\d+[.,]?\d*\s?%?",
     "valeur chiffree precise"),
    (r"\b(?:jamais|toujours|tous\sles|chaque|aucun|personne\sne)\b",
     "affirmation absolue (drapeau rouge)"),
    (r"\b(?:premier|meilleur|seul|unique|numero\s?1|leader)\b",
     "superlatif (drapeau rouge)"),
]

# ─── Incoherences internes ────────────────────────────────────────────

INCOHERENCE_CHECKS: list[tuple[str, str]] = [
    (r"\b20\d{2}\b", "dates contradictoires"),
    (r"\b\d+(?:,\d+)?\s?%", "pourcentages contradictoires"),
]


def _strip_html(html: str, limit: int = 8000) -> str:
    class _S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.t: list[str] = []
        def handle_data(self, d):
            self.t.append(d)
    s = _S(); s.feed(html[:limit])
    return " ".join(s.t)


def _extract_facts(text: str) -> list[dict]:
    """Extrait toutes les affirmations factuelles du texte."""
    facts = []
    for pattern, fact_type in FACT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            contexte = text[start:end].strip()
            facts.append({
                "texte": match.group(0),
                "type": fact_type,
                "contexte": contexte,
                "position": f"caractere {match.start()}",
            })
    return facts


def _check_internal_consistency(facts: list[dict]) -> list[ErreurFactuelle]:
    """Verifie la coherence interne des faits (contradictions)."""
    erreurs: list[ErreurFactuelle] = []

    # Extraire toutes les annees
    annees = re.findall(r"\b(20\d{2})\b", " ".join(f["contexte"] for f in facts))
    annees_ints = [int(a) for a in annees]

    # Detecter des dates futures improbables (> annee courante + 1)
    current_year = datetime.now().year
    for a in annees_ints:
        if a > current_year + 1:
            erreurs.append(ErreurFactuelle(
                emplacement="Texte",
                texte_original=f"Annee {a}",
                correction=f"Verifier l'annee — {a} est dans le futur",
                source="Calendrier",
                gravite="majeure",
            ))

    # Detecter des affirmations absolues non etayees
    for f in facts:
        if f["type"] == "affirmation absolue (drapeau rouge)":
            erreurs.append(ErreurFactuelle(
                emplacement=f"Autour de '{f['texte']}'",
                texte_original=f["contexte"],
                correction="Nuancer ou sourcer l'affirmation absolue",
                source="A verifier",
                gravite="moderee",
            ))
        if f["type"] == "superlatif (drapeau rouge)":
            erreurs.append(ErreurFactuelle(
                emplacement=f"Autour de '{f['texte']}'",
                texte_original=f["contexte"],
                correction="Ajouter une source pour justifier le superlatif",
                source="A verifier",
                gravite="mineure",
            ))

    return erreurs


def _score_fiabilite(erreurs: list[ErreurFactuelle], facts_count: int) -> int:
    """Calcule un score de fiabilite 0-10."""
    base = 10
    for e in erreurs:
        gravite_score = {"mineure": -1, "moderee": -2, "majeure": -4, "critique": -10}
        base += gravite_score.get(e.gravite, 0)
    # Bonus si beaucoup de faits extraits = transparence
    if facts_count > 10:
        base = min(10, base + 1)
    return max(0, min(10, base))


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except json.JSONDecodeError: pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except json.JSONDecodeError: pass
    try: return json.loads(text.strip())
    except json.JSONDecodeError: pass
    return {}


def _build_user_message(state: SessionState, text: str, facts: list[dict]) -> str:
    facts_text = "\n".join(
        f"  - [{f['type']}] {f['texte']} (contexte: {f['contexte'][:100]}...)"
        for f in facts[:20]
    ) if facts else "Aucune affirmation factuelle detectee"

    return (
        f"Verifie les affirmations factuelles du contenu.\n\n"
        f"**Mot-cle :** {state.keyword or 'N/A'}\n"
        f"**Type de page :** {state.type_page or 'N/A'}\n\n"
        f"**Affirmations factuelles detectees :**\n{facts_text}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- erreurs: [{{"emplacement": "...", "texte_original": "...", '
        f'"correction": "...", "source": "...", "gravite": "mineure|moderee|majeure|critique"}}]\n'
        f'- score_fiabilite: 0-10\n'
        f'- sources_verifiees: ["https://...", ...]'
    )


def _mock_factcheck(state: SessionState) -> FactCheckData:
    text = _strip_html(state.brouillon_html or "", 10000)
    facts = _extract_facts(text)
    erreurs = _check_internal_consistency(facts)

    # Ajouter une erreur de demonstration en dry-run si rien trouve
    if not erreurs and facts:
        # Verifier si le contenu a des superlatifs
        for f in facts:
            if f["type"] in ("superlatif (drapeau rouge)", "affirmation absolue (drapeau rouge)"):
                break
        else:
            # Pas de drapeau rouge = contenu probablement correct
            pass

    return FactCheckData(
        erreurs=erreurs[:10],
        corrections=[{
            "emplacement": e.emplacement,
            "correction": e.correction,
        } for e in erreurs],
        score_fiabilite=_score_fiabilite(erreurs, len(facts)),
        sources_verifiees=[],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_15"
    agent_name = "Fact-checking"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"

    try:
        html = state.brouillon_html or ""
        text = _strip_html(html, 10000)
        facts = _extract_facts(text)
        erreurs = _check_internal_consistency(facts)

        if state.config.dry_run:
            fc = FactCheckData(
                erreurs=erreurs[:10],
                corrections=[{"emplacement": e.emplacement, "correction": e.correction}
                              for e in erreurs],
                score_fiabilite=_score_fiabilite(erreurs, len(facts)),
                sources_verifiees=[],
            )
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            try:
                factory = LLMFactory(
                    anthropic_api_key=config.ANTHROPIC_API_KEY,
                    openai_api_key=config.OPENAI_API_KEY,
                    deepseek_api_key=config.DEEPSEEK_API_KEY,
                    gemini_api_key=config.GEMINI_API_KEY,
                    ollama_base_url=config.OLLAMA_BASE_URL,
                    dry_run=False,
                )
                system_prompt = (
                    "Tu es un fact-checker rigoureux. Tu verifies les affirmations "
                    "factuelles, les chiffres, les dates et les sources. "
                    "Signale TOUTE erreur potentielle. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt,
                    user_message=_build_user_message(state, text, facts),
                    agent_id=agent_id,
                    temperature=0.1,
                    max_tokens=1200,
                )
                data = _extract_json(llm_text)

                llm_erreurs = []
                for e in data.get("erreurs", []):
                    llm_erreurs.append(ErreurFactuelle(
                        emplacement=e.get("emplacement", ""),
                        texte_original=e.get("texte_original", ""),
                        correction=e.get("correction", ""),
                        source=e.get("source", ""),
                        gravite=e.get("gravite", "mineure"),
                    ))

                all_erreurs = erreurs + llm_erreurs
                fc = FactCheckData(
                    erreurs=all_erreurs[:20],
                    corrections=[{"emplacement": e.emplacement, "correction": e.correction}
                                  for e in all_erreurs[:10]],
                    score_fiabilite=_score_fiabilite(all_erreurs, len(facts)),
                    sources_verifiees=data.get("sources_verifiees", []),
                )
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                fc = FactCheckData(
                    erreurs=erreurs[:10],
                    corrections=[{"emplacement": e.emplacement, "correction": e.correction}
                                  for e in erreurs],
                    score_fiabilite=_score_fiabilite(erreurs, len(facts)),
                    sources_verifiees=[],
                )
                result.model_used = "heuristic-only"

        state.fact_check_data = fc.model_dump()
        result.data = state.fact_check_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        fc = FactCheckData(score_fiabilite=5,
                           erreurs=[ErreurFactuelle(
                               emplacement="Global",
                               texte_original="Erreur d'analyse",
                               correction=f"Fact-checking interrompu: {e}",
                               source="Systeme",
                               gravite="moderee",
                           )])
        state.fact_check_data = fc.model_dump()
        result.data = state.fact_check_data
        result.status = AgentStatus.COMPLETED
        result.model_used = result.model_used or "fallback"
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(
        agent_id, agent_name, result.duration_ms,
        tokens_input=result.tokens_input or 0,
        tokens_output=result.tokens_output or 0,
        cost_estimated=result.cost_estimated or 0.0,
        prompt_version="v1",
        model_used=result.model_used or "inconnu",
    )
    state.last_completed_agent_id = agent_id
    return state


def _estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
