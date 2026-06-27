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
from hermes.agents.agent_27_coherence import run as agent_27
from hermes.agents.agent_28_qualite_linguistique import run as agent_28
from hermes.agents.agent_29_seo_local import run as agent_29
from hermes.agents.agent_30_categories_taxonomies import run as agent_30
from hermes.agents.agent_31_business_roi import run as agent_31
from hermes.agents.agent_32_post_publication import run as agent_32
from hermes.agents.agent_33_images_medias import run as agent_33
from hermes.agents.agent_34_international import run as agent_34
from hermes.agents.agent_35_reputation_social import run as agent_35
from hermes.agents.agent_36_ab_test import run as agent_36
from hermes.agents.agent_37_pagerank_maillage import run as agent_37
from hermes.agents.agent_38_structure_types import run as agent_38
from hermes.agents.agent_39_lsi_coverage import run as agent_39
from hermes.agents.agent_11b_aeo_enrichi import run as agent_11b
from hermes.agents.agent_28b_linguistique_avancee import run as agent_28b
from hermes.agents.agent_40_verification_propriete import run as agent_40
from hermes.agents.agent_41_geo_entities import run as agent_41
from hermes.agents.agent_42_eeat_avance import run as agent_42
from hermes.agents.agent_43_business_intel import run as agent_43
from hermes.agents.agent_44_crawl_avance import run as agent_44
from hermes.agents.agent_45_postpub_alerts import run as agent_45
from hermes.agents.agent_46_performance_cwv import run as agent_46
from hermes.agents.agent_47_schemas_avances import run as agent_47

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
    "agent_27": agent_27,
    "agent_28": agent_28,
    "agent_29": agent_29,
    "agent_30": agent_30, "agent_31": agent_31, "agent_32": agent_32,
    "agent_33": agent_33, "agent_34": agent_34, "agent_35": agent_35,
    "agent_36": agent_36,
    "agent_37": agent_37,
    "agent_38": agent_38, "agent_39": agent_39,
    "agent_11b": agent_11b, "agent_28b": agent_28b,
    "agent_40": agent_40, "agent_41": agent_41, "agent_42": agent_42,
    "agent_43": agent_43, "agent_44": agent_44, "agent_45": agent_45,
    "agent_46": agent_46, "agent_47": agent_47,
}

__all__ = ["AGENT_REGISTRY"]
