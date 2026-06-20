"""Routeur heuristique — deterministe avant LLM.

Pattern : essayer une analyse deterministe (gratuite, rapide) avant
d'appeler le LLM. Si la confiance heuristique est suffisante,
economiser l'appel LLM. Sinon, utiliser le LLM en fallback.

Portage du principe saas-seo : Cheerio(0$) -> score(0$) -> LLM(nuance)
"""

import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("hermes.heuristic_router")


def route_heuristic_first(
    agent_id: str,
    heuristic_fn: Callable,
    heuristic_input: Any,
    llm_fn: Optional[Callable] = None,
    confidence_threshold: float = 0.7,
) -> tuple[Any, bool, str]:
    """Essaie l'heuristique d'abord, fallback LLM si necessaire.

    Args:
        agent_id: ID de l'agent (pour les logs)
        heuristic_fn: fonction deterministe a executer en premier
        heuristic_input: donnees d'entree pour l'heuristique
        llm_fn: fonction LLM asynchrone (si None, retourne juste l'heuristique)
        confidence_threshold: seuil de confiance pour accepter l'heuristique

    Returns:
        (resultat, used_llm, source)
        used_llm: True si le LLM a ete appele
        source: "heuristic" | "llm" | "heuristic+llm"
    """
    # Etape 1 : heuristique
    try:
        heuristic_result = heuristic_fn(heuristic_input)
        if heuristic_result is not None and _has_sufficient_confidence(
            heuristic_result, confidence_threshold
        ):
            logger.info(
                f"[{agent_id}] Heuristique OK (confiance >= {confidence_threshold}), "
                f"LLM non appele → economie $"
            )
            return heuristic_result, False, "heuristic"
    except Exception as e:
        logger.warning(f"[{agent_id}] Heuristique echouee: {e}, fallback LLM")

    # Etape 2 : LLM
    if llm_fn is not None:
        logger.info(f"[{agent_id}] Heuristique insuffisante, appel LLM...")
        try:
            llm_result = llm_fn(heuristic_input)
            return llm_result, True, "llm"
        except Exception as e:
            logger.error(f"[{agent_id}] LLM egalement echoue: {e}")
            # Dernier recours : retourner l'heuristique meme faible
            if heuristic_result is not None:
                return heuristic_result, False, "heuristic_fallback"
            raise

    return heuristic_result, False, "heuristic"


def _has_sufficient_confidence(result: Any, threshold: float) -> bool:
    """Evalue la confiance d'un resultat heuristique.

    Pour un dict : cherche une cle 'confidence' ou 'score'.
    Pour un objet : cherche un attribut 'confidence'.
    Sinon : True si non-None (confiance par defaut).
    """
    if isinstance(result, dict):
        conf = result.get("confidence", result.get("score", result.get("_confidence")))
        if conf is not None:
            return float(conf) >= threshold
        # Si pas de champ confidence mais resultat non vide → confiance OK
        return bool(result)

    if hasattr(result, "confidence"):
        return float(result.confidence) >= threshold

    return result is not None


async def async_route_heuristic_first(
    agent_id: str,
    heuristic_fn: Callable,
    heuristic_input: Any,
    llm_fn: Optional[Callable] = None,
    confidence_threshold: float = 0.7,
) -> tuple[Any, bool, str]:
    """Version asynchrone de route_heuristic_first."""
    # Etape 1 : heuristique (peut etre async)
    try:
        if asyncio.iscoroutinefunction(heuristic_fn):
            heuristic_result = await heuristic_fn(heuristic_input)
        else:
            heuristic_result = heuristic_fn(heuristic_input)

        if heuristic_result is not None and _has_sufficient_confidence(
            heuristic_result, confidence_threshold
        ):
            logger.info(
                f"[{agent_id}] Heuristique OK → LLM non appele (economie $)"
            )
            return heuristic_result, False, "heuristic"
    except Exception as e:
        logger.warning(f"[{agent_id}] Heuristique echouee: {e}")

    # Etape 2 : LLM
    if llm_fn is not None:
        logger.info(f"[{agent_id}] Fallback LLM...")
        try:
            if asyncio.iscoroutinefunction(llm_fn):
                llm_result = await llm_fn(heuristic_input)
            else:
                llm_result = llm_fn(heuristic_input)
            return llm_result, True, "llm"
        except Exception as e:
            logger.error(f"[{agent_id}] LLM echoue: {e}")
            if heuristic_result is not None:
                return heuristic_result, False, "heuristic_fallback"
            raise

    return heuristic_result, False, "heuristic"


# Mapping agent → economie potentielle LLM
AGENT_LLM_COST_SAVING: dict[str, float] = {
    "agent_01": 0.0004,  # DeepSeek V4 Flash
    "agent_02": 0.0005,  # DeepSeek V4 Flash
    "agent_04": 0.0003,  # DeepSeek V4 Flash
    "agent_05": 0.0003,  # DeepSeek V4 Flash
    "agent_06": 0.0002,  # DeepSeek V4 Flash
    "agent_07": 0.0003,  # DeepSeek V4 Flash
}

# Agents qui ont deja des heuristiques solides
AGENTS_WITH_HEURISTICS: dict[str, Callable] = {
    # agent_04 a deja _classify_intent_heuristic + _classify_type_heuristic
    "agent_04": True,
    # Les autres peuvent etre ajoutes progressivement
}
