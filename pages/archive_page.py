"""Page Archive — Historique, recherche, statistiques et gestion des sessions.

Quatre onglets : Dashboard, Sessions, Budget, Timeline.
"""

from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

from hermes.core.archive_service import ArchiveService
from hermes.models.archive import (
    BudgetSnapshot,
    ExportFormat,
    MetaArchiveEntry,
    RetentionPolicy,
    SessionFilter,
    TimelineEntry,
)
from hermes.models.common import QualityMode, SessionStatus


def render_archive_page() -> None:
    """Point d'entree de la page Archive."""
    services = ArchiveService()
    st.markdown(
        '<p style="font-size:1.8rem;font-weight:700;">Archive & Historique</p>',
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Dashboard", "Sessions", "Budget", "Timeline"]
    )

    with tab1:
        _render_dashboard(services)
    with tab2:
        _render_sessions_list(services)
    with tab3:
        _render_budget(services)
    with tab4:
        _render_timeline(services)


# ─── Dashboard ──────────────────────────────────────────────────────────

def _render_dashboard(services: ArchiveService) -> None:
    """Onglet Dashboard : KPIs, graphiques, resume."""
    stats = services.get_stats()

    if stats.total_sessions == 0:
        st.info("Aucune session pour le moment. Lancez un pipeline pour commencer.")
        return

    # Periode
    if stats.period_start and stats.period_end:
        st.caption(
            f"Periode : {stats.period_start.strftime('%d/%m/%Y')} → "
            f"{stats.period_end.strftime('%d/%m/%Y')}"
        )

    # KPI cards
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.metric("Sessions", stats.total_sessions)
    with kpi2:
        st.metric("Terminees", stats.total_completed)
    with kpi3:
        st.metric("Echecs", stats.total_failed)
    with kpi4:
        st.metric(
            "Score moyen",
            f"{stats.average_score}/100" if stats.average_score else "N/A",
        )
    with kpi5:
        st.metric("Cout total", f"${stats.total_cost:.2f}")
    with kpi6:
        success = (
            round(stats.total_completed / stats.total_sessions * 100)
            if stats.total_sessions
            else 0
        )
        st.metric("Reussite", f"{success}%")

    st.markdown("---")

    # Graphiques
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Sessions par jour")
        if stats.sessions_per_day:
            data = {
                d["date"]: d["count"] for d in stats.sessions_per_day[-60:]
            }
            st.bar_chart(data, height=250)
        else:
            st.caption("Pas assez de donnees.")

    with col2:
        st.markdown("#### Par statut")
        if stats.sessions_by_status:
            st.bar_chart(stats.sessions_by_status, height=250)

    col3, col4 = st.columns(2)
    with col3:
        st.markdown("#### Par mode")
        if stats.sessions_by_mode:
            st.bar_chart(stats.sessions_by_mode, height=200)

    with col4:
        st.markdown("#### Top keywords")
        if stats.top_keywords:
            for kw in stats.top_keywords[:10]:
                st.markdown(
                    f"- **{kw['keyword']}** — Score: {kw['score']}/100"
                )
        else:
            st.caption("Pas de scores disponibles.")

    # Resume par secteur
    with st.expander("Par secteur"):
        if stats.sessions_by_secteur:
            for secteur, count in sorted(
                stats.sessions_by_secteur.items(), key=lambda x: x[1], reverse=True
            ):
                st.markdown(f"- {secteur}: {count} sessions")

    # Tour de rein
    st.markdown("---")
    st.caption(
        f"Tokens totaux: {stats.total_tokens:,} | "
        f"Cout estime (hors dry-run): ${stats.budget_used_total:.4f} | "
        f"Archives: {stats.total_archived}"
    )


# ─── Sessions ───────────────────────────────────────────────────────────

