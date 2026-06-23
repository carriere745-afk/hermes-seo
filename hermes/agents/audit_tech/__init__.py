"""Pipeline Audit Technique — Registre des 20 agents.

Ordre d'execution :
  Phase 0 : T00
  Phase 1 : T01, T02, T03, T04, T20
  Phase 2 : T05, T06, T07, T08, T09, T10, T11, T12, T13
  Phase 3 : T14
  Phase 4 : T15, T16, T17
  Phase 5 : T18, T19
"""

# Agents implementes au Sprint 1
from hermes.agents.audit_tech.tt00_supervisor import run as tt00
from hermes.agents.audit_tech.tt01_crawler import run as tt01
# Sprint 2
from hermes.agents.audit_tech.tt03_architecture import run as tt03
from hermes.agents.audit_tech.tt04_sitemap import run as tt04
# Sprint 3
from hermes.agents.audit_tech.tt02_indexation import run as tt02
from hermes.agents.audit_tech.tt05_structure import run as tt05
from hermes.agents.audit_tech.tt06_thin_content import run as tt06

# Sprint 4
from hermes.agents.audit_tech.tt07_performance import run as tt07
from hermes.agents.audit_tech.tt08_mobile import run as tt08
from hermes.agents.audit_tech.tt09_schemas import run as tt09
# Sprint 5
from hermes.agents.audit_tech.tt10_international import run as tt10
from hermes.agents.audit_tech.tt11_security import run as tt11
from hermes.agents.audit_tech.tt12_maillage import run as tt12
from hermes.agents.audit_tech.tt21_code_quality import run as tt21
# Sprint 6 — Phase 3: Detection & Impact
from hermes.agents.audit_tech.tt13_anomalies import run as tt13
from hermes.agents.audit_tech.tt14_impact import run as tt14
# Sprint 7 — Phase 4: Synthese & Decision
from hermes.agents.audit_tech.tt15_synthesis import run as tt15
from hermes.agents.audit_tech.tt16_prioritization import run as tt16
from hermes.agents.audit_tech.tt17_roadmap import run as tt17
# Sprint 8 — Phase 5: Export & Routing
from hermes.agents.audit_tech.tt18_routing import run as tt18
from hermes.agents.audit_tech.tt19_export import run as tt19
from hermes.agents.audit_tech.tt20_logs import run as tt20

TECH_REGISTRY: dict[str, callable] = {
    "tt00": tt00, "tt01": tt01, "tt02": tt02, "tt03": tt03,
    "tt04": tt04, "tt05": tt05, "tt06": tt06, "tt07": tt07,
    "tt08": tt08, "tt09": tt09, "tt10": tt10, "tt11": tt11,
    "tt12": tt12, "tt13": tt13, "tt14": tt14, "tt15": tt15,
    "tt16": tt16, "tt17": tt17, "tt18": tt18, "tt19": tt19,
    "tt20": tt20, "tt21": tt21,
    # Sprint 4+
    # "tt07": tt07, "tt08": tt08, "tt09": tt09,
    # Sprint 5+
    # "tt10": tt10, "tt11": tt11, "tt12": tt12,
    # Sprint 6+
    # "tt13": tt13, "tt14": tt14,
    # Sprint 7+
    # "tt15": tt15, "tt16": tt16, "tt17": tt17,
    # Sprint 8+
    # "tt18": tt18, "tt19": tt19, "tt20": tt20,
}

TECH_ORDER: list[str] = [
    # Phase 0
    "tt00",
    # Phase 1 — Collecte
    "tt01", "tt02", "tt03", "tt04", "tt20",
    # Phase 2 — Analyse
    "tt05", "tt06", "tt07", "tt08", "tt09",
    "tt10", "tt11", "tt12", "tt13", "tt21",
    # Phase 3 — Impact
    "tt14",
    # Phase 4 — Synthese
    "tt15", "tt16", "tt17",
    # Phase 5 — Export
    "tt18", "tt19",
]
