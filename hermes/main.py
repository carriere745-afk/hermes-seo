"""Point d'entrée CLI Hermes SEO."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click

from hermes import config
from hermes.core.exceptions import (
    HermesError,
    SkipBlockedError,
    StartupCheckError,
)
from hermes.core.logging import configure_logging
from hermes.core.session_manager import SessionManager
from hermes.models.common import AgentStatus, QualityMode, SessionStatus, generate_session_id
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.startup_check import check_and_exit


@click.group()
@click.version_option(version="0.1.0", prog_name="Hermes SEO")
def cli() -> None:
    """Hermes SEO v3 — Usine éditoriale multi-agents SEO/AEO/GEO."""
    pass


@cli.command()
@click.option("--keyword", "-k", required=True, help="Mot-clé cible")
@click.option("--site-url", "-s", default="", help="URL du site cible")
@click.option("--objectif", "-o", default="", help="Objectif éditorial")
@click.option("--mode", "-m", default="standard",
              type=click.Choice(["fast", "standard", "premium", "compliance", "debug"]),
              help="Mode qualité")
@click.option("--secteur", default="autre", help="Secteur d'activité")
@click.option("--dry-run", is_flag=True, help="Mode simulation sans appel API")
@click.option("--skip", "-x", multiple=True, help="Agents à ignorer (répétable)")
@click.option("--token-budget", type=int, default=config.DEFAULT_TOKEN_BUDGET,
              help="Budget max en tokens")
@click.option("--cost-budget", type=float, default=config.DEFAULT_COST_BUDGET,
              help="Budget max en USD")
@click.option("--yes", is_flag=True, help="Confirmer automatiquement les skips")
def run(
    keyword: str,
    site_url: str,
    objectif: str,
    mode: str,
    secteur: str,
    dry_run: bool,
    skip: tuple[str, ...],
    token_budget: int,
    cost_budget: float,
    yes: bool,
) -> None:
    """Lance un pipeline complet pour un mot-clé."""
    # Startup check
    require_serp = not dry_run and mode != "fast"
    check_and_exit(require_llm=not dry_run, require_serp=require_serp)

    # Construire la session
    session = SessionState(
        config=SessionConfig(
            mode=QualityMode(mode),
            dry_run=dry_run,
            token_budget=token_budget,
            cost_budget=cost_budget,
            target_url=site_url or None,
            secteur=secteur,
            user_skipped_agents=list(skip),
            skip_confirmed=yes,
        ),
        keyword=keyword,
        site_url=site_url or None,
        objectif=objectif or None,
    )

    # Configurer les logs
    configure_logging(session.session_id)

    # Exécuter le pipeline
    session_manager = SessionManager(config.SESSION_DIRECTORY)
    asyncio.run(_run_pipeline(session, session_manager))


async def _run_pipeline(session: SessionState, session_manager: SessionManager) -> None:
    """Exécute le pipeline complet."""
    from hermes.core.workflow import get_active_agents
    from hermes.core.transitions import should_skip_agent, get_skip_warning
    from hermes.core.logging import (
        log_agent_start, log_agent_completed, log_agent_failed, log_agent_skipped,
    )
    from hermes.core.budget import BudgetTracker
    from hermes.agents import AGENT_REGISTRY
    from hermes.core.exceptions import SkipBlockedError
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.panel import Panel

    console = Console()

    # Afficher l'en-tête
    console.print(Panel.fit(
        f"[bold]Hermes SEO v3[/bold]\n"
        f"Mot-clé : [cyan]{session.keyword}[/cyan]\n"
        f"Mode : [yellow]{session.config.mode.value}[/yellow] | "
        f"Budget : {session.config.token_budget:,} tokens / ${session.config.cost_budget:.2f}\n"
        f"Dry-run : {'[red]ON[/red]' if session.config.dry_run else '[green]OFF[/green]'} | "
        f"Session : [dim]{session.session_id}[/dim]",
        title="Session démarrée",
    ))

    # Calculer les agents actifs
    has_existing = False
    if "agent_08" not in session.config.user_skipped_agents:
        try:
            from hermes.core.memory import MemoryStore
            mem = MemoryStore(config.CHROMA_PERSIST_DIRECTORY)
            has_existing = mem.has_existing_content()
        except Exception:
            pass

    active_agents = get_active_agents(
        mode=session.config.mode,
        secteur=session.config.secteur,
        user_skipped=list(session.config.user_skipped_agents),
        has_existing_content=has_existing,
        has_locale_target=bool(session.config.target_locales),
    )

    # Vérifier les skips non autorisés
    non_skippable = {"agent_00", "agent_01", "agent_04", "agent_07", "agent_15", "agent_25"}
    if session.config.mode != QualityMode.DEBUG:
        illegal = set(session.config.user_skipped_agents) & non_skippable
        if illegal:
            raise SkipBlockedError(list(illegal)[0])

    budget = BudgetTracker(
        token_budget=session.config.token_budget,
        cost_budget=session.config.cost_budget,
    )

    # Tableau de progression
    table = Table(title="Progression du pipeline")
    table.add_column("Agent", style="cyan")
    table.add_column("Statut", style="yellow")
    table.add_column("Durée", style="dim")
    table.add_column("Tokens", style="green")
    table.add_column("Coût", style="magenta")

    # Initialiser tous les résultats
    for agent_id in active_agents:
        session.agent_results[agent_id] = AgentResult(
            agent_id=agent_id,
            agent_name=agent_id.replace("_", " ").title(),
            status=AgentStatus.PENDING,
        )

    with Live(table, console=console, refresh_per_second=4) as live:
        for agent_id in active_agents:
            # Mettre à jour l'affichage
            session.current_agent_id = agent_id
            result = session.agent_results[agent_id]

            # Vérifier le skip
            skip_decision, skip_reason, skip_type = should_skip_agent(
                agent_id, session, set(active_agents), has_existing,
                bool(session.config.target_locales),
            )

            if skip_decision:
                if skip_type == "user" and not session.config.skip_confirmed:
                    # Avertissement pour skip manuel
                    console.print(
                        f"[yellow]⚠ {get_skip_warning(agent_id)}[/yellow]\n"
                        f"[yellow]Confirmer le skip de {agent_id} ? (utilisez --yes pour confirmer)[/yellow]"
                    )
                    if not click.confirm("Continuer ?"):
                        console.print("[red]Pipeline annulé.[/red]")
                        return

                result.status = AgentStatus.SKIPPED_USER if skip_type == "user" else AgentStatus.SKIPPED_AUTO
                result.skip_reason = skip_reason
                result.skip_impact = get_skip_warning(agent_id)
                log_agent_skipped(agent_id, result.agent_name, result.status.value, skip_reason)
                _update_table_row(table, result, agent_id)

                # Sauvegarder après chaque agent
                session_manager.save(session)
                continue

            # Exécuter l'agent
            result.status = AgentStatus.RUNNING
            _update_table_row(table, result, agent_id)
            log_agent_start(agent_id, result.agent_name)
            start_time = datetime.now()

            try:
                # Appeler l'agent
                agent_fn = AGENT_REGISTRY[agent_id]
                session = await agent_fn(session)
                elapsed = (datetime.now() - start_time)
                result.duration_ms = int(elapsed.total_seconds() * 1000)
                result.status = AgentStatus.COMPLETED
                result.prompt_version = "v1"
                result.model_used = "stub" if session.config.dry_run else "auto"

                log_agent_completed(
                    agent_id, result.agent_name, result.duration_ms,
                    tokens_input=result.tokens_input or 0,
                    tokens_output=result.tokens_output or 0,
                    cost_estimated=result.cost_estimated or 0.0,
                    prompt_version=result.prompt_version,
                    model_used=result.model_used,
                )

            except Exception as e:
                elapsed = (datetime.now() - start_time)
                result.duration_ms = int(elapsed.total_seconds() * 1000)
                result.status = AgentStatus.FAILED
                result.error_message = str(e)
                result.error_traceback = str(e)
                session.error_count += 1
                session.status = "failed"

                log_agent_failed(agent_id, result.agent_name, str(e), result.duration_ms)
                _update_table_row(table, result, agent_id)

                # Sauvegarder l'état avant de quitter
                session_manager.save(session)
                console.print(
                    f"\n[red]Pipeline échoué à {agent_id} : {e}[/red]\n"
                    f"[dim]Session sauvegardée : {session.session_id}[/dim]\n"
                    f"[dim]Relancez avec : hermes resume --session-id {session.session_id}[/dim]"
                )
                return

            # Mettre à jour l'affichage
            _update_table_row(table, result, agent_id)

            # Sauvegarder après chaque agent
            session_manager.save(session)

    # Pipeline terminé
    session.status = "completed"
    session_manager.save(session)

    elapsed_total = (datetime.now() - session.created_at).total_seconds()
    console.print(
        f"\n[bold green]Pipeline terminé avec succès ![/bold green]\n"
        f"Session : [dim]{session.session_id}[/dim]\n"
        f"Durée totale : {elapsed_total:.1f}s\n"
        f"Budget : {budget.summary()}"
    )


def _update_table_row(table, result, agent_id):
    """Ajoute ou met a jour une ligne dans le tableau de progression."""
    status_icons = {
        "completed": "[green]OK[/green]",
        "skipped_auto": "[yellow]SKIP[/yellow]",
        "skipped_user": "[yellow]SKIP[/yellow]",
        "failed": "[red]FAIL[/red]",
        "running": "[blue]...[/blue]",
        "pending": "[dim]-[/dim]",
    }
    st = str(result.status.value) if hasattr(result.status, 'value') else str(result.status)
    icon = status_icons.get(st, "?")
    dur = f"{result.duration_ms}ms" if result.duration_ms else "-"
    tok = f"{result.tokens_input or 0}+{result.tokens_output or 0}" if result.tokens_input else "-"
    cost = f"${result.cost_estimated:.4f}" if result.cost_estimated else "-"

    # Supprimer la derniere ligne (running) et re-ajouter avec le statut final
    if table.row_count > 0:
        # On ne peut pas modifier les lignes Rich facilement, on ajoute simplement
        pass

    table.add_row(agent_id, f"{icon} {st}", dur, tok, cost)


@cli.command()
@click.option("--session-id", "-s", required=True, help="ID de la session à reprendre")
@click.option("--from", "from_agent", default=None, help="Reprendre depuis un agent spécifique")
def resume(session_id: str, from_agent: Optional[str] = None) -> None:
    """Reprend une session interrompue."""
    session_manager = SessionManager(config.SESSION_DIRECTORY)

    try:
        session = session_manager.load(session_id)
    except Exception as e:
        click.echo(f"Session {session_id} introuvable : {e}", err=True)
        sys.exit(1)

    session_manager.create_backup(session_id)

    click.echo(f"Reprise de la session {session_id}")
    click.echo(f"État : {session.status} | Dernier agent : {session.last_completed_agent_id or 'aucun'}")

    if from_agent:
        # Réinitialiser à partir de l'agent spécifié
        click.echo(f"Reprise forcée depuis {from_agent}")
        session.current_agent_id = from_agent
        session.status = "running"
        # Marquer les agents précédents comme completed s'ils ne le sont pas
        from_index = _agent_index(from_agent)
        for agent_id, result in session.agent_results.items():
            if _agent_index(agent_id) >= from_index:
                if result.status == AgentStatus.COMPLETED:
                    result.status = AgentStatus.PENDING  # Re-exécuter

    configure_logging(session_id)
    asyncio.run(_run_pipeline(session, session_manager))


def _agent_index(agent_id: str) -> int:
    from hermes.core.workflow import AGENT_ORDER
    try:
        return AGENT_ORDER.index(agent_id)
    except ValueError:
        return 999


@cli.command()
@click.option("--session-id", "-s", required=True, help="ID de la session à rejouer")
def replay(session_id: str) -> None:
    """Rejoue une session en mode dry-run (debug sans API)."""
    session_manager = SessionManager(config.SESSION_DIRECTORY)
    try:
        session = session_manager.load(session_id)
    except Exception as e:
        click.echo(f"Session {session_id} introuvable : {e}", err=True)
        sys.exit(1)

    session.config.dry_run = True
    session.config.replay_session_id = session_id
    click.echo(f"Replay de la session {session_id} en mode dry-run")
    configure_logging(f"replay_{session_id}")
    asyncio.run(_run_pipeline(session, session_manager))


@cli.command()
@click.option("--session-id", "-s", default=None, help="Afficher une session spécifique")
@click.option("--list", "list_all", is_flag=True, help="Lister toutes les sessions")
def status(session_id: Optional[str] = None, list_all: bool = False) -> None:
    """Affiche l'état des sessions."""
    session_manager = SessionManager(config.SESSION_DIRECTORY)

    if list_all or not session_id:
        sessions = session_manager.list_sessions()
        if not sessions:
            click.echo("Aucune session trouvée.")
            return
        for s in sessions:
            status_icon = {"completed": "✓", "failed": "✗", "running": "…", "created": "○"}.get(
                s.get("status", ""), "?"
            )
            click.echo(
                f"[{status_icon}] {s['session_id']} | {s.get('keyword', 'N/A')} | "
                f"{s.get('status', '?')} | {s.get('agent_count', 0)} agents | "
                f"{s.get('updated_at', '?')[:19]}"
            )
    else:
        session = session_manager.load(session_id)
        click.echo(f"Session: {session.session_id}")
        click.echo(f"Mot-clé: {session.keyword}")
        click.echo(f"Statut: {session.status.value}")
        click.echo(f"Mode: {session.config.mode.value}")
        click.echo(f"Créée: {session.created_at}")
        click.echo(f"Mise à jour: {session.updated_at}")
        click.echo(f"Erreurs: {session.error_count}")
        click.echo(f"Avertissements: {len(session.warnings)}")
        click.echo("\nAgents:")
        for agent_id, result in session.agent_results.items():
            icon = {"completed": "✓", "failed": "✗", "skipped_auto": "⏭", "skipped_user": "⏭",
                    "pending": "○", "running": "…"}.get(result.status.value, "?")
            click.echo(
                f"  [{icon}] {agent_id} — {result.status.value}"
                f"{' — ' + result.error_message if result.error_message else ''}"
            )


