"""Page Audit de Contenu — Streamlit UI.

5 modes d'entree : URL unique, Liste, Sitemap, Crawl, Import CSV.
Pipeline complet en 1 clic avec progression live.
Resultats : dashboard, scores par page, roadmap, export.
"""

import asyncio
from datetime import datetime

import streamlit as st

from hermes.core.audit_entry import resolve_entry_urls
from hermes.core.audit_workflow import run_audit_pipeline


def _run_audit_sync(urls, site_url, mode):
    """Wrapper synchrone pour lancer le pipeline audit."""
    return asyncio.run(run_audit_pipeline(urls=urls, site_url=site_url, mode=mode))


def render_audit_page():
    """Point d'entree de la page Audit de Contenu."""

    if "audit_done" not in st.session_state:
        st.session_state.audit_done = False
    if "audit_result" not in st.session_state:
        st.session_state.audit_result = None
    if "audit_urls" not in st.session_state:
        st.session_state.audit_urls = []

    st.markdown(
        '<p style="font-size:1.8rem;font-weight:700;">Audit de Contenu</p>',
        unsafe_allow_html=True,
    )
    st.caption("Analysez vos pages existantes sur 7 dimensions SEO / AEO / GEO / EEAT / UX.")

    # ─── Mode d'entree ──────────────────────────────────────────────────
    mode_labels = {
        "single": "URL unique",
        "list": "Liste d'URLs",
        "sitemap": "Sitemap XML (auto-detection)",
        "crawl": "Crawl BFS (page d'accueil)",
        "csv": "Import CSV",
    }
    mode_choice = st.selectbox(
        "Mode d'entree",
        options=list(mode_labels.keys()),
        format_func=lambda x: mode_labels[x],
    )

    input_value = ""
    if mode_choice == "single":
        input_value = st.text_input(
            "URL de la page a auditer",
            placeholder="https://mon-site.fr/page",
        )
    elif mode_choice == "list":
        input_value = st.text_area(
            "URLs (une par ligne)",
            placeholder="https://mon-site.fr\nhttps://mon-site.fr/blog\nhttps://mon-site.fr/contact",
        )
    elif mode_choice == "sitemap":
        input_value = st.text_input(
            "URL du site",
            placeholder="https://mon-site.fr",
            help="Le sitemap sera detecte automatiquement (robots.txt + candidats classiques)",
        )
    elif mode_choice == "crawl":
        input_value = st.text_input(
            "Page d'accueil du site",
            placeholder="https://mon-site.fr",
        )
    elif mode_choice == "csv":
        input_value = st.text_area(
            "Contenu du CSV (colonne 'url' obligatoire)",
            placeholder="url,priority\nhttps://mon-site.fr,1\nhttps://mon-site.fr/blog,2",
            help="Collez le contenu de votre fichier CSV",
        )

    # Options avancees
    with st.expander("Options avancees", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            max_urls = st.number_input(
                "Nombre max d'URLs",
                min_value=1, max_value=5000, value=50, step=10,
            )
        with col2:
            audit_mode = st.selectbox(
                "Mode qualite",
                options=["fast", "standard", "premium", "debug"],
                index=1,
            )

    # ─── Bouton ────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        launch = st.button(
            "Lancer l'audit", type="primary",
            use_container_width=True, disabled=not input_value,
        )

    # ─── Execution ──────────────────────────────────────────────────────
    if launch and input_value:
        st.session_state.audit_done = False
        st.session_state.audit_result = None

        progress_bar = st.progress(0, text="Resolution des URLs...")
        status_text = st.empty()

        result = asyncio.run(
            resolve_entry_urls(
                mode=mode_choice, input_value=input_value, max_urls=max_urls,
            )
        )

        if not result["success"]:
            st.error(result["error"])
            st.stop()

        urls = result["urls"]
        site_url = result["site_url"]
        meta = result["meta"]

        status_text.info(
            f"{len(urls)} URLs resolues ({meta.get('mode', '?')})"
        )

        if result.get("type_distribution"):
            with st.expander("Repartition des types de pages"):
                dist = result["type_distribution"]
                for pt, cnt in sorted(dist.items(), key=lambda x: x[1], reverse=True):
                    st.markdown(f"- {pt}: **{cnt}** pages")

        progress_bar.progress(0, text="Lancement du pipeline...")
        status_text.text("Audit en cours...")

        with st.spinner(""):
            start_time = datetime.now()
            audit_result = _run_audit_sync(urls, site_url, audit_mode)
            elapsed = (datetime.now() - start_time).total_seconds()

        progress_bar.progress(1.0, text="Termine !")
        status_text.success(
            f"Audit termine en {elapsed:.0f}s — "
            f"{len(audit_result.crawled_pages)} pages analysees"
        )

        st.session_state.audit_done = True
        st.session_state.audit_result = audit_result
        st.session_state.audit_urls = urls
        st.rerun()

    # ─── Resultats ──────────────────────────────────────────────────────
    if st.session_state.audit_done and st.session_state.audit_result:
        result = st.session_state.audit_result

        st.markdown("---")
        st.markdown("## Resultats de l'audit")

        total = len(result.crawled_pages)
        avg_score = int(
            sum(s.global_score for s in result.scores.values()) / max(1, len(result.scores))
        ) if result.scores else 0

        k1, k2, k3, k4 = st.columns(4)
        with k1: st.metric("Pages auditees", total)
        with k2: st.metric("Score moyen", f"{avg_score}/100")
        with k3: st.metric("Briefs generes", len(result.briefs))
        with k4: st.metric("Cannibalisation", len(result.cannibalisation))

        # Distribution
        if result.scores:
            good = sum(1 for s in result.scores.values() if s.global_score >= 75)
            ok = sum(1 for s in result.scores.values() if 50 <= s.global_score < 75)
            weak = sum(1 for s in result.scores.values() if s.global_score < 50)

            st.markdown("### Distribution")
            dc1, dc2, dc3 = st.columns(3)
            with dc1: st.metric("Excellent (>=75)", good)
            with dc2: st.metric("Bon (50-74)", ok)
            with dc3: st.metric("Faible (<50)", weak)

        # Tableau des scores
        st.markdown("### Scores par page")
        table_data = []
        for page in result.crawled_pages:
            if page.fetch_error:
                table_data.append({"URL": page.url[:70], "Global": "Erreur"})
                continue
            s = result.scores.get(page.url)
            brief = result.briefs.get(page.url)
            if not s: continue
            table_data.append({
                "URL": page.url[:70],
                "SEO": s.seo_onpage.score,
                "Qualite": s.quality.score,
                "AEO": s.aeo.score,
                "GEO": s.geo.score,
                "EEAT": f"{s.eea_t.score}/16",
                "UX": s.ux.score,
                "Transp.": s.transparency.score if getattr(s.transparency, 'score', None) else "-",
                "Global": s.global_score,
                "Action": brief.action if brief else "?",
            })

        st.dataframe(table_data, use_container_width=True)

        st.markdown("### Detail par page")
        for page in result.crawled_pages:
            if page.fetch_error: continue
            s = result.scores.get(page.url)
            brief = result.briefs.get(page.url)
            if not s: continue

            with st.expander(f"{page.url[:80]} — {s.global_score}/100"):
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                with m1: st.metric("SEO", s.seo_onpage.score)
                with m2: st.metric("Qualite", s.quality.score)
                with m3: st.metric("AEO", s.aeo.score)
                with m4: st.metric("GEO", s.geo.score)
                with m5: st.metric("EEAT", f"{s.eea_t.score}/16")
                with m6: st.metric("UX", s.ux.score)
                with m7: st.metric("Transp.", s.transparency.score)

                if brief:
                    cf1, cf2 = st.columns(2)
                    with cf1:
                        st.markdown("**Forces**")
                        for f in brief.forces[:5]:
                            st.markdown(f"- {f}")
                    with cf2:
                        st.markdown("**Faiblesses**")
                        for f in brief.faiblesses[:5]:
                            st.markdown(f"- {f}")
                    st.markdown(f"**Action recommandee :** {brief.action}")
                    if brief.recommandations:
                        st.markdown("**Recommandations :**")
                        for r in brief.recommandations[:3]:
                            st.markdown(f"- [{r.priorite}] {r.description} ({r.effort_estime})")

        # Cannibalisation
        if result.cannibalisation:
            st.markdown("---")
            st.markdown("### Cannibalisation detectee")
            for c in result.cannibalisation:
                st.warning(
                    f"**{c['page1'][:50]}** <-> **{c['page2'][:50]}** "
                    f"(similarite {c['similarite']}) -> {c['action']}"
                )

        # Roadmap
        if result.roadmap:
            st.markdown("---")
            st.markdown("### Roadmap de reecriture")
            for item in result.roadmap[:10]:
                icons = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}
                st.markdown(
                    f"[{icons.get(item['priorite'], '?')}] **{item['action']}** — "
                    f"{item['url'][:60]} — Score: {item['score']}/100"
                )

        # Export
        st.markdown("---")
        st.markdown("### Export")
        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            html = f"<html><body><h1>Audit {getattr(result, 'site_url', '')}</h1><table border=1><tr><th>URL</th><th>SEO</th><th>Global</th></tr>"
            for page in result.crawled_pages:
                if page.fetch_error: continue
                s = result.scores.get(page.url)
                if not s: continue
                html += f"<tr><td>{page.url[:80]}</td><td>{s.seo_onpage.score}</td><td>{s.global_score}</td></tr>"
            html += "</table></body></html>"
            st.download_button(
                "Telecharger HTML", data=html,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.html",
                mime="text/html", use_container_width=True,
            )
        with exp_col2:
            csv = "URL,SEO,Qualite,AEO,GEO,EEAT,UX,Transparence,Global\n"
            for page in result.crawled_pages:
                if page.fetch_error: continue
                s = result.scores.get(page.url)
                if not s: continue
                t = s.transparency.score if getattr(s.transparency, 'score', None) else 0
                csv += f"{page.url},{s.seo_onpage.score},{s.quality.score},{s.aeo.score},{s.geo.score},{s.eea_t.score},{s.ux.score},{t},{s.global_score}\n"
            st.download_button(
                "Telecharger CSV", data=csv,
                file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv", use_container_width=True,
            )
