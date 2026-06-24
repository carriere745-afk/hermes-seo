"""Page Admin Dashboard — Consommation API & Etat des connecteurs.

Vue synthetique de toutes les API Hermes SEO :
- Connecteurs (etat, cle, cout unitaire)
- Consommation par pipeline
- Budget mensuel estime
- Observability (hermes_events, predictions_history)
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
            "pipelines": "P1, P2, P3, P4, P5",
            "usage": "Positions, impressions, CTR, CWV, indexation",
        })
    except Exception:
        apis.append({"nom": "Google Search Console", "connecteur": "gsc_connector.py", "configure": False, "disabled": "Import error", "type": "Gratuit", "cout": "$0", "pipelines": "P1-P5", "usage": "—"})

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
            "pipelines": "P1, P3, P4, P5",
            "usage": "SERP top 10, PAA, AI Overview, Featured Snippet, concurrents P5",
        })
    except Exception:
        apis.append({"nom": "TalorData", "configure": False, "disabled": "?", "type": "Payant", "cout": "$0.25-0.90/1K", "pipelines": "P1, P3, P4, P5", "usage": "—"})

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
            "pipelines": "P1, P4, P5",
            "usage": "Volume, CPC, positions SERP, SERP features, competitors P5",
        })
    except Exception:
        apis.append({"nom": "DataForSEO", "configure": False, "disabled": "?", "type": "Payant", "cout": "$0.001-0.02", "pipelines": "P1, P4, P5", "usage": "—"})

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
            "pipelines": "P1, P2, P4, P5",
            "usage": "Volume de recherche, CPC, tendances, volumes P5",
        })
    except Exception:
        apis.append({"nom": "Keywords Everywhere", "configure": False, "disabled": "?", "type": "Payant", "cout": "~$0.01/100 kw", "pipelines": "P1-P5", "usage": "—"})

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
            "pipelines": "P2, P3, P4, P5",
            "usage": "Domain Authority, backlinks, faisabilite concurrentielle P5",
        })
    except Exception:
        apis.append({"nom": "RankParse", "configure": False, "disabled": "?", "type": "Payant", "cout": "~$0.009", "pipelines": "P2-P5", "usage": "—"})

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
            "pipelines": "P1, P2, P3, P4, P5",
            "usage": "Redaction, synthese, gap content, correlation, roadmap strategique (Haiku)",
        })
        apis.append({
            "nom": "OpenAI / GPT",
            "connecteur": "llm.py",
            "configure": openai_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "~$0.15/1M tokens",
            "pipelines": "P1",
            "usage": "Agents SEO, AEO, GEO (fallback P5)",
        })
        apis.append({
            "nom": "DeepSeek",
            "connecteur": "llm.py",
            "configure": deepseek_ok,
            "disabled": "",
            "type": "Payant",
            "cout": "~$0.10/1M tokens",
            "pipelines": "P1",
            "usage": "Agents strategie, differenciation (fallback P5)",
        })
    except Exception:
        pass

    # GA4 (optionnel)
    try:
        from hermes import config
        ga4_ok = bool(getattr(config, "_cfg", None) and config._cfg._resolve("GA4_PROPERTY_ID"))
        apis.append({
            "nom": "Google Analytics 4",
            "connecteur": "ga4 (optionnel)",
            "configure": ga4_ok,
            "disabled": "",
            "type": "Gratuit",
            "cout": "$0",
            "pipelines": "P5 (premium)",
            "usage": "Conversions, revenus, taux de conversion reels (ST05)",
        })
    except Exception:
        pass

    # SQLite Strategie
    apis.append({
        "nom": "SQLite Strategie",
        "connecteur": "strategie_db.py",
        "configure": True,
        "disabled": "",
        "type": "Gratuit",
        "cout": "$0",
        "pipelines": "P5 + Observability",
        "usage": "hermes_events, predictions_history, strategie_sessions",
    })

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
        {
            "pipeline": "5. Strategie Editoriale",
            "agents": 18,
            "cout_unitaire": "~$0.00 (fast) / ~$0.08 (std) / ~$0.15 (premium)",
            "cout_100": "~$8.00 (100 sessions standard)",
            "apis": "Claude Haiku (ST04/ST06/ST06b), ChromaDB ($0), SQLite Strategie ($0), GA4 (opt)",
            "mode": "On-demand",
        },
        {
            "pipeline": "6. Maillage & Backlinks",
            "agents": 18,
            "cout_unitaire": "~$0.15/audit (MVP) / ~$0.20/audit (complet)",
            "cout_100": "~$20.00 (100 audits complets)",
            "apis": "DataForSEO Backlinks, GSC ($0), Bing Webmaster ($0), Claude Haiku (B06)",
            "mode": "On-demand",
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
        st.metric("Standard", "~$3.33/mois", help="Articles + audits + SERP 500kw + 1 strategie + 1 audit backlinks")
    with sc3:
        st.metric("Intensif (premium)", "~$90/mois", help="100 articles premium + tous les pipelines + longue traine + strategie GA4")

    st.caption("Comparaison : Semrush ~$120/mois, Ahrefs ~$99/mois. Hermes SEO : ~$3/mois en standard.")

    # ── Quick Status ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Statut global Hermes SEO")

    from datetime import datetime
    total_agents = 28 + 11 + 23 + 11 + 18 + 18  # P1 + P2 + P3 + P4 + P5 + P6
    pipelines_en_prod = 6
    pipelines_total = 7

    q1, q2, q3, q4, q5 = st.columns(5)
    with q1: st.metric("Pipelines en prod", f"{pipelines_en_prod}/{pipelines_total}")
    with q2: st.metric("Agents", total_agents)
    with q3: st.metric("Connecteurs", total_api)
    with q4: st.metric("Outils OSS", "10")
    with q5: st.metric("Date", datetime.now().strftime("%d/%m/%Y"))

    # ── Observability ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Observability Layer")

    try:
        from hermes.core.strategie_db import get_db_stats as get_strategie_stats
        s5_stats = get_strategie_stats()
    except Exception:
        s5_stats = {}

    try:
        from hermes.core.serp_db import get_db_stats as get_serp_stats
        s4_stats = get_serp_stats()
    except Exception:
        s4_stats = {}

    try:
        from hermes.core.backlinks_db import get_db_stats as get_backlinks_stats
        b6_stats = get_backlinks_stats()
    except Exception:
        b6_stats = {}

    o1, o2, o3, o4 = st.columns(4)
    with o1:
        st.metric("Hermes Events (P5)", s5_stats.get("hermes_events", 0))
    with o2:
        st.metric("Backlinks (P6)", b6_stats.get("backlinks", 0))
    with o3:
        st.metric("Campagnes CRM (P6)", b6_stats.get("campaigns", 0))
    with o4:
        st.metric("Positions (P4)", s4_stats.get("positions_history", 0))

    o1b, o2b, o3b, o4b = st.columns(4)
    with o1b:
        st.metric("Predictions (P5)", s5_stats.get("predictions_history", 0))
    with o2b:
        st.metric("Sessions Strategie", s5_stats.get("strategie_sessions", 0))
    with o3b:
        st.metric("Domaines Ref. (P6)", b6_stats.get("referring_domains", 0))
    with o4b:
        st.metric("Opportunites (P6)", b6_stats.get("backlink_opportunities", 0))

    st.caption("Tables SQLite : hermes_events, predictions_history, strategie_sessions, "
               "serp_visibility (7 tables), backlinks (10 tables).")
