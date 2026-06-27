"""Systeme de disclaimers — integration UI Streamlit.

Affiche les disclaimers contextuels, gere l'acceptation, bloque
les actions si les disclaimers obligatoires ne sont pas acceptes.

8 types de disclaimers (voir hermes/models/project.py).
"""

import streamlit as st
from datetime import datetime

DISCLAIMER_TEXTS = {
    "performance": {
        "icon": "📊",
        "title": "Projections de performance",
        "text": "Les estimations de trafic, positions et ROI sont des projections "
                "statistiques basees sur des moyennes sectorielles. Aucune garantie de resultat. "
                "Les performances reelles dependent de centaines de facteurs.",
    },
    "delais": {
        "icon": "⏱️",
        "title": "Delais de resultat",
        "text": "Les delais indiques sont des estimations. Le referencement est un processus "
                "progressif. Google peut prendre plusieurs semaines a indexer un nouveau contenu.",
    },
    "donnees": {
        "icon": "📡",
        "title": "Sources des donnees",
        "text": "Les donnees de volume, positions et backlinks proviennent d'APIs tierces "
                "(GSC, DataForSEO). Leur exactitude depend de ces fournisseurs.",
    },
    "ia_generated": {
        "icon": "🤖",
        "title": "Contenu genere par IA",
        "text": "Certaines analyses et recommandations sont generees par des modeles d'IA "
                "(Claude, GPT). Elles doivent etre validees par un humain avant toute action.",
    },
    "ymyl": {
        "icon": "⚠️",
        "title": "Contenu sensible (YMYL)",
        "text": "Les contenus relatifs a la sante, la finance, le droit ou tout sujet "
                "reglemente necessitent une relecture par un expert qualifie.",
    },
    "concurrence": {
        "icon": "🔍",
        "title": "Analyses concurrentielles",
        "text": "Les analyses concurrentielles sont basees sur les donnees publiquement "
                "disponibles. Les strategies internes des concurrents ne sont pas accessibles.",
    },
    "budget": {
        "icon": "💰",
        "title": "Estimations budgetaires",
        "text": "Les couts estimes sont indicatifs. Les couts reels varient selon les "
                "prestataires, la complexite et la disponibilite des ressources.",
    },
    "non_substitution": {
        "icon": "📋",
        "title": "Outil d'aide a la decision",
        "text": "Hermes SEO est un outil d'aide a la decision. Il ne remplace pas un "
                "consultant SEO professionnel. Les decisions prises sur la seule base de ces "
                "recommandations relevent de votre responsabilite.",
    },
}


def init_disclaimers():
    """Initialise les disclaimers dans st.session_state."""
    if "disclaimers_accepted" not in st.session_state:
        st.session_state.disclaimers_accepted = {}


def show_disclaimer(disclaimer_type: str) -> bool:
    """Affiche un disclaimer et retourne True si accepte."""
    init_disclaimers()

    if st.session_state.disclaimers_accepted.get(disclaimer_type):
        return True

    info = DISCLAIMER_TEXTS.get(disclaimer_type, {})
    icon = info.get("icon", "ℹ️")
    title = info.get("title", disclaimer_type)
    text = info.get("text", "")

    with st.expander(f"{icon} {title} — Lire avant de continuer", expanded=True):
        st.markdown(text)
        if st.button(f"✅ Compris — Continuer", key=f"accept_{disclaimer_type}"):
            st.session_state.disclaimers_accepted[disclaimer_type] = True
            st.rerun()
        return False
    return False


def show_required_disclaimers(action_type: str, is_ymyl: bool = False) -> bool:
    """Affiche tous les disclaimers requis pour une action. Retourne True si tous acceptes."""
    init_disclaimers()

    required = ["non_substitution"]

    if action_type in ("generate", "article"):
        required.append("ia_generated")
    if action_type in ("publish", "optimize"):
        required.append("performance")
    if action_type in ("audit", "backlinks") or "analyse" in action_type:
        required.append("donnees")
    if is_ymyl:
        required.append("ymyl")

    all_ok = True
    for dt in required:
        if not show_disclaimer(dt):
            all_ok = False
    return all_ok


def get_disclaimer_footer() -> str:
    """Retourne le HTML du bandeau disclaimer permanent."""
    return '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px 15px;margin:15px 0;font-size:12px;color:#64748b">⚖️ Hermes SEO est un outil d\'aide a la decision. Les projections sont des estimations, pas des garanties.</div>'
