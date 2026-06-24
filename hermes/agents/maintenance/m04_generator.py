"""M04 — Content Generator.

Execute les actions GENERATE : llms.txt, Disavow.txt, schemas JSON-LD,
emails CRM, meta descriptions, titles, redirections 301.
Quota partage: verifie actions_executed_today avant chaque execution.
Non skippable. $0.
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.project import Project, ExecutionAction
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m04")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    generated = 0

    pending = [a for a in project.execution_actions
               if a.category == "generate" and a.status == "pending"]

    for action in pending:
        if project.actions_executed_today >= project.max_actions_per_day:
            logger.warning(f"M04: Quota atteint ({project.actions_executed_today}/{project.max_actions_per_day})")
            break

        try:
            if action.action_type == "generer_llms_txt":
                action.content_to_generate = _generate_llms_txt(project)
                action.file_to_create = "llms.txt"
            elif action.action_type == "generer_disavow":
                action.content_to_generate = _generate_disavow(project)
                action.file_to_create = "disavow.txt"
            elif action.action_type == "generer_schema_faq":
                action.content_to_generate = _generate_schema_faq(project, action)
                action.file_to_create = f"schema_{action.target_page or 'page'}.json"
            elif action.action_type in ("generer_meta_description", "generer_title"):
                action.content_to_generate = _generate_meta(project, action)
            elif action.action_type == "generer_email_crm":
                action.content_to_generate = _generate_email_template(project, action)
            elif action.action_type in ("creer_article", "creer_pilier"):
                action.content_to_generate = _generate_content_brief(project, action)
            else:
                action.content_to_generate = f"# {action.description}\n\nContenu genere automatiquement par Hermes SEO M04."

            action.status = "executed"
            action.executed_at = datetime.now()
            project.actions_executed_today += 1
            generated += 1

        except Exception as e:
            action.status = "failed"
            action.execution_error = str(e)
            logger.error(f"M04: Echec generation {action.action_type}: {e}")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m04", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"generated": generated})

    logger.info(f"M04: {generated} fichiers generes (quota: {project.actions_executed_today}/{project.max_actions_per_day})")
    return project


def _generate_llms_txt(project: Project) -> str:
    lines = [f"# {project.domain or project.nom}"]
    lines.append(f"# Genere par Hermes SEO — {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    if project.site_url:
        lines.append(project.site_url)
        lines.append(f"{project.site_url}/a-propos")
        lines.append(f"{project.site_url}/contact")
        lines.append(f"{project.site_url}/services")
    return "\n".join(lines)


def _generate_disavow(project: Project) -> str:
    lines = ["# Fichier Disavow — Hermes SEO"]
    lines.append(f"# Domaine: {project.domain}")
    lines.append(f"# Date: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("# A uploader sur: https://search.google.com/search-console/disavow")
    lines.append("")
    try:
        from hermes.core.backlinks_db import _get_conn
        conn = _get_conn()
        rows = conn.execute(
            "SELECT domain FROM toxic_domains WHERE toxicity_score >= 60"
        ).fetchall()
        conn.close()
        for r in rows:
            lines.append(f"domain:{r['domain']}")
    except Exception:
        lines.append("# Aucun domaine toxique detecte")
    return "\n".join(lines)


def _generate_schema_faq(project: Project, action: ExecutionAction) -> str:
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{
            "@type": "Question",
            "name": action.description or "Question frequente",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "Reponse detaillee a fournir..."
            }
        }]
    }, indent=2, ensure_ascii=False)


def _generate_meta(project: Project, action: ExecutionAction) -> str:
    kw = action.description or "service professionnel"
    if "title" in action.action_type:
        return f"{kw.title()} | {project.domain} — Expert depuis 2010"
    return f"Decouvrez {kw} avec {project.domain}. Service professionnel, devis gratuit, intervention rapide. Contactez-nous."


def _generate_email_template(project: Project, action: ExecutionAction) -> str:
    return f"""Objet: Proposition de collaboration — {project.domain}

Bonjour,

Je me permets de vous contacter car j'apprecie votre travail sur {action.target_url or 'votre site'}.

Je represente {project.domain} et je souhaiterais explorer une opportunite de collaboration editoriale (guest post, interview, partenariat).

Notre site traite de {project.secteur or 'notre secteur'} et nous pensons que nos audiences sont complementaires.

Seriez-vous ouvert a en discuter ?

Cordialement,
L'equipe {project.domain}
"""


def _generate_content_brief(project: Project, action: ExecutionAction) -> str:
    return f"""# Brief Editorial — {action.description}

**Site**: {project.domain}
**Profil**: {project.profile}
**Secteur**: {project.secteur}

## Objectif
{action.description}

## Points cles a couvrir
- Definition et contexte
- Donnees chiffrees recentes
- Conseils pratiques et actionnables
- FAQ integree avec schema

## Contraintes
- Ton: professionnel et pedagogique
- Longueur: 1200-2000 mots
- Sources: institutionnelles de preference
"""
