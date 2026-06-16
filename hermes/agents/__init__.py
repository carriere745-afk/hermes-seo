"""Agents Hermes SEO — 1 fichier par agent.

Chaque agent implémente :
- Une fonction `async def run(state: SessionState) -> SessionState`
- Un identifiant unique (ex: "agent_01")
- Une validation Pydantic en entrée et en sortie
"""

from hermes.agents.agent_00_supervisor import run as agent_00
from hermes.agents.agent_01_brief_entreprise import run as agent_01
from hermes.agents.agent_02_persona import run as agent_02
from hermes.agents.agent_03_analyse_serp import run as agent_03
from hermes.agents.agent_04_intention import run as agent_04
from hermes.agents.agent_05_offre_conversion import run as agent_05
from hermes.agents.agent_06_differenciation import run as agent_06
from hermes.agents.agent_07_template import run as agent_07
from hermes.agents.agent_08_anti_cannibalisation import run as agent_08
from hermes.agents.agent_09_redaction import run as agent_09
from hermes.agents.agent_10_seo import run as agent_10
from hermes.agents.agent_11_aeo import run as agent_11
from hermes.agents.agent_12_geo import run as agent_12
from hermes.agents.agent_13_eeat import run as agent_13
from hermes.agents.agent_14_conformite import run as agent_14
from hermes.agents.agent_15_fact_checking import run as agent_15
from hermes.agents.agent_16_maillage_interne import run as agent_16
from hermes.agents.agent_17_maillage_externe import run as agent_17
from hermes.agents.agent_18_multiformat import run as agent_18
from hermes.agents.agent_19_test_ab import run as agent_19
from hermes.agents.agent_20_localisation import run as agent_20
from hermes.agents.agent_21_schema_org import run as agent_21
from hermes.agents.agent_22_images import run as agent_22
from hermes.agents.agent_23_cms_export import run as agent_23
from hermes.agents.agent_24_mise_a_jour import run as agent_24
from hermes.agents.agent_25_critique_qualite import run as agent_25
from hermes.agents.agent_26_audit_post_publication import run as agent_26

AGENT_REGISTRY: dict[str, callable] = {
    "agent_00": agent_00,
    "agent_01": agent_01,
    "agent_02": agent_02,
    "agent_03": agent_03,
    "agent_04": agent_04,
    "agent_05": agent_05,
    "agent_06": agent_06,
    "agent_07": agent_07,
    "agent_08": agent_08,
    "agent_09": agent_09,
    "agent_10": agent_10,
    "agent_11": agent_11,
    "agent_12": agent_12,
    "agent_13": agent_13,
    "agent_14": agent_14,
    "agent_15": agent_15,
    "agent_16": agent_16,
    "agent_17": agent_17,
    "agent_18": agent_18,
    "agent_19": agent_19,
    "agent_20": agent_20,
    "agent_21": agent_21,
    "agent_22": agent_22,
    "agent_23": agent_23,
    "agent_24": agent_24,
    "agent_25": agent_25,
    "agent_26": agent_26,
}

__all__ = ["AGENT_REGISTRY"]
