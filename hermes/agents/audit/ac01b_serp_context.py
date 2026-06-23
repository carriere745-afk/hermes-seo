"""AC01b — Contexte SERP pour l'Audit de Contenu.

Pour chaque page auditee, interroge TalorData + DataForSEO + KE
pour comparer les signaux on-page avec le paysage concurrentiel.

Enrichit le score : si le top 10 fait 2500 mots en moyenne et
la page en fait 600, le score qualite est penalise.
Si le top 10 n'a pas de FAQ non plus, l'absence de FAQ est
moins penalisee.
"""

import asyncio
import logging
from datetime import datetime
from urllib.parse import urlparse

from hermes.connectors.serp_api import SerpAPIClient
from hermes.connectors.dataforseo_connector import dataforseo
from hermes.connectors.keywordseverywhere_connector import keywordseverywhere
from hermes.connectors.rankparse_connector import rankparse
from hermes.models.audit import AuditSessionState

logger = logging.getLogger("hermes.audit.ac01b")


async def _get_serp_context(keyword: str) -> dict:
    """Recupere le contexte SERP pour un mot-cle.

    Combine TalorData (top 10, PAA) + DataForSEO (volume, domain metrics)
    + Keywords Everywhere (CPC, trend, competition).

    Returns: {top10, word_count_avg, domain_count, paa_count, volume, cpc, competition}
    """
    context = {
        "top10": [],
        "word_count_avg": 0,
        "domain_count": 0,
        "paa_count": 0,
        "search_volume": 0,
        "cpc": 0,
        "competition": 0,
        "source": "none",
    }

    # 1. TalorData — top 10 + PAA
    try:
        client = SerpAPIClient(dry_run=False)
        serp = await client.search(keyword, "fr", "fr")
        organic = serp.get("organic_results", [])
        if organic:
            context["top10"] = organic[:10]
            context["domain_count"] = len(set(r.get("domain", "") for r in organic))
            context["paa_count"] = len(serp.get("related_questions", []))
            context["source"] = "talordata"

            # Estimer le word count moyen (si dispo)
            wcs = [r.get("word_count") for r in organic if r.get("word_count")]
            if wcs:
                context["word_count_avg"] = sum(wcs) // len(wcs)
    except Exception as e:
        logger.warning(f"TalorData failed for audit context: {e}")

    # 2. Keywords Everywhere — volume, CPC
    if keywordseverywhere.is_configured:
        try:
            ke_data = await keywordseverywhere.get_keyword_metrics([keyword], "fr")
            if ke_data and keyword.lower() in ke_data:
                metrics = ke_data[keyword.lower()]
                context["search_volume"] = metrics.get("vol", 0)
                context["cpc"] = metrics.get("cpc", 0)
                context["competition"] = metrics.get("competition", 0)
                if context["source"] == "none":
                    context["source"] = "keywordseverywhere"
        except Exception as e:
            logger.warning(f"KE failed for audit context: {e}")

    return context


def _apply_serp_adjustments(scores: dict, serp_context: dict, page_word_count: int) -> dict:
    """Applique des ajustements aux scores en fonction du contexte SERP.

    Si une page est penalisee pour un critere mais que la concurrence
    n'est pas meilleure, la penalite est reduite.
    """
    adj = {"quality": 0, "seo": 0, "aeo": 0, "geo": 0, "notes": []}

    if not serp_context.get("top10"):
        return adj

    avg_wc = serp_context.get("word_count_avg", 0)
    if avg_wc > 0 and page_word_count > 0:
        ratio = page_word_count / avg_wc
        if ratio < 0.5:
            # Page beaucoup plus courte que le top 10
            adj["quality"] -= 15
            adj["notes"].append(
                f"Page trop courte ({page_word_count} mots vs {avg_wc} mots moyenne top 10). "
                f"Visez >= {int(avg_wc * 1.2)} mots."
            )
        elif ratio < 0.8:
            adj["quality"] -= 7
            adj["notes"].append(
                f"Page legerement courte ({page_word_count} mots vs {avg_wc} mots). "
                f"Visez {int(avg_wc * 1.1)} mots."
            )
        elif ratio >= 1.2:
            adj["quality"] += 5
            adj["notes"].append(
                f"Page plus longue que la moyenne du top 10 (+{int((ratio - 1) * 100)}%)"
            )

    # Si le top 10 a peu de PAA, l'absence de FAQ est moins grave
    if serp_context.get("paa_count", 0) <= 2:
        adj["aeo"] += 5
        adj["notes"].append("Peu de PAA dans la SERP — l'absence de FAQ est moins penalisante")

    # Volume eleve = plus competitif
    vol = serp_context.get("search_volume", 0)
    if vol > 5000:
        adj["notes"].append(f"Fort volume ({vol}/mois) — concurrence elevee, contenu premium recommande")
    elif vol > 1000:
        adj["notes"].append(f"Volume correct ({vol}/mois) — opportunite exploitable")

    return adj


