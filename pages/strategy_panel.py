"""Panneau Strategie — Donnees SERP, intention, persona, differenciation.

Affiche les insights sur lesquels la strategie editoriale se construit.
"""

from datetime import datetime
from typing import Any, Optional

import streamlit as st


def _badge(label: str, value: str, color: str = "blue") -> str:
    return f'<span style="background:{color};color:white;padding:2px 10px;border-radius:10px;font-size:0.85rem;margin-right:6px;">{label}</span>'


def render_strategy_panel(session_data: dict[str, Any]) -> None:
    """Affiche les insights strategiques d'une session.

    Args:
        session_data: dict brut du fichier session JSON (pas le modele SessionDetail).
    """
    st.markdown("---")
    st.markdown("## Stratégie Editoriale")

    tabs = st.tabs([
        "Analyse Concurrentielle",
        "Intention & Persona",
        "Offre & Conversion",
        "Différenciation",
    ])

    with tabs[0]:
        _render_serp_tab(session_data)
    with tabs[1]:
        _render_intent_persona_tab(session_data)
    with tabs[2]:
        _render_offre_tab(session_data)
    with tabs[3]:
        _render_diff_tab(session_data)


# ─── SERP ────────────────────────────────────────────────────────────────

def _render_serp_tab(session_data: dict) -> None:
    """Onglet analyse SERP et paysage concurrentiel."""
    serp = session_data.get("serp_data") or {}
    keyword = session_data.get("keyword", "")
    intention = session_data.get("intention", "?")
    type_page = session_data.get("type_page", "?")

    # Header
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.caption("Mot-cle")
        st.markdown(f"**{keyword}**")
    with col2:
        st.metric("Intention", intention or "?")
    with col3:
        st.metric("Type de page", type_page or "?")
    with col4:
        top10_count = len(serp.get("top10", []) or [])
        st.metric("Concurrents analyses", top10_count if top10_count else "N/A")

    # Volume et difficulte
    vol = serp.get("search_volume")
    diff = serp.get("keyword_difficulty")
    if vol or diff:
        vcol1, vcol2 = st.columns(2)
        with vcol1:
            if vol:
                st.metric("Volume mensuel", f"{vol:,}")
        with vcol2:
            if diff:
                st.metric("Difficulte", f"{diff}/100")

    # Top 10 concurrents
    top10 = serp.get("top10") or []
    if top10:
        st.markdown("### Top 10 — Classement Google")

        table_data = []
        for r in top10[:10]:
            domain = r.get("domain", "")
            features = []
            if r.get("has_featured_snippet"):
                features.append("Featured")
            if r.get("has_paa"):
                features.append("PAA")
            if r.get("has_ai_overview"):
                features.append("AI Overview")
            table_data.append({
                "Pos.": r.get("position", "?"),
                "Titre": r.get("title", "")[:80],
                "Domaine": domain[:30],
                "Mots": r.get("word_count") or "?",
                "H2": r.get("h2_count") or "?",
                "Rich": ", ".join(features) if features else "-",
            })

        st.dataframe(
            table_data,
            use_container_width=True,
            height=320,
            column_config={
                "Pos.": st.column_config.NumberColumn(width="small"),
                "Titre": st.column_config.TextColumn(width="large"),
                "Domaine": st.column_config.TextColumn(width="small"),
                "Mots": st.column_config.NumberColumn(width="small"),
                "H2": st.column_config.NumberColumn(width="small"),
                "Rich": st.column_config.TextColumn(width="medium"),
            },
        )

        # Resume concurrentiel
        st.markdown("### Synthese concurrentielle")
        words = [r.get("word_count") for r in top10 if r.get("word_count")]
        if words:
            avg_words = sum(words) // len(words)
            min_w, max_w = min(words), max(words)
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Mots moyens", f"{avg_words:,}")
            with col_b:
                st.metric("Minimum", f"{min_w:,}")
            with col_c:
                st.metric("Maximum", f"{max_w:,}")
            st.caption(
                f"Pour ce mot-cle, la moyenne est de {avg_words} mots. "
                f"Hermes visera ~{int(avg_words * 1.15):,} mots pour surpasser le top 10. "
                f"Le concurrent le plus long fait {max_w:,} mots."
            )

        # Concurrents directs
        directs = serp.get("concurrents_directs") or []
        if directs:
            st.markdown("#### Concurrents directs identifies")
            st.markdown(" ".join(
                f'<code style="margin:2px;">{c}</code>' for c in directs[:15]
            ), unsafe_allow_html=True)

    else:
        st.info(
            "Donnees SERP non disponibles pour cette session. "
            "L'analyse a ete faite en mode heuristique (fallback sans API). "
            "Pour obtenir les donnees completes, assurez-vous que TalorData est configure "
            "et que les credits sont actifs."
        )

    # PAA
    paa = serp.get("paa") or []
    if paa:
        st.markdown("### Questions posees (People Also Ask)")
        for q in paa[:12]:
            st.markdown(f"- {q}")

    # AI Overviews
    ai_overviews = serp.get("ai_overviews") or []
    if ai_overviews:
        st.markdown("### AI Overviews detectees")
        for ai in ai_overviews[:3]:
            if isinstance(ai, dict):
                st.info(ai.get("text", ai.get("summary", str(ai)))[:500])
            else:
                st.info(str(ai)[:500])

    # Mots-cles associes
    kws = serp.get("mots_cles_associes") or []
    if kws:
        st.markdown("### Mots-cles associes")
        st.markdown(" ".join(
            f'<code style="margin:2px;">{kw}</code>' for kw in kws[:30]
        ), unsafe_allow_html=True)


