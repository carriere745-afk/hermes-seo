"""Pipeline 5 — Strategie Editoriale — 18 agents."""

from hermes.agents.strategie.st00_supervisor import run as st00
from hermes.agents.strategie.st01_topical_map import run as st01
from hermes.agents.strategie.st01b_topical_authority import run as st01b
from hermes.agents.strategie.st02_cannibalisation import run as st02
from hermes.agents.strategie.st03_opportunites import run as st03
from hermes.agents.strategie.st04_gap_concurrentiel import run as st04
from hermes.agents.strategie.st04b_feasibility import run as st04b
from hermes.agents.strategie.st04c_geo_opportunity import run as st04c
from hermes.agents.strategie.st05_business_score import run as st05
from hermes.agents.strategie.st05b_seo_economics import run as st05b
from hermes.agents.strategie.st06_roadmap import run as st06
from hermes.agents.strategie.st06b_forecast import run as st06b
from hermes.agents.strategie.st06c_portfolio import run as st06c
from hermes.agents.strategie.st07_silos_clusters import run as st07
from hermes.agents.strategie.st08_fusion_separation import run as st08
from hermes.agents.strategie.st09_revue_humaine import run as st09
from hermes.agents.strategie.st10_priorisation import run as st10
from hermes.agents.strategie.st10b_kill_list import run as st10b
from hermes.agents.strategie.st11_export_routage import run as st11

STRATEGIE_REGISTRY: dict[str, callable] = {
    "st00": st00, "st01": st01, "st01b": st01b, "st02": st02,
    "st03": st03, "st04": st04, "st04b": st04b, "st04c": st04c,
    "st05": st05, "st05b": st05b, "st06": st06, "st06b": st06b,
    "st06c": st06c, "st07": st07, "st08": st08, "st09": st09,
    "st10": st10, "st10b": st10b, "st11": st11,
}

# Ordre d'execution : Phase 0 → Phase 1 (parallele possible) → Phase 2 (sequentiel) → Phase 3
STRATEGIE_ORDER: list[str] = [
    # Phase 0 — Startup
    "st00",
    # Phase 1 — Analyses (ordre contraint : ST04b depend de ST01b, ST04 depend de ST04)
    "st01", "st01b", "st02", "st07", "st08",
    "st03", "st04", "st04b", "st04c",
    "st05", "st05b",
    # Phase 2 — Synthese
    "st06", "st06b", "st06c",
    "st09", "st10", "st10b",
    # Phase 3 — Export
    "st11",
]
