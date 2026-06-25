"""Page Outils SEO Gratuits — Lead Generation pour Hermes SEO SaaS.

12+ outils SEO gratuits. Limites volontaires pour upsell vers la suite complete.
Accessible sans login (freemium).
"""

import asyncio
import streamlit as st
from hermes.tools.free_seo_tools import TOOLS_REGISTRY


def render_free_tools_page():
    st.markdown('<p style="font-size:1.8rem;font-weight:700;">Outils SEO Gratuits</p>', unsafe_allow_html=True)
    st.caption("12+ outils SEO, AEO et GEO gratuits. Sans inscription. Pour des analyses avancees, decouvrez Hermes SEO Pro.")

    # Tool selector
    categories = {"all-in-one": "Tout-en-un", "on-page": "On-Page SEO",
                  "content": "Contenu", "technical": "Technique"}
    selected_cat = st.selectbox("Categorie", ["Tous"] + list(categories.values()),
                                key="tool_cat")

    # Filter tools
    tools = []
    for tool_id, tool in TOOLS_REGISTRY.items():
        cat_name = categories.get(tool["category"], tool["category"])
        if selected_cat == "Tous" or cat_name == selected_cat:
            tools.append((tool_id, tool))

    # Display tools as cards
    cols = st.columns(2)
    for i, (tool_id, tool) in enumerate(tools):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"### {tool['icon']} {tool['name']}")
                st.caption(tool["description"])
                if st.button(f"Lancer {tool['name']}", key=f"use_{tool_id}", use_container_width=True):
                    st.session_state.active_tool = tool_id
                    st.rerun()

    # Active tool
    active_id = st.session_state.get("active_tool")
    if active_id and active_id in TOOLS_REGISTRY:
        tool = TOOLS_REGISTRY[active_id]
        st.markdown("---")
        st.markdown(f"## {tool['icon']} {tool['name']}")

        # Input based on tool
        if active_id == "serp_preview":
            with st.form("serp_form"):
                title = st.text_input("Meta Title", "Mon article SEO optimise | Mon Site",
                                     help="50-60 caracteres recommandes")
                desc = st.text_area("Meta Description", "Decouvrez notre guide complet sur le SEO. Conseils pratiques, exemples et astuces pour ameliorer votre referencement naturel.",
                                   help="120-155 caracteres recommandes")
                url = st.text_input("URL", "https://www.example.com/article-seo")
                if st.form_submit_button("Generer l'apercu SERP", type="primary"):
                    result = tool["function"](title, desc, url)
                    st.markdown("### Apercu dans Google")
                    st.markdown(result["preview_html"], unsafe_allow_html=True)
                    st.metric("Score", f'{result["score"]}/100')
                    for r in result["recommendations"]:
                        st.info(r)

        elif active_id == "word_counter":
            text = st.text_area("Collez votre texte ici", height=300,
                               placeholder="Collez votre contenu pour analyse...")
            if st.button("Analyser le texte", type="primary"):
                if text:
                    result = tool["function"](text)
                    c1, c2, c3, c4 = st.columns(4)
                    with c1: st.metric("Mots", result["words"])
                    with c2: st.metric("Caracteres", result["chars"])
                    with c3: st.metric("Phrases", result["sentences"])
                    with c4: st.metric("Paragraphes", result["paragraphs"])
                    st.info(f"Temps de lecture: {result['reading_time']} | "
                           f"Mots/phrase: {result['avg_words_per_sentence']}")
                    st.caption(result["appreciation"])
                    if result["keyword_density"]:
                        st.markdown("**Mots-cles principaux:**")
                        for kw in result["keyword_density"][:8]:
                            st.markdown(f"- **{kw['word']}**: {kw['count']}x ({kw['density']}%)")

        elif active_id == "heading_structure":
            input_mode = st.radio("Source", ["URL", "HTML"], horizontal=True)
            if input_mode == "URL":
                url = st.text_input("URL de la page", "https://")
                if st.button("Analyser les headings", type="primary"):
                    result = tool["function"](url, is_url=True)
                    _display_heading_result(result)
            else:
                html = st.text_area("HTML de la page", height=200)
                if st.button("Analyser les headings", type="primary"):
                    result = tool["function"](html, is_url=False)
                    _display_heading_result(result)

        elif active_id == "schema_generator":
            schema_type = st.selectbox("Type de schema", ["FAQ", "Article", "LocalBusiness", "Product", "Breadcrumb"])
            import json as _json
            if schema_type == "FAQ":
                questions = st.text_area("Questions (une par ligne)", "Comment faire ?\nPourquoi est-ce important ?\nOu trouver ?")
                if st.button("Generer le schema FAQ"):
                    qlist = [q.strip() for q in questions.split("\n") if q.strip()]
                    schema = tool["function"](qlist)
                    st.code(_json.dumps(schema, indent=2, ensure_ascii=False), language="json")
            elif schema_type == "Article":
                title = st.text_input("Titre de l'article")
                author = st.text_input("Auteur")
                if st.button("Generer le schema Article"):
                    from hermes.tools.free_seo_tools import generate_schema_article
                    schema = generate_schema_article(title, author)
                    st.code(_json.dumps(schema, indent=2, ensure_ascii=False), language="json")
            elif schema_type == "LocalBusiness":
                name = st.text_input("Nom de l'entreprise")
                address = st.text_input("Adresse")
                phone = st.text_input("Telephone")
                if st.button("Generer le schema LocalBusiness"):
                    from hermes.tools.free_seo_tools import generate_schema_local_business
                    schema = generate_schema_local_business(name, address, phone)
                    st.code(_json.dumps(schema, indent=2, ensure_ascii=False), language="json")

        elif active_id == "robots_generator":
            domain = st.text_input("Domaine", "example.com")
            sitemap_url = st.text_input("URL du sitemap", "https://example.com/sitemap.xml")
            if st.button("Generer robots.txt"):
                result = tool["function"](domain, sitemap_url)
                st.code(result, language="text")
                st.download_button("Telecharger robots.txt", result, "robots.txt", "text/plain")

        elif active_id == "meta_analyzer":
            url = st.text_input("URL a analyser", "https://www.example.com")
            if st.button("Analyser les meta tags", type="primary"):
                with st.spinner("Analyse en cours..."):
                    result = asyncio.run(tool["function"](url))
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.metric("Score", f'{result["score"]}/100')
                    st.markdown(f"**Title** ({result['title_length']} chars): {result['title']}")
                    st.markdown(f"**Meta Description** ({result['meta_desc_length']} chars): {result['meta_description']}")
                    st.markdown(f"**H1**: {result['h1']} ({result['h1_count']} trouve(s))")
                    for issue in result["issues"]:
                        st.warning(issue)

        elif active_id == "keyword_density":
            text = st.text_area("Texte a analyser", height=200)
            kw = st.text_input("Mot-cle cible")
            if st.button("Analyser la densite"):
                result = tool["function"](text, kw)
                st.metric("Densite du mot-cle cible", f'{result["keyword_density"]}%')
                st.caption(result["appreciation"])
                st.markdown("**Top mots-cles:**")
                for kd in result["top_keywords"][:8]:
                    st.markdown(f"- **{kd['word']}**: {kd['count']}x ({kd['density']}%)")

        elif active_id in ("ssl_checker", "url_analyzer", "internal_links", "mobile_friendly", "quick_score"):
            url = st.text_input("URL a analyser", "https://www.example.com")
            if st.button(f"Lancer {tool['name']}", type="primary"):
                with st.spinner("Analyse en cours..."):
                    if tool["async"]:
                        result = asyncio.run(tool["function"](url))
                    else:
                        result = tool["function"](url)
                if isinstance(result, dict):
                    if "error" in result:
                        st.error(result["error"])
                    elif "score" in result:
                        st.metric("Score", f'{result["score"]}/100' if isinstance(result["score"], int) else f'{result["score"]}')
                    for k, v in result.items():
                        if k not in ("error", "score") and isinstance(v, (str, int, float)):
                            st.markdown(f"**{k}**: {v}")
                    if "issues" in result:
                        for issue in result["issues"]:
                            st.warning(issue)
                else:
                    st.code(str(result))

    # Upsell
    st.markdown("---")
    st.info("**Passez a Hermes SEO Pro** pour des analyses completes: 7 pipelines, 109+ agents, audits techniques, strategie editoriale, backlinks, et plus. [Decouvrir Hermes SEO Pro →](#)")


def _display_heading_result(result):
    if "error" in result:
        st.error(result["error"])
        return
    st.metric("Score", f'{result["score"]}/100')
    st.metric("Total headings", result["total_headings"])
    for level in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        if result["headings"][level]:
            st.markdown(f"**{level.upper()}** ({len(result['headings'][level])})")
            for h in result["headings"][level][:10]:
                st.markdown(f"- {h}")
    for issue in result["issues"]:
        st.warning(issue)
