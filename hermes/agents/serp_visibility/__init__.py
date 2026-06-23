"""Pipeline 4 — SERP & Visibility Intelligence — Registre des 11 agents."""

from hermes.agents.serp_visibility.sv00_supervisor import run as sv00
from hermes.agents.serp_visibility.sv01_rank_tracker import run as sv01
from hermes.agents.serp_visibility.sv02_variations import run as sv02
from hermes.agents.serp_visibility.sv02b_google_update import run as sv02b
from hermes.agents.serp_visibility.sv06_quick_wins import run as sv06
from hermes.agents.serp_visibility.sv07_alerts import run as sv07

SERP_REGISTRY: dict[str, callable] = {
    "sv00": sv00, "sv01": sv01,
    "sv02": sv02, "sv02b": sv02b,
    "sv06": sv06, "sv07": sv07,
}

SERP_ORDER: list[str] = [
    "sv00", "sv01", "sv02", "sv02b", "sv06", "sv07",
]
