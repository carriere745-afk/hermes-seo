"""Pipeline 4 — SERP & Visibility Intelligence — Registre des 11 agents."""

from hermes.agents.serp_visibility.sv00_supervisor import run as sv00
from hermes.agents.serp_visibility.sv01_rank_tracker import run as sv01

SERP_REGISTRY: dict[str, callable] = {
    "sv00": sv00,
    "sv01": sv01,
    # Sprint 2+
    # "sv02": sv02, "sv02b": sv02b, "sv06": sv06, "sv07": sv07,
    # Sprint 3+
    # "sv03": sv03, "sv04": sv04, "sv04b": sv04b,
    # Sprint 4+
    # "sv05": sv05, "sv08": sv08,
    # Sprint 5+
    # "sv09": sv09, "sv10": sv10,
}

SERP_ORDER: list[str] = [
    "sv00",
    "sv01",
    # Ajoute au fur et a mesure des sprints
]