@cli.command()
def check() -> None:
    """Exécute le startup check uniquement."""
    check_and_exit()


# ─── Audit Technique ──────────────────────────────────────────────────

@cli.group()
def audit_tech() -> None:
    """Pipeline 3 — Audit Technique complet (12 dimensions)."""
    pass


@audit_tech.command("run")
@click.option("--site-url", "-s", required=True, help="URL du site a auditer")
@click.option("--max-urls", "-n", default=50, type=int, help="Nombre max d'URLs")
@click.option("--mode", "-m", default="standard",
              type=click.Choice(["fast", "standard", "premium", "debug"]),
              help="Mode qualite")
@click.option("--profile", "-p", default="blog",
              type=click.Choice(["ecommerce", "blog", "institutionnel", "agence", "saas"]),
              help="Profil client")
@click.option("--entry-mode", "-e", default="sitemap",
              type=click.Choice(["single", "list", "sitemap", "crawl", "csv"]),
              help="Mode d'entree")
@click.option("--yes", is_flag=True, help="Consentement automatique (bypass confirmation)")
def audit_tech_run(site_url: str, max_urls: int, mode: str,
                   profile: str, entry_mode: str, yes: bool) -> None:
    """Lance un audit technique complet sur un site.

    Exemples :
      hermes audit-tech run -s https://mon-site.fr
      hermes audit-tech run -s https://mon-site.fr -n 100 -m premium -p ecommerce --yes
    """
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logger = logging.getLogger("hermes.cli.audit_tech")

    # Consentement
    if not yes:
        click.echo(f"\n{'='*60}")
        click.echo(f"  AUDIT TECHNIQUE — {site_url}")
        click.echo(f"  Max URLs: {max_urls} | Mode: {mode} | Profil: {profile}")
        click.echo(f"  Rate limit: 2 req/s | Respect robots.txt: OUI")
        click.echo(f"  Aucun scan intrusif. Tests defensifs uniquement.")
        click.echo(f"{'='*60}")
        if not click.confirm("Lancer l'audit technique ?"):
            click.echo("Annule.")
            return

    async def _run():
        from hermes.core.audit_entry import resolve_entry_urls
        from hermes.core.audit_tech_entry import init_tech_audit
        from hermes.agents.audit_tech import TECH_ORDER, TECH_REGISTRY

        # Resolution
        click.echo("Resolution des URLs...")
        resolved = await resolve_entry_urls(entry_mode, site_url, max_urls=max_urls)
        if not resolved["success"]:
            click.echo(f"Erreur: {resolved.get('error')}")
            return
        urls = resolved["urls"]
        click.echo(f"  {len(urls)} URLs resolues (source: {resolved['meta'].get('source', '?')})")

        # Init
        state = await init_tech_audit(
            site_url=site_url, urls=urls, consent_given=True,
            profile=profile, mode=mode, max_urls=max_urls,
        )

        # Pipeline
        for i, agent_id in enumerate(TECH_ORDER):
            if agent_id in TECH_REGISTRY:
                click.echo(f"  [{i+1}/{len(TECH_ORDER)}] {agent_id}...")
                state = await TECH_REGISTRY[agent_id](state)

        # Resume
        click.echo(f"\n{'='*60}")
        click.echo(f"  AUDIT TERMINE")
        click.echo(f"  CMS: {state.cms_detected or 'non detecte'} ({state.cms_confidence}%)")
        click.echo(f"  Pages: {len(state.crawled_pages)} | Issues: {len(state.issues)}")
        click.echo(f"  Score global: {state.scores.global_score}/100 ({state.scores.global_confidence})")

        dims = ['crawlability','indexation','architecture','structure','content',
                'performance','mobile','structured_data','international','security','maillage']
        for d in dims:
            s = getattr(state.scores, d)
            click.echo(f"    {d}: {s.score}/100 ({s.confidence})")

        p0 = sum(1 for i in state.issues if i.priority == 'P0')
        p1 = sum(1 for i in state.issues if i.priority == 'P1')
        click.echo(f"  Priorites: P0={p0}, P1={p1}, P2={sum(1 for i in state.issues if i.priority=='P2')}, P3={sum(1 for i in state.issues if i.priority=='P3')}")

        if state.roadmap:
            click.echo(f"  Roadmap:")
            for sprint in state.roadmap:
                click.echo(f"    {sprint['sprint']}: {sprint['count']} taches, ~{sprint['estimated_hours']}h")
        click.echo(f"{'='*60}")

    asyncio.run(_run())


