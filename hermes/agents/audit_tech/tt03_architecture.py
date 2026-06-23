"""T03 — Architecture du Site.

Analyse la structure globale du site :
- Graphe des liens internes (NetworkX)
- Detection de communautes (Louvain via scikit-network)
- Silos "fantomes" : groupes thematiques sans page hub
- Profondeur moyenne/max depuis la homepage
- Hubs (pages avec > 10 liens entrants)
- Clusters
- Diametre du site

$0 — pas de LLM. Deterministe.
"""

import logging
import re
from collections import Counter
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import networkx as nx
from sknetwork.clustering import Louvain
from sknetwork.data import from_edge_list
import numpy as np

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt03")


def _build_link_graph(pages: list) -> nx.DiGraph:
    """Construit un graphe dirige des liens internes.

    Chaque page est un noeud, chaque lien interne est une arete.
    """
    G = nx.DiGraph()

    # Indexer les URLs pour lookup rapide
    url_set = {p.url for p in pages}
    domain = urlparse(pages[0].url).netloc.lower().replace("www.", "") if pages else ""

    for page in pages:
        G.add_node(page.url, title=page.title[:80], depth=page.crawl_depth)

        for link in page.internal_links_list:
            target = link.get("url", "")
            # Normaliser pour le matching
            target_normalized = target.rstrip("/")
            if target_normalized in url_set or target in url_set:
                found = target if target in url_set else target_normalized
                G.add_edge(page.url, found)

    return G


def _detect_silos(G: nx.DiGraph, pages: list) -> tuple[list[dict], list[dict]]:
    """Detecte les silos et silos fantomes dans le graphe.

    Un silo = une communaute detectee par Louvain.
    Un silo fantome = un silo sans page hub (aucune page avec degre entrant > 5).
    """
    silos = []
    silos_fantomes = []

    if G.number_of_nodes() < 3 or G.number_of_edges() < 2:
        return silos, silos_fantomes

    try:
        # Convertir le graphe NetworkX en edge list pour scikit-network
        nodes = list(G.nodes())
        node_to_idx = {n: i for i, n in enumerate(nodes)}

        edges = []
        for u, v in G.edges():
            if u in node_to_idx and v in node_to_idx:
                edges.append((node_to_idx[u], node_to_idx[v]))

        if len(edges) < 2:
            return silos, silos_fantomes

        # Creer la matrice d'adjacence et appliquer Louvain
        edge_list = np.array(edges)
        adjacency = from_edge_list(edge_list, directed=True)
        louvain = Louvain()
        labels = louvain.fit_transform(adjacency)

        # Grouper les noeuds par communaute
        communities: dict[int, list[str]] = {}
        for i, label in enumerate(labels):
            label = int(label)
            if label not in communities:
                communities[label] = []
            communities[label].append(nodes[i])

        # Analyser chaque communaute
        for community_id, members in communities.items():
            if len(members) < 2:
                continue

            # Trouver le hub (page avec le plus de liens entrants dans la communaute)
            subgraph = G.subgraph(members)
            in_degrees = dict(subgraph.in_degree())
            hub = max(in_degrees, key=in_degrees.get) if in_degrees else members[0]
            max_in_degree = in_degrees.get(hub, 0)

            silo = {
                "id": f"silo-{community_id}",
                "members": members,
                "size": len(members),
                "hub": hub,
                "hub_in_degree": max_in_degree,
                "is_fantome": max_in_degree < 5,
            }
            silos.append(silo)

            if silo["is_fantome"]:
                silos_fantomes.append(silo)

    except Exception as e:
        logger.warning(f"T03: Louvain clustering failed: {e}")

    return silos, silos_fantomes


