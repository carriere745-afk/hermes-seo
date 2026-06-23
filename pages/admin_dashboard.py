"""Page Admin Dashboard — Consommation API & Etat des connecteurs.

Vue synthetique de toutes les API Hermes SEO :
- Connecteurs (etat, cle, cout unitaire)
- Consommation par pipeline
- Budget mensuel estime
"""

import streamlit as st


def _status_badge(configured: bool, disabled_reason: str = "") -> str:
    if disabled_reason:
        return f'<span style="background:#fce4ec;color:#c62828;padding:2px 8px;border-radius:10px;font-size:12px">⛔ Echec ({disabled_reason[:20]})</span>'
    if configured:
        return f'<span style="background:#e8f5e9;color:#2e7d32;padding:2px 8px;border-radius:10px;font-size:12px">✅ Connecte</span>'
    return f'<span style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:10px;font-size:12px">⬜ Non configure</span>'


def _get_api_status() -> dict:
    """Scanne tous les connecteurs et retourne leur etat."""
    apis = []

    # GSC
    try:
        from hermes.connectors.gsc_connector import gsc
        apis.append({
            "nom": "Google Search Console",
            "connecteur": "gsc_connector.py",
            "configure": gsc.is_configured,
            "disabled": "",
            "type": "Gratuit",
            "cout": "$0",
            "pipelines": "P1, P2, P3, P4",
            "usage": "Positions, impressions, CTR, CWV, indexation",
        })
    except Exception:
        apis.append({"nom": "Google Search Console", "connecteur": "gsc_connector.py", "configure": False, "disabled": "Import error", "type": "Gratuit", "cout": "$0", "pipelines": "P1-P4", "usage": "—"})

    # TalorData
    try:
        from hermes import config
        talor_ok = bool(config.TALORDATA_API_KEY)
        apis.append({
            "nom": "TalorData",
            "connecteur": "serp_api.py",
            "configure": talor_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "$0.25-0.90/1K reqs",
            "pipelines": "P1, P3, P4",
            "usage": "SERP top 10, PAA, AI Overview, Featured Snippet",
        })
    except Exception:
        apis.append({"nom": "TalorData", "configure": False, "disabled": "?", "type": "Payant", "cout": "$0.25-0.90/1K", "pipelines": "P1, P3, P4", "usage": "—"})

    # DataForSEO
    try:
        from hermes.connectors.dataforseo_connector import dataforseo
        apis.append({
            "nom": "DataForSEO",
            "connecteur": "dataforseo_connector.py",
            "configure": dataforseo.is_configured,
            "disabled": "",
            "type": "Payant",
            "cout": "$0.001-0.02/req",
            "pipelines": "P1, P4",
            "usage": "Volume, CPC, positions SERP, SERP features",
        })
    except Exception:
        apis.append({"nom": "DataForSEO", "configure": False, "disabled": "?", "type": "Payant", "cout": "$0.001-0.02", "pipelines": "P1, P4", "usage": "—"})

    # Keywords Everywhere
    try:
        from hermes.connectors.keywordseverywhere_connector import keywordseverywhere
        ke_disabled = getattr(keywordseverywhere, "_disabled_reason", "") or ""
        apis.append({
            "nom": "Keywords Everywhere",
            "connecteur": "keywordseverywhere_connector.py",
            "configure": keywordseverywhere.is_configured if not ke_disabled else False,
            "disabled": ke_disabled,
            "type": "Payant",
            "cout": "~$0.01/100 kw",
            "pipelines": "P1, P2, P4",
            "usage": "Volume de recherche, CPC, tendances",
        })
    except Exception:
        apis.append({"nom": "Keywords Everywhere", "configure": False, "disabled": "?", "type": "Payant", "cout": "~$0.01/100 kw", "pipelines": "P1-P4", "usage": "—"})

    # RankParse
    try:
        from hermes.connectors.rankparse_connector import rankparse
        apis.append({
            "nom": "RankParse",
            "connecteur": "rankparse_connector.py",
            "configure": rankparse.is_configured,
            "disabled": "",
            "type": "Payant",
            "cout": "~$0.009/credit",
            "pipelines": "P2, P3, P4",
            "usage": "Domain Authority, backlinks, faisabilite",
        })
    except Exception:
        apis.append({"nom": "RankParse", "configure": False, "disabled": "?", "type": "Payant", "cout": "~$0.009", "pipelines": "P2-P4", "usage": "—"})

    # Scrape.do / Serpstack (fallback)
    try:
        from hermes import config
        scrapedo_ok = bool(getattr(config, "SCRAPEDO_API_KEY", ""))
        serpstack_ok = bool(getattr(config, "SERPSTACK_API_KEY", ""))
        apis.append({
            "nom": "Scrape.do + Serpstack",
            "connecteur": "serp_api.py (fallback)",
            "configure": scrapedo_ok or serpstack_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "$1.16/1K (Scrape.do)",
            "pipelines": "P1 (fallback)",
            "usage": "Fallback SERP si TalorData KO",
        })
    except Exception:
        pass

    # PageSpeed Insights
    apis.append({
        "nom": "PageSpeed Insights",
        "connecteur": "pagespeed_connector.py",
        "configure": True,
        "disabled": "",
        "type": "Gratuit",
        "cout": "$0 (25K req/jour)",
        "pipelines": "P3",
        "usage": "Core Web Vitals, Lighthouse scores",
    })

    # LLM APIs
    try:
        from hermes import config
        anthropic_ok = bool(getattr(config, "ANTHROPIC_API_KEY", ""))
        openai_ok = bool(getattr(config, "OPENAI_API_KEY", ""))
        deepseek_ok = bool(getattr(config, "DEEPSEEK_API_KEY", ""))
        apis.append({
            "nom": "Claude (Anthropic)",
            "connecteur": "llm.py",
            "configure": anthropic_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "~$3/1M tokens (Haiku ~$0.60)",
            "pipelines": "P1, P2, P3, P4",
            "usage": "Redaction, synthese, gap content, correlation",
        })
        apis.append({
            "nom": "OpenAI / GPT",
            "connecteur": "llm.py",
            "configure": openai_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "~$0.15/1M tokens",
            "pipelines": "P1",
            "usage": "Agents SEO, AEO, GEO",
        })
        apis.append({
            "nom": "DeepSeek",
            "connecteur": "llm.py",
            "configure": deepseek_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "~$0.10/1M tokens",
            "pipelines": "P1",
            "usage": "Agents strategie, differenciation",
        })
    except Exception:
        pass

    return apis


