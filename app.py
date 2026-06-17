"""Hermes SEO — Interface Web.

Application Streamlit pour utilisateurs non-techniques.
Un champ mot-clé, un bouton, et le contenu est généré.
Navigation : Generator | Archive | Session Detail
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# S'assurer que le projet est dans le path
sys.path.insert(0, str(Path(__file__).parent))

from hermes.core.session_manager import SessionManager
from hermes.core.workflow import (
    AGENT_ORDER,
    get_active_agents,
)
from hermes.models.common import AgentStatus as AgentStatusEnum
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.agents import AGENT_REGISTRY
from pages.archive_page import render_archive_page
from pages.session_detail_page import render_session_detail

# Configuration de la page
st.set_page_config(
    page_title="Hermes SEO",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Styles CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: 700; margin-bottom: 0; }
    .sub-header { color: #666; font-size: 1.1rem; margin-top: 0; }
    .score-card { background: #f0f2f6; border-radius: 12px; padding: 1.5rem; text-align: center; }
    .score-value { font-size: 3rem; font-weight: 700; }
    .score-green { color: #28a745; }
    .score-orange { color: #fd7e14; }
    .score-red { color: #dc3545; }
    .agent-row { padding: 0.3rem 0; border-bottom: 1px solid #eee; font-size: 0.85rem; }
    .fc-footer { text-align: center; color: #999; font-size: 0.8rem; padding: 2rem 0 1rem 0; border-top: 1px solid #eee; margin-top: 3rem; }
</style>
""", unsafe_allow_html=True)


# ─── Initialisation de session Streamlit ──────────────────────────────

if "pipeline_done" not in st.session_state:
    st.session_state.pipeline_done = False
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "content" not in st.session_state:
    st.session_state.content = None
if "scores" not in st.session_state:
    st.session_state.scores = None
if "agent_results" not in st.session_state:
    st.session_state.agent_results = {}
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Generator"
if "selected_session_id" not in st.session_state:
    st.session_state.selected_session_id = None


async def _run_pipeline(
    session: SessionState, progress_bar, status_text,
    session_manager: SessionManager | None = None,
    resume_from: str | None = None,
) -> SessionState:
    """Execute le pipeline complet avec feedback temps reel et sauvegarde apres chaque agent.

    Si resume_from est fourni, reprend depuis cet agent (les precedents sont preserves).
    """
    active = get_active_agents(
        mode=session.config.mode,
        secteur=session.config.secteur,
        user_skipped=list(session.config.user_skipped_agents),
        has_existing_content=False,
        has_locale_target=bool(session.config.target_locales),
    )

    total = len(active)
    agent_names = {
        "agent_00": "Superviseur",
        "agent_01": "Brief entreprise",
        "agent_02": "Persona",
        "agent_03": "Analyse SERP",
        "agent_04": "Intention",
        "agent_05": "Offre & Conversion",
        "agent_06": "Différenciation",
        "agent_07": "Template",
        "agent_08": "Anti-cannibalisation",
        "agent_09": "✍️ Rédaction",
        "agent_10": "SEO",
        "agent_11": "AEO",
        "agent_12": "GEO",
        "agent_13": "EEAT",
        "agent_14": "Conformité",
        "agent_15": "Fact-checking",
        "agent_16": "Maillage interne",
        "agent_17": "Maillage externe",
        "agent_18": "Multiformat",
        "agent_19": "Test A/B",
        "agent_20": "Localisation",
        "agent_21": "Schema.org",
        "agent_22": "Images",
        "agent_23": "CMS Export",
        "agent_24": "Mise à jour",
        "agent_25": "Critique Qualité",
        "agent_26": "Audit",
    }

    # Reprise : sauter les agents deja completes
    start_index = 0
    if resume_from:
        try:
            start_index = AGENT_ORDER.index(resume_from)
        except ValueError:
            pass

    for i, agent_id in enumerate(active):
        if agent_id not in AGENT_ORDER:
            continue
        agent_order_idx = AGENT_ORDER.index(agent_id)
        if agent_order_idx < start_index:
            # Agent deja execute dans une session precedente
            progress = (i + 1) / total
            progress_bar.progress(progress, text=f"{agent_names.get(agent_id, agent_id)} (deja fait)")
            continue

        name = agent_names.get(agent_id, agent_id)
        progress = (i + 1) / total
        progress_bar.progress(progress, text=f"{name}...")
        status_text.text(f"Étape {i+1}/{total} : {name}")

        if agent_id in AGENT_REGISTRY:
            try:
                session.current_agent_id = agent_id
                session = await AGENT_REGISTRY[agent_id](session)
                result = session.agent_results.get(agent_id)
                session.last_completed_agent_id = agent_id
                st.session_state.agent_results[agent_id] = (
                    result.status.value if result else "?"
                )

                # Sauvegarder apres chaque agent (resilience)
                if session_manager:
                    session_manager.save(session)

            except Exception as e:
                st.session_state.agent_results[agent_id] = f"❌ {e}"
                # Sauvegarder avant de quitter pour pouvoir reprendre
                session.error_count += 1
                session.status = "failed"
                if session_manager:
                    session_manager.save(session)
                status_text.error(f"Échec a {name}: {e}")
                return session

    session.status = "completed"
    if session_manager:
        session_manager.save(session)
    return session


