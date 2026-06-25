"""Page Maillage & Backlinks — Streamlit UI.

Pipeline 6 : 18 agents, audit backlinks, CRM, prospect discovery, anchor strategy.
"""

import asyncio
from datetime import datetime

import streamlit as st

from hermes.models.backlinks import BacklinksState
from hermes.agents.backlinks import BACKLINKS_ORDER, BACKLINKS_REGISTRY


async def _run_pipeline(state: BacklinksState) -> dict:
    for agent_id in BACKLINKS_ORDER:
        if agent_id in BACKLINKS_REGISTRY:
            state = await BACKLINKS_REGISTRY[agent_id](state)
    return {
        "state": state,
        "backlinks": len(state.backlinks),
        "domains": len(state.referring_domains),
        "toxic": len(state.toxic_domains),
        "recommandations": len(state.recommandations),
        "campaigns": len(state.campaigns),
        "authority": state.authority_score,
        "health": state.link_profile_health,
        "diversity": state.portfolio_diversity_score,
    }


def _badge(level: str) -> str:
    c = {"toxic": "#c62828", "suspicious": "#e65100", "low_risk": "#f9a825", "safe": "#2e7d32"}.get(level, "#333")
    b = {"toxic": "#fce4ec", "suspicious": "#fff3e0", "low_risk": "#fffde7", "safe": "#e8f5e9"}.get(level, "#eee")
    return f'<span style="background:{b};color:{c};padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">{level.upper()}</span>'