def _get_pipeline_costs() -> dict:
    """Couts mensuels estimes par pipeline."""
    return [
        {
            "pipeline": "1. Editorial (Redaction)",
            "agents": 28,
            "cout_unitaire": "~$0.60/article",
            "cout_100": "~$60",
            "apis": "Claude, GPT, DeepSeek, TalorData, DataForSEO, KE, GSC",
            "mode": "On-demand",
        },
        {
            "pipeline": "2. Audit de Contenu",
            "agents": 11,
            "cout_unitaire": "~$0.005/page",
            "cout_100": "~$0.50",
            "apis": "CMS Detector ($0), Sitemap Parser ($0), GSC ($0), KE, RankParse",
            "mode": "On-demand",
        },
        {
            "pipeline": "3. Audit Technique",
            "agents": 23,
            "cout_unitaire": "$0.00/10 pages",
            "cout_100": "~$0.00 (std) / ~$0.05 (premium)",
            "apis": "PSI ($0), shcheck ($0), polly ($0), GSC ($0), geo-optimizer ($0), KE, RankParse",
            "mode": "On-demand",
        },
        {
            "pipeline": "4. SERP & Visibilite",
            "agents": 11,
            "cout_unitaire": "~$0.03/semaine (500 kw)",
            "cout_100": "~$2.50/mois (site moyen) / ~$20/mois (longue traine)",
            "apis": "GSC ($0), TalorData, DataForSEO, KE, RankParse",
            "mode": "Cron (configurable)",
        },
    ]