def run_pipeline_sync(session, progress_bar, status_text,
                     session_manager=None, resume_from=None):
    return asyncio.run(_run_pipeline(
        session, progress_bar, status_text,
        session_manager=session_manager,
        resume_from=resume_from,
    ))


# ─── Sidebar ──────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/document.png", width=60)

    # Navigation
    st.markdown("## Navigation")
    nav = st.radio(
        "Page",
        options=["Generator", "Archive", "Session Detail"],
        label_visibility="collapsed",
        key="nav_page",
    )

    # Parametre session_id dans l'URL
    params = st.query_params
    if "session_id" in params:
        st.session_state.selected_session_id = params["session_id"]

    # Sidebar specifique a la page Generator
    if nav == "Generator":
        st.markdown("---")
        st.markdown("## ⚙️ Configuration")

        mode_labels = {
            "fast": "⚡ Rapide — Essentiel seulement",
            "standard": "⭐ Standard — Recommandé",
            "premium": "💎 Premium — Complet",
            "compliance": "🛡️ Conformité — Secteurs réglementés",
        }
        mode_choice = st.selectbox(
            "Mode qualité",
            options=list(mode_labels.keys()),
            format_func=lambda x: mode_labels[x],
            index=1,
            key="sidebar_mode",
        )

        secteur_labels = {
            "autre": "Généraliste",
            "finance": "Finance / Assurance",
            "sante": "Santé / Médical",
            "droit": "Droit / Juridique",
            "ecommerce": "E-commerce",
            "saas": "SaaS / Logiciel",
            "formation": "Formation",
            "immobilier": "Immobilier",
            "tourisme": "Tourisme",
            "rh": "RH / Recrutement",
            "cybersecurite": "Cybersécurité",
            "enfants": "Enfants / Jeunesse",
        }
        secteur = st.selectbox(
            "Secteur d'activité",
            options=list(secteur_labels.keys()),
            format_func=lambda x: secteur_labels[x],
            key="sidebar_secteur",
        )

        st.markdown("---")
        st.markdown("### 🔗 Options")
        site_url = st.text_input("URL du site (optionnel)", placeholder="https://mon-site.fr", key="sidebar_url")
        objectif = st.text_area("Objectif (optionnel)", placeholder="Ex: Générer un guide complet sur...", height=80, key="sidebar_objectif")

        st.markdown("---")
        st.markdown("### 💰 Mode")
        dry_run = st.checkbox("Mode essai (gratuit, sans API)", value=True,
                              help="En mode essai, aucun appel API réel n'est effectué. "
                                   "Idéal pour tester avant de consommer du budget.",
                              key="sidebar_dry_run")
        if not dry_run:
            st.warning("⚠️ Le mode réel consomme du budget API. Vérifiez vos clés dans .env.")

        st.markdown("---")
        st.markdown("### 📊 Session")
        if st.session_state.session_id:
            st.success(f"Session: `{st.session_state.session_id}`")
            if st.button("📋 Copier l'ID"):
                st.code(st.session_state.session_id)

        # Detection de sessions interrompues
        sess_mgr = SessionManager(Path("sessions"))
        all_sessions = sess_mgr.list_sessions()
        interrupted = [
            s for s in all_sessions
            if s.get("status") in ("failed", "running")
            and s.get("agent_count", 0) > 0
        ]
        if interrupted:
            st.markdown("---")
            st.warning(f"🔴 {len(interrupted)} session(s) interrompue(s)")
            for s in interrupted[:5]:
                last = s.get("session_id", "")[:12]
                kw = s.get("keyword", "?")
                agents = s.get("agent_count", 0)
                if st.button(
                    f"🔄 Reprendre '{kw}' ({agents} agents faits)",
                    key=f"resume_{last}",
                    use_container_width=True,
                ):
                    st.session_state.resume_session_id = last
                    st.rerun()

    else:
        # Sidebar minimale pour Archive et Session Detail
        st.markdown("---")
        if nav == "Archive":
            st.caption("Historique, stats et gestion des sessions.")
        elif nav == "Session Detail":
            st.caption("Detail d'une session.")
            if st.session_state.get("selected_session_id"):
                st.info(f"Session: `{st.session_state.selected_session_id}`")