def _extract_keyword_from_page(page) -> str:
    """Extrait un mot-cle probable depuis les signaux de la page."""
    # Priorite : H1 > title > URL path
    h1 = getattr(page, "h1", "")
    if h1 and len(h1) > 10:
        # Nettoyer : enlever la marque apres | ou -
        import re
        parts = re.split(r"\s*[|–—-]\s*", h1)
        return parts[0].strip()[:80]

    title = getattr(page, "title", "")
    if title:
        parts = re.split(r"\s*[|–—-]\s*", title)
        return parts[0].strip()[:80]

    # Fallback : derniere partie du path
    url = getattr(page, "url", "")
    if url:
        try:
            path = urlparse(url).path.strip("/")
            if path:
                return path.replace("/", " ").replace("-", " ")[:80]
        except Exception:
            pass

    return ""


async def run(state: AuditSessionState) -> AuditSessionState:
    """Enrichit l'audit avec le contexte SERP pour chaque page."""
    state.current_agent = "ac01b"

    # Cache evite de rappeler KE/DataForSEO pour chaque page
    kw_cache = {}

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        keyword = _extract_keyword_from_page(page)
        if not keyword:
            continue

        # Utiliser le cache si le mot-cle a deja ete traite
        kw_key = keyword.lower().strip()
        if kw_key in kw_cache:
            serp_context = kw_cache[kw_key]
        else:
            logger.info(f"AC01b: SERP context for '{keyword}'")
            serp_context = await _get_serp_context(keyword)
            kw_cache[kw_key] = serp_context

        # Appliquer les ajustements aux scores existants
        s = state.scores.get(page.url)
        if s:
            adj = _apply_serp_adjustments(
                {"quality": s.quality.score, "seo": s.seo_onpage.score,
                 "aeo": s.aeo.score, "geo": s.geo.score},
                serp_context,
                page.word_count,
            )
            s.quality.score = max(0, min(100, s.quality.score + adj["quality"]))
            s.aeo.score = max(0, min(100, s.aeo.score + adj["aeo"]))
            s.global_score = max(0, min(100, s.global_score + adj["quality"] // 3))
            for note in adj["notes"]:
                s.quality.strengths.append(f"[SERP] {note}" if adj["quality"] >= 0 else f"[SERP] {note}")

            # ── Faisabilite SEO (RankParse DA) ─────────────────────
            feasibility = None
            if rankparse.is_configured:
                try:
                    # DA du site (depuis l'URL de la page)
                    from urllib.parse import urlparse
                    site_domain = urlparse(state.site_url or page.url).netloc.replace("www.", "")
                    site_da_data = await rankparse.get_domain_authority(site_domain)
                    site_da = site_da_data.get("da", 0)

                    # DA moyen du top 10 (depuis les domaines SERP)
                    top_domains = [r.get("domain", "") for r in serp_context.get("top10", [])[:5] if r.get("domain")]
                    top_das = []
                    if top_domains:
                        batch = await rankparse.batch_domain_authority(top_domains[:5])
                        top_das = [v.get("da", 0) for v in batch.values() if v.get("da", 0) > 0]

                    if top_das and site_da > 0:
                        avg_top_da = sum(top_das) // len(top_das)
                        feasibility = rankparse.feasibility_score(site_da, avg_top_da)
                        feasibility["site_da"] = site_da
                        feasibility["avg_top_da"] = avg_top_da
                        feasibility["top_das"] = top_das[:5]
                        feasibility["domain"] = site_domain
                        logger.info(
                            f"AC01b: feasibility for {site_domain}: "
                            f"DA={site_da} vs avg={avg_top_da} -> {feasibility['score']}%"
                        )
                except Exception as e:
                    logger.warning(f"AC01b: RankParse feasibility failed: {e}")

            # Stocker le contexte SERP dans la page (metadata)
            if not hasattr(page, "serp_context"):
                page.serp_context = {}
            page.serp_context = {
                "keyword": keyword,
                "word_count_avg": serp_context["word_count_avg"],
                "domain_count": serp_context["domain_count"],
                "paa_count": serp_context["paa_count"],
                "search_volume": serp_context["search_volume"],
                "cpc": serp_context["cpc"],
                "source": serp_context["source"],
                "feasibility": feasibility,
            }
            # Ajouter la note de faisabilite aux forces/faiblesses
            if feasibility and s:
                if feasibility["score"] >= 70:
                    s.quality.strengths.append(
                        f"[DA] Faisabilite: {feasibility['score']}% — "
                        f"DA site {feasibility['site_da']} vs top10 {feasibility['avg_top_da']} "
                        f"({feasibility['label']})"
                    )
                else:
                    s.quality.weaknesses.append(
                        f"[DA] Faisabilite: {feasibility['score']}% — "
                        f"DA site {feasibility['site_da']} vs top10 {feasibility['avg_top_da']} "
                        f"({feasibility['label']}). {feasibility['reco']}"
                    )

    state.updated_at = datetime.now()
    return state
