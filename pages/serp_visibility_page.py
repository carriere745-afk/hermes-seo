"""Page SERP & Visibility Intelligence — Streamlit UI.

Pipeline 4 : 11 agents, mode continu/on-demand.
"""

import asyncio
from datetime import datetime

import streamlit as st

from hermes.models.serp_visibility import SerpVisibilityState
from hermes.agents.serp_visibility import SERP_ORDER, SERP_REGISTRY


async def _run_pipeline(state: SerpVisibilityState) -> dict:
    for agent_id in SERP_ORDER:
        if agent_id in SERP_REGISTRY:
            state = await SERP_REGISTRY[agent_id](state)
    return {
        "state": state, "keywords": len(state.keywords),
        "positions": len(state.positions), "quick_wins": state.quick_wins,
        "alerts": state.alerts, "variations": state.variations,
        "health": state.health_score, "ai_vis": state.ai_visibility_score,
        "sov": state.sov_score, "competitors": state.competitors,
        "features": state.serp_features, "gaps": state.content_gaps,
        "correlations": state.correlations, "export": state,
    }


def _badge(s: str) -> str:
    c = {"P0": "#c62828","P1": "#e65100","P2": "#f9a825","P3": "#2e7d32","info":"#1565c0"}.get(s, "#333")
    b = {"P0":"#fce4ec","P1":"#fff3e0","P2":"#fffde7","P3":"#e8f5e9","info":"#e3f2fd"}.get(s,"#eee")
    return f'<span style="background:{b};color:{c};padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">{s}</span>'


def render_serp_visibility_page():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">SERP & Visibility Intelligence</p>', unsafe_allow_html=True)
    st.caption("Surveillance des positions, analyse concurrentielle, AI visibility, alertes.")

    # Lire le projet partage (sidebar)
    site_url = st.session_state.get("project_url", "")
    keywords = st.session_state.get("project_keywords", [])
    competitors = st.session_state.get("project_competitors", [])
    mode = st.session_state.get("project_mode", "standard")
    profile = st.session_state.get("project_profile", "blog")

    if not site_url or not site_url.startswith("http"):
        st.info("Renseignez l'URL de votre site dans la sidebar (Projet) pour commencer l'analyse.")
        return

    st.markdown(f"**Site:** {site_url} | **Mode:** {mode} | **Profil:** {profile}")
    if keywords:
        st.markdown(f"**Mots-cles:** {', '.join(keywords[:6])}{'...' if len(keywords) > 6 else ''}")
    if competitors:
        st.markdown(f"**Concurrents:** {', '.join(competitors[:4])}")

    launch = st.button("Lancer l'analyse SERP", type="primary", use_container_width=True)

    if launch:
        state = SerpVisibilityState(
            site_url=site_url, keywords=keywords, competitors=competitors,
            mode=mode, profile=profile,
        )
        with st.spinner("Analyse SERP en cours..."):
            result = asyncio.run(_run_pipeline(state))
        st.session_state.sv_result = result
        st.rerun()

    if "sv_result" not in st.session_state or not st.session_state.sv_result:
        return

    r = st.session_state.sv_result
    state = r["export"]

    st.markdown("---")
    st.markdown("## Résultats")

    # Dashboard
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    with k1: st.metric("Keywords", r["keywords"])
    with k2: st.metric("Positions", r["positions"])
    with k3: st.metric("Quick Wins", len(r["quick_wins"]))
    with k4: st.metric("Alertes", len(r["alerts"]))
    with k5: st.metric("Health", f"{r['health']}/100")
    with k6: st.metric("AI Visibility", f"{r['ai_vis']}/100")
    with k7: st.metric("Share of Voice", f"{r['sov']}/100")

    # Alerts
    if r["alerts"]:
        st.markdown("### Alertes")
        for a in r["alerts"][:10]:
            icon = "🔴" if a.priorite == "P0" else "🟠" if a.priorite == "P1" else "🟡"
            st.markdown(f"{icon} **[{a.type}]** {a.note[:150]}", unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Positions", "⚡ Quick Wins", "🔍 Concurrence", "📋 Rapport"])
    with tab1:
        if r["positions"]:
            st.dataframe(
                [{"Keyword": p.keyword, "Pos": p.position, "Impr": p.impressions,
                  "Clics": p.clicks, "CTR": f"{p.ctr}%", "Vol": p.search_volume, "Src": p.source}
                 for p in state.positions[:50]],
                use_container_width=True, hide_index=True
            )
        if r["variations"]:
            st.markdown("**Variations détectées**")
            for v in r["variations"][:10]:
                delta = v.get("delta", 0)
                direction = "🔴" if delta > 0 else "🟢"
                st.markdown(f"{direction} **{v['keyword']}** : {v['position_before']} → {v['position_after']} ({v['type']})")
    with tab2:
        if r["quick_wins"]:
            for w in r["quick_wins"][:15]:
                with st.container():
                    st.markdown(f"**{w.keyword}** — Pos {w.position} | BS: {w.business_score}")
                    st.caption(f"{w.action_recommandee} → Pipeline {w.pipeline_cible}")
        else:
            st.info("Aucun quick win détecté (positions 4-15 avec volume > 100)")
    with tab3:
        if state.competitors:
            st.markdown(f"**Concurrents surveillés** : {', '.join(state.competitors[:5])}")
        if state.competitor_positions:
            st.dataframe(
                [{"Domaine": c.domain, "KW": c.keyword, "Pos": c.position}
                 for c in state.competitor_positions[:30]],
                use_container_width=True, hide_index=True
            )
        if state.share_of_voice:
            st.markdown("**Share of Voice**")
            for s in state.share_of_voice[:5]:
                st.markdown(f"- **{s.domain}** : {s.weighted_visibility:.1f}% (imp: {s.sov_impressions:.1f}%, clics: {s.sov_clicks:.1f}%)")
    with tab4:
        if state.rapport_html:
            st.download_button("📄 Télécharger rapport HTML", data=state.rapport_html,
                               file_name=f"serp_report_{state.domain}_{datetime.now().strftime('%Y%m%d')}.html",
                               mime="text/html", use_container_width=True)
        st.markdown("**Résumé**")
        st.markdown(f"- Score santé SERP : {r['health']}/100")
        st.markdown(f"- AI Visibility : {r['ai_vis']}/100")
        st.markdown(f"- Share of Voice : {r['sov']}/100")
        st.markdown(f"- Keywords suivis : {r['keywords']}")
        st.markdown(f"- Quick Wins : {len(r['quick_wins'])}")
        st.markdown(f"- Corrélations : {len(r['correlations'])}")
        st.markdown(f"- Concurrents : {len(state.competitors)}")