# ─── Archive ───────────────────────────────────────────────────────

@cli.group()
def archive() -> None:
    """Gestion de l'historique et des archives."""
    pass


@archive.command(name="list")
@click.option("--search", "-s", default=None, help="Recherche dans les mots-cles")
@click.option("--status", multiple=True, help="Filtrer par statut")
@click.option("--mode", multiple=True, help="Filtrer par mode qualite")
@click.option("--page", default=1, type=int, help="Numero de page")
@click.option("--page-size", default=20, type=int, help="Resultats par page")
@click.option("--include-archived", is_flag=True, help="Inclure les sessions archivees")
def archive_list(
    search: Optional[str],
    status: tuple[str, ...],
    mode: tuple[str, ...],
    page: int,
    page_size: int,
    include_archived: bool,
) -> None:
    """Liste toutes les sessions avec filtres."""
    from hermes.core.archive_service import ArchiveService
    from hermes.models.archive import SessionFilter

    svc = ArchiveService()
    f = SessionFilter(
        search=search or None,
        status=[SessionStatus(s) for s in status] if status else None,
        mode=[QualityMode(m) for m in mode] if mode else None,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
    )
    result = svc.list_sessions(f)

    console = Console()
    table = Table(title=f"Sessions ({result.total} au total)")
    table.add_column("ID", style="dim")
    table.add_column("Mot-cle")
    table.add_column("Statut", style="yellow")
    table.add_column("Score", style="green")
    table.add_column("Cout", style="magenta")
    table.add_column("Date")

    for entry in result.items:
        score = str(entry.score_total) if entry.score_total else "-"
        date_str = str(entry.updated_at)[:19] if entry.updated_at else "-"
        table.add_row(
            entry.session_id,
            entry.keyword or "-",
            entry.status,
            score,
            f"${entry.total_cost:.4f}",
            date_str,
        )

    console.print(table)
    if result.total_pages > 1:
        console.print(
            f"Page {result.page}/{result.total_pages} | "
            f"[dim]--page N pour naviguer[/dim]"
        )


