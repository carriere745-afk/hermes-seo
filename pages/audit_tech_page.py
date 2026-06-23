"""Page Audit Technique — Streamlit UI.

Pipeline 3 : 23 agents, 12 dimensions techniques.
Mode consentement obligatoire, poids de priorisation configurables,
resultats organises en vues : Sante technique, Roadmap, Issues.
"""

import asyncio
import json as _json
from datetime import datetime
from urllib.parse import urlparse

import streamlit as st

from hermes.core.audit_entry import resolve_entry_urls
from hermes.core.audit_tech_entry import init_tech_audit, CLIENT_PROFILES
from hermes.agents.audit_tech import TECH_ORDER, TECH_REGISTRY

# ─── Profils client ─────────────────────────────────────────────────────

PROFILE_LABELS = {
    "ecommerce": "E-commerce",
    "blog": "Blog / Média",
    "institutionnel": "Site institutionnel",
    "agence": "Agence / Portfolio",
    "saas": "SaaS / B2B",
}

MODE_LABELS = {
    "fast": "Rapide — Déterministe uniquement",
    "standard": "Standard — Recommandé",
    "premium": "Premium — Synthèse LLM enrichie",
    "debug": "Debug — Tous les agents + logs",
}


async def _run_pipeline(urls: list[str], site_url: str, mode: str,
                        profile: str, consent: bool) -> dict:
    """Execute le pipeline complet et retourne le state."""
    state = await init_tech_audit(
        site_url=site_url, urls=urls, consent_given=consent,
        profile=profile, mode=mode,
    )
    for agent_id in TECH_ORDER:
        if agent_id in TECH_REGISTRY:
            try:
                state = await TECH_REGISTRY[agent_id](state)
            except Exception as e:
                st.error(f"Erreur {agent_id}: {e}")
                break
    return {
        "state": state,
        "site_url": site_url,
        "domain": state.domain,
        "cms": state.cms_detected,
        "cms_version": state.cms_version,
        "cms_confidence": state.cms_confidence,
        "pages": len(state.crawled_pages),
        "issues": len(state.issues),
        "score": state.scores.global_score,
        "confidence": state.scores.global_confidence,
        "roadmap": state.roadmap,
        "critical": len(state.critical_issues),
        "p0": sum(1 for i in state.issues if i.priority == "P0"),
        "p1": sum(1 for i in state.issues if i.priority == "P1"),
        "p2": sum(1 for i in state.issues if i.priority == "P2"),
        "p3": sum(1 for i in state.issues if i.priority == "P3"),
        "export": state,
    }


def _badge(severity: str) -> str:
    colors = {
        "critical": "#c62828", "high": "#e65100", "medium": "#f9a825",
        "low": "#2e7d32", "info": "#1565c0",
    }
    bg = {
        "critical": "#fce4ec", "high": "#fff3e0", "medium": "#fffde7",
        "low": "#e8f5e9", "info": "#e3f2fd",
    }
    c = colors.get(severity, "#333")
    b = bg.get(severity, "#eee")
    return f'<span style="background:{b};color:{c};padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">{severity.upper()}</span>'


