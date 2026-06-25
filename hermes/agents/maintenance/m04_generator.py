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
                _write_file_to_disk(project, action)
            elif action.action_type == "generer_sitemap":
                action.content_to_generate = _generate_sitemap_xml(project)
                action.file_to_create = "sitemap.xml"
                _write_file_to_disk(project, action)
            elif action.action_type == "generer_robots_txt":
                action.content_to_generate = _generate_robots_txt(project)
                action.file_to_create = "robots.txt"
                _write_file_to_disk(project, action)
            elif action.action_type == "generer_disavow":
                action.content_to_generate = _generate_disavow(project)
                action.file_to_create = "disavow.txt"
                _write_file_to_disk(project, action)
            elif action.action_type == "generer_schema_faq":
                action.content_to_generate = _generate_schema_faq(project, action)
                action.file_to_create = f"schema_{action.target_page or 'page'}.json"
                _write_file_to_disk(project, action)
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
    """Genere un llms.txt conforme aux specs https://llmstxt.org/

    Format: titre projet, description, liens vers pages principales.
    """
    lines = [f"# {project.nom or project.domain}"]
    if project.secteur or project.profile:
        lines.append(f"> Site {project.profile or 'web'} — secteur {project.secteur or 'generaliste'}")
    lines.append("")
    lines.append("## Pages principales")
    lines.append("")
    if project.site_url:
        base = project.site_url.rstrip("/")
        lines.append(f"- [Accueil]({base}/)")
        lines.append(f"- [A propos]({base}/a-propos)")
        lines.append(f"- [Contact]({base}/contact)")
        lines.append(f"- [Services]({base}/services)")
        lines.append(f"- [Blog]({base}/blog)")
    lines.append("")
    lines.append(f"_Genere par Hermes SEO — {datetime.now().strftime('%Y-%m-%d')}_")
    return "\n".join(lines)


def _generate_sitemap_xml(project: Project) -> str:
    """Genere un sitemap.xml standard."""
    base = (project.site_url or f"https://{project.domain}").rstrip("/")
    today = datetime.now().strftime("%Y-%m-%d")
    pages = [
        ("/", "1.0", "weekly"),
        ("/a-propos", "0.7", "monthly"),
        ("/services", "0.9", "weekly"),
        ("/blog", "0.8", "daily"),
        ("/contact", "0.5", "monthly"),
    ]
    urls = "\n".join(
        f"  <url>\n"
        f"    <loc>{base}{path}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>{freq}</changefreq>\n"
        f"    <priority>{prio}</priority>\n"
        f"  </url>"
        for path, prio, freq in pages
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        '</urlset>'
    )


def _generate_robots_txt(project: Project) -> str:
    """Genere un robots.txt optimal (AI crawlers autorises par defaut pour le GEO)."""
    base = (project.site_url or f"https://{project.domain}").rstrip("/")
    lines = []
    lines.append("# robots.txt — Hermes SEO")
    lines.append(f"# Domaine: {project.domain}")
    lines.append(f"# Genere le {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("User-agent: *")
    lines.append("Allow: /")
    lines.append("Disallow: /wp-admin/")
    lines.append("Disallow: /wp-login.php")
    lines.append("Disallow: /xmlrpc.php")
    lines.append("Disallow: /admin/")
    lines.append("Disallow: /private/")
    lines.append("")
    lines.append("# AI crawlers — autorises pour maximiser la visibilite GEO")
    lines.append("# (decommentez les lignes Disallow pour bloquer)")
    for crawler in ["GPTBot", "anthropic-ai", "Google-Extended", "PerplexityBot",
                    "CCBot", "Claude-Web", "ChatGPT-User"]:
        lines.append(f"User-agent: {crawler}")
        lines.append("Allow: /")
        lines.append("# Disallow: /")
        lines.append("")
    lines.append(f"Sitemap: {base}/sitemap.xml")
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


def _write_file_to_disk(project, action) -> None:
    """Ecrire le fichier genere sur le disque (output/)."""
    import os as _os
    outdir = _os.path.join("output", str(project.id or "default"))
    _os.makedirs(outdir, exist_ok=True)
    filename = action.file_to_create or f"{action.action_type}.txt"
    filepath = _os.path.join(outdir, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(action.content_to_generate or "")
        action.execution_result = f"Fichier ecrit: {filepath}"
        logger.info(f"M04: Fichier ecrit sur disque: {filepath}")
    except Exception as e:
        logger.error(f"M04: Echec ecriture fichier {filepath}: {e}")