@archive.command(name="view")
@click.option("--session-id", "-s", required=True, help="ID de la session")
@click.option("--logs", is_flag=True, help="Afficher les logs")
def archive_view(session_id: str, logs: bool) -> None:
    """Affiche le detail complet d'une session."""
    from hermes.core.archive_service import ArchiveService
    from rich.console import Console
    from rich.panel import Panel

    svc = ArchiveService()
    try:
        detail = svc.get_session_detail(session_id)
    except Exception as e:
        click.echo(f"Session {session_id} introuvable : {e}", err=True)
        sys.exit(1)

    console = Console()
    scores = detail.scores or {}
    score_total = scores.get("score_total", "?")

    console.print(
        Panel.fit(
            f"[bold]{detail.keyword}[/bold]\n"
            f"Session: [dim]{detail.session_id}[/dim] | "
            f"Status: [yellow]{detail.status}[/yellow] | "
            f"Score: [green]{score_total}/100[/green]\n"
            f"Cost: ${detail.total_cost:.4f} | "
            f"Tokens: {detail.total_tokens:,} | "
            f"Duree: {detail.duration_seconds or '?'}s",
            title="Session Detail",
        )
    )

    # Agents
    agent_table = Table(title="Agents executes")
    agent_table.add_column("ID")
    agent_table.add_column("Nom")
    agent_table.add_column("Statut")
    agent_table.add_column("Duree")
    agent_table.add_column("Tokens")
    agent_table.add_column("Cout")
    for a in detail.agents:
        agent_table.add_row(
            a.agent_id,
            a.agent_name,
            a.status,
            f"{a.duration_ms}ms" if a.duration_ms else "-",
            f"{a.tokens_input or 0}+{a.tokens_output or 0}",
            f"${a.cost_estimated or 0:.4f}",
        )
    console.print(agent_table)

    if logs and detail.log_events:
        log_table = Table(title=f"Logs ({len(detail.log_events)} evenements)")
        log_table.add_column("Timestamp")
        log_table.add_column("Event")
        log_table.add_column("Agent")
        for evt in detail.log_events[:50]:
            log_table.add_row(evt.timestamp, evt.event, evt.agent_name)
        console.print(log_table)


