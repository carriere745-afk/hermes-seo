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

TECH_REGISTRY: dict[str, callable] = {
    "tt00": tt00,
    "tt01": tt01,
    # Sprint 2+
    # "tt02": tt02, "tt03": tt03, "tt04": tt04,
    # Sprint 3+
    # "tt05": tt05, "tt06": tt06,
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
    "tt00",
    "tt01",
    # Les agents suivants seront ajoutes au fur et a mesure des sprints
]