# ─── Contenu principal ─────────────────────────────────────────────────

if nav == "Archive":
    render_archive_page()

elif nav == "Session Detail":
    sid = st.session_state.get("selected_session_id")
    if sid:
        render_session_detail(sid)
    else:
        st.info("Selectionnez une session dans l'Archive ou utilisez ?session_id=... dans l'URL.")

else:
    # ─── Page Generator (existante) ─────────────────────────────────

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<p class="main-header">Hermes SEO</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="sub-header">Usine editoriale intelligente — '
            'Contenus SEO, AEO et GEO en un clic | Par FC Solutions</p>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown("")
        st.markdown("")

    keyword = st.text_input(
        "Mot-clé",
        placeholder="Ex: assurance vie temporaire, guide comptabilité, meilleur aspirateur...",
        key="keyword_input",
    )

    col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
    with col_btn1:
        generate = st.button("🚀 Générer le contenu", type="primary", use_container_width=True)
    with col_btn2:
        if st.session_state.session_id:
            replay = st.button("🔄 Rejouer", use_container_width=True)
        else:
            replay = False
    with col_btn3:
        if st.session_state.content:
            st.download_button(
                "📥 Télécharger",
                data=st.session_state.content.get("html", ""),
                file_name=f"{keyword.replace(' ', '-') or 'article'}.html",
                mime="text/html",
                use_container_width=True,
            )

    # ─── Reprise de session interrompue ──────────────────────────────

    if st.session_state.get("resume_session_id"):
        rid = st.session_state.pop("resume_session_id")
        try:
            mgr = SessionManager(Path("sessions"))
            session = mgr.load(rid)

            # Trouver le dernier agent termine
            from hermes.core.workflow import AGENT_ORDER as AO
            last_completed = None
            for aid in AO:
                result = session.agent_results.get(aid)
                if result and str(result.status.value) in ("completed", "skipped_auto", "skipped_user"):
                    last_completed = aid
                else:
                    break

            resume_from = None
            if last_completed:
                idx = AO.index(last_completed)
                if idx + 1 < len(AO):
                    resume_from = AO[idx + 1]

            # Reconfigurer la sidebar
            st.session_state.sidebar_mode = session.config.mode.value if hasattr(session.config.mode, 'value') else str(session.config.mode)
            st.session_state.sidebar_secteur = session.config.secteur or "autre"
            st.session_state.sidebar_dry_run = session.config.dry_run
            st.session_state.sidebar_url = session.config.target_url or ""
            st.session_state.sidebar_objectif = session.objectif or ""
            st.session_state.session_id = session.session_id
            st.session_state.agent_results = {}

            progress_bar = st.progress(0, text="Reprise...")
            status_text = st.empty()
            status_text.info(
                f"Reprise depuis {resume_from or 'le debut'} "
                f"(dernier agent termine: {last_completed or 'aucun'})"
            )

            with st.spinner(""):
                start_time = datetime.now()
                session = run_pipeline_sync(
                    session, progress_bar, status_text,
                    session_manager=mgr,
                    resume_from=resume_from,
                )
                elapsed = (datetime.now() - start_time).total_seconds()

            progress_bar.progress(1.0, text="Termine !")
            status_text.success(f"Session reprise en {elapsed:.1f}s")

            st.session_state.pipeline_done = True
            st.session_state.content = {
                "html": session.brouillon_html or "",
                "title": (session.seo_data or {}).get("title_optimise", session.keyword),
                "meta": (session.seo_data or {}).get("meta_description_optimise", ""),
                "schema": (session.ld_json or {}).get("ld_json", ""),
            }
            st.session_state.scores = session.scores
            st.session_state.session = session
            st.rerun()

        except Exception as e:
            st.error(f"Impossible de reprendre la session {rid}: {e}")

    # ─── Génération ─────────────────────────────────────────────────

    if generate and keyword:
        st.session_state.pipeline_done = False
        st.session_state.session_id = None
        st.session_state.content = None
        st.session_state.scores = None
        st.session_state.agent_results = {}

        # Relire les valeurs de la sidebar
        m = st.session_state.get("sidebar_mode", "standard")
        sec = st.session_state.get("sidebar_secteur", "autre")
        dr = st.session_state.get("sidebar_dry_run", True)
        su = st.session_state.get("sidebar_url", "")
        obj = st.session_state.get("sidebar_objectif", "")

        session = SessionState(
            keyword=keyword,
            site_url=su or None,
            objectif=obj or None,
            config=SessionConfig(
                mode=QualityMode(m),
                dry_run=dr,
                secteur=sec,
                token_budget=2_000_000,
                cost_budget=10.0,
            ),
        )
        st.session_state.session_id = session.session_id

        progress_bar = st.progress(0, text="Initialisation...")
        status_text = st.empty()

        with st.spinner(""):
            start_time = datetime.now()
            mgr = SessionManager(Path("sessions"))
            session = run_pipeline_sync(
                session, progress_bar, status_text, session_manager=mgr
            )
            elapsed = (datetime.now() - start_time).total_seconds()

        progress_bar.progress(1.0, text="Terminé !")
        status_text.success(f"Contenu généré en {elapsed:.1f}s — Session: `{session.session_id}`")

        st.session_state.pipeline_done = True
        st.session_state.content = {
            "html": session.brouillon_html or "",
            "title": (session.seo_data or {}).get("title_optimise", keyword),
            "meta": (session.seo_data or {}).get("meta_description_optimise", ""),
            "schema": (session.ld_json or {}).get("ld_json", ""),
        }
        st.session_state.scores = session.scores
        st.session_state.session = session

        # Enregistrer dans la timeline
        try:
            from hermes.core.archive_service import ArchiveService
            svc = ArchiveService()
            svc.record_session_completed(session.session_id, keyword, (session.scores or {}).get("score_total"))
        except Exception:
            pass

        st.rerun()

    elif replay and st.session_state.session_id:
        manager = SessionManager(Path("sessions"))
        session = manager.load(st.session_state.session_id)
        session.config.dry_run = True
        progress_bar = st.progress(0, text="Replay...")
        status_text = st.empty()
        session = run_pipeline_sync(
            session, progress_bar, status_text,
            session_manager=SessionManager(Path("sessions")),
        )
        st.rerun()

    # ─── Résultats ──────────────────────────────────────────────────

    if st.session_state.pipeline_done and st.session_state.scores:
        st.markdown("---")
        st.markdown("## 📊 Résultats")

        scores = st.session_state.scores
        score_total = scores.get("score_total", 0)
        seuil = scores.get("seuil_publication", 75)
        seuil_ok = scores.get("seuil_atteint", False)

        cols = st.columns(4)
        with cols[0]:
            color = "score-green" if score_total >= 80 else ("score-orange" if score_total >= 65 else "score-red")
            st.markdown(
                f'<div class="score-card"><p>Score Qualité</p>'
                f'<span class="score-value {color}">{score_total}</span><span>/100</span>'
                f'<p style="color:#888;">Seuil: {seuil}</p></div>',
                unsafe_allow_html=True,
            )
        with cols[1]:
            verdict = "✅ Publiable" if seuil_ok else "❌ À corriger"
            st.markdown(
                f'<div class="score-card"><p>Décision</p>'
                f'<p style="font-size:1.5rem;font-weight:700;">{verdict}</p></div>',
                unsafe_allow_html=True,
            )
        with cols[2]:
            eeat = st.session_state.session.score_eeat or {}
            st.markdown(
                f'<div class="score-card"><p>Score EEAT</p>'
                f'<span class="score-value">{eeat.get("score_global", "?")}</span><span>/16</span></div>',
                unsafe_allow_html=True,
            )
        with cols[3]:
            fiab = st.session_state.session.fact_check_data or {}
            st.markdown(
                f'<div class="score-card"><p>Fiabilité</p>'
                f'<span class="score-value">{fiab.get("score_fiabilite", "?")}</span><span>/10</span></div>',
                unsafe_allow_html=True,
            )

        st.markdown("### Détail des 9 critères")
        grille = scores.get("scores", {})
        criteres = [
            ("Lisibilité", grille.get("lisibilite", 0), 10),
            ("Densité sémantique", grille.get("densite_semantique", 0), 15),
            ("Réponse aux PAA", grille.get("reponse_paa", 0), 20),
            ("Originalité", grille.get("originalite", 0), 15),
            ("Fraîcheur des sources", grille.get("fraicheur", 0), 10),
            ("Respect AEO", grille.get("respect_aeo", 0), 10),
            ("Respect GEO", grille.get("respect_geo", 0), 10),
            ("Absence d'erreurs", grille.get("absence_erreurs", 0), 6),
            ("Naturalité", grille.get("naturalite", 0), 4),
        ]
        for nom, valeur, max_val in criteres:
            pct = valeur / max_val if max_val else 0
            color = "green" if pct >= 0.7 else ("orange" if pct >= 0.4 else "red")
            st.markdown(
                f'<div style="display:flex;align-items:center;margin:0.3rem 0;">'
                f'<span style="width:180px;">{nom}</span>'
                f'<div style="flex:1;background:#e0e0e0;border-radius:8px;height:20px;">'
                f'<div style="width:{pct*100}%;background:{color};border-radius:8px;height:20px;"></div>'
                f'</div>'
                f'<span style="width:60px;text-align:right;">{valeur}/{max_val}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        verifications = scores.get("verifications_humaines", [])
        if verifications:
            st.markdown("### 🔍 Points à vérifier")
            for v in verifications:
                st.markdown(f"- {v}")

        blocages = scores.get("blocages", [])
        if blocages:
            st.markdown("### ⛔ Blocages")
            for b in blocages:
                st.error(b)

        st.markdown("---")
        st.markdown("### 🔄 Agents exécutés")
        results = st.session_state.agent_results
        if results:
            cols_agents = st.columns(4)
            for i, (aid, status) in enumerate(sorted(results.items())):
                icon = {"completed": "✅", "skipped_auto": "⏭️", "skipped_user": "⏭️",
                        "failed": "❌"}.get(status, "⬜")
                cols_agents[i % 4].markdown(f'<div class="agent-row">{icon} {aid}</div>',
                                            unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📄 Contenu généré")
        html_content = st.session_state.content.get("html", "")
        if html_content:
            with st.expander("Voir le contenu HTML", expanded=True):
                clean = html_content.replace("<h1>", "\n# ").replace("</h1>", "\n")
                clean = clean.replace("<h2>", "\n## ").replace("</h2>", "\n")
                clean = clean.replace("<h3>", "\n### ").replace("</h3>", "\n")
                clean = clean.replace("<p>", "\n").replace("</p>", "\n")
                clean = clean.replace("<strong>", "**").replace("</strong>", "**")
                clean = clean.replace("<li>", "- ").replace("</li>", "")
                clean = clean.replace("<ul>", "").replace("</ul>", "")
                clean = clean.replace("<ol>", "").replace("</ol>", "")
                clean = clean.replace("<blockquote>", "> ").replace("</blockquote>", "")
                st.markdown(clean[:10000])

        st.markdown("### 🔎 Métadonnées SEO")
        seo_col1, seo_col2 = st.columns(2)
        with seo_col1:
            st.markdown("**Title SEO**")
            st.code(st.session_state.content.get("title", ""))
        with seo_col2:
            st.markdown("**Meta Description**")
            st.code(st.session_state.content.get("meta", ""))

        schema = st.session_state.content.get("schema", "")
        if schema:
            with st.expander("📋 Schema.org JSON-LD"):
                st.code(schema, language="json")

        export = st.session_state.session.export_data or {}
        if export.get("fichier"):
            st.markdown(f"**Fichier d'export** : `{export.get('fichier', '')}`")
            st.markdown(f"**Format** : `{export.get('format', 'html')}`")

    elif not keyword and not st.session_state.pipeline_done:
        st.markdown("---")
        st.markdown("""
        ### 🚀 Comment ça marche ?

        1. **Entrez un mot-clé** — le sujet que vous voulez traiter
        2. **Choisissez votre secteur** — pour adapter le contenu au contexte légal
        3. **Cliquez sur Générer** — 26 agents spécialisés travaillent pour vous

        ### ✨ Ce que vous obtenez

        - Un **article complet** optimisé SEO, AEO et GEO
        - Une **grille de qualité** sur 100 points
        - Les **métadonnées** (title, meta description)
        - Le **balisage Schema.org** pour les rich snippets
        - Un **plan de mise à jour** pour garder le contenu frais

        ### 🔒 Mode essai gratuit

        Par défaut, vous êtes en **mode essai** — tout fonctionne sans appel API.
        Quand vous êtes prêt, décochez le mode essai et configurez vos clés API dans `.env`.
        """)


# ─── Footer ─────────────────────────────────────────────────────────

st.markdown(
    '<div class="fc-footer">© 2026 FC Solutions — Hermes SEO v3. Tous droits reserves.</div>',
    unsafe_allow_html=True,
)