def render_admin_dashboard():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Administration Hermes SEO</p>', unsafe_allow_html=True)
    st.caption("Consommation API, etat des connecteurs, couts par pipeline.")

    # ── API Status ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Connecteurs API")

    apis = _get_api_status()
    total_api = len(apis)
    configured = sum(1 for a in apis if a.get("configure") and not a.get("disabled"))
    failed = sum(1 for a in apis if a.get("disabled"))
    unconfigured = total_api - configured - failed

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total APIs", total_api)
    with c2: st.metric("Connectees", configured)
    with c3: st.metric("Non configurees", unconfigured)
    with c4: st.metric("En echec", failed, delta=f"-{failed}" if failed else None, delta_color="inverse")

    table_rows = ""
    for api in apis:
        status = _status_badge(api.get("configure", False), api.get("disabled", ""))
        table_rows += (
            f"<tr>"
            f"<td><strong>{api['nom']}</strong><br><small>{api.get('connecteur','')}</small></td>"
            f"<td>{status}</td>"
            f"<td>{api.get('type','')}</td>"
            f"<td>{api.get('cout','')}</td>"
            f"<td style='font-size:12px'>{api.get('pipelines','')}</td>"
            f"<td style='font-size:12px'>{api.get('usage','')}</td>"
            f"</tr>"
        )
    st.markdown(
        f"<table style='width:100%;border-collapse:collapse;font-size:13px'>"
        f"<tr style='background:#1E88E5;color:#fff'><th>API</th><th>Statut</th><th>Type</th><th>Coût</th><th>Pipelines</th><th>Usage</th></tr>"
        f"{table_rows}"
        f"</table>",
        unsafe_allow_html=True
    )

    # Alertes
    if failed:
        st.error(f"{failed} API(s) en echec — verifier les cles et les credits.")
    if any(a.get("nom") == "Keywords Everywhere" and a.get("disabled") for a in apis):
        st.warning("Keywords Everywhere : credit epuise (HTTP 402). Renouveler la cle pour avoir les volumes de recherche.")

    # ── Coûts par pipeline ───────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Cout operationnel par pipeline")

    costs = _get_pipeline_costs()
    for p in costs:
        with st.container():
            st.markdown(f"### {p['pipeline']}")
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Agents", p["agents"])
            with c2: st.metric("Cout unitaire", p["cout_unitaire"])
            with c3: st.metric("Cout /100", p["cout_100"])
            st.caption(f"APIs : {p['apis']} | Mode : {p['mode']}")

    # ── Budget mensuel estimé ────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Budget mensuel estime")

    # Scenarios
    st.markdown("### Scenarios (site moyen, 500 mots-cles)")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.metric("Minimal (fast)", "$0.00/mois", help="GSC uniquement, pas de LLM, pas de premium")
    with sc2:
        st.metric("Standard", "~$3.10/mois", help="Articles standard + audit contenu + audit tech + SERP 500kw")
    with sc3:
        st.metric("Intensif (premium)", "~$83/mois", help="100 articles premium + tous les pipelines + longue traine")

    st.caption("Comparaison : Semrush ~$120/mois, Ahrefs ~$99/mois. Hermes SEO : ~$3/mois en standard.")

    # ── Quick Status ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Statut global Hermes SEO")

    from datetime import datetime
    total_agents = 28 + 11 + 23 + 11  # P1 + P2 + P3 + P4
    pipelines_en_prod = 4
    pipelines_total = 7

    q1, q2, q3, q4, q5 = st.columns(5)
    with q1: st.metric("Pipelines en prod", f"{pipelines_en_prod}/{pipelines_total}")
    with q2: st.metric("Agents", total_agents)
    with q3: st.metric("Connecteurs", total_api)
    with q4: st.metric("Outils OSS", "10")
    with q5: st.metric("Date", datetime.now().strftime("%d/%m/%Y"))
