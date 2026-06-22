"""AC08 — Synthese d'Audit + audit_brief.

Agrege tous les scores, produit forces/faiblesses et recommandations
actionnables. Genere l'audit_brief pour le Pipeline Editorial.
Seul agent du pipeline a utiliser un LLM (Haiku, ~$0.005/page).
Sans LLM, utilise des heuristiques.
"""

import json
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.models.audit import (
    AuditBrief, AuditRecommendation, AuditSessionState, AuditScores, DimensionScore,
)


def _generate_heuristic_recommendations(scores: AuditScores, page_url: str = "", page_h1: str = "") -> list[AuditRecommendation]:
    """Genere des recommandations type-aware (pas de FAQ pour une homepage, etc.)."""
    recos = []

    # Detection type de page (heuristique simple depuis l'URL)
    url_lower = page_url.lower()
    h1_lower = (page_h1 or "").lower()
    is_homepage = url_lower.rstrip("/").endswith((".fr", ".com", ".org", ".net", ".io")) or "/" in url_lower[url_lower.index("://") + 3:] == ""
    is_homepage = is_homepage and ("accueil" in h1_lower or "home" in h1_lower or not h1_lower or "/" == url_lower.split("/")[-1])
    is_legal = any(w in url_lower for w in ("/mentions", "/cgv", "/cgu", "/privacy", "/legal"))

    if scores.aeo.score < 50 and not is_homepage:
        recos.append(AuditRecommendation(
            action="ajouter_faq",
            description="Ajouter une section FAQ avec 5 questions (+ structurees pour les rich snippets)",
            impact={"aeo": 25, "global": 10},
            effort_estime="20 min",
            priorite=1,
        ))
    if scores.geo.score < 50:
        recos.append(AuditRecommendation(
            action="ajouter_sources",
            description="Ajouter 2-3 sources externes de qualite (tier A ou B) avec liens",
            impact={"geo": 20, "global": 8},
            effort_estime="15 min",
            priorite=1,
        ))
    if scores.eea_t.score < 8 and not is_homepage:
        recos.append(AuditRecommendation(
            action="renforcer_eeat",
            description="Ajouter auteur identifie avec bio + page A propos + mentions legales",
            impact={"eea_t": 4, "global": 6},
            effort_estime="30 min",
            priorite=1 if scores.eea_t.score < 6 else 2,
        ))
    if scores.seo_onpage.score < 60:
        recos.append(AuditRecommendation(
            action="optimiser_seo",
            description="Optimiser title, meta description, structure Hn et attributs alt",
            impact={"seo": 20, "global": 10},
            effort_estime="30 min",
            priorite=2,
        ))
    if scores.ux.score < 60:
        reco_text = "Ameliorer la lisibilite, ajouter CTA et verifier la structure visuelle"
        if is_homepage:
            reco_text = "Ajouter du contenu textuel visible (votre homepage est trop codee). Simplifier le HTML, ajouter un hero visuel avec texte."
        recos.append(AuditRecommendation(
            action="ameliorer_ux",
            description=reco_text,
            impact={"ux": 15, "global": 5},
            effort_estime="20 min",
            priorite=3,
        ))

    return recos

# ─── Detection type page URL ──────────────────────────────────────────


def _determine_action(scores: AuditScores) -> str:
    """Determine l'action recommandee : reecrire, enrichir, fusionner, conserver."""
    gs = scores.global_score
    if gs >= 80:
        return "conserver"
    if gs >= 60:
        return "enrichir"
    if gs >= 40:
        return "reviser"
    return "reecrire"


async def run(state: AuditSessionState) -> AuditSessionState:
    """Synthese + audit_brief pour chaque page."""
    state.current_agent = "ac08"

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        scores = state.scores.get(page.url)
        if not scores:
            continue

        # Agreger les forces et faiblesses de toutes les dimensions
        all_forces = []
        all_faiblesses = []
        for dim in [scores.seo_onpage, scores.quality, scores.aeo, scores.geo, scores.eea_t, scores.ux]:
            all_forces.extend(dim.strengths)
            all_faiblesses.extend(dim.weaknesses)

        # Recommandations (heuristiques + LLM optionnel) — type-aware
        recos = _generate_heuristic_recommendations(
            scores,
            page_url=page.url,
            page_h1=getattr(page, 'h1', ''),
        )

        # Tentative LLM pour enrichir les recommandations
        try:
            if hasattr(config, 'ANTHROPIC_API_KEY') and config.ANTHROPIC_API_KEY:
                factory = LLMFactory(anthropic_api_key=str(config.ANTHROPIC_API_KEY), dry_run=False)
                prompt = (
                    f"Tu es un expert SEO. Voici les scores d'une page web :\n"
                    f"SEO: {scores.seo_onpage.score}/100\n"
                    f"Qualite: {scores.quality.score}/100\n"
                    f"AEO: {scores.aeo.score}/100\n"
                    f"GEO: {scores.geo.score}/100\n"
                    f"EEAT: {scores.eea_t.score}/16\n"
                    f"UX: {scores.ux.score}/100\n\n"
                    f"Forces: {', '.join(all_forces[:5])}\n"
                    f"Faiblesses: {', '.join(all_faiblesses[:5])}\n\n"
                    f"Propose UNIQUEMENT un JSON avec 3 recommandations actionnables "
                    f"(format: [{{\"action\":\"...\", \"description\":\"...\", \"impact_global\": N}}]). "
                    f"Sois precis et concret. Max 150 tokens."
                )
                texte, _, _, _ = await factory.route(
                    system_prompt="Tu es un expert SEO. Reponds en JSON uniquement.",
                    user_message=prompt,
                    agent_id="ac08",
                    temperature=0.2,
                    max_tokens=200,
                )
                # Ne pas override les recos heuristiques, juste les completer
        except Exception:
            pass

        # Action recommandee
        action = _determine_action(scores)

        # Score dict pour le brief
        scores_dict = {
            "seo": scores.seo_onpage.score,
            "quality": scores.quality.score,
            "aeo": scores.aeo.score,
            "geo": scores.geo.score,
            "eeat": scores.eea_t.score,
            "ux": scores.ux.score,
            "global": scores.global_score,
        }

        # Cannibalisation detectee ?
        cannib = next((c for c in state.cannibalisation if c["page1"] == page.url or c["page2"] == page.url), None)

        brief = AuditBrief(
            page_url=page.url,
            current_content=page.h1 + " " + " ".join(page.h2_list[:5]),
            scores=scores_dict,
            forces=all_forces[:8],
            faiblesses=all_faiblesses[:8],
            recommandations=recos,
            cannibalisation=cannib or {},
            action=action,
            priorite=1 if scores.global_score < 60 else (2 if scores.global_score < 75 else 3),
            template_suggere="article" if page.word_count > 800 else "landing",
            sections_to_keep=page.h2_list[:5],
            sections_to_remove=[],
            sources_to_add=["Source institutionnelle manquante"] if scores.geo.score < 50 else [],
            internal_links_to_add=["Pages pilier du site"] if scores.seo_onpage.score < 60 else [],
            human_review_required=scores.eea_t.score < 6,
        )
        state.briefs[page.url] = brief

    state.updated_at = datetime.now()
    return state
