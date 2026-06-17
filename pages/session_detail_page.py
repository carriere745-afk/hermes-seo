"""Page Session Detail — Vue detaillee d'une session Hermes SEO.

Affiche scores, strategie editoriale, contenu, logs et budget.
"""

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from hermes.core.archive_service import ArchiveService
from hermes.core.exceptions import SessionNotFoundError
from hermes.config import SESSION_DIRECTORY
from hermes.models.archive import ExportFormat
from pages.strategy_panel import render_strategy_panel


def _load_raw_session(session_id: str) -> dict | None:
    """Charge la session JSON brute pour les donnees strategiques."""
    path = SESSION_DIRECTORY / f"{session_id}.json"
    if not path.exists():
        archive_path = SESSION_DIRECTORY.parent / "archive" / "sessions" / f"{session_id}.json.gz"
        if archive_path.exists():
            import gzip
            return json.loads(gzip.decompress(archive_path.read_bytes()))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def render_session_detail(session_id: str) -> None:
    """Affiche le detail complet d'une session."""
    services = ArchiveService()

    # Back button
    if st.button("← Retour a l'Archive"):
        st.session_state.selected_session_id = None
        st.rerun()

    try:
        detail = services.get_session_detail(session_id)
    except SessionNotFoundError:
        st.error(f"Session `{session_id}` introuvable.")
        return

    # ─── Header ────────────────────────────────────────────────────
    st.markdown(f"## {detail.keyword or '(sans mot-cle)'}")
    st.caption(f"Session: `{detail.session_id}`")

    col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)
    with col_h1:
        status_badge = {
            "completed": "✅ Termine",
            "failed": "❌ Echoue",
            "running": "🔄 En cours",
            "created": "⬜ Cree",
        }.get(detail.status, detail.status)
        st.markdown(f"**Statut**: {status_badge}")
    with col_h2:
        st.markdown(f"**Mode**: {detail.config.get('mode', '?')}")
    with col_h3:
        secteur = detail.config.get("secteur") or "generaliste"
        st.markdown(f"**Secteur**: {secteur}")
    with col_h4:
        if detail.duration_seconds:
            mins = detail.duration_seconds // 60
            secs = detail.duration_seconds % 60
            st.markdown(f"**Duree**: {mins}m{secs}s")
        else:
            st.markdown("**Duree**: -")
    with col_h5:
        if detail.created_at:
            st.markdown(
                f"**Creee**: {detail.created_at.strftime('%d/%m %H:%M') if hasattr(detail.created_at, 'strftime') else str(detail.created_at)[:16]}"
            )

    # Action buttons
    ca1, ca2, ca3, ca4, ca5 = st.columns(5)
    with ca1:
        if st.button("🔄 Replay (dry-run)", use_container_width=True):
            st.info(
                f"Replay lance. Utilisez le CLI: `python -m hermes.main replay --session-id {session_id}`"
            )
    with ca2:
        fmt = st.selectbox(
            "Format", ["json", "csv", "markdown"], key="export_fmt_det"
        )
    with ca3:
        data = services.export_session(session_id, ExportFormat(fmt))
        ext = "md" if fmt == "markdown" else fmt
        st.download_button(
            "📥 Exporter",
            data=data,
            file_name=f"{session_id}.{ext}",
            mime="application/json" if fmt == "json" else "text/csv",
            use_container_width=True,
        )
    with ca4:
        if st.button("📦 Archiver", use_container_width=True):
            if services.archive_session(session_id):
                st.success("Session archivee.")
                st.rerun()
            else:
                st.error("Echec de l'archivage.")
    with ca5:
        if st.button("🗑️ Supprimer", use_container_width=True, type="secondary"):
            if services.delete_session(session_id):
                st.success("Session supprimee.")
                st.session_state.selected_session_id = None
                st.rerun()
            else:
                st.error("Echec de la suppression.")

    # ─── Strategie Editoriale ──────────────────────────────────────
    raw = _load_raw_session(session_id)
    if raw:
        render_strategy_panel(raw)

    st.markdown("---")

    # ─── Scores qualite ────────────────────────────────────────────
    scores = detail.scores
    if scores:
        st.markdown("### Scores Qualite")

        sc1, sc2, sc3, sc4 = st.columns(4)
        score_total = scores.get("score_total", 0)
        seuil = scores.get("seuil_publication", 75)
        seuil_ok = scores.get("seuil_atteint", False)

        with sc1:
            color = (
                "green" if score_total >= 80
                else "orange" if score_total >= 65
                else "red"
            )
            st.markdown(
                f"**Score Global**  \n:{color}[**{score_total}/100**]  \nSeuil: {seuil}"
            )
        with sc2:
            verdict = "✅ Publiable" if seuil_ok else "❌ A corriger"
            st.markdown(f"**Decision**  \n{verdict}")
        with sc3:
            eeat = detail.scores.get("score_eeat", {})
            if isinstance(eeat, dict):
                st.markdown(
                    f"**Score EEAT**  \n**{eeat.get('score_global', '?')}**/16"
                )
            else:
                st.markdown("**Score EEAT**  \nN/A")
        with sc4:
            fiab = detail.scores.get("score_fiabilite", detail.scores.get("fiabilite", "?"))
            st.markdown(f"**Fiabilite**  \n**{fiab}**/10")

        # Criteres detailles
        with st.expander("Detail des 9 criteres"):
            grille = scores.get("scores", {})
            criteres = [
                ("Lisibilite", grille.get("lisibilite", 0), 10),
                ("Densite semantique", grille.get("densite_semantique", 0), 15),
                ("Reponse aux PAA", grille.get("reponse_paa", 0), 20),
                ("Originalite", grille.get("originalite", 0), 15),
                ("Fraicheur des sources", grille.get("fraicheur", 0), 10),
                ("Respect AEO", grille.get("respect_aeo", 0), 10),
                ("Respect GEO", grille.get("respect_geo", 0), 10),
                ("Absence d'erreurs", grille.get("absence_erreurs", 0), 6),
                ("Naturalite", grille.get("naturalite", 0), 4),
            ]
            for nom, valeur, max_val in criteres:
                pct = valeur / max_val if max_val else 0
                bar_color = "green" if pct >= 0.7 else ("orange" if pct >= 0.4 else "red")
                st.markdown(
                    f'<div style="display:flex;align-items:center;margin:0.3rem 0;">'
                    f'<span style="width:180px;">{nom}</span>'
                    f'<div style="flex:1;background:#e0e0e0;border-radius:8px;height:20px;">'
                    f'<div style="width:{pct*100}%;background:{bar_color};border-radius:8px;height:20px;"></div>'
                    f'</div>'
                    f'<span style="width:60px;text-align:right;">{valeur}/{max_val}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Recommandations et blocages
        verifications = scores.get("verifications_humaines", [])
        if verifications:
            st.markdown("#### Points a verifier")
            for v in verifications:
                st.markdown(f"- {v}")

        blocages = scores.get("blocages", [])
        if blocages:
            st.markdown("#### Blocages")
            for b in blocages:
                st.error(b)

    # ─── Agents ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Agents executes")

    if detail.agents:
        total_tokens = sum(a.tokens_input or 0 for a in detail.agents)
        total_cost = sum(a.cost_estimated or 0 for a in detail.agents)

        for agent in detail.agents:
            icon = {
                "completed": "✅",
                "skipped_auto": "⏭️",
                "skipped_user": "⏭️",
                "failed": "❌",
                "pending": "⬜",
                "running": "🔄",
            }.get(agent.status, "⬜")

            expander_label = (
                f"{icon} {agent.agent_name} — {agent.status}"
            )
            if agent.error_message:
                expander_label += f" — {agent.error_message[:60]}"

            with st.expander(expander_label):
                col_a1, col_a2, col_a3, col_a4 = st.columns(4)
                with col_a1:
                    st.caption(f"Duree: {agent.duration_ms or '-'} ms")
                with col_a2:
                    st.caption(
                        f"Tokens: {agent.tokens_input or 0}+{agent.tokens_output or 0}"
                    )
                with col_a3:
                    st.caption(f"Cout: ${agent.cost_estimated or 0:.4f}")
                with col_a4:
                    st.caption(
                        f"Modele: {agent.model_used or '-'} | Prompt: {agent.prompt_version or '-'}"
                    )

                if agent.error_message:
                    st.error(agent.error_message)
                if agent.skip_reason:
                    st.info(f"Raison skip: {agent.skip_reason}")

        # Resume agents
        st.markdown(
            f"**Total**: {total_tokens:,} tokens | ${total_cost:.4f}"
        )
    else:
        st.caption("Aucun agent execute.")

    # ─── Budget ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Budget")
    budget = detail.budget_summary
    if budget:
        cb1, cb2, cb3 = st.columns(3)
        with cb1:
            st.metric("Tokens utilises", f"{budget.get('tokens_used', 0):,}")
        with cb2:
            st.metric("Cout", f"${budget.get('cost_used', 0):.4f}")
        with cb3:
            pct = budget.get("cost_pct", 0)
            st.metric(
                "% du budget",
                f"{pct}%",
                delta="OK" if pct < 100 else "DEPASSE",
            )

    # ─── Logs ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Logs d'execution")

    if detail.log_events:
        with st.expander(f"Voir les {len(detail.log_events)} evenements", expanded=False):
            for evt in detail.log_events:
                level_icon = {"INFO": "ℹ️", "ERROR": "❌", "WARNING": "⚠️"}.get(
                    evt.level, "•"
                )
                st.markdown(
                    f"{level_icon} `{evt.timestamp}` **{evt.event}** "
                    f"— {evt.agent_name}"
                )
                if evt.error:
                    st.caption(f"Erreur: {evt.error}")
                if evt.duration_ms or evt.tokens_input:
                    st.caption(
                        f"Duree: {evt.duration_ms}ms | "
                        f"Tokens: {evt.tokens_input}+{evt.tokens_output} | "
                        f"Cout: ${evt.cost_estimated:.4f}"
                    )
    else:
        st.caption("Aucun log trouve pour cette session.")

    # ─── Contenu ───────────────────────────────────────────────────
    # ─── Contenu ───────────────────────────────────────────────────
    raw = _load_raw_session(session_id)
    html_content = (raw or {}).get("brouillon_html", "") if raw else ""
    if not html_content:
        html_content = detail.content_preview or ""

    if html_content:
        st.markdown("---")
        st.markdown("### Contenu genere")

        # Option 1: Rendu HTML direct dans le navigateur
        st.html(html_content)

        # Option 2: Telechargement en 1 clic
        seo = (raw or {}).get("seo_data") or {}
        title = seo.get("title_optimise", detail.keyword)
        meta = seo.get("meta_description_optimise", "")
        full_html = (
            f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
            f'<title>{title}</title>'
            f'<meta name="description" content="{meta}">'
            f'<style>body{{max-width:800px;margin:auto;padding:20px;'
            f'font-family:Georgia,serif;font-size:18px;line-height:1.8;color:#222}}'
            f'h1{{font-size:2rem;margin:1em 0 .5em}}h2{{font-size:1.4rem;margin:1.5em 0 .5em}}'
            f'h3{{font-size:1.1rem;margin:1em 0 .3em}}'
            f'blockquote{{border-left:4px solid #ddd;padding-left:1em;color:#555}}'
            f'ul{{padding-left:1.5em}}li{{margin:.3em 0}}'
            f'</style></head><body>{html_content}</body></html>'
        )
        st.download_button(
            "Telecharger l'article HTML",
            data=full_html,
            file_name=f"{detail.keyword.replace(' ', '-') or 'article'}.html",
            mime="text/html",
            use_container_width=True,
        )
