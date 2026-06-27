"""Page Strategie Editoriale — Streamlit UI.

Pipeline 5 : 18 agents, analysis business, roadmap, kill list, CEO summary.
"""

import asyncio
from datetime import datetime

import streamlit as st

from hermes.models.strategie import StrategieState
from hermes.agents.strategie import STRATEGIE_ORDER, STRATEGIE_REGISTRY


async def _run_pipeline(state: StrategieState) -> dict:
    for agent_id in STRATEGIE_ORDER:
        if agent_id in STRATEGIE_REGISTRY:
            state = await STRATEGIE_REGISTRY[agent_id](state)
    return {
        "state": state,
        "recommandations": len(state.recommandations),
        "kill_list": len(state.kill_list),
        "sujets": len(state.sujets),
        "opportunites": len(state.opportunites),
        "health": state.executive_summary.sante_strategique if state.executive_summary else 0,
        "export": state,
    }


def _badge(p: str) -> str:
    c = {"P0": "#c62828", "P1": "#e65100", "P2": "#f9a825", "P3": "#2e7d32", "KILL": "#6a1b9a"}.get(p, "#333")
    b = {"P0": "#fce4ec", "P1": "#fff3e0", "P2": "#fffde7", "P3": "#e8f5e9", "KILL": "#f3e5f5"}.get(p, "#eee")
    return f'<span style="background:{b};color:{c};padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">{p}</span>'


