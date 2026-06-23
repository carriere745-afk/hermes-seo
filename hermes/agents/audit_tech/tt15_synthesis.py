"""T15 — Synthese Technique.

Agrege tous les resultats, produit un resume executif :
- Score global (ponderation des dimensions)
- Niveau de confiance global
- Top 10 issues par priorite
- Resume par dimension avec confiance

Optionnel : LLM Haiku pour enrichir les recommandations (~$0.001/page).
$0 par defaut — Haiku seulement si API dispo et mode premium.
"""

import logging
from datetime import datetime

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt15")

# Poids des dimensions pour le score global
DIMENSION_WEIGHTS = {
    "crawlability": 10, "indexation": 15, "architecture": 10,
    "structure": 15, "content": 10, "performance": 10,
    "mobile": 5, "structured_data": 5, "international": 5,
    "security": 10, "maillage": 5,
}


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt15"

    # 1. Score global pondere
    dims = state.scores
    total_weight = 0
    weighted_sum = 0

    for dim_name, weight in DIMENSION_WEIGHTS.items():
        score = getattr(dims, dim_name, None)
        if score and score.score > 0:
            weighted_sum += score.score * weight
            total_weight += weight

    if total_weight > 0:
        state.scores.global_score = int(weighted_sum / total_weight)
    else:
        state.scores.global_score = 0

    # 2. Confiance globale
    confidences = []
    for dim_name in DIMENSION_WEIGHTS:
        dim = getattr(dims, dim_name, None)
        if dim and dim.confidence != "medium":
            confidences.append(dim.confidence)

    if confidences.count("low") > len(confidences) * 0.5:
        state.scores.global_confidence = "low"
    elif confidences.count("high") > len(confidences) * 0.5:
        state.scores.global_confidence = "high"
    else:
        state.scores.global_confidence = "medium"

    # 3. Deduplication : consolider les issues similaires (meme URL + meme categorie)
    deduped = _deduplicate_issues(state.issues)
    state.issues = deduped

    # 4. Compteurs par dimension
    for dim_name in DIMENSION_WEIGHTS:
        dim = getattr(dims, dim_name, None)
        if dim:
            cat_issues = [i for i in state.issues if _category_to_dim(i.category) == dim_name]
            dim.issues_count = len(cat_issues)
            dim.critical_count = sum(1 for i in cat_issues if i.severity == "critical")

    # 5. Top issues P0/P1
    critical = [i for i in state.issues if i.priority in ("P0", "P1")]
    critical.sort(key=lambda i: (0 if i.priority == "P0" else 1, i.severity))

    # Enrichissement LLM optionnel (mode premium uniquement)
    if state.mode == "premium" and len(critical) > 0:
        try:
            await _enrich_with_llm(critical[:5], state)
        except Exception as e:
            logger.debug(f"T15: LLM enrichment skipped ({e})")

    logger.info(f"T15: global_score={state.scores.global_score}, confidence={state.scores.global_confidence}, issues={len(state.issues)}")
    state.status = "synthesized"
    state.updated_at = datetime.now()
    return state


def _deduplicate_issues(issues: list[TechIssue]) -> list[TechIssue]:
    """Consolide les issues dupliquees (meme URL + meme categorie).

    Garde la severite la plus elevee et fusionne les descriptions.
    """
    seen: dict[tuple, list[TechIssue]] = {}
    for issue in issues:
        key = (issue.url, issue.category)
        if key not in seen:
            seen[key] = []
        seen[key].append(issue)

    deduped = []
    for key, group in seen.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Fusionner : garder le plus severe, concatener les descriptions
            severities = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            group.sort(key=lambda i: severities.get(i.severity, 9))
            consolidated = group[0]
            if len(group) > 1:
                extra = "; ".join(set(i.description for i in group[1:3]))
                if extra and extra not in consolidated.description:
                    consolidated.description += f" (+ {len(group)-1} autres: {extra[:100]})"
                # Prendre la priorite la plus elevee
                priorities = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
                consolidated.priority = min(group, key=lambda i: priorities.get(i.priority, 9)).priority
            deduped.append(consolidated)

    return deduped


def _category_to_dim(category: str) -> str:
    mapping = {
        "anomalies": "crawlability", "indexation": "indexation",
        "architecture": "architecture", "structure": "structure",
        "content": "content", "performance": "performance",
        "mobile": "mobile", "schema": "structured_data",
        "international": "international", "security": "security",
        "maillage": "maillage", "sitemap": "crawlability",
        "code_quality": "structure",
    }
    return mapping.get(category, "structure")


async def _enrich_with_llm(issues: list[TechIssue], state: TechAuditState):
    """Enrichit les recommandations via Haiku."""
    try:
        from hermes.core.llm import call_llm

        issues_text = "\n".join(
            f"- [{i.priority}] {i.category}: {i.description} (url: {i.url})"
            for i in issues
        )
        prompt = (
            f"Site audite: {state.site_url} (CMS: {state.cms_detected or 'inconnu'}, "
            f"profil: {state.profile}).\n"
            f"Top issues techniques:\n{issues_text}\n\n"
            "Pour chaque issue, ajoute une recommandation actionnable en 1 phrase, "
            "adaptee au CMS si pertinent. Format JSON: [{\"id\": \"P-XXX\", \"reco\": \"...\"}]"
        )
        response = await call_llm(prompt, model="haiku", max_tokens=300, temperature=0.3)
        if response:
            import json as _json
            recos = _json.loads(response) if isinstance(response, str) else response
            reco_map = {r["id"]: r["reco"] for r in recos if "id" in r and "reco" in r}
            for issue in issues:
                if issue.id in reco_map:
                    issue.description += f" 💡 {reco_map[issue.id]}"
    except Exception:
        pass
