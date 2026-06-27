"""Page Learning Engine — Streamlit UI. Pipeline 8."""

import asyncio
import streamlit as st
from hermes.models.project import Project
from hermes.core.learning_workflow import run_learning_pipeline


async def _run(project: Project) -> Project:
    return await run_learning_pipeline(project)


def render_learning_page():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Learning Engine</p>', unsafe_allow_html=True)
    st.caption("Apprentissage continu, calibration, patterns. Pipeline 8 — 8 agents.")

    # Lire le projet partage
    project_url = st.session_state.get("project_url", "")
    project_domain = st.session_state.get("project_domain", "")
    project_profile = st.session_state.get("project_profile", "blog")

    if not project_url or not project_url.startswith("http"):
        st.warning("Aucun projet actif.")
        if st.button("✨ Creer un projet", key="learn_create_project", use_container_width=True):
            st.session_state.nav_page = "🏠 Mon Site"; st.rerun()
        return

    st.markdown(f"**Site:** {project_url} | **Profil:** {project_profile}")

    from hermes.core.project_db import get_project, create_project
    existing = get_project(domain=project_domain) if project_domain else None
    pid = existing["id"] if existing else create_project({
        "nom": project_domain or "Projet", "site_url": project_url,
        "domain": project_domain, "profile": project_profile, "secteur": "autre",
    })

    opt_in = st.checkbox("Opt-in apprentissage global (anonymise)", value=False, key="learn_optin",
                         help="Partagez vos donnees anonymisees pour ameliorer le modele global")

    launch = st.button("Lancer l'apprentissage", type="primary")

    if launch:
        project = Project(id=pid)
        project.local_seo["learning_opt_in"] = opt_in
        with st.spinner("Apprentissage en cours... (8 agents)"):
            result = asyncio.run(_run(project))
            st.session_state.learn_result = result

    result = st.session_state.get("learn_result")
    if result:
        st.success("Apprentissage termine")

        try:
            from hermes.core.project_db import get_db_stats
            stats = get_db_stats()
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Patterns", stats.get("patterns", 0))
            with c2: st.metric("Failures", stats.get("failures", 0))
            with c3: st.metric("Actions executees", stats.get("execution_actions", 0))
        except Exception:
            pass

        st.info("Mode accumulation silencieuse: les donnees sont collectees. "
                "La calibration se declenchera automatiquement quand le volume de predictions sera suffisant (50+ par type d'action et secteur).")