def render_strategie_page():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Strategie Editoriale</p>', unsafe_allow_html=True)
    st.caption("Roadmap, forecast, kill list, CEO summary. Pipeline 5 — 18 agents.")

    # Lire le projet partage
    site_url = st.session_state.get("project_url", "")
    keywords = st.session_state.get("project_keywords", [])
    competitors = st.session_state.get("project_competitors", [])
    mode = st.session_state.get("project_mode", "standard")
    profile = st.session_state.get("project_profile", "blog")

    if not site_url or not site_url.startswith("http"):
        st.warning("Aucun projet actif.")
        if st.button("✨ Creer un projet", key="st_create_project", use_container_width=True):
            st.session_state.nav_page = "🏠 Mon Site"; st.rerun()
        return

    st.markdown(f"**Site:** {site_url} | **Mode:** {mode} | **Profil:** {profile}")
    valeur_lead = st.number_input("Valeur lead (euros)", value=100, min_value=0, key="st_valeur")
    taux_conv = st.number_input("Taux conversion (%)", value=2.0, min_value=0.0, max_value=100.0, key="st_conv") / 100.0

    launch = st.button("Elaborer la Strategie", type="primary", use_container_width=True)

    if launch and site_url:
        state = StrategieState(
            site_url=site_url,
            mode=mode,
            profile=profile,
            keywords_monitored=keywords,
            competitors=competitors,
            valeur_lead=valeur_lead,
            taux_conversion=taux_conv,
        )

        with st.spinner("Analyse strategique en cours... (18 agents, ~10-30 secondes)"):
            result = asyncio.run(_run_pipeline(state))
            st.session_state.st_result = result
            st.session_state.st_state = result["state"]

    result = st.session_state.get("st_result")
    state_obj = st.session_state.get("st_state")

    if not result or not state_obj:
        st.info("Configurez votre site et vos mots-cles, puis lancez l'analyse.")
        _show_methodology()
        return

    es = state_obj.executive_summary

    # ─── CEO Dashboard ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## CEO Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        health = es.sante_strategique if es else 50
        color = "#28a745" if health >= 70 else ("#fd7e14" if health >= 40 else "#dc3545")
        st.markdown(f'<div style="text-align:center"><div style="font-size:2.5rem;font-weight:700;color:{color}">{health}/100</div>'
                    f'<div style="font-size:0.8rem;color:#666">Sante Strategique</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div style="text-align:center"><div style="font-size:2.5rem;font-weight:700;color:#2563eb">{result["recommandations"]}</div>'
                    f'<div style="font-size:0.8rem;color:#666">Recommandations</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div style="text-align:center"><div style="font-size:2.5rem;font-weight:700;color:#9333ea">{result["kill_list"]}</div>'
                    f'<div style="font-size:0.8rem;color:#666">Kill List</div></div>', unsafe_allow_html=True)
    with col4:
        roi = f"{es.roi_12mois_haut:.0f}" if es else "—"
        st.markdown(f'<div style="text-align:center"><div style="font-size:2.5rem;font-weight:700;color:#059669">{roi} euros</div>'
                    f'<div style="font-size:0.8rem;color:#666">ROI 12 mois estime</div></div>', unsafe_allow_html=True)

    # ─── Executive Summary ──────────────────────────────────────────────
    if es:
        st.markdown("---")
        st.markdown("## Executive Summary")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### Top 3 Opportunites")
            for o in es.top_opportunites:
                st.markdown(f"- **{o['sujet']}** — {o['volume']}/mois — {o.get('potentiel', '')}")
            st.markdown(f"**ROI estime 12 mois:** {es.roi_12mois_bas:.0f} euros — {es.roi_12mois_haut:.0f} euros")
            st.markdown(f"**Budget mensuel recommande:** {es.budget_mensuel_recommande:.0f} euros")
        with col_b:
            st.markdown("### Top Menaces")
            for m in es.top_menaces:
                st.markdown(f"- **{m['type']}**: {m.get('impact', '')}")
            st.markdown(f"**Perte estimee si inaction:** {es.perte_estimee_si_inaction}")
            st.markdown("**Recommandations cles:**")
            for r in es.recommandations_cles:
                st.markdown(f"- {r}")

    # ─── Roadmap ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Roadmap Editoriale")

    recs = state_obj.recommandations
    if recs:
        tabs = st.tabs(["Toutes", "P0 - Immediat", "P1 - 1-3 mois", "P2 - 3-6 mois", "P3 - 6-12 mois", "KILL"])
        for tab, priorite_filter in zip(tabs, [None, "P0", "P1", "P2", "P3", "KILL"]):
            with tab:
                filtered = [r for r in recs if priorite_filter is None or r.priorite == priorite_filter]
                if filtered:
                    for r in filtered:
                        conf_color = "green" if r.confidence_score >= 80 else ("orange" if r.confidence_score >= 60 else "red")
                        with st.expander(f"{r.sujet} — {r.priorite} — Vol: {r.volume_recherche}/mois — Confiance: :{conf_color}[{r.confidence_score}/100]"):
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                st.markdown(f"**Action**: {r.action.replace('_', ' ').title()}")
                                st.markdown(f"**Justification**: {r.justification}")
                                st.markdown(f"**Effort**: {r.effort_estime} | **Cout**: {r.cout_estime:.0f} euros | **ROI 12m**: {r.roi_12mois:+.0f} euros")
                                st.markdown(f"**Delai**: {r.delai_resultats} | **Pipeline**: {r.pipeline_cible} | **Portfolio**: {r.portfolio}")
                                if r.dependencies:
                                    st.markdown(f"**Dependances**: {', '.join(r.dependencies)}")
                            with c2:
                                st.markdown(f"**Confiance**: :{conf_color}[{r.confidence_score}/100]")
                                st.caption(r.confidence_justification)
                                if r.trace:
                                    with st.expander("Decision Trace"):
                                        st.json(r.trace.model_dump())
                else:
                    st.info("Aucune recommandation dans cette categorie.")

    # ─── Kill List ──────────────────────────────────────────────────────
    st.markdown("---")
    if state_obj.kill_list:
        st.markdown("## Kill List")
        for k in state_obj.kill_list:
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(k.severite, "⚪")
            st.markdown(f"- {severity_icon} **{k.sujet}** — {k.raison}")
            with st.expander("Details"):
                st.markdown(f"**Categorie**: {k.categorie}")
                st.markdown(f"**Justification**: {k.justification}")
                if k.trace:
                    st.json(k.trace.model_dump())

    # ─── Forecast ───────────────────────────────────────────────────────
    if state_obj.forecast:
        st.markdown("---")
        st.markdown("## Forecast 12 mois")
        try:
            import plotly.graph_objects as go
            mois = [f.mois for f in state_obj.forecast]
            trafic = [f.trafic_estime for f in state_obj.forecast]
            leads = [f.leads_estimes for f in state_obj.forecast]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=mois, y=trafic, mode='lines+markers', name='Trafic estime',
                                     line=dict(color='#2563eb', width=3), fill='tozeroy', fillcolor='rgba(37,99,235,0.1)'))
            fig.add_trace(go.Bar(x=mois, y=leads, name='Leads estimes', marker_color='#059669', opacity=0.5, yaxis='y2'))
            fig.update_layout(
                title="Projection trafic & leads", xaxis_title="Mois",
                yaxis=dict(title="Visites/mois"), yaxis2=dict(title="Leads/mois", overlaying='y', side='right'),
                hovermode='x unified', height=400, margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.line_chart({f"Mois {f.mois}": f.trafic_estime for f in state_obj.forecast})

    # ─── Portfolio ──────────────────────────────────────────────────────
    if state_obj.portfolio_allocation:
        st.markdown("---")
        st.markdown("## Portfolio Strategy")
        alloc = state_obj.portfolio_allocation
        cols = st.columns(len(alloc))
        for col, (cat, pct) in zip(cols, alloc.items()):
            with col:
                st.markdown(f'<div style="text-align:center"><div style="font-size:1.5rem;font-weight:700">{pct}%</div>'
                            f'<div style="font-size:0.8rem;color:#666">{cat.title()}</div></div>', unsafe_allow_html=True)

    # ─── Cannibalisations ───────────────────────────────────────────────
    if state_obj.cannibalisations:
        st.markdown("---")
        st.markdown("## Cannibalisations detectees")
        for c in state_obj.cannibalisations[:10]:
            g = c.get("gravite", "low")
            gcolor = "#c62828" if g == "critical" else ("#e65100" if g == "high" else ("#f9a825" if g == "medium" else "#666"))
            st.markdown(f'- <span style="color:{gcolor};font-weight:600">[{g.upper()}]</span> **{c.get("keyword","")}** — {c.get("recommandation","")}',
                        unsafe_allow_html=True)

    # ─── Export ─────────────────────────────────────────────────────────
    if state_obj.rapport_html:
        st.markdown("---")
        st.markdown("## Export")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Telecharger le rapport HTML", state_obj.rapport_html,
                               f"strategie_{state_obj.domain}_{datetime.now().strftime('%Y%m%d')}.html",
                               "text/html", use_container_width=True)
        with col2:
            st.download_button("Telecharger le JSON (API)", state_obj.rapport_json,
                               f"strategie_{state_obj.domain}_{datetime.now().strftime('%Y%m%d')}.json",
                               "application/json", use_container_width=True)


