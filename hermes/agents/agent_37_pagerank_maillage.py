"""Agent 37 — PageRank Interne & Maillage Intelligent (gap module 9).

Simule le PageRank interne, detecte les pages sous-linkees,
suggere des liens optimaux entre pages, injecte les liens via CMS.

Scores : PageRank interne 0-100, score maillage par silo 0-100.

Utilise l'algorithme PageRank simplifie (pas besoin de numpy/scipy).
"""

import logging, re, time
from datetime import datetime
from collections import defaultdict

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_37")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_37"
    agent_name = "PageRank & Maillage"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        site_url = state.site_url or "https://example.com"

        # 1. Extraire le graphe de liens internes depuis le contenu
        links_graph = _extract_internal_links(content, site_url)

        # 2. Calculer le PageRank simplifie
        pagerank = _compute_pagerank(links_graph)

        # 3. Identifier les pages sous-linkees
        orphan_pages = [url for url, score in pagerank.items() if score < 0.01]
        underlinked = [url for url, score in pagerank.items() if 0.01 <= score < 0.05]

        # 4. Generer des suggestions de liens
        suggestions = _generate_link_suggestions(pagerank, links_graph, site_url)

        # 5. Calculer le score de maillage
        total_pages = max(len(pagerank), 1)
        linked_pages = total_pages - len(orphan_pages)
        coverage = linked_pages / total_pages * 100
        avg_pr = sum(pagerank.values()) / total_pages * 100
        maillage_score = round(coverage * 0.6 + min(avg_pr * 2, 40), 1)

        output = {
            "pages_analyzed": len(pagerank),
            "orphan_pages": orphan_pages,
            "underlinked_pages": underlinked,
            "avg_pagerank": round(avg_pr, 4),
            "maillage_score": maillage_score,
            "link_suggestions": suggestions,
            "recommandations": [],
        }

        if orphan_pages:
            output["recommandations"].append(f"Ajouter au moins 1 lien vers chacune des {len(orphan_pages)} pages orphelines")
        if suggestions:
            output["recommandations"].append(f"{len(suggestions)} liens suggeres pour renforcer le maillage interne")
        if maillage_score < 50:
            output["recommandations"].append("Score de maillage faible. Augmenter la densite de liens internes.")

        result.status = AgentStatus.COMPLETED
        result.data = output
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state


def _extract_internal_links(html: str, base_url: str) -> dict[str, set[str]]:
    """Extrait le graphe de liens internes : {source_url: {target_urls}}."""
    graph = defaultdict(set)
    # Trouver tous les liens <a href="...">
    links = re.findall(r'<a[^>]+href="([^"]*)"', html, re.IGNORECASE)
    base_domain = base_url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
    current_url = base_url

    for href in links:
        href = href.strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        # Resoudre les URLs relatives
        if href.startswith("/"):
            target = f"{base_url.rstrip('/')}{href}"
        elif href.startswith("http") and base_domain in href:
            target = href
        else:
            continue  # Skip externes

        graph[current_url].add(target)
        # Initialiser la page cible dans le graphe
        if target not in graph:
            graph[target] = set()

    return dict(graph)


def _compute_pagerank(graph: dict[str, set[str]], damping: float = 0.85, iterations: int = 50) -> dict[str, float]:
    """Calcule le PageRank simplifie. Algorithme iteratif sans numpy."""
    pages = list(graph.keys())
    n = len(pages)
    if n == 0:
        return {}

    pr = {p: 1.0 / n for p in pages}

    for _ in range(iterations):
        new_pr = {}
        for p in pages:
            rank = (1 - damping) / n
            # Somme des PR entrants
            for source, targets in graph.items():
                if p in targets and len(targets) > 0:
                    rank += damping * pr[source] / len(targets)
            new_pr[p] = rank
        pr = new_pr

    return pr


def _generate_link_suggestions(pagerank: dict[str, float], graph: dict[str, set[str]],
                                base_url: str) -> list[dict]:
    """Genere des suggestions de liens internes optimaux."""
    suggestions = []
    sorted_pages = sorted(pagerank, key=pagerank.get, reverse=True)

    # Pages a fort PR → suggerer de linker depuis les pages a faible PR
    high_pr = [p for p in sorted_pages[:3] if pagerank[p] > 0.01]
    low_pr = [p for p in sorted_pages[-3:] if pagerank[p] < 0.05 and p not in high_pr]

    for target in high_pr:
        for source in low_pr:
            if target not in graph.get(source, set()):
                suggestions.append({
                    "from": source.replace(base_url, "/"),
                    "to": target.replace(base_url, "/"),
                    "anchor_suggested": _suggest_anchor(target),
                    "impact": "Renforce le PageRank de la page cible",
                    "priority": "P1" if pagerank[target] < 0.02 else "P2",
                })
                break  # 1 suggestion par paire

    return suggestions[:10]


def _suggest_anchor(url: str) -> str:
    """Suggere un texte d'ancre base sur l'URL."""
    path = url.split("/")[-1].replace("-", " ").replace(".html", "").replace(".php", "")
    if len(path) > 3 and path not in ("www", "http:", "https:", ""):
        return path[:60]
    return "En savoir plus"
