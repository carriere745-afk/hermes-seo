"""Pipeline 5 — Strategie Editoriale — 21 agents."""

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
from hermes.agents.strategie.st11b_auto_creator import run as st11b
from hermes.agents.strategie.st12_semantic_gap import run as st12
from hermes.agents.strategie.st13_geo_sources import run as st13
from hermes.agents.strategie.st14_ctr_reformulator import run as st14
from hermes.agents.strategie.st15_content_gap_detail import run as st15

STRATEGIE_REGISTRY: dict[str, callable] = {
    "st00": st00, "st01": st01, "st01b": st01b, "st02": st02,
    "st03": st03, "st04": st04, "st04b": st04b, "st04c": st04c,
    "st05": st05, "st05b": st05b, "st06": st06, "st06b": st06b,
    "st06c": st06c, "st07": st07, "st08": st08, "st09": st09,
    "st10": st10, "st10b": st10b, "st11": st11, "st11b": st11b,
    "st12": st12, "st13": st13, "st14": st14, "st15": st15,
}

STRATEGIE_ORDER: list[str] = [
    "st00",
    "st01", "st01b", "st02", "st07", "st08",
    "st03", "st04", "st04b", "st04c",
    "st05", "st05b",
    "st06", "st06b", "st06c", "st12", "st13", "st14", "st15",
    "st09", "st10", "st10b",
    "st11", "st11b",
]