@archive.command(name="export")
@click.option("--session-id", "-s", required=True, help="ID de la session")
@click.option("--format", "-f", default="json",
              type=click.Choice(["json", "csv", "markdown"]),
              help="Format d'export")
@click.option("--output", "-o", default=None, help="Fichier de sortie")
def archive_export(session_id: str, format: str, output: Optional[str] = None) -> None:
    """Exporte une session."""
    from hermes.core.archive_service import ArchiveService, ExportFormat

    svc = ArchiveService()
    try:
        content = svc.export_session(session_id, ExportFormat(format))
    except Exception as e:
        click.echo(f"Erreur export : {e}", err=True)
        sys.exit(1)

    if output:
        Path(output).write_text(content, encoding="utf-8")
        click.echo(f"Exporte vers {output}")
    else:
        click.echo(content)


@archive.command(name="delete")
@click.option("--session-id", "-s", required=True, help="ID de la session")
@click.option("--force", is_flag=True, help="Sans confirmation")
def archive_delete(session_id: str, force: bool) -> None:
    """Supprime une session."""
    if not force:
        click.confirm(
            f"Supprimer definitivement la session {session_id} ?",
            abort=True,
        )
    from hermes.core.archive_service import ArchiveService

    svc = ArchiveService()
    if svc.delete_session(session_id):
        click.echo(f"Session {session_id} supprimee.")
    else:
        click.echo(f"Session {session_id} introuvable.", err=True)


