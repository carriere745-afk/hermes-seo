"""Pipeline 6 — Maillage & Backlinks — 18 agents."""

from hermes.agents.backlinks.b00_supervisor import run as b00
from hermes.agents.backlinks.b01_import import run as b01
from hermes.agents.backlinks.b02_scoring import run as b02
from hermes.agents.backlinks.b03_toxiques import run as b03
from hermes.agents.backlinks.b04_gap import run as b04
from hermes.agents.backlinks.b05_reclamation import run as b05
from hermes.agents.backlinks.b05b_broken_links import run as b05b
from hermes.agents.backlinks.b06_recommandations import run as b06
from hermes.agents.backlinks.b07_crm import run as b07
from hermes.agents.backlinks.b08_preuve_seo import run as b08
from hermes.agents.backlinks.b09_scarcity import run as b09
from hermes.agents.backlinks.b10_authority_graph import run as b10
from hermes.agents.backlinks.b11_export import run as b11
from hermes.agents.backlinks.b12_prospect_discovery import run as b12
from hermes.agents.backlinks.b14_anchor_strategy import run as b14
from hermes.agents.backlinks.b15_portfolio import run as b15
from hermes.agents.backlinks.b16_entity_authority import run as b16
from hermes.agents.backlinks.b17_media_relationship import run as b17

BACKLINKS_REGISTRY: dict[str, callable] = {
    "b00": b00, "b01": b01, "b02": b02, "b03": b03,
    "b04": b04, "b05": b05, "b05b": b05b, "b06": b06,
    "b07": b07, "b08": b08, "b09": b09, "b10": b10,
    "b11": b11, "b12": b12, "b14": b14, "b15": b15,
    "b16": b16, "b17": b17,
}

BACKLINKS_ORDER: list[str] = [
    # Phase 0 — Startup
    "b00",
    # Phase 1 — Collecte
    "b01",
    # Phase 2 — Analyse (parallele conceptuel, sequentiel technique)
    "b02", "b03", "b04", "b05", "b05b",
    "b12", "b14", "b15", "b16", "b17",
    "b08", "b09", "b10",
    # Phase 3 — Synthese
    "b06",
    # Phase 4 — Execution
    "b07",
    # Phase 5 — Export
    "b11",
]
