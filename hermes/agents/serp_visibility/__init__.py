"""Pipeline 4 — SERP & Visibility Intelligence — 11 agents."""

from hermes.agents.serp_visibility.sv00_supervisor import run as sv00
from hermes.agents.serp_visibility.sv01_rank_tracker import run as sv01
from hermes.agents.serp_visibility.sv02_variations import run as sv02
from hermes.agents.serp_visibility.sv02b_google_update import run as sv02b
from hermes.agents.serp_visibility.sv03_serp_features import run as sv03
from hermes.agents.serp_visibility.sv04_concurrent import run as sv04
from hermes.agents.serp_visibility.sv04b_share_of_voice import run as sv04b
from hermes.agents.serp_visibility.sv05_gap_content import run as sv05
from hermes.agents.serp_visibility.sv06_quick_wins import run as sv06
from hermes.agents.serp_visibility.sv07_alerts import run as sv07
from hermes.agents.serp_visibility.sv08_aeo_ai import run as sv08
from hermes.agents.serp_visibility.sv09_correlation import run as sv09
from hermes.agents.serp_visibility.sv10_synthesis import run as sv10

SERP_REGISTRY: dict[str, callable] = {
    "sv00": sv00, "sv01": sv01, "sv02": sv02, "sv02b": sv02b,
    "sv03": sv03, "sv04": sv04, "sv04b": sv04b, "sv05": sv05,
    "sv06": sv06, "sv07": sv07, "sv08": sv08, "sv09": sv09, "sv10": sv10,
}

SERP_ORDER: list[str] = [
    "sv00", "sv01", "sv02", "sv02b", "sv03", "sv04", "sv04b",
    "sv05", "sv06", "sv07", "sv08", "sv09", "sv10",
]