@archive.command(name="stats")
def archive_stats() -> None:
    """Affiche les statistiques agregees."""
    from hermes.core.archive_service import ArchiveService
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    svc = ArchiveService()
    stats = svc.get_stats()

    console = Console()
    console.print(
        Panel.fit(
            f"Sessions: [bold]{stats.total_sessions}[/bold] | "
            f"Terminees: [green]{stats.total_completed}[/green] | "
            f"Echecs: [red]{stats.total_failed}[/red] | "
            f"Archives: [dim]{stats.total_archived}[/dim]\n"
            f"Score moyen: [green]{stats.average_score or 'N/A'}/100[/green] | "
            f"Cout total: [yellow]${stats.total_cost:.4f}[/yellow] | "
            f"Tokens: {stats.total_tokens:,}\n"
            f"Cout estime (prod): ${stats.budget_used_total:.4f}\n"
            f"Periode: {stats.period_start or '?'} → {stats.period_end or '?'}",
            title="Statistiques",
        )
    )

    if stats.sessions_by_status:
        table = Table(title="Par statut")
        table.add_column("Statut")
        table.add_column("Nombre")
        for s, c in sorted(stats.sessions_by_status.items(), key=lambda x: x[1], reverse=True):
            table.add_row(s, str(c))
        console.print(table)