def _compute_graph_metrics(G: nx.DiGraph, pages: list) -> dict:
    """Calcule les metriques du graphe."""
    metrics = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "depth_avg": 0.0,
        "depth_max": 0,
        "depth_pages_gt_3": 0,
        "diameter": 0,
        "hubs": [],
        "orphans": [],
        "weakly_mailled": [],
        "gini_coefficient": 0.0,
    }

    if G.number_of_nodes() == 0:
        return metrics

    # Profondeur moyenne (depuis les donnees crawlees)
    depths = [p.crawl_depth for p in pages if p.crawl_depth >= 0]
    if depths:
        metrics["depth_avg"] = round(sum(depths) / len(depths), 2)
        metrics["depth_max"] = max(depths)
        metrics["depth_pages_gt_3"] = sum(1 for d in depths if d > 3)

    # Diametre (sur le plus grand composant connexe)
    if G.number_of_nodes() > 1:
        try:
            undirected = G.to_undirected()
            largest_cc = max(nx.connected_components(undirected), key=len)
            subgraph = undirected.subgraph(largest_cc)
            if subgraph.number_of_nodes() > 1:
                metrics["diameter"] = nx.diameter(subgraph)
        except Exception:
            pass

    # Hubs : pages avec > 10 liens entrants (ou top 5 si petit site)
    in_degrees = dict(G.in_degree())
    threshold = max(3, min(10, G.number_of_nodes() // 5))
    hubs = [(url, deg) for url, deg in in_degrees.items() if deg >= threshold]
    hubs.sort(key=lambda x: -x[1])
    metrics["hubs"] = [{"url": u, "in_degree": d} for u, d in hubs[:10]]

    # Orphelines : degre entrant = 0
    metrics["orphans"] = [url for url, deg in in_degrees.items() if deg == 0]

    # Faiblement maillees : degre entrant < 3 (mais > 0)
    metrics["weakly_mailled"] = [url for url, deg in in_degrees.items() if 0 < deg < 3]

    # Coefficient de Gini (distribution des liens entrants)
    if in_degrees:
        values = sorted(in_degrees.values())
        n = len(values)
        if n > 1 and sum(values) > 0:
            index = np.arange(1, n + 1)
            gini = (2 * np.sum(index * np.array(values)) - (n + 1) * np.sum(values)) / (n * np.sum(values))
            metrics["gini_coefficient"] = round(float(gini), 3)

    return metrics


async def run(state: TechAuditState) -> TechAuditState:
    """Analyse l'architecture du site."""
    state.current_agent = "tt03"

    if not state.crawled_pages:
        logger.warning("T03: aucune page crawlee — skip")
        state.status = "crawled"
        return state

    logger.info(f"T03: analysing architecture for {len(state.crawled_pages)} pages")

    # 1. Construire le graphe
    G = _build_link_graph(state.crawled_pages)
    logger.info(f"T03: graph built — {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # 2. Stocker les edges pour la suite
    state.graph_edges = [{"from": u, "to": v} for u, v in G.edges()]

    # 3. Detection de silos
    silos, silos_fantomes = _detect_silos(G, state.crawled_pages)
    state.silos = silos
    state.silos_fantomes = silos_fantomes
    logger.info(f"T03: {len(silos)} silos, {len(silos_fantomes)} silos fantomes")

    # 4. Metriques du graphe
    metrics = _compute_graph_metrics(G, state.crawled_pages)
    state.orphans = metrics["orphans"]
    logger.info(
        f"T03: depth_avg={metrics['depth_avg']}, depth_max={metrics['depth_max']}, "
        f"diameter={metrics['diameter']}, hubs={len(metrics['hubs'])}, "
        f"orphans={len(metrics['orphans'])}, gini={metrics['gini_coefficient']}"
    )

    # 5. Generer les issues
    issue_counter = 0

    # Profondeur excessive
    if metrics["depth_avg"] > 4:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description=f"Profondeur moyenne elevee ({metrics['depth_avg']} clics depuis l'accueil)",
            url=state.site_url,
            observed=f"depth_avg: {metrics['depth_avg']}",
            rule="depth_avg > 4",
            confidence="high",
            source_agent="T03",
            severity="high",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Varie — revoir la navigation",
            priority="P2",
        ))

    if metrics["depth_max"] > 5:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description=f"Profondeur max elevee ({metrics['depth_max']} clics) — pages difficiles a atteindre",
            url=state.site_url,
            observed=f"depth_max: {metrics['depth_max']}",
            rule="depth_max > 5",
            confidence="high",
            source_agent="T03",
            severity="high",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Ajouter des liens depuis les pages proches de l'accueil",
            priority="P2",
        ))

    if metrics["depth_pages_gt_3"] > len(state.crawled_pages) * 0.2:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description=f"{metrics['depth_pages_gt_3']} pages a plus de 3 clics de l'accueil ({round(metrics['depth_pages_gt_3']/max(1,len(state.crawled_pages))*100)}%)",
            url=state.site_url,
            observed=f"pages_depth_gt_3: {metrics['depth_pages_gt_3']}/{len(state.crawled_pages)}",
            rule="pages_depth_gt_3 > 20%",
            confidence="high",
            source_agent="T03",
            severity="medium",
            impact_business="Medium",
            gain_potentiel="Medium",
            effort="Ajouter des liens internes transversaux",
            priority="P3",
        ))

    # Silos fantomes
    for silo in silos_fantomes[:5]:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description=f"Silo fantome detecte ({silo['size']} pages) : groupe thematique sans page hub",
            url=silo.get("members", [""])[0] if silo.get("members") else state.site_url,
            observed=f"silo {silo['id']}: {silo['size']} pages, hub_in_degree={silo['hub_in_degree']}",
            rule="silo sans hub (degre entrant < 5)",
            confidence="medium",
            source_agent="T03",
            severity="medium",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Creer une page hub (categorie ou pilier) pour federer ce silo",
            priority="P2",
        ))

    # Pages orphelines
    if metrics["orphans"]:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description=f"{len(metrics['orphans'])} page(s) orpheline(s) — aucun lien interne entrant",
            url=metrics["orphans"][0] if len(metrics["orphans"]) == 1 else state.site_url,
            observed=f"orphans: {len(metrics['orphans'])} pages",
            rule="degre entrant = 0",
            confidence="high",
            source_agent="T03",
            severity="critical",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Ajouter des liens depuis des pages pertinentes",
            priority="P1",
        ))

    # Distribution desequilibree (Gini)
    if metrics["gini_coefficient"] > 0.8:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description=f"Distribution des liens internes desequilibree (Gini={metrics['gini_coefficient']})",
            url=state.site_url,
            observed=f"gini: {metrics['gini_coefficient']}",
            rule="gini > 0.8",
            confidence="medium",
            source_agent="T03",
            severity="medium",
            impact_business="Low",
            gain_potentiel="Medium",
            effort="Egaliser le maillage interne",
            priority="P3",
        ))

    # Pas de silos
    if not silos:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="architecture",
            description="Aucune structure en silos detectee — le site manque d'organisation thematique",
            url=state.site_url,
            observed="0 silos detectes",
            rule="silos == 0",
            confidence="medium",
            source_agent="T03",
            severity="medium",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Organiser le contenu en silos thematiques avec pages hub",
            priority="P2",
        ))

    logger.info(f"T03: {issue_counter} issues generated")
    state.updated_at = datetime.now()
    return state
