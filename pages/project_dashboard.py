"""Page Dashboard Projet Unifie — vue consolidee "Mon Site" (gap #2).

Remplace la navigation en silos. Affiche les 6 scores consolides,
la prochaine action recommandee, et les KPIs de tous les pipelines
sur une seule page.
"""

import streamlit as st
from datetime import datetime

def render_project_dashboard():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Mon Site</p>', unsafe_allow_html=True)
    st.caption("Vue consolidee de tous les pipelines. Un site = un projet.")

    url = st.session_state.get("project_url", "")
    domain = st.session_state.get("project_domain", "") or (url.replace("https://", "").replace("www.", "") if url else "")
    profile = st.session_state.get("project_profile", "blog")
    keywords = st.session_state.get("project_keywords", [])

    if not url or not url.startswith("http"):
        st.info("Renseignez l'URL de votre site dans la sidebar (Projet) pour voir le dashboard consolide.")
        return

    # Header
    st.markdown(f"## {domain or 'Mon Site'}")
    st.caption(f"Profil: {profile} | Mots-cles: {len(keywords)} | Pipeline pret")

    # Scores consolides
    st.markdown("### Scores")
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    # Recuperer les scores depuis le state ou les resultats precedents
    serp_result = st.session_state.get("sv_result", {})
    st_result = st.session_state.get("st_result", {})
    bl_result = st.session_state.get("bl_result", {})

    health = serp_result.get("health", 0) if isinstance(serp_result, dict) else 0
    sante = (st_result.get("state", None) and st_result["state"].executive_summary and st_result["state"].executive_summary.sante_strategique) or 0 if isinstance(st_result, dict) else 0
    authority = bl_result.get("authority", 0) if isinstance(bl_result, dict) else 0
    link_health = bl_result.get("health", 0) if isinstance(bl_result, dict) else 0
    anchor_h = bl_result.get("state", None) and bl_result["state"].anchor_profile.get("health_score", 0) if isinstance(bl_result, dict) and bl_result.get("state") else 0
    ai_vis = bl_result.get("state", None) and bl_result["state"].ai_status.get("ai_visibility_score", 0) if isinstance(bl_result, dict) and bl_result.get("state") and hasattr(bl_result["state"], "ai_status") else 0

    scores = [
        ("SERP", health, "P4"), ("Strategie", sante, "P5"),
        ("Authority", authority, "P6"), ("Link Health", link_health, "P6"),
        ("Ancres", anchor_h, "P6"), ("AI Vis.", ai_vis, "P6"),
    ]
    for col, (label, val, pipe) in zip([c1, c2, c3, c4, c5, c6], scores):
        color = "#28a745" if val >= 70 else ("#fd7e14" if val >= 40 else "#dc3545")
        with col:
            st.markdown(f'<div style="text-align:center"><div style="font-size:2rem;font-weight:700;color:{color}">{val}/100</div><small>{label}<br>({pipe})</small></div>', unsafe_allow_html=True)

    # Next Action
    st.markdown("---")
    st.markdown("### Prochaine action recommandee")
    next_action = ""
    if isinstance(st_result, dict) and st_result.get("state"):
        next_action = getattr(st_result["state"], "next_action", "") or "Lancer un diagnostic complet"
    elif isinstance(bl_result, dict) and bl_result.get("state"):
        ns = bl_result["state"]
        if hasattr(ns, "next_action"):
            next_action = ns.next_action or "Auditer le profil backlinks"

    if next_action:
        st.success(f"→ {next_action}")
    else:
        st.info("Lancez le diagnostic complet pour obtenir des recommandations personnalisees.")

    # Actions rapides
    st.markdown("### Actions rapides")
    ca1, ca2, ca3, ca4 = st.columns(4)
    with ca1:
        if st.button("Diagnostic complet", use_container_width=True, type="primary"):
            st.session_state.launch_all = True
    with ca2:
        if st.button("Audit technique", use_container_width=True):
            st.session_state.nav_page = "Audit Technique"
            st.rerun()
    with ca3:
        if st.button("Strategie", use_container_width=True):
            st.session_state.nav_page = "Strategie"
            st.rerun()
    with ca4:
        if st.button("Backlinks", use_container_width=True):
            st.session_state.nav_page = "Backlinks"
            st.rerun()

    # Statut des pipelines
    st.markdown("---")
    st.markdown("### Etat des pipelines")
    pipe_status = {
        "P1 Editorial": "Pret" if url else "Configurer",
        "P2 Audit Contenu": "Pret" if url else "Configurer",
        "P3 Audit Technique": "Pret" if url else "Configurer",
        "P4 SERP": f"{health}/100" if health else "A lancer",
        "P5 Strategie": f"{sante}/100" if sante else "A lancer",
        "P6 Backlinks": f"{authority}/100" if authority else "A lancer",
        "P7 Maintenance": "Auto",
        "P8 Learning": "Actif",
    }
    cols = st.columns(4)
    for i, (pipe, status) in enumerate(pipe_status.items()):
        with cols[i % 4]:
            color = "#28a745" if ("Pret" in str(status) or "Auto" in str(status) or "Actif" in str(status) or "/" in str(status)) else "#fd7e14"
            st.markdown(f'**{pipe}**<br><span style="color:{color}">{status}</span>', unsafe_allow_html=True)

    # Timeline
    st.markdown("---")
    st.markdown("### Historique recent")
    st.caption("Les analyses de ce site sont logguees dans hermes.db. Lancez un diagnostic pour voir l'historique.")