def render_backlinks_page():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Maillage & Backlinks</p>', unsafe_allow_html=True)
    st.caption("Audit backlinks, CRM netlinking, prospect discovery, anchor strategy. Pipeline 6 — 18 agents.")

    # Lire le projet partage
    site_url = st.session_state.get("project_url", "")
    keywords = st.session_state.get("project_keywords", [])
    competitors = st.session_state.get("project_competitors", [])
    mode = st.session_state.get("project_mode", "standard")
    profile = st.session_state.get("project_profile", "blog")

    if not site_url or not site_url.startswith("http"):
        st.info("Renseignez l'URL de votre site dans la sidebar (Projet) pour commencer l'analyse.")
        return

    st.markdown(f"**Site:** {site_url} | **Mode:** {mode} | **Profil:** {profile}")
    budget = st.number_input("Budget mensuel netlinking (euros)", value=300, min_value=0, key="bl_budget")

    launch = st.button("Auditer le profil Backlinks", type="primary", use_container_width=True)

    if launch:
        state = BacklinksState(
            site_url=site_url, mode=mode, profile=profile,
            competitors=competitors, keywords_cibles=keywords,
            budget_mensuel=budget,
        )
        with st.spinner("Audit backlinks en cours... (18 agents, ~15-30 secondes)"):
            result = asyncio.run(_run_pipeline(state))
            st.session_state.bl_result = result
            st.session_state.bl_state = result["state"]

    result = st.session_state.get("bl_result")
    state_obj = st.session_state.get("bl_state")

    if not result or not state_obj:
        st.info("Configurez votre site, vos concurrents et lancez l'audit.")
        _show_methodology()
        return

    # ─── Dashboard Scores ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Scores d'Autorite")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        auth = result["authority"]
        color = "#28a745" if auth >= 70 else ("#fd7e14" if auth >= 40 else "#dc3545")
        st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700;color:{color}">{auth}/100</div><small>Authority</small></div>', unsafe_allow_html=True)
    with c2:
        health = result["health"]
        st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700;color:#2563eb">{health}/100</div><small>Link Health</small></div>', unsafe_allow_html=True)
    with c3:
        div = result["diversity"]
        st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700;color:#9333ea">{div}/100</div><small>Diversite</small></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700">{result["backlinks"]}</div><small>Backlinks</small></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700">{result["domains"]}</div><small>Domaines</small></div>', unsafe_allow_html=True)

    # ─── Domaines suspects ───────────────────────────────────────────
    if state_obj.toxic_domains:
        st.markdown("---")
        st.markdown("## Domaines Suspects")
        for td in state_obj.toxic_domains[:10]:
            level = td.get("toxicity_level", "safe")
            st.markdown(f"- {_badge(level)} **{td['domain']}** — Score: {td.get('toxicity_score', 0):.0f}/100 — {', '.join(td.get('reasons', []))}", unsafe_allow_html=True)

    # ─── Profil d'ancres ─────────────────────────────────────────────
    if state_obj.anchor_profile.get("deviations"):
        st.markdown("---")
        st.markdown("## Profil d'Ancres")
        devs = state_obj.anchor_profile.get("deviations", {})
        cols = st.columns(len(devs))
        for col, (atype, data) in zip(cols, devs.items()):
            delta = data.get("deviation", 0)
            dcolor = "#28a745" if abs(delta) < 10 else ("#fd7e14" if abs(delta) < 20 else "#dc3545")
            with col:
                st.markdown(f'<div style="text-align:center"><small>{atype}</small><br>'
                            f'<span style="font-size:1.2rem;font-weight:700">{data["current"]}%</span><br>'
                            f'<span style="color:{dcolor};font-size:0.8rem">cible: {data["target"]}%</span></div>',
                            unsafe_allow_html=True)
        alerts = state_obj.anchor_profile.get("alerts", [])
        if alerts:
            st.warning("\n".join(f"- {a}" for a in alerts))

        # Suggestions concretes d'ancres
        suggestions = state_obj.anchor_profile.get("priority_suggestions", [])
        if suggestions:
            with st.expander("Textes d'ancres suggeres — Copier-coller pret a l'emploi"):
                by_type = {}
                for s in suggestions:
                    by_type.setdefault(s["type"], []).append(s["text"])
                for atype, texts in by_type.items():
                    st.markdown(f"**{atype.replace('_', ' ').title()}**:")
                    for text in texts[:3]:
                        st.code(text, language=None)

    # ─── Follow/Nofollow + AI Links ──────────────────────────────────
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("## Ratio Follow / Nofollow")
        ap = state_obj.anchor_profile
        dofollow = ap.get("dofollow_ratio", 100)
        nofollow = ap.get("nofollow_ratio", 0)
        st.markdown(f"**Dofollow**: {ap.get('dofollow_count', 0)} liens ({dofollow:.0f}%)")
        st.markdown(f"**Nofollow**: {ap.get('nofollow_count', 0)} liens ({nofollow:.0f}%)")
        follow_alert = ap.get("follow_alert", "OK")
        if "Risque" in follow_alert or "penalite" in follow_alert:
            st.error(follow_alert)
        elif "OK" not in follow_alert:
            st.warning(follow_alert)
        else:
            st.success(follow_alert)
    with c2:
        st.markdown("## Liens IA / GEO (AEO)")
        ai = state_obj.ai_status if hasattr(state_obj, 'ai_status') and state_obj.ai_status else {}
        ai_vis = ai.get("ai_visibility_score", 0)
        ai_color = "#28a745" if ai_vis >= 60 else ("#fd7e14" if ai_vis >= 30 else "#dc3545")
        st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700;color:{ai_color}">{ai_vis}/100</div><small>AI Visibility Score</small></div>', unsafe_allow_html=True)
        llms = "✅ Detecte" if ai.get("llms_txt") else "❌ Absent"
        st.markdown(f"**llms.txt**: {llms}")
        n_allowed = len(ai.get("ai_crawlers_allowed", []))
        n_blocked = len(ai.get("ai_crawlers_blocked", []))
        st.markdown(f"**AI Crawlers**: {n_allowed} autorises, {n_blocked} bloques")
        entity_auth = ai.get("entity_authority_score", 0)
        st.markdown(f"**Entity Authority**: {entity_auth}/100")
    geo_recs = ai.get("geo_recommendations", [])
    if geo_recs:
        with st.expander("Recommandations GEO/AEO"):
            for rec in geo_recs:
                st.markdown(f"- {rec}")

    # ─── Recommandations ─────────────────────────────────────────────
    if state_obj.recommandations:
        st.markdown("---")
        st.markdown(f"## Plan d'Action ({len(state_obj.recommandations)} recommandations)")
        tabs = st.tabs(["P0-P1 (Prioritaires)", "P2-P3", "Toutes"])
        for tab, filt in zip(tabs, [["P0", "P1"], ["P2", "P3"], None]):
            with tab:
                filtered = [r for r in state_obj.recommandations if filt is None or r.priorite in filt]
                for r in filtered[:20]:
                    with st.expander(f"{r.priorite} | {r.type_action} | {r.domaine_cible or 'Global'} | Cout: {r.cout_estime:.0f}euros | Confiance: {r.confidence_score}/100"):
                        st.markdown(f"**Justification**: {r.justification}")
                        st.markdown(f"**Impact**: {r.impact_estime} | **Delai**: {r.delai_estime} | **Effort**: {r.effort_estime}")

    # ─── CRM ─────────────────────────────────────────────────────────
    if state_obj.campaigns:
        st.markdown("---")
        st.markdown(f"## CRM Netlinking ({len(state_obj.campaigns)} campagnes)")
        statuses = {"prospect": 0, "contacte": 0, "relance": 0, "en_cours": 0, "accepte": 0, "publie": 0, "refuse": 0, "abandonne": 0}
        for c in state_obj.campaigns:
            statuses[c.status] = statuses.get(c.status, 0) + 1
        cols = st.columns(4)
        for col, (st_name, st_count) in zip(cols, list(statuses.items())[:4]):
            with col: st.metric(st_name.title(), st_count)
        cols2 = st.columns(4)
        for col, (st_name, st_count) in zip(cols2, list(statuses.items())[4:]):
            with col: st.metric(st_name.title(), st_count)

    # ─── Exports ─────────────────────────────────────────────────────
    if state_obj.rapport_html:
        st.markdown("---")
        st.markdown("## Export")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("Telecharger le rapport HTML", state_obj.rapport_html,
                               f"backlinks_{state_obj.domain}_{datetime.now().strftime('%Y%m%d')}.html",
                               "text/html", use_container_width=True)
        with c2:
            st.download_button("Telecharger le JSON", state_obj.rapport_json,
                               f"backlinks_{state_obj.domain}_{datetime.now().strftime('%Y%m%d')}.json",
                               "application/json", use_container_width=True)


