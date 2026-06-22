"""Agents du Pipeline Audit de Contenu — 10 agents.

AC00 : Superviseur Audit
AC01 : Content Crawler + Indexabilite
AC02 : Scoring SEO On-Page + Qualite Editoriale
AC03 : Scoring AEO
AC04 : Scoring GEO
AC05 : Scoring EEAT
AC06 : Scoring UX / Lisibilite
AC07 : Cannibalisation Inter-Pages
AC08 : Synthese + audit_brief
AC09 : Roadmap + Export + Connecteur
"""

from hermes.agents.audit.ac00_supervisor import run as ac00
from hermes.agents.audit.ac01_crawler import run as ac01
from hermes.agents.audit.ac02_seo_quality import run as ac02
from hermes.agents.audit.ac03_aeo import run as ac03
from hermes.agents.audit.ac04_geo import run as ac04
from hermes.agents.audit.ac05_eeat import run as ac05
from hermes.agents.audit.ac06_ux import run as ac06
from hermes.agents.audit.ac07_cannibalisation import run as ac07
from hermes.agents.audit.ac08_synthesis import run as ac08
from hermes.agents.audit.ac09_roadmap_export import run as ac09
from hermes.agents.audit.ac09_roadmap_export import prepare_audit_brief_for_editorial

AUDIT_REGISTRY: dict[str, callable] = {
    "ac00": ac00,
    "ac01": ac01,
    "ac02": ac02,
    "ac03": ac03,
    "ac04": ac04,
    "ac05": ac05,
    "ac06": ac06,
    "ac07": ac07,
    "ac08": ac08,
    "ac09": ac09,
}

AUDIT_ORDER: list[str] = [
    "ac00", "ac01", "ac02", "ac03", "ac04", "ac05",
    "ac06", "ac07", "ac08", "ac09",
]

__all__ = ["AUDIT_REGISTRY", "AUDIT_ORDER", "prepare_audit_brief_for_editorial"]