def render_audit_tech_page():
    """Point d'entree de la page Audit Technique."""

    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Audit Technique</p>', unsafe_allow_html=True)
    st.caption("Scan complet du site sur 12 dimensions : SEO technique, performance, sécurité, AEO/GEO...")

    # ── Mode consentement ──────────────────────────────────────────
    with st.expander("⚙️ Configuration & Consentement", expanded=True):
        st.markdown("### Paramètres de l'audit")
        st.markdown("L'audit est **défensif** : aucun test d'intrusion, respect de robots.txt, rate limiting.")

        col1, col2 = st.columns(2)
        with col1:
            mode_choice = st.selectbox(
                "Mode qualité", options=list(MODE_LABELS.keys()),
                format_func=lambda x: MODE_LABELS[x], index=1, key="tech_mode"
            )
            profile = st.selectbox(
                "Profil du site", options=list(PROFILE_LABELS.keys()),
                format_func=lambda x: PROFILE_LABELS[x], key="tech_profile"
            )
        with col2:
            max_urls = st.number_input("Nombre max d'URLs", min_value=1, max_value=500, value=20, step=10, key="tech_max_urls")
            rate_limit = st.slider("Rate limit (req/s)", min_value=0.5, max_value=10.0, value=2.0, step=0.5, key="tech_rate")

        # Poids configurables
        st.markdown("#### Poids de priorisation")
        weights = CLIENT_PROFILES.get(profile, CLIENT_PROFILES["blog"])
        cw1, cw2, cw3, cw4 = st.columns(4)
        with cw1:
            w_seo = st.slider("Impact SEO", 0, 100, int(weights["impact_seo"] * 100), 5, key="w_seo") / 100
        with cw2:
            w_biz = st.slider("Impact Business", 0, 100, int(weights["impact_business"] * 100), 5, key="w_biz") / 100
        with cw3:
            w_eff = st.slider("Effort", 0, 100, int(weights["effort"] * 100), 5, key="w_eff") / 100
        with cw4:
            w_conf = st.slider("Conformité", 0, 100, int(weights["conformite"] * 100), 5, key="w_conf") / 100

        # Consentement explicite
        st.markdown("---")
        consent = st.checkbox(
            f"✅ J'autorise l'audit technique du site cible. Max {max_urls} URLs, "
            f"respect de robots.txt, rate limit {rate_limit} req/s. "
            "Aucun scan intrusif ne sera effectué.",
            key="tech_consent"
        )

    # ── Entrée URL ───────────────────────────────────────────────────
    mode_labels = {
        "single": "URL unique", "list": "Liste d'URLs",
        "sitemap": "Sitemap XML (auto-detection)", "crawl": "Crawl BFS (page d'accueil)", "csv": "Import CSV",
    }
    entry_mode = st.selectbox("Mode d'entrée", options=list(mode_labels.keys()),
                               format_func=lambda x: mode_labels[x], key="tech_entry_mode")

    input_value = ""
    if entry_mode == "single":
        input_value = st.text_input("URL du site ou de la page", placeholder="https://mon-site.fr")
    elif entry_mode == "list":
        input_value = st.text_area("URLs (une par ligne)", placeholder="https://mon-site.fr\nhttps://mon-site.fr/page")
    elif entry_mode == "sitemap":
        input_value = st.text_input("URL du site", placeholder="https://mon-site.fr", help="Sitemap détecté automatiquement")
    elif entry_mode == "crawl":
        input_value = st.text_input("Page d'accueil du site", placeholder="https://mon-site.fr")
    elif entry_mode == "csv":
        input_value = st.text_area("Contenu CSV (colonne 'url')", placeholder="url\nhttps://mon-site.fr")

    # Coût estimé
    if mode_choice == "premium":
        st.caption("💰 Coût estimé : ~$0.005 (synthèse Haiku)")

    # ── Lancement ──────────────────────────────────────────────────────
    launch = st.button("🔍 Lancer l'audit technique", type="primary",
                       use_container_width=True, disabled=not (input_value and consent))

    if launch and input_value and consent:
        with st.spinner("Résolution des URLs..."):
            resolved = asyncio.run(resolve_entry_urls(
                mode=entry_mode, input_value=input_value, max_urls=max_urls
            ))
        if not resolved["success"]:
            st.error(resolved.get("error", "Erreur de résolution d'URLs"))
            st.stop()

        urls = resolved["urls"]
        site_url = resolved["site_url"]
        domain = urlparse(site_url).netloc.replace("www.", "")

        if resolved.get("type_distribution"):
            st.info(f"**{len(urls)} URLs résolues** — Types: {resolved['type_distribution']}")

        progress = st.progress(0, "Audit en cours...")
        result = asyncio.run(_run_pipeline(
            urls=urls, site_url=site_url, mode=mode_choice,
            profile=profile, consent=consent
        ))
        progress.progress(1.0, "Terminé !")

        state = result["export"]
        st.session_state.tech_result = result
        st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # RESULTATS
    # ═══════════════════════════════════════════════════════════════════
    if "tech_result" not in st.session_state or not st.session_state.tech_result:
        return

    result = st.session_state.tech_result
    state = result["export"]

    st.markdown("---")
    st.markdown("## Résultats de l'audit technique")

    # ── VUE 1 : SANTE TECHNIQUE ────────────────────────────────────
    st.markdown("### Santé technique du site")
    st.caption(f"Domaine : **{result['domain']}** | CMS : **{result['cms'] or 'non détecté'}** | Mode : **{mode_choice}** | Profil : **{PROFILE_LABELS.get(profile, profile)}**")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Pages auditées", result["pages"])
    with col2:
        st.metric("Score global", f"{result['score']}/100",
                  delta=result["confidence"].upper() if result["confidence"] != "medium" else None)
    with col3:
        st.metric("Issues", result["issues"])
    with col4:
        st.metric("Critiques", result["critical"])
    with col5:
        st.metric("Quick Wins (P0)", result["p0"])

    # Scores par dimension
    dims_display = [
        ("crawlability", "Crawl"), ("indexation", "Index"), ("architecture", "Arch"),
        ("structure", "Struct"), ("content", "Contenu"), ("performance", "Perf"),
        ("mobile", "Mobile"), ("structured_data", "Schema"), ("international", "Intl"),
        ("security", "Secu"), ("maillage", "Maillage"),
    ]
    cols = st.columns(len(dims_display))
    for i, (dim_key, dim_label) in enumerate(dims_display):
        d = getattr(state.scores, dim_key)
        with cols[i]:
            st.metric(dim_label, f"{d.score}%",
                      delta=d.confidence.upper() if d.confidence != "medium" else None,
                      delta_color="off")

    # Alertes
    alerts = []
    if result["p0"] > 0:
        alerts.append(f"🔴 {result['p0']} issues critiques (P0) — correction immédiate recommandée")
    if result["p1"] > 10:
        alerts.append(f"🟠 {result['p1']} issues haute priorité (P1)")
    if result["score"] < 50:
        alerts.append(f"🔴 Score global faible ({result['score']}/100)")
    if hasattr(state, 'orphans') and len(state.orphans) > 3:
        alerts.append(f"⚠️ {len(state.orphans)} pages orphelines")
    if alerts:
        st.markdown("**Alertes :**")
        for a in alerts:
            st.markdown(f"- {a}")

    # ── VUE 2 : ROADMAP ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Roadmap priorisée")
    if state.roadmap:
        for sprint in state.roadmap:
            emoji = "🔴" if "Quick Win" in sprint["sprint"] else "🟠" if "critique" in sprint["sprint"].lower() else "🟡" if "Optimis" in sprint["sprint"] else "🔵"
            with st.expander(f"{emoji} {sprint['sprint']} — {sprint['count']} tâches, ~{sprint['estimated_hours']}h — Profils : {', '.join(sprint['targets'])}"):
                for item in sprint["items"][:10]:
                    st.markdown(
                        f"- [{item['priority']}] {item['description'][:120]} "
                        f"({item.get('effort', '?')})"
                    )
                    if item.get("cms_location"):
                        st.caption(f"  📍 {item['cms_location']}")
                if len(sprint["items"]) > 10:
                    st.caption(f"... et {len(sprint['items']) - 10} autres")

    # ── VUE 3 : ISSUES ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Top issues")
    tab_p0, tab_p1, tab_all = st.tabs(["P0 · Critiques", "P0+P1 · Haute priorité", "Toutes"])
    with tab_p0:
        p0_issues = [i for i in state.issues if i.priority == "P0"]
        for issue in p0_issues[:20]:
            st.markdown(
                f"**{_badge(issue.severity)} [{issue.category}]** {issue.description[:130]}",
                unsafe_allow_html=True
            )
            st.caption(f"URL: {issue.url[:80]} | Impact: {issue.impact_business} | Gain: {issue.gain_potentiel} | Effort: {issue.effort} | {issue.confidence}")
    with tab_p1:
        p1_issues = [i for i in state.issues if i.priority in ("P0", "P1")]
        for issue in p1_issues[:30]:
            st.markdown(
                f"**[{issue.priority}] {_badge(issue.severity)} [{issue.category}]** {issue.description[:130]}",
                unsafe_allow_html=True
            )
            st.caption(f"URL: {issue.url[:80]} | Effort: {issue.effort} | {issue.confidence}")
    with tab_all:
        for issue in state.issues[:50]:
            st.markdown(f"**[{issue.priority}]** {issue.description[:130]}")
            st.caption(f"URL: {issue.url[:60]} | {issue.category} | {issue.severity} | {issue.confidence}")

    # ── EXPORTS ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Exports")
    exp1, exp2, exp3 = st.columns(3)
    with exp1:
        from hermes.agents.audit_tech.tt19_export import build_html_report
        html = build_html_report(state)
        st.download_button("📄 HTML", data=html, file_name=f"audit_technique_{result['domain']}_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html", use_container_width=True)
    with exp2:
        from hermes.agents.audit_tech.tt19_export import build_json_export
        json_str = build_json_export(state)
        st.download_button("📊 JSON", data=json_str, file_name=f"audit_technique_{result['domain']}.json", mime="application/json", use_container_width=True)
    with exp3:
        from hermes.agents.audit_tech.tt19_export import build_csv_export
        csv = build_csv_export(state)
        st.download_button("📋 CSV", data=csv, file_name=f"audit_technique_{result['domain']}.csv", mime="text/csv", use_container_width=True)
