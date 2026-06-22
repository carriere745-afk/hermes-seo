"""Page Audit de Contenu — Streamlit UI.

5 modes d'entree. Pipeline complet en 1 clic.
Resultats organises en 3 vues : Sante du site, Roadmap, Detail par page.
Bouton Reecrire connecte au Pipeline Editorial.
"""

import asyncio
from datetime import datetime

import streamlit as st

from hermes.core.audit_entry import resolve_entry_urls
from hermes.core.audit_workflow import run_audit_pipeline


def _run_audit_sync(urls, site_url, mode):
    return asyncio.run(run_audit_pipeline(urls=urls, site_url=site_url, mode=mode))


def render_audit_page():
    """Point d'entree de la page Audit de Contenu."""

    if "audit_done" not in st.session_state:
        st.session_state.audit_done = False
    if "audit_result" not in st.session_state:
        st.session_state.audit_result = None

    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Audit de Contenu</p>', unsafe_allow_html=True)
    st.caption("Analysez vos pages existantes sur 7 dimensions SEO / AEO / GEO / EEAT / UX.")

    mode_labels = {
        "single": "URL unique", "list": "Liste d'URLs",
        "sitemap": "Sitemap XML (auto-detection)", "crawl": "Crawl BFS (page d'accueil)", "csv": "Import CSV",
    }
    mode_choice = st.selectbox("Mode d'entree", options=list(mode_labels.keys()), format_func=lambda x: mode_labels[x])

    input_value = ""
    if mode_choice == "single":
        input_value = st.text_input("URL de la page a auditer", placeholder="https://mon-site.fr/page")
    elif mode_choice == "list":
        input_value = st.text_area("URLs (une par ligne)", placeholder="https://mon-site.fr\nhttps://mon-site.fr/blog")
    elif mode_choice == "sitemap":
        input_value = st.text_input("URL du site", placeholder="https://mon-site.fr", help="Sitemap detecte automatiquement")
    elif mode_choice == "crawl":
        input_value = st.text_input("Page d'accueil du site", placeholder="https://mon-site.fr")
    elif mode_choice == "csv":
        input_value = st.text_area("Contenu du CSV (colonne 'url' obligatoire)", placeholder="url\nhttps://mon-site.fr", help="Collez votre CSV")

    with st.expander("Options avancees", expanded=False):
        col1, col2 = st.columns(2)
        with col1: max_urls = st.number_input("Nombre max d'URLs", min_value=1, max_value=5000, value=50, step=10)
        with col2: audit_mode = st.selectbox("Mode qualite", options=["fast", "standard", "premium", "debug"], index=1)

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1: launch = st.button("Lancer l'audit", type="primary", use_container_width=True, disabled=not input_value)

    if launch and input_value:
        st.session_state.audit_done = False
        st.session_state.audit_result = None
        progress_bar = st.progress(0, text="Resolution des URLs...")
        status_text = st.empty()
        result = asyncio.run(resolve_entry_urls(mode=mode_choice, input_value=input_value, max_urls=max_urls))
        if not result["success"]:
            st.error(result["error"]); st.stop()
        urls = result["urls"]; site_url = result["site_url"]
        status_text.info(f"{len(urls)} URLs resolues")
        progress_bar.progress(0, text="Lancement du pipeline..."); status_text.text("Audit en cours...")
        with st.spinner(""):
            start_time = datetime.now()
            audit_result = _run_audit_sync(urls, site_url, audit_mode)
            elapsed = (datetime.now() - start_time).total_seconds()
        progress_bar.progress(1.0, text="Termine !")
        status_text.success(f"Audit termine en {elapsed:.0f}s — {len(audit_result.crawled_pages)} pages analysees")
        st.session_state.audit_done = True; st.session_state.audit_result = audit_result
        st.rerun()

    # ═══════════════════════════════════════════════════════════════════
    # RESULTATS
    # ═══════════════════════════════════════════════════════════════════
    if st.session_state.audit_done and st.session_state.audit_result:
        result = st.session_state.audit_result
        st.markdown("---"); st.markdown("## Resultats de l'audit")
        total = len(result.crawled_pages)
        avg_score = int(sum(s.global_score for s in result.scores.values()) / max(1, len(result.scores))) if result.scores else 0

        # ─── VUE 1 : SANTE DU SITE ───────────────────────────────────
        st.markdown("### Sante du site")
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1: st.metric("Pages auditees", total)
        with k2: st.metric("Score moyen", f"{avg_score}/100")
        with k3: st.metric("Cannibalisation", len(result.cannibalisation))
        with k4: st.metric("Briefs prets", len(result.briefs))
        with k5: st.metric("A reecrire", sum(1 for s in result.scores.values() if s.global_score < 50))

        if result.scores:
            avg_seo = int(sum(s.seo_onpage.score for s in result.scores.values()) / len(result.scores))
            avg_qual = int(sum(s.quality.score for s in result.scores.values()) / len(result.scores))
            avg_aeo = int(sum(s.aeo.score for s in result.scores.values()) / len(result.scores))
            avg_geo = int(sum(s.geo.score for s in result.scores.values()) / len(result.scores))
            avg_eeat = int(sum(s.eea_t.score for s in result.scores.values()) / len(result.scores))
            avg_ux = int(sum(s.ux.score for s in result.scores.values()) / len(result.scores))
            d1, d2, d3, d4, d5, d6 = st.columns(6)
            with d1: st.metric("SEO", f"{avg_seo}%")
            with d2: st.metric("Qualite", f"{avg_qual}%")
            with d3: st.metric("AEO", f"{avg_aeo}%")
            with d4: st.metric("GEO", f"{avg_geo}%")
            with d5: st.metric("EEAT", f"{avg_eeat}/16")
            with d6: st.metric("UX", f"{avg_ux}%")

            good = sum(1 for s in result.scores.values() if s.global_score >= 75)
            ok = sum(1 for s in result.scores.values() if 50 <= s.global_score < 75)
            weak = sum(1 for s in result.scores.values() if s.global_score < 50)
            st.caption(f"Excellent: {good} | Bon: {ok} | Faible: {weak}")

            # Alertes
            alerts = []
            if weak > 0: alerts.append(f"{weak} page(s) a reecrire — score < 50")
            if avg_aeo < 40: alerts.append(f"AEO moyen faible ({avg_aeo}%)")
            if avg_geo < 40: alerts.append(f"GEO moyen faible ({avg_geo}%)")
            if avg_eeat < 8: alerts.append(f"EEAT insuffisant ({avg_eeat}/16)")
            if result.cannibalisation: alerts.append(f"{len(result.cannibalisation)} paire(s) cannibale(s)")
            if alerts:
                st.markdown("**Alertes :**")
                for a in alerts: st.markdown(f"- {a}")

        # ─── VUE 2 : ROADMAP ────────────────────────────────────────
        if result.roadmap:
            st.markdown("---"); st.markdown("### Roadmap priorisee")
            p1 = [r for r in result.roadmap if r["priorite"] == 1]
            p2 = [r for r in result.roadmap if r["priorite"] == 2]
            p3 = [r for r in result.roadmap if r["priorite"] == 3]
            p4 = [r for r in result.roadmap if r["priorite"] >= 4]
            if p1:
                st.error(f"**P1 — A reecrire ({len(p1)} pages)**")
                for item in p1: st.markdown(f"- {item['url'][:70]} — Score: {item['score']}/100 — {item.get('effort','?')}")
            if p2:
                st.warning(f"**P2 — A enrichir ({len(p2)} pages)**")
                for item in p2[:5]: st.markdown(f"- {item['url'][:70]} — Score: {item['score']}/100")
                if len(p2) > 5: st.caption(f"... et {len(p2)-5} autres")
            if p3:
                st.info(f"**P3 — Revisions mineures ({len(p3)} pages)**")
            if p4:
                st.success(f"**P4 — A conserver ({len(p4)} pages)**")

        # ─── VUE 3 : DETAIL PAR PAGE + BOUTON REECRIRE ──────────────
        st.markdown("---"); st.markdown("### Detail par page")
        for page in result.crawled_pages:
            if page.fetch_error: continue
            s = result.scores.get(page.url)
            brief = result.briefs.get(page.url)
            if not s: continue
            emoji = "P1" if s.global_score < 50 else "P2" if s.global_score < 75 else "P3" if s.global_score < 90 else "P4"
            with st.expander(f"[{emoji}] {page.url[:80]} — {s.global_score}/100"):
                m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
                with m1: st.metric("SEO", s.seo_onpage.score)
                with m2: st.metric("Qualite", s.quality.score)
                with m3: st.metric("AEO", s.aeo.score)
                with m4: st.metric("GEO", s.geo.score)
                with m5: st.metric("EEAT", f"{s.eea_t.score}/16")
                with m6: st.metric("UX", s.ux.score)
                with m7: st.metric("Transp.", s.transparency.score)
                # Radar chart
                import plotly.graph_objects as go
                cats = ['SEO', 'Qualite', 'AEO', 'GEO', 'EEAT', 'UX']
                vals = [s.seo_onpage.score, s.quality.score, s.aeo.score, s.geo.score, s.eea_t.score * 6.25, s.ux.score]
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=vals, theta=cats, fill='toself', line=dict(color='#1E88E5', width=2), fillcolor='rgba(30,136,229,0.2)'))
                fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], showticklabels=False)), showlegend=False, height=250, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)
                if brief:
                    cf1, cf2 = st.columns(2)
                    with cf1:
                        st.markdown("**Forces**")
                        for f in brief.forces[:5]: st.markdown(f"- {f}")
                    with cf2:
                        st.markdown("**Faiblesses**")
                        for f in brief.faiblesses[:5]: st.markdown(f"- {f}")
                    if brief.recommandations:
                        st.markdown("**Recommandations :**")
                        for r in brief.recommandations[:3]:
                            st.markdown(f"- [{r.priorite}] {r.description} ({r.effort_estime})")
                # BOUTON REECRIRE
                rcol1, rcol2 = st.columns([2, 1])
                with rcol1:
                    if st.button(f"Reecrire cette page", key=f"rw_{page.url[:60]}", use_container_width=True):
                        from hermes.agents.audit import prepare_audit_brief_for_editorial
                        brief_dict = prepare_audit_brief_for_editorial(result, page.url)
                        if brief_dict:
                            st.session_state.rewrite_brief = brief_dict
                            st.session_state.rewrite_url = page.url
                            st.session_state.nav_page = "Generator"
                            st.rerun()
                with rcol2:
                    import json as _json
                    fiche = {"url": page.url, "scores": s.model_dump(), "brief": brief.model_dump() if brief else {}}
                    st.download_button("Exporter fiche", data=_json.dumps(fiche, indent=2, ensure_ascii=False), file_name=f"audit_{page.url.split('/')[-1] or 'page'}.json", mime="application/json", key=f"exp_{page.url[:60]}")

        if result.cannibalisation:
            st.markdown("---"); st.markdown("### Cannibalisation detectee")
            for c in result.cannibalisation:
                st.warning(f"{c['page1'][:50]} <-> {c['page2'][:50]} (similarite {c['similarite']}) -> {c['action']}")

        # Export global
        st.markdown("---"); st.markdown("### Export global")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        with exp_col1:
            html = f"<html><body><h1>Audit {getattr(result, 'site_url', '')}</h1><table border=1><tr><th>URL</th><th>SEO</th><th>Global</th></tr>"
            for page in result.crawled_pages:
                if page.fetch_error: continue
                s = result.scores.get(page.url)
                if not s: continue
                html += f"<tr><td>{page.url[:80]}</td><td>{s.seo_onpage.score}</td><td>{s.global_score}</td></tr>"
            html += "</table></body></html>"
            st.download_button("Telecharger HTML", data=html, file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.html", mime="text/html", use_container_width=True)
        with exp_col2:
            csv = "URL,SEO,Qualite,AEO,GEO,EEAT,UX,Transparence,Global\n"
            for page in result.crawled_pages:
                if page.fetch_error: continue
                s = result.scores.get(page.url)
                if not s: continue
                t = s.transparency.score if getattr(s.transparency, 'score', None) else 0
                csv += f"{page.url},{s.seo_onpage.score},{s.quality.score},{s.aeo.score},{s.geo.score},{s.eea_t.score},{s.ux.score},{t},{s.global_score}\n"
            st.download_button("Telecharger CSV", data=csv, file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
        with exp_col3:
            try:
                from weasyprint import HTML as wpHTML
                pdf_html = html.replace("<table border=1", "<table border=1 style='border-collapse:collapse;width:100%'")
                pdf_bytes = wpHTML(string=pdf_html).write_pdf()
                st.download_button("Telecharger PDF", data=pdf_bytes, file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.pdf", mime="application/pdf", use_container_width=True)
            except Exception:
                st.caption("PDF: installer weasyprint")
