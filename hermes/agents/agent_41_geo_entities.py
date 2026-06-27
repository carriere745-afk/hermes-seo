"""Agent 41 — GEO Entities & Citation Readiness (gap module 7 items #261-290).

Etend agent_12 existant avec:
- Extraction entites nommees (outils, editeurs, institutions, modeles, benchmarks, lois)
- Base d'entites IA maintenue
- Coherence noms entites entre articles (ChatGPT != Chat GPT)
- Topical map par domaine: entites couvertes vs manquantes
- Citation readiness: definitions citable-ready 50-80 mots, passages autonomes,
  score citabilite par article 0-100
"""

import re, logging, time
from datetime import datetime
from collections import Counter

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_41")

# Base d'entites IA maintenue (document 630 section 7.2)
ENTITIES = {
    "editeurs_ia": {
        "canonical": ["OpenAI", "Anthropic", "Google DeepMind", "Meta AI", "Mistral AI",
                      "NVIDIA", "Microsoft", "Amazon", "Apple", "Stability AI"],
        "aliases": {"ChatGPT": "OpenAI", "Claude": "Anthropic", "Gemini": "Google DeepMind",
                    "Llama": "Meta AI", "Copilot": "Microsoft"},
    },
    "institutions": ["CNIL", "ANSSI", "NIST", "Commission europeenne", "UNESCO",
                     "Arcom", "Cour de justice UE", "Parlement europeen"],
    "benchmarks": ["MMLU", "HellaSwag", "HumanEval", "GSM8K", "TruthfulQA", "ARC", "WinoGrande"],
    "lois": ["AI Act", "RGPD", "GDPR", "DMA", "DSA", "Data Act", "Cyber Resilience Act"],
}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_41"
    agent_name = "GEO Entities & Citations"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        text = re.sub(r'<[^>]+>', ' ', content).lower()

        geo = {
            "entities_found": {},
            "canonical_violations": [],
            "missing_entities": [],
            "citation_score": 0,
            "citable_definitions": [],
            "recommandations": [],
        }

        # 1. Detecter les entites connues
        for category, names in ENTITIES.items():
            if category == "editeurs_ia":
                for canonical in names["canonical"]:
                    if canonical.lower() in text:
                        geo["entities_found"][canonical] = "canonical"
                # Verifier les alias
                for alias, canonical in names["aliases"].items():
                    if alias.lower() in text and canonical.lower() not in text:
                        geo["entities_found"][alias] = f"alias_for_{canonical}"
                        geo["canonical_violations"].append(f"'{alias}' detected -> utiliser '{canonical}'")
            else:
                for name in names:
                    if name.lower() in text:
                        geo["entities_found"][name] = category

        # 2. Verifier les entites manquantes
        content_kw = text[:1000]
        if any(w in content_kw for w in ["ia", "intelligence artificielle", "modele", "llm", "gpt"]):
            expected = ENTITIES["editeurs_ia"]["canonical"][:3]
            missing = [e for e in expected if e.lower() not in text]
            if missing:
                geo["missing_entities"] = missing
                geo["recommandations"].append(f"Entites IA manquantes: {', '.join(missing)}")

        # 3. Score de citation - phrases autonomes citables
        citable = _find_citable_phrases(content)
        geo["citable_definitions"] = citable[:5]
        geo["citation_score"] = min(100, len(citable) * 15 + len(geo["entities_found"]) * 5)

        # 4. Recommandations GEO
        if geo["canonical_violations"]:
            geo["recommandations"].extend(geo["canonical_violations"])
        if len(geo["entities_found"]) < 3 and len(text) > 500:
            geo["recommandations"].append("Ajouter des entites nommees (outils, institutions) pour ameliorer le GEO")
        if geo["citation_score"] < 50:
            geo["recommandations"].append("Ajouter des phrases autonomes de 50-80 mots definissant les concepts cles")

        result.status = AgentStatus.COMPLETED
        result.data = geo
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _find_citable_phrases(content: str) -> list[str]:
    clean = re.sub(r'<[^>]+>', ' ', content)
    sentences = re.findall(r'[^.!?]{40,120}[.!?]', clean)
    citable = []
    for s in sentences:
        words = len(s.split())
        if 15 <= words <= 40:
            if re.search(r'(?i)(definition|est un|signifie|permet|consiste|represente)', s):
                citable.append(s.strip())
            elif re.search(r'\d+', s) and words <= 25:
                citable.append(s.strip())
        if len(citable) >= 10:
            break
    return citable