@archive.command(name="budget")
def archive_budget() -> None:
    """Affiche l'historique budget."""
    from hermes.core.archive_service import ArchiveService
    from rich.console import Console
    from rich.table import Table

    svc = ArchiveService()
    history = svc.get_budget_history(limit=50)

    if not history:
        click.echo("Aucune donnee budget.")
        return

    console = Console()
    table = Table(title="Historique budget")
    table.add_column("Date")
    table.add_column("Mot-cle")
    table.add_column("Tokens")
    table.add_column("Cout")
    table.add_column("Score")

    total_cost = 0.0
    for snap in history:
        date_str = str(snap.created_at)[:19] if snap.created_at else "?"
        total_cost += snap.total_cost
        table.add_row(
            date_str,
            snap.keyword,
            str(snap.total_tokens),
            f"${snap.total_cost:.4f}",
            str(snap.score_total) if snap.score_total else "-",
        )

    console.print(table)
    console.print(f"Cout total: [yellow]${total_cost:.4f}[/yellow]")


@archive.command(name="timeline")
@click.option("--limit", default=50, type=int, help="Nombre d'evenements")
@click.option("--type", "event_type", default=None, help="Filtrer par type")
def archive_timeline(limit: int, event_type: Optional[str] = None) -> None:
    """Affiche la timeline du projet."""
    from hermes.core.archive_service import ArchiveService
    from rich.console import Console

    svc = ArchiveService()
    entries = svc.get_timeline(limit=limit, event_type=event_type)
    console = Console()

    if not entries:
        click.echo("Aucun evenement dans la timeline.")
        return

    for entry in entries:
        ts = entry.timestamp
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)[:19]
        console.print(
            f"[dim]{ts_str}[/dim] [{entry.event_type}] {entry.description}"
        )


@archive.command(name="retention")
@click.option("--dry-run", is_flag=True, help="Simuler sans executer")
@click.option("--days", default=30, type=int, help="Archiver sessions plus vieilles que N jours")
def archive_retention(dry_run: bool, days: int) -> None:
    """Execute la politique de retention."""
    from hermes.core.archive_service import ArchiveService, RetentionPolicy

    svc = ArchiveService()
    policy = RetentionPolicy(archive_after_days=days)
    result_rp = svc.run_retention_policy(policy, dry_run=dry_run)

    if dry_run:
        click.echo(f"A archiver : {len(result_rp['to_archive'])} sessions")
        click.echo(f"A supprimer : {len(result_rp['to_delete'])} sessions")
    else:
        click.echo(f"Archives : {len(result_rp['archived'])}")
        click.echo(f"Supprimes : {len(result_rp['deleted'])}")


@archive.command(name="meta")
@click.option("--title", required=True, help="Titre de l'evenement")
@click.option("--description", required=True, help="Description")
@click.option("--type", "event_type", default="milestone",
              type=click.Choice(["deployment", "config_change", "milestone", "prompt_update"]))
@click.option("--version", default=None, help="Version (ex: v0.2.0)")
def archive_meta(title: str, description: str, event_type: str, version: Optional[str] = None) -> None:
    """Enregistre un evenement dans le meta-archivage."""
    from hermes.core.archive_service import ArchiveService, MetaArchiveEntry

    svc = ArchiveService()
    entry = MetaArchiveEntry(
        event_type=event_type,
        title=title,
        description=description,
        version=version,
    )
    svc.record_meta_event(entry)
    click.echo(f"Evenement enregistre : {title}")


if __name__ == "__main__":
    cli()