def _show_methodology():
    with st.expander("Methodologie — 18 agents backlinks"):
        st.markdown("""
        ### Phase 0 — Startup
        - **B00** Superviseur : verification APIs (DataForSEO, GSC, Bing)

        ### Phase 1 — Collecte
        - **B01** Import Backlinks : DataForSEO + GSC + fallback

        ### Phase 2 — Analyse
        - **B02** Qualite & Scoring : DR, topical, scarcity, geo
        - **B03** Toxiques : PBN, spam, sur-optimisation
        - **B04** Gap Analysis : domaines concurrents non acquis
        - **B05** Link Reclamation : mentions sans lien, liens perdus
        - **B05b** Broken Link Building (V1.5)
        - **B12** Prospect Discovery : medias, blogs, podcasts par secteur
        - **B14** Anchor Strategy : profil d'ancres cible vs actuel
        - **B15** Portfolio Optimizer (V3)
        - **B16** Entity Authority (V3)
        - **B17** Media Relationship Score (V3)
        - **B08** Moteur de Preuve SEO (V2)
        - **B09** Link Scarcity & Velocity (V2)
        - **B10** Authority Graph (V2)

        ### Phase 3 — Synthese
        - **B06** Recommandations & Plan d'Action (Haiku)

        ### Phase 4 — Execution
        - **B07** CRM & Pilotage Campagnes

        ### Phase 5 — Export
        - **B11** Export & Routage HTML/JSON/CSV

        ### Scores
        - Authority Score 0-100, Link Profile Health 0-100, Portfolio Diversity 0-100
        - Anchor Risk Score 0-100, Competitor Gap Score 0-100
        - Entity Authority Score (V3), Media Relationship Score (V3)
        """)