# ─── Intention & Persona ─────────────────────────────────────────────────

def _render_intent_persona_tab(session_data: dict) -> None:
    """Onglet intention de recherche et persona."""
    intention = session_data.get("intention", "")
    type_page = session_data.get("type_page", "")
    persona = session_data.get("fiche_persona") or {}

    # Intent card
    st.markdown("### Intention de recherche")

    intent_labels = {
        "informative": ("Information", "Le lecteur cherche a comprendre un sujet", "blue"),
        "transactionnelle": ("Achat/Conversion", "Le lecteur veut acheter, s'inscrire ou obtenir un devis", "green"),
        "comparative": ("Comparaison", "Le lecteur compare des options avant de decider", "orange"),
        "locale": ("Recherche locale", "Le lecteur cherche un service pres de chez lui", "purple"),
    }
    label, desc, color = intent_labels.get(intention, (intention, "", "gray"))

    ic1, ic2 = st.columns([1, 3])
    with ic1:
        st.markdown(
            f'<div style="background:{color};color:white;padding:20px;border-radius:12px;text-align:center;">'
            f'<p style="font-size:1.5rem;font-weight:700;margin:0;">{label}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with ic2:
        st.markdown(f"#### {label}")
        st.markdown(desc)
        st.caption(f"Type de page selectionne : **{type_page}**")

    # Persona
    if persona:
        st.markdown("---")
        st.markdown("### Persona cible")

        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.markdown(f"**Nom** : {persona.get('nom_persona', '?')}")
            st.markdown(f"**Maturite** : {persona.get('maturite', '?')}")
            st.markdown(f"**Canal** : {persona.get('canal_acquisition', '?')}")
        with pcol2:
            st.markdown(f"**Objectif** : {persona.get('objectif_lecture', '?')}")
            freins = persona.get("freins") or []
            if freins:
                st.markdown("**Freins** :")
                for f in freins:
                    st.markdown(f"- {f}")

        vocab = persona.get("vocabulaire_recommande") or []
        if vocab:
            st.markdown("**Vocabulaire recommande** :")
            st.markdown(" ".join(
                f'<code style="margin:2px;">{v}</code>' for v in vocab
            ), unsafe_allow_html=True)


# ─── Offre & Conversion ──────────────────────────────────────────────────

def _render_offre_tab(session_data: dict) -> None:
    """Onglet strategie de conversion."""
    offre = session_data.get("offre_conversion_data") or {}
    fiche = session_data.get("fiche_entreprise") or {}

    if not offre and not fiche:
        st.info("Donnees de conversion non disponibles pour cette session.")
        return

    # CTA
    if offre:
        st.markdown("### Call-to-Action")
        cta1 = offre.get("cta_principal", "")
        cta2 = offre.get("cta_secondaire", "")
        ocol1, ocol2 = st.columns(2)
        with ocol1:
            if cta1:
                st.success(f"**Principal** : {cta1}")
        with ocol2:
            if cta2:
                st.info(f"**Secondaire** : {cta2}")

        # Benefices
        benefices = offre.get("benefices") or []
        if benefices:
            st.markdown("### Benefices a mettre en avant")
            for b in benefices:
                st.markdown(f"- {b}")

        # Objections
        objections = offre.get("objections") or []
        if objections:
            st.markdown("### Objections a traiter")
            for o in objections:
                st.markdown(f"- {o}")

        # Preuves
        preuves = offre.get("preuves") or []
        if preuves:
            st.markdown("### Preuves sociales / chiffres cles")
            for p in preuves:
                st.markdown(f"- {p}")

        # Valeur ajoutee unique
        vau = offre.get("valeur_ajoutee_unique", "")
        if vau:
            st.markdown("### Proposition de valeur unique")
            st.info(vau)

    # Fiche entreprise
    if fiche:
        st.markdown("---")
        st.markdown("### Fiche entreprise")
        st.markdown(f"**Nom** : {fiche.get('nom', '?')}")
        st.markdown(f"**Secteur** : {fiche.get('secteur', '?')}")
        st.markdown(f"**Positionnement** : {fiche.get('positionnement', '?')}")
        st.markdown(f"**Ton de marque** : {fiche.get('ton_marque', '?')}")

        offres = fiche.get("offres") or []
        if offres:
            st.markdown("**Offres** :")
            for o in offres:
                st.markdown(f"- {o}")

        preuves_ent = fiche.get("preuves") or []
        if preuves_ent:
            st.markdown("**Preuves / Credibilite** :")
            for p in preuves_ent:
                st.markdown(f"- {p}")

        contraintes = fiche.get("contraintes_legales") or []
        if contraintes:
            st.markdown("**Contraintes legales** :")
            for c in contraintes:
                st.warning(c)

        interdits = fiche.get("mots_cles_interdits") or []
        if interdits:
            st.markdown("**Mots-cles interdits** :")
            for kw in interdits:
                st.markdown(f"- `{kw}`")


# ─── Differenciation ─────────────────────────────────────────────────────

def _render_diff_tab(session_data: dict) -> None:
    """Onglet angles differenciants."""
    diff = session_data.get("angles_differenciants") or {}
    serp = session_data.get("serp_data") or {}

    st.markdown("### Opportunites de differenciation")

    # Angle principal
    angle = diff.get("angle_principal", "")
    if angle:
        st.success(f"**Angle retenu** : {angle}")

    # Opportunites uniques
    opps = diff.get("opportunites_uniques") or []
    if opps:
        st.markdown("#### Opportunites uniques identifiees")
        for o in opps:
            st.markdown(f"- {o}")

    # Angles faibles des concurrents
    faibles = diff.get("angles_faibles") or []
    if faibles:
        st.markdown("#### Faiblesses des concurrents")
        for f in faibles:
            st.markdown(f"- {f}")

    # Facteurs de differenciation
    facteurs = diff.get("facteurs_differenciation") or []
    if facteurs:
        st.markdown("#### Facteurs de differenciation")
        for f in facteurs:
            st.markdown(f"- {f}")

    # Opportunites SERP
    st.markdown("---")
    st.markdown("### Analyse des opportunites SERP")

    top10 = serp.get("top10") or []
    if top10:
        # Compter les featured snippets, PAA, AI overviews
        with_featured = sum(1 for r in top10 if r.get("has_featured_snippet"))
        with_paa = sum(1 for r in top10 if r.get("has_paa"))
        with_ai = sum(1 for r in top10 if r.get("has_ai_overview"))

        ocol1, ocol2, ocol3 = st.columns(3)
        with ocol1:
            st.metric("Featured Snippets", with_featured,
                     delta="Opportunite" if with_featured < 3 else "Concurrentiel")
        with ocol2:
            st.metric("PAA", with_paa,
                     delta="Opportunite" if with_paa < 5 else "Concurrentiel")
        with ocol3:
            st.metric("AI Overviews", with_ai,
                     delta="Opportunite" if with_ai < 2 else "Concurrentiel")

        # Analyse des gaps
        words = [r.get("word_count") for r in top10 if r.get("word_count")]
        h2s = [r.get("h2_count") for r in top10 if r.get("h2_count")]

        if words:
            avg_words = sum(words) // len(words)
            if avg_words < 1500:
                st.info(
                    f"Le contenu moyen fait {avg_words} mots. "
                    f"Un article de 2000-2500 mots couvrira le sujet plus en profondeur que "
                    f"la concurrence et aura plus de chances de ranker."
                )
            elif avg_words < 3000:
                st.info(
                    f"Le contenu moyen fait {avg_words} mots. "
                    f"Visez 3500-4000 mots avec une structure H2/H3 plus riche "
                    f"pour vous demarquer."
                )
            else:
                st.info(
                    f"Marche concurrentiel : {avg_words} mots en moyenne. "
                    f"La differentiation passera par la qualite, la structure et les visuels "
                    f"plutot que par la longueur."
                )
    else:
        st.info(
            "Donnees SERP insuffisantes pour l'analyse des opportunites. "
            "Activez TalorData pour obtenir cette analyse."
        )
