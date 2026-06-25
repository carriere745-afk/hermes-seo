"""Page Maintenance & Execution — Streamlit UI. Pipeline 7."""

import asyncio
from datetime import datetime
import streamlit as st
from hermes.models.project import Project
from hermes.core.maintenance_workflow import run_maintenance_pipeline


async def _run(project: Project) -> Project:
    return await run_maintenance_pipeline(project)


def render_maintenance_page():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Maintenance & Execution</p>', unsafe_allow_html=True)
    st.caption("Content decay, Core Update recovery, execution automatique. Pipeline 7 — 12 agents.")

    # Lire le projet partage
    project_url = st.session_state.get("project_url", "")
    project_domain = st.session_state.get("project_domain", "")
    project_profile = st.session_state.get("project_profile", "blog")
    project_mode = st.session_state.get("project_mode", "standard")
    project_keywords = st.session_state.get("project_keywords", [])
    project_competitors = st.session_state.get("project_competitors", [])

    if not project_url or not project_url.startswith("http"):
        st.info("Renseignez l'URL de votre site dans la sidebar (Projet) pour activer la maintenance.")
        return

    st.markdown(f"**Site:** {project_url} | **Profil:** {project_profile}")

    # Auto-create project if needed
    from hermes.core.project_db import get_project, create_project
    existing = get_project(domain=project_domain) if project_domain else None
    pid = existing["id"] if existing else create_project({
        "nom": project_domain or "Projet", "site_url": project_url,
        "domain": project_domain, "profile": project_profile,
        "secteur": "autre", "competitors": project_competitors,
        "keywords_cibles": project_keywords,
    })

    mode = st.selectbox("Mode execution", ["semi-auto", "manual", "auto"], key="maint_mode")

    launch = st.button("Lancer la maintenance", type="primary")

    if launch:
        from hermes.core.project_db import get_project
        existing = get_project(project_id=pid)
        if not existing:
            st.error(f"Projet {pid} introuvable.")
            return

        project = Project(
            id=pid, nom=existing.get("nom", ""), site_url=existing.get("site_url", ""),
            domain=existing.get("domain", ""), profile=existing.get("profile", "blog"),
            secteur=existing.get("secteur", "autre"), mode_execution=mode,
            max_actions_per_day=existing.get("max_actions_per_day", 20),
            onboarding_step=existing.get("onboarding_step", "welcome"),
            onboarding_progress=existing.get("onboarding_progress", 0),
        )

        with st.spinner("Maintenance en cours... (12 agents)"):
            result = asyncio.run(_run(project))
            st.session_state.maint_result = result

    result = st.session_state.get("maint_result")
    if result:
        st.success(f"Maintenance terminee — {len(result.execution_actions)} actions")
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Actions generees", len(result.execution_actions))
        with c2: st.metric("Auto", sum(1 for a in result.execution_actions if not a.human_approval_required))
        with c3: st.metric("Review humaine", sum(1 for a in result.execution_actions if a.human_approval_required))

        for a in result.execution_actions[:20]:
            with st.expander(f"{a.category.upper()} | {a.action_type} | {a.priority} | Status: {a.status}"):
                st.markdown(f"**Description**: {a.description}")
                if a.content_to_generate:
                    st.code(a.content_to_generate[:500], language="text" if a.file_to_create != "llms.txt" else None)
                if a.human_approval_required:
                    st.warning("Validation humaine requise")
                if a.execution_error:
                    st.error(a.execution_error)