def _show_methodology():
    with st.expander("Methodologie — 18 agents strategiques"):
        st.markdown("""
        ### Phase 0 — Startup
        - **ST00** — Superviseur : verification P2/P3/P4, init DB, configuration

        ### Phase 1 — Analyses (paralleles)
        - **ST01** — Cartographie des Sujets : couvert vs manquant par silo
        - **ST01b** — Topical Authority Score 0-100 par silo
        - **ST02** — Cannibalisation : detection P4 + ChromaDB
        - **ST03** — Opportunites : requetes sans page dediee
        - **ST04** — Gap Concurrentiel (Haiku) : ecarts semantiques et GEO
        - **ST04b** — Competitive Feasibility Score 0-100
        - **ST04c** — GEO Opportunity Mapping
        - **ST05** — Business Score : trafic x conversion x valeur
        - **ST05b** — SEO Economics : effort, cout, ROI
        - **ST07** — Silos & Clusters : piliers sans satellites, silos vides
        - **ST08** — Fusion/Separation : recommandations structurelles

        ### Phase 2 — Synthese & Decision
        - **ST06** — Roadmap Editoriale (Haiku) : aggregation + priorisation
        - **ST06b** — Forecast 12 mois (Haiku)
        - **ST06c** — Portfolio Strategy : acquisition/retention/defense/conversion/authority
        - **ST09** — Revue Humaine : flags YMYL, controverses, legal
        - **ST10** — Priorisation Globale : matrice configurable
        - **ST10b** — Kill List : sujets a eviter

        ### Phase 3 — Export
        - **ST11** — Export & Routage : CEO Summary HTML + JSON + routage P1/P2/P3/P6/P7

        ### Confidence Score
        Chaque recommandation inclut un score 0-100 et une Decision Trace.
        """)
