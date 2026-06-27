"""Hermes SEO — Interface Web.

Application Streamlit pour utilisateurs non-techniques.
Un champ mot-clé, un bouton, et le contenu est généré.
Navigation : Generator | Archive | Audit | Session Detail
"""

import asyncio
import re
import sys
from datetime import datetime
from collections import Counter
from urllib.parse import urlparse

import httpx
import streamlit as st
from pathlib import Path

# S'assurer que le projet est dans le path
sys.path.insert(0, str(Path(__file__).parent))

from hermes.core.guard import (
    sanitize_input,
    validate_keyword,
    validate_objectif,
    validate_url,
)
from hermes.core.session_manager import SessionManager
from hermes.core.workflow import (
    AGENT_ORDER,
    get_active_agents,
)
from hermes.models.common import AgentStatus as AgentStatusEnum
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.core.pipeline_guard import (
    build_error_summary,
    get_failure_severity,
    get_upstream_failures,
)
from hermes.agents import AGENT_REGISTRY
from pages.archive_page import render_archive_page
from pages.audit_page import render_audit_page
from pages.audit_tech_page import render_audit_tech_page
from pages.serp_visibility_page import render_serp_visibility_page
from pages.strategie_page import render_strategie_page
from pages.backlinks_page import render_backlinks_page
from pages.maintenance_page import render_maintenance_page
from pages.learning_page import render_learning_page
from pages.free_tools_page import render_free_tools_page
from pages.project_dashboard import render_project_dashboard
from pages.admin_dashboard import render_admin_dashboard
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
    /* Hermes SEO — Design System v3 */
    :root { --blue: #1E88E5; --green: #28a745; --orange: #fd7e14; --red: #dc3545;
            --gray-50: #f8fafc; --gray-100: #f1f5f9; --gray-200: #e2e8f0; --gray-600: #64748b; --gray-800: #1e293b; }
    .main-header { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.2rem; letter-spacing: -0.02em; }
    .sub-header { color: var(--gray-600); font-size: 1.05rem; margin-top: 0; }
    .score-card { background: #fff; border: 1px solid var(--gray-200); border-radius: 12px; padding: 1.25rem; text-align: center; transition: box-shadow .2s; }
    .score-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,.06); }
    .score-value { font-size: 2.2rem; font-weight: 700; }
    .score-green { color: var(--green); } .score-orange { color: var(--orange); } .score-red { color: var(--red); }
    .agent-row { padding: 0.3rem 0; border-bottom: 1px solid #f1f5f9; font-size: 0.85rem; }
    .pill { display:inline-block; padding:2px 10px; border-radius:20px; font-size:11px; font-weight:600; letter-spacing:.02em; }
    .pill-free { background:#e8f5e9; color:#2e7d32; }
    .pill-pro { background:#e3f2fd; color:#1565c0; }
    .pill-beta { background:#f3e5f5; color:#6a1b9a; }
    .pill-upgrade { background:linear-gradient(135deg,#1E88E5,#42a5f5); color:#fff;cursor:pointer; }
    .divider { border-top:1px solid var(--gray-200); margin:0.8rem 0; }
    .sidebar-project { background:linear-gradient(135deg,#f8fafc,#f1f5f9); border-radius:10px; padding:12px; margin-bottom:12px; border:1px solid var(--gray-200); }
    .sidebar-welcome { background:linear-gradient(135deg,#e8f5e9,#e3f2fd); border-radius:10px; padding:16px; margin-bottom:12px; text-align:center; }
    .fc-footer { text-align: center; color: #999; font-size: 0.8rem; padding: 1.5rem 0 0.5rem 0; border-top: 1px solid #eee; margin-top: 2rem; }
    .empty-state { text-align:center; padding:3rem 1rem; color:var(--gray-600); }
    .empty-state-icon { font-size:3rem; margin-bottom:1rem; }
    .upgrade-banner { background:linear-gradient(135deg,#1E88E5,#1565c0); color:#fff; border-radius:10px; padding:1rem 1.2rem; margin:1rem 0; font-size:0.9rem; }
    .upgrade-banner a { color:#fff; font-weight:700; text-decoration:underline; }
    .nav-section-title { font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em; color:var(--gray-600); margin:1rem 0 0.3rem 0; padding-left:4px; font-weight:700; }
    @media (max-width:768px) { .score-value { font-size:1.5rem; } }
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
    st.session_state.nav_page = "📝 Generateur"
if "selected_session_id" not in st.session_state:
    st.session_state.selected_session_id = None
if "pipeline_error" not in st.session_state:
    st.session_state.pipeline_error = None

# ─── Projet Global Partagé (tous les pipelines) ────────────────────────
if "project_url" not in st.session_state:
    st.session_state.project_url = ""
if "project_keywords" not in st.session_state:
    st.session_state.project_keywords = []
if "project_competitors" not in st.session_state:
    st.session_state.project_competitors = []
if "project_profile" not in st.session_state:
    st.session_state.project_profile = "blog"
if "project_domain" not in st.session_state:
    st.session_state.project_domain = ""
if "project_autodetected" not in st.session_state:
    st.session_state.project_autodetected = False


# ─── Auto-detection du site ──────────────────────────────────────────

def _auto_detect_site(url: str, domain: str) -> tuple[list[str], list[str], str]:
    """Crawl la page d'accueil pour extraire mots-cles, concurrents et profil."""
    keywords = []
    competitors = []
    profile = "blog"

    try:
        resp = httpx.get(url.strip("/"), timeout=8.0, follow_redirects=True)
        if resp.status_code != 200:
            return keywords, competitors, profile

        html = resp.text[:80000]

        # Extraire title, meta, H1
        title_m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        title = title_m.group(1) if title_m else ""
        desc_m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html, re.IGNORECASE)
        desc = desc_m.group(1) if desc_m else ""
        headers = re.findall(r"<h[12][^>]*>([^<]+)</h[12]>", html, re.IGNORECASE)

        # Nettoyer HTML → texte visible
        html_clean = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r"<style[^>]*>.*?</style>", " ", html_clean, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r"\{[^}]*\}", " ", html_clean)
        html_clean = re.sub(r"<[^>]+>", " ", html_clean)
        html_clean = re.sub(r"[^a-zA-ZÀ-ÿ\s]", " ", html_clean)
        html_clean = re.sub(r"\s+", " ", html_clean).lower()

        combined = f"{title} {desc} {' '.join(headers[:5])} {html_clean[:3000]}"

        # Stopwords
        stopwords = {"le","la","les","des","une","est","sont","avec","pour","sur","dans","par",
                      "qui","que","pas","plus","tout","aux","nos","vous","votre","vos","nous","notre",
                      "leur","leurs","cette","entre","bien","tres","fait","faire","etre","avoir","aussi",
                      "peut","site","cookies","fermer","savoir","suivre","ainsi","travail","necessaire",
                      "navigation","choix","formulaire","interlocuteur","menu","mobile","header","main",
                      "body","style","https","www","com","html","content","slide","opened","closed",
                      "before","important","dipi","animation","background","fullscreen","collapse","submenu"}

        words = re.findall(r"[a-zà-ÿ]{4,}", combined)
        word_freq = Counter(w for w in words if w not in stopwords)
        top_words = [w for w, _ in word_freq.most_common(15)]

        # Bigrammes
        clean_words = [w for w in words if w not in stopwords]
        bigrams = []
        for i in range(len(clean_words) - 1):
            bg = f"{clean_words[i]} {clean_words[i + 1]}"
            if len(bg) >= 8:
                bigrams.append(bg)
        top_bigrams = list(set(bigrams))[:10]

        for w in top_words[:8]:
            keywords.append(w)
        for bg in top_bigrams[:4]:
            keywords.append(bg)

        # Geo detection
        cities = list(set(re.findall(r"(?:a|sur|dans|pres de)\s+([A-ZÀ-Ü][a-zà-ü]+)",
                                      f"{title} {desc} {' '.join(headers[:3])}")))[:3]
        for city in cities:
            for w in top_words[:3]:
                keywords.append(f"{w} {city.lower()}")

        domain_root = domain.split(".")[0][:25]
        for w in top_words[:3]:
            keywords.append(f"{w} {domain_root}")

        keywords = list(set(k.strip() for k in keywords if len(k.strip()) >= 4))[:20]

        # Profil + concurrents
        geo_lower = combined.lower()
        if any(w in geo_lower for w in ["nettoyage","plombier","electricien","coiffeur","boulanger",
                                         "restaurant","artisan","chantier","entretien","bureaux",
                                         "commerces","vitres","locaux","professionnel","particulier"]):
            profile = "local"
            competitors = ["pagesjaunes.fr", "solutions-proprete.fr"]
        elif any(w in geo_lower for w in ["boutique","shop","produit","achat","panier","ecommerce"]):
            profile = "ecommerce"
            competitors = ["amazon.fr"]
        elif any(w in geo_lower for w in ["logiciel","saas","api","demo","app","software"]):
            profile = "saas"
            competitors = ["capterra.com"]

        keywords = [k for k in keywords if len(k) >= 4 and not all(w in stopwords for w in k.split())][:20]

    except Exception:
        pass

    return keywords, competitors, profile


async def _run_pipeline(
    session: SessionState, progress_bar, status_text,
    session_manager: SessionManager | None = None,
    resume_from: str | None = None,
) -> tuple[SessionState, dict | None]:
    """Execute le pipeline complet avec feedback temps reel et sauvegarde apres chaque agent.

    Si resume_from est fourni, reprend depuis cet agent (les precedents sont preserves).

    Returns (session, error_summary).
    error_summary est None si tout s'est bien passe.
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

    critical_failures = []
    for i, agent_id in enumerate(active):
        if agent_id not in AGENT_ORDER:
            continue
        agent_order_idx = AGENT_ORDER.index(agent_id)
        if agent_order_idx < start_index:
            progress = (i + 1) / total
            progress_bar.progress(progress, text=f"{agent_names.get(agent_id, agent_id)} (deja fait)")
            continue

        name = agent_names.get(agent_id, agent_id)
        progress = (i + 1) / total
        progress_bar.progress(progress, text=f"{name}...")
        status_text.text(f"Étape {i+1}/{total} : {name}")

        if agent_id in AGENT_REGISTRY:
            try:
                # Verification des donnees d'entree pour les agents qui en dependent
                upstream = get_upstream_failures(agent_id, session.agent_results)
                if upstream:
                    severity = get_failure_severity(agent_id)
                    if severity == "critical":
                        status_text.warning(
                            f"⚠️ {name} non execute — "
                            f"donnees manquantes: {', '.join(upstream)}"
                        )
                        st.session_state.agent_results[agent_id] = (
                            f"⏭️ Donnees manquantes: {', '.join(upstream)}"
                        )
                        # Marquer comme skipped pour le resume
                        session.agent_results[agent_id] = AgentResult(
                            agent_id=agent_id,
                            agent_name=name,
                            status=AgentStatus.SKIPPED_AUTO,
                            skip_reason=f"Donnees manquantes: {', '.join(upstream)}",
                        )
                        if session_manager:
                            session_manager.save(session)
                        continue
                    else:
                        status_text.warning(
                            f"⚠️ {name}: donnees amont degradees, tentative quand meme..."
                        )

                session.current_agent_id = agent_id
                session = await AGENT_REGISTRY[agent_id](session)
                result = session.agent_results.get(agent_id)
                session.last_completed_agent_id = agent_id

                # Verifier si l'agent a echoue (status failed)
                agent_status = result.status if result else None
                status_val = (
                    agent_status.value if hasattr(agent_status, 'value')
                    else str(agent_status) if agent_status else "?"
                )

                if status_val == "failed":
                    severity = get_failure_severity(agent_id)
                    if severity == "critical":
                        critical_failures.append(agent_id)
                        st.session_state.agent_results[agent_id] = "❌ Critique"
                        session.error_count += 1
                        session.status = "blocked"
                        if session_manager:
                            session_manager.save(session)
                        status_text.error(
                            f"⛔ {name} : echec critique. "
                            f"Le pipeline s'arrete pour eviter un resultat degrade."
                        )
                        break
                    else:
                        st.session_state.agent_results[agent_id] = (
                            f"⚠️ Degrade: {result.error_message or 'Erreur inconnue'}"
                        )
                else:
                    st.session_state.agent_results[agent_id] = (
                        result.status.value if result else "?"
                    )

                # Sauvegarder apres chaque agent
                if session_manager:
                    session_manager.save(session)

            except Exception as e:
                severity = get_failure_severity(agent_id)
                st.session_state.agent_results[agent_id] = f"❌ {e}"
                session.error_count += 1
                session.status = "failed"
                if session_manager:
                    session_manager.save(session)

                if severity == "critical":
                    status_text.error(
                        f"⛔ {name} : erreur critique — "
                        f"pipeline arrete pour eviter un resultat degrade."
                    )
                    break
                else:
                    status_text.warning(
                        f"⚠️ {name} : erreur non-critique, le pipeline continue."
                    )

    if critical_failures:
        session.status = "blocked"
        if session_manager:
            session_manager.save(session)
        return session, build_error_summary(session)

    session.status = "completed"
    if session_manager:
        session_manager.save(session)
    return session, None


def run_pipeline_sync(session, progress_bar, status_text,
                     session_manager=None, resume_from=None):
    return asyncio.run(_run_pipeline(
        session, progress_bar, status_text,
        session_manager=session_manager,
        resume_from=resume_from,
    ))


# ─── Composant Erreur Pipeline ────────────────────────────────────────

def _render_pipeline_error(error_summary: dict) -> None:
    """Affiche une page d'erreur claire quand le pipeline s'arrete.

    Montre ce qui a reussi, ce qui a echoue, et propose de reprendre.
    """
    st.markdown("---")
    st.markdown("## Pipeline Interrompu")

    critical = error_summary.get("critical_failed", [])
    succeeded = error_summary.get("succeeded", [])
    not_run = error_summary.get("not_run", [])
    last_ok = error_summary.get("last_successful", "")

    st.warning(
        "Le pipeline s'est arrete automatiquement pour eviter "
        "de produire un contenu de qualite insuffisante. "
        "Les donnees deja analysees sont preservees."
    )

    # Resume
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.metric("Agents reussis", len(succeeded))
    with c2:
        st.metric("Echecs critiques", len(critical))
    with c3:
        st.metric("Non executes", len(not_run))

    names = {
        "agent_01": "Brief Entreprise",
        "agent_02": "Persona",
        "agent_03": "Analyse SERP",
        "agent_04": "Intention",
        "agent_05": "Offre & Conversion",
        "agent_06": "Differenciation",
        "agent_07": "Template",
        "agent_08": "Anti-cannibalisation",
        "agent_09": "Redaction",
        "agent_10": "SEO",
        "agent_11": "AEO",
        "agent_12": "GEO",
        "agent_13": "EEAT",
        "agent_14": "Conformite",
        "agent_15": "Fact-checking",
        "agent_16": "Maillage interne",
        "agent_17": "Maillage externe",
        "agent_18": "Multiformat",
        "agent_19": "Test A/B",
        "agent_20": "Localisation",
        "agent_21": "Schema.org",
        "agent_22": "Images",
        "agent_23": "CMS Export",
        "agent_24": "Mise a jour",
        "agent_25": "Critique Qualite",
        "agent_26": "Audit",
    }

    # Detaille
    st.markdown("---")
    st.markdown("### Ce qui a fonctionne")
    if succeeded:
        for aid in succeeded:
            nm = names.get(aid, aid)
            st.markdown(f"✅ {nm}")
    else:
        st.caption("Aucun agent n'a abouti.")

    st.markdown("---")
    st.markdown("### Ce qui a echoue")
    for aid in critical:
        nm = names.get(aid, aid)
        st.error(f"⛔ {nm} — Cet agent est critique pour la qualite du contenu.")

    if not_run:
        st.markdown("### En attente")
        for aid in not_run[:10]:
            nm = names.get(aid, aid)
            st.markdown(f"⏭️ {nm}")

    # Actions
    st.markdown("---")
    resume_from = error_summary.get("resume_from", "")
    session_id = st.session_state.get("session_id", "")

    ac1, ac2 = st.columns(2)
    with ac1:
        if resume_from and session_id:
            if st.button("🔄 Reprendre le pipeline", type="primary", use_container_width=True):
                st.session_state.resume_session_id = session_id
                st.rerun()
        else:
            st.info(
                "La reprise automatique n'est pas disponible. "
                "Relancez le pipeline avec un nouveau mot-cle."
            )
    with ac2:
        if session_id:
            if st.button("📋 Voir le detail de session", use_container_width=True):
                st.session_state.nav_page = "Session Detail"
                st.session_state.selected_session_id = session_id
                st.rerun()


# ─── Sidebar ──────────────────────────────────────────────────────────

with st.sidebar:
    # ─── LOGO ─────────────────────────────────────────────────────────
    st.markdown('<div style="display:flex;align-items:center;gap:10px;margin-bottom:1rem"><div style="background:linear-gradient(135deg,#1E88E5,#42a5f5);width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px">H</div><span style="font-weight:700;font-size:1.1rem">Hermes SEO</span></div>', unsafe_allow_html=True)

    deploy_mode = "local"  # TODO: read from config._cfg
    domain_display = (st.session_state.get("project_domain", "") or
                     st.session_state.get("project_url", "").replace("https://", "").replace("www.", "").rstrip("/"))
    has_project = bool(st.session_state.get("project_url", "").startswith("http"))

    if has_project:
        # ─── PROJET ACTIF ────────────────────────────────────────────────
        st.markdown(f"""<div class="sidebar-project">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
          <div style="width:8px;height:8px;background:#28a745;border-radius:50%"></div>
          <strong style="font-size:0.95rem">{domain_display or 'Mon Projet'}</strong>
        </div>
        <div style="font-size:0.75rem;color:#64748b">{st.session_state.get('project_profile','blog')} · {st.session_state.get('project_mode','standard')}</div>
        </div>""", unsafe_allow_html=True)

        # ─── NAVIGATION unifiee ───────────────────────────────────────────
        nav = st.radio("Navigation", [
            "🏠 Mon Site",
            "🔍 SERP & Visibilite",
            "🧠 Strategie",
            "📝 Generateur",
            "🔗 Backlinks",
            "🛠️ Audit Technique",
            "📄 Audit Contenu",
            "🔧 Maintenance",
            "📚 Learning",
            "📦 Archive",
            "🧰 Outils SEO",
            "⚙️ Admin",
        ], label_visibility="collapsed", key="nav_page")

        # Blog link (external)
        st.markdown(f'<a href="https://hermes-seo.fr/blog" target="_blank" style="color:#64748b;text-decoration:none;font-size:0.85rem;display:block;padding:4px 8px;margin-top:0.5rem">📰 Blog SEO ↗</a>', unsafe_allow_html=True)

        # Upgrade banner (if on free tier)
        if deploy_mode == "saas":
            st.markdown('<div class="upgrade-banner"><strong>Essai gratuit</strong> · 7 jours restants<br><a href="/pricing">Passer a Pro →</a></div>', unsafe_allow_html=True)

    else:
        # ─── PAS DE PROJET — Welcome Screen ──────────────────────────────
        st.markdown("""<div class="sidebar-welcome">
        <div style="font-size:2rem;margin-bottom:0.5rem">🚀</div>
        <strong style="font-size:1rem">Bienvenue</strong>
        <p style="font-size:0.8rem;color:#64748b;margin:0.5rem 0">Analysez et optimisez votre site en quelques clics.</p>
        </div>""", unsafe_allow_html=True)

        new_url = st.text_input("URL de votre site", placeholder="https://www.mon-site.fr", key="sidebar_new_project", label_visibility="collapsed")
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("✨ Creer mon projet", type="primary", use_container_width=True, disabled=not new_url.startswith("http")):
                st.session_state.project_url = new_url.strip().rstrip("/")
                from urllib.parse import urlparse
                st.session_state.project_domain = urlparse(st.session_state.project_url).netloc.replace("www.", "")
                st.session_state.project_autodetected = False
                st.rerun()
        with c2:
            if st.button("🎥 Demo", use_container_width=True):
                st.session_state.project_url = "https://www.cleantout37.fr"
                st.session_state.project_domain = "cleantout37.fr"
                st.session_state.project_profile = "local"
                st.session_state.project_autodetected = False
                st.rerun()

        st.markdown('<br>', unsafe_allow_html=True)
        nav = st.radio("Navigation", [
            "🧰 Outils SEO",
            "📦 Archive",
            "⚙️ Admin",
        ], label_visibility="collapsed", key="nav_page")
        st.markdown(f'<a href="https://hermes-seo.fr/blog" target="_blank" style="color:#1E88E5;text-decoration:none;font-size:0.9rem;display:block;padding:6px 8px">📰 Blog SEO ↗</a>', unsafe_allow_html=True)

    # ─── FOOTER ──────────────────────────────────────────────────────────
    st.caption("Hermes SEO v3 · FC Solutions")


# ─── Contenu principal ─────────────────────────────────────────────────

from_url = st.session_state.pop("from_url", False)
if from_url:
    sid = st.session_state.get("selected_session_id")
    if sid:
        render_session_detail(sid)
    else:
        st.info("Session introuvable.")

# ─── Diagnostic Complet (One-Click) ────────────────────────────────────
elif st.session_state.pop("launch_full_audit", False):
    import asyncio as _asyncio

    async def _launch():
        from hermes.models.serp_visibility import SerpVisibilityState
        from hermes.models.strategie import StrategieState
        from hermes.models.backlinks import BacklinksState
        from hermes.models.project import Project
        from hermes.core.project_db import create_project, get_project, init_db

        url = st.session_state.project_url
        domain = st.session_state.project_domain
        kw = st.session_state.project_keywords
        comp = st.session_state.project_competitors
        profile = st.session_state.project_profile
        mode = st.session_state.get("project_mode", "standard")

        from hermes.agents.serp_visibility import SERP_ORDER, SERP_REGISTRY
        p4 = SerpVisibilityState(site_url=url, keywords=kw, competitors=comp, mode=mode)
        for aid in SERP_ORDER:
            if aid in SERP_REGISTRY: p4 = await SERP_REGISTRY[aid](p4)
        st.session_state.sv_result = {"health": p4.health_score, "state": p4}

        from hermes.agents.strategie import STRATEGIE_ORDER, STRATEGIE_REGISTRY
        p5 = StrategieState(site_url=url, domain=domain, mode=mode, profile=profile, keywords_monitored=kw, competitors=comp)
        for aid in STRATEGIE_ORDER:
            if aid in STRATEGIE_REGISTRY: p5 = await STRATEGIE_REGISTRY[aid](p5)
        st.session_state.st_result = {"state": p5}

        from hermes.agents.backlinks import BACKLINKS_ORDER, BACKLINKS_REGISTRY
        p6 = BacklinksState(site_url=url, domain=domain, mode=mode, profile=profile, competitors=comp, keywords_cibles=kw[:8] if kw else [])
        for aid in BACKLINKS_ORDER:
            if aid in BACKLINKS_REGISTRY: p6 = await BACKLINKS_REGISTRY[aid](p6)
        st.session_state.bl_result = {"state": p6}

        init_db()
        existing = get_project(domain=domain)
        pid = existing["id"] if existing else create_project({"nom": domain, "site_url": url, "domain": domain, "profile": profile, "secteur": "autre", "competitors": comp, "keywords_cibles": kw})
        project = Project(id=pid, nom=domain, site_url=url, domain=domain, profile=profile, secteur="autre", mode_execution="semi-auto")
        from hermes.agents.maintenance import MAINTENANCE_ORDER, MAINTENANCE_REGISTRY
        for aid in MAINTENANCE_ORDER:
            if aid in MAINTENANCE_REGISTRY: project = await MAINTENANCE_REGISTRY[aid](project)

    with st.spinner("Diagnostic complet en cours... (4 pipelines, ~2 min)"):
        _asyncio.run(_launch())
    st.success("Diagnostic complet termine !")
    st.balloons()
    st.rerun()

elif nav == "🏠 Mon Site":
    render_project_dashboard()
elif nav == "📦 Archive":
    render_archive_page()
elif nav == "📄 Audit Contenu":
    render_audit_page()
elif nav == "🛠️ Audit Technique":
    render_audit_tech_page()
elif nav == "🔍 SERP & Visibilite":
    render_serp_visibility_page()
elif nav == "🧠 Strategie":
    render_strategie_page()
elif nav == "🔗 Backlinks":
    render_backlinks_page()
elif nav == "🧰 Outils SEO":
    render_free_tools_page()
elif nav == "🔧 Maintenance":
    render_maintenance_page()
elif nav == "📚 Learning":
    render_learning_page()
elif nav == "📝 Generateur":
    pass  # Fall through to generator block below
elif nav == "⚙️ Admin":
    render_admin_dashboard()
elif nav == "Session Detail":
    sid = st.session_state.get("selected_session_id")
    if sid:
        render_session_detail(sid)
    else:
        st.info("Selectionnez une session dans l'Archive ou utilisez ?session_id=... dans l'URL.")

else:
    # ─── Page Generator (existante) ─────────────────────────────────

    # ─── Mode Reecriture (depuis Audit) ──────────────────────────
    rewrite_brief = st.session_state.pop("rewrite_brief", None)
    rewrite_url = st.session_state.pop("rewrite_url", None)
    if rewrite_brief:
        st.success(f"Mode Reecriture active depuis l'audit")
        st.info(f"Page source : {rewrite_url} | Score actuel : {rewrite_brief.get('scores', {}).get('global', '?')}/100")
        with st.expander("Voir les recommandations d'audit"):
            for r in rewrite_brief.get("recommandations", [])[:5]:
                st.markdown(f"- **{r.get('action', '?')}** : {r.get('description', '?')} (impact: +{r.get('impact', {}).get('global', 0)} pts)")
        # Pre-remplir l'objectif avec les recommandations
        audit_objectif = "; ".join(r.get("description", "") for r in rewrite_brief.get("recommandations", [])[:3])
        if audit_objectif:
            st.session_state.sidebar_objectif = audit_objectif

    keyword_default = rewrite_brief.get("current_content", "")[:80] if rewrite_brief else ""

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
        value=keyword_default if keyword_default else "",
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
                session, _ = run_pipeline_sync(
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
        # Guardrails — validation securite
        kw_clean = sanitize_input(keyword)
        kw_check = validate_keyword(kw_clean)
        if not kw_check.passed:
            st.error(f"Mot-cle refuse : {kw_check.reason}")
            st.stop()

        obj_clean = sanitize_input(
            st.session_state.get("sidebar_objectif", ""),
            max_length=500,
        )
        obj_check = validate_objectif(obj_clean)
        if not obj_check.passed:
            st.error(f"Objectif refuse : {obj_check.reason}")
            st.stop()

        url_clean = sanitize_input(
            st.session_state.get("sidebar_url", ""),
        )
        url_check = validate_url(url_clean)
        if not url_check.passed:
            st.error(f"URL refusee : {url_check.reason}")
            st.stop()

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

        # Si on est en mode reecriture, injecter l'audit_brief comme contrainte
        import json as _json
        contraintes = []
        if rewrite_brief:
            contraintes.append(_json.dumps(rewrite_brief, ensure_ascii=False))
            if rewrite_brief.get("page_url") and not url_clean:
                url_clean = rewrite_brief["page_url"]

        session = SessionState(
            keyword=kw_clean,
            site_url=url_clean or None,
            objectif=obj_clean or None,
            contraintes=contraintes,
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
            session, error_summary = run_pipeline_sync(
                session, progress_bar, status_text, session_manager=mgr
            )
            elapsed = (datetime.now() - start_time).total_seconds()

        progress_bar.progress(1.0, text="Terminé !")

        if error_summary:
            status_text.warning(
                f"Pipeline partiellement termine en {elapsed:.1f}s — "
                f"Session: `{session.session_id}`"
            )
        else:
            status_text.success(
                f"Contenu genere en {elapsed:.1f}s — Session: `{session.session_id}`"
            )

        st.session_state.pipeline_done = True
        st.session_state.pipeline_error = error_summary
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
        session, error_summary = run_pipeline_sync(
            session, progress_bar, status_text,
            session_manager=SessionManager(Path("sessions")),
        )
        st.session_state.pipeline_error = error_summary
        st.rerun()

    # ─── Résultats ──────────────────────────────────────────────────

    error_summary = st.session_state.get("pipeline_error")

    if st.session_state.pipeline_done and error_summary:
        # ─── Pipeline arrete avec erreurs ──────────────────────────
        _render_pipeline_error(error_summary)

    elif st.session_state.pipeline_done and st.session_state.scores:
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
            st.html(html_content)
            st.download_button(
                "📥 Telecharger l'article HTML",
                data=(
                    f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
                    f'<title>{st.session_state.content.get("title", "Article")}</title>'
                    f'<meta name="description" content="{st.session_state.content.get("meta", "")}">'
                    f'</head><body>{html_content}</body></html>'
                ),
                file_name=f"{keyword.replace(' ', '-') or 'article'}.html",
                mime="text/html",
                use_container_width=True,
            )

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