def _render_sessions_list(services: ArchiveService) -> None:
    """Onglet Sessions : liste filtrable, paginee, avec actions."""
    st.markdown("### Toutes les sessions")

    # Filtres
    with st.expander("Filtres", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            search = st.text_input("Recherche", placeholder="Mot-cle ou ID...")
        with col_f2:
            status_filter = st.multiselect(
                "Statut",
                options=[s.value for s in SessionStatus],
                default=[],
            )
        with col_f3:
            mode_filter = st.multiselect(
                "Mode",
                options=[m.value for m in QualityMode],
                default=[],
            )

        col_f4, col_f5, col_f6 = st.columns(3)
        with col_f4:
            min_score = st.slider("Score minimum", 0, 100, 0, step=5)
        with col_f5:
            only_failed = st.checkbox("Echecs uniquement")
        with col_f6:
            page_size = st.selectbox("Par page", [20, 50, 100], index=1)

    # Construire le filtre
    filter_obj = SessionFilter(
        search=search or None,
        status=(
            [SessionStatus(s) for s in status_filter] if status_filter else None
        ),
        mode=([QualityMode(m) for m in mode_filter] if mode_filter else None),
        min_score=min_score if min_score > 0 else None,
        only_failed=only_failed,
        page_size=page_size,
    )

    # Pagination
    page_num = st.number_input("Page", min_value=1, value=1, step=1)
    filter_obj.page = page_num

    result = services.list_sessions(filter_obj)

    if not result.items:
        st.info("Aucune session ne correspond aux filtres.")
        return

    # Tableau
    st.caption(f"{result.total} sessions trouvees | Page {result.page}/{result.total_pages}")

    # Header
    hcol1, hcol2, hcol3, hcol4, hcol5, hcol6, hcol7 = st.columns(
        [3, 1.5, 1, 1, 1.2, 1, 1.5]
    )
    hcol1.markdown("**Mot-cle**")
    hcol2.markdown("**Statut**")
    hcol3.markdown("**Mode**")
    hcol4.markdown("**Score**")
    hcol5.markdown("**Cout**")
    hcol6.markdown("**Tokens**")
    hcol7.markdown("**Date**")

    for entry in result.items:
        col1, col2, col3, col4, col5, col6, col7 = st.columns(
            [3, 1.5, 1, 1, 1.2, 1, 1.5]
        )
        with col1:
            st.markdown(
                f"[{entry.keyword or '(sans mot-cle)'}](?session_id={entry.session_id})"
            )
        with col2:
            badge = {
                "completed": "✅",
                "failed": "❌",
                "running": "🔄",
                "created": "⬜",
            }.get(entry.status, "⬜")
            st.markdown(f"{badge} {entry.status}")
        with col3:
            st.caption(entry.mode)
        with col4:
            if entry.score_total is not None:
                color = (
                    "green" if entry.score_total >= 75 else "orange"
                    if entry.score_total >= 50 else "red"
                )
                st.markdown(f":{color}[{entry.score_total}/100]")
            else:
                st.caption("-")
        with col5:
            st.caption(f"${entry.total_cost:.3f}")
        with col6:
            st.caption(str(entry.total_tokens))
        with col7:
            created = entry.created_at
            if created:
                st.caption(created.strftime("%d/%m %H:%M") if hasattr(created, "strftime") else str(created)[:16])
            else:
                st.caption("-")

    st.markdown("---")

    # Pagination controls
    pc1, pc2, pc3 = st.columns([1, 2, 1])
    with pc1:
        if result.has_prev:
            if st.button("← Page precedente"):
                st.session_state.arch_page = result.page - 1
                st.rerun()
    with pc2:
        st.caption(f"Page {result.page} / {result.total_pages}")
    with pc3:
        if result.has_next:
            if st.button("Page suivante →"):
                st.session_state.arch_page = result.page + 1
                st.rerun()

    # Bulk actions
    st.markdown("#### Actions")
    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        if st.button("🔄 Reconstruire l'index"):
            services._rebuild_index()
            st.success("Index reconstruit.")
    with ac2:
        export_format = st.selectbox(
            "Format export", ["json", "csv"], key="bulk_export_fmt"
        )
    with ac3:
        if st.button("📥 Exporter toutes (filtrees)"):
            data = services.export_filtered(
                filter_obj, ExportFormat(export_format)
            )
            st.download_button(
                "Telecharger",
                data=data,
                file_name=f"sessions_export.{export_format}",
                mime="application/json" if export_format == "json" else "text/csv",
            )

    # Nettoyage
    with st.expander("Nettoyage & Retention"):
        st.markdown("**Politique de retention**")
        days_archive = st.number_input(
            "Archiver apres (jours)", 1, 365, 30
        )
        days_delete = st.number_input(
            "Supprimer apres (jours)", 1, 730, 365
        )
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("📋 Simuler (dry-run)"):
                policy = RetentionPolicy(
                    archive_after_days=days_archive,
                    delete_after_days=days_delete,
                )
                result_rp = services.run_retention_policy(policy, dry_run=True)
                st.info(
                    f"A archiver: {len(result_rp['to_archive'])} sessions\n\n"
                    f"A supprimer: {len(result_rp['to_delete'])} sessions"
                )
        with col_p2:
            if st.button("⚠️ Executer la retention", type="primary"):
                policy = RetentionPolicy(
                    archive_after_days=days_archive,
                    delete_after_days=days_delete,
                )
                result_rp = services.run_retention_policy(policy, dry_run=False)
                st.success(
                    f"Archives: {len(result_rp['archived'])} | "
                    f"Supprimes: {len(result_rp['deleted'])}"
                )


# ─── Budget ─────────────────────────────────────────────────────────────

def _render_budget(services: ArchiveService) -> None:
    """Onglet Budget : historique des couts et tokens."""
    history = services.get_budget_history(limit=200)

    if not history:
        st.info("Aucune donnee budget pour le moment.")
        return

    # Graphique cout cumule
    st.markdown("### Cout cumule")
    cumul = 0.0
    dates = []
    costs = []
    for snap in reversed(history):
        cumul += snap.total_cost
        if snap.created_at:
            dates.append(
                snap.created_at.strftime("%d/%m")
                if hasattr(snap.created_at, "strftime")
                else str(snap.created_at)[:10]
            )
        else:
            dates.append("?")
        costs.append(round(cumul, 4))

    if dates and costs:
        st.line_chart(
            {"Cout cumule ($)": costs},
            height=250,
        )
        st.caption(f"Cout total: ${cumul:.4f}")

    # Tableau detail
    st.markdown("### Historique detaille")
    table_data = []
    for snap in history[:100]:
        date_str = (
            snap.created_at.strftime("%d/%m/%Y %H:%M")
            if snap.created_at and hasattr(snap.created_at, "strftime")
            else str(snap.created_at)[:19] if snap.created_at else "?"
        )
        table_data.append(
            {
                "Date": date_str,
                "Mot-cle": snap.keyword,
                "Tokens": snap.total_tokens,
                "Cout": f"${snap.total_cost:.4f}",
                "Mode": snap.mode,
                "Dry-run": "Oui" if snap.dry_run else "Non",
                "Score": snap.score_total if snap.score_total else "-",
            }
        )

    st.dataframe(table_data, use_container_width=True, height=400)


# ─── Timeline ────────────────────────────────────────────────────────────

def _render_timeline(services: ArchiveService) -> None:
    """Onglet Timeline : flux chronologique et meta-archivage."""
    col_tl, col_meta = st.columns([2, 1])

    with col_tl:
        st.markdown("### Evenements projet")

        event_types = st.multiselect(
            "Filtrer par type",
            options=[
                "session_created",
                "session_completed",
                "session_failed",
                "session_archived",
                "session_deleted",
                "deployment",
                "config_change",
                "milestone",
                "prompt_update",
                "budget_alert",
            ],
            default=[],
        )

        limit = st.slider("Nombre d'evenements", 10, 200, 50)
        entries = services.get_timeline(limit=limit)

        if not entries:
            st.info("Aucun evenement dans la timeline pour le moment.")
        else:
            for entry in entries:
                if event_types and entry.event_type not in event_types:
                    continue

                icon = {
                    "session_created": "🆕",
                    "session_completed": "✅",
                    "session_failed": "❌",
                    "session_archived": "📦",
                    "session_deleted": "🗑️",
                    "deployment": "🚀",
                    "config_change": "⚙️",
                    "milestone": "🏁",
                    "prompt_update": "📝",
                    "budget_alert": "💰",
                }.get(entry.event_type, "📌")

                ts = entry.timestamp
                ts_str = (
                    ts.strftime("%d/%m/%Y %H:%M:%S")
                    if hasattr(ts, "strftime")
                    else str(ts)[:19]
                )

                st.markdown(
                    f"{icon} **{ts_str}** — {entry.description}\n\n"
                    f"*{entry.event_type}*"
                )
                if entry.session_id:
                    st.caption(f"Session: `{entry.session_id}`")
                st.markdown("---")

    with col_meta:
        st.markdown("### Meta-archivage")
        st.caption("Jalons, deploiements, changements de config")

        st.markdown("#### Enregistrer un evenement")
        meta_type = st.selectbox(
            "Type",
            options=["deployment", "config_change", "milestone", "prompt_update"],
            key="meta_type",
        )
        meta_title = st.text_input("Titre", placeholder="Ex: Deploiement v0.2", key="meta_title")
        meta_desc = st.text_area("Description", placeholder="Detail de l'evenement...", key="meta_desc")
        meta_version = st.text_input("Version (optionnel)", placeholder="v0.2.0")

        if st.button("Enregistrer", key="meta_save"):
            if meta_title and meta_desc:
                entry = MetaArchiveEntry(
                    event_type=meta_type,
                    title=meta_title,
                    description=meta_desc,
                    version=meta_version or None,
                )
                services.record_meta_event(entry)
                st.success(f"Evenement enregistre : {meta_title}")

        st.markdown("---")
        st.markdown("#### Evenements enregistres")

        meta_filter = st.selectbox(
            "Type",
            options=["tous", "deployment", "config_change", "milestone", "prompt_update"],
            key="meta_filter",
        )
        meta_entries = services.get_meta_events(
            limit=30,
            event_type=None if meta_filter == "tous" else meta_filter,
        )

        for me in meta_entries:
            ts = me.timestamp
            ts_str = (
                ts.strftime("%d/%m/%Y %H:%M")
                if hasattr(ts, "strftime")
                else str(ts)[:16]
            )
            ver = f" ({me.version})" if me.version else ""
            st.markdown(
                f"**{me.title}**{ver}\n\n"
                f"{me.description}\n\n"
                f"*{ts_str}*"
            )
            st.markdown("---")
