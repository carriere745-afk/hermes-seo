"""Factory LLM multi-modèle avec routage intelligent.

Supporte Claude, GPT, DeepSeek, et Ollama (fallback local).
Chaque type de tâche a un modèle principal et un fallback.
Timeout + retry automatique pour éviter les coupures.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger("hermes.llm")


class ModelProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class TaskType(str, Enum):
    REDACTION = "redaction"          # Rédaction longue → Claude Sonnet
    ANALYSIS = "analysis"             # Analyse structurée → GPT-5.4
    VERIFICATION = "verification"     # Vérification rapide → Claude Haiku
    LIGHT = "light"                   # Tâche légère → DeepSeek V4 Flash
    BUDGET = "budget"                 # Budget serré → DeepSeek V4 Flash


@dataclass
class ModelConfig:
    provider: ModelProvider
    model_id: str
    input_cost: float   # $ par million tokens
    output_cost: float  # $ par million tokens
    supports_vision: bool = False
    supports_prompt_caching: bool = False
    max_tokens: int = 4096
    temperature: float = 0.3  # Basse pour tâches structurées


# Configuration des modèles — juin 2026
MODELS: dict[str, ModelConfig] = {
    "claude-sonnet-4-6": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-sonnet-4-6-20250514",
        input_cost=3.00, output_cost=15.00,
        supports_vision=True, supports_prompt_caching=True,
        max_tokens=8192, temperature=0.7,
    ),
    "claude-haiku-4-5": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-haiku-4-5-20251001",
        input_cost=1.00, output_cost=5.00,
        supports_vision=True, supports_prompt_caching=True,
        max_tokens=4096, temperature=0.3,
    ),
    "claude-opus-4-7": ModelConfig(
        provider=ModelProvider.ANTHROPIC,
        model_id="claude-opus-4-7-20250601",
        input_cost=5.00, output_cost=25.00,
        supports_vision=True, supports_prompt_caching=True,
        max_tokens=16384, temperature=0.5,
    ),
    "gpt-5.4": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-5.4",
        input_cost=2.50, output_cost=15.00,
        supports_vision=True, supports_prompt_caching=True,
        max_tokens=8192, temperature=0.3,
    ),
    "gpt-5.4-mini": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-5.4-mini",
        input_cost=0.75, output_cost=4.50,
        max_tokens=4096, temperature=0.3,
    ),
    "gpt-5.4-nano": ModelConfig(
        provider=ModelProvider.OPENAI,
        model_id="gpt-5.4-nano",
        input_cost=0.20, output_cost=1.25,
        max_tokens=4096, temperature=0.3,
    ),
    "deepseek-v4-flash": ModelConfig(
        provider=ModelProvider.DEEPSEEK,
        model_id="deepseek-v4-flash",
        input_cost=0.14, output_cost=0.28,
        supports_prompt_caching=True,
        max_tokens=8192, temperature=0.3,
    ),
    "deepseek-v4-pro": ModelConfig(
        provider=ModelProvider.DEEPSEEK,
        model_id="deepseek-v4-pro",
        input_cost=0.435, output_cost=0.87,
        supports_prompt_caching=True,
        max_tokens=8192, temperature=0.5,
    ),
    "gemini-3.1-flash-lite": ModelConfig(
        provider=ModelProvider.GEMINI,
        model_id="gemini-3.1-flash-lite",
        input_cost=0.25, output_cost=1.50,
        max_tokens=4096, temperature=0.3,
    ),
    "ollama-llama4": ModelConfig(
        provider=ModelProvider.OLLAMA,
        model_id="llama4:latest",
        input_cost=0.0, output_cost=0.0,
        max_tokens=4096, temperature=0.3,
    ),
}

# Routage par type de tâche
TASK_ROUTING: dict[TaskType, tuple[str, str, str]] = {
    # (principal, fallback1, fallback2)
    TaskType.REDACTION:    ("claude-sonnet-4-6", "gpt-5.4", "deepseek-v4-pro"),
    TaskType.ANALYSIS:     ("gpt-5.4", "deepseek-v4-flash", "claude-haiku-4-5"),
    TaskType.VERIFICATION: ("claude-haiku-4-5", "deepseek-v4-flash", "gpt-5.4-mini"),
    TaskType.LIGHT:        ("deepseek-v4-flash", "gpt-5.4-mini", "claude-haiku-4-5"),
    TaskType.BUDGET:       ("deepseek-v4-flash", "gemini-3.1-flash-lite", "gpt-5.4-nano"),
}

# Mapping agent_id → task_type
AGENT_TASK_TYPE: dict[str, TaskType] = {
    "agent_01": TaskType.LIGHT,
    "agent_02": TaskType.LIGHT,
    "agent_03": TaskType.ANALYSIS,
    "agent_04": TaskType.ANALYSIS,
    "agent_05": TaskType.LIGHT,
    "agent_06": TaskType.LIGHT,
    "agent_07": TaskType.LIGHT,
    "agent_08": TaskType.VERIFICATION,
    "agent_09": TaskType.REDACTION,
    "agent_10": TaskType.ANALYSIS,
    "agent_11": TaskType.VERIFICATION,
    "agent_12": TaskType.VERIFICATION,
    "agent_13": TaskType.VERIFICATION,
    "agent_14": TaskType.VERIFICATION,
    "agent_15": TaskType.VERIFICATION,
    "agent_16": TaskType.LIGHT,
    "agent_17": TaskType.LIGHT,
    "agent_18": TaskType.REDACTION,
    "agent_19": TaskType.ANALYSIS,
    "agent_20": TaskType.REDACTION,
    "agent_21": TaskType.ANALYSIS,
    "agent_22": TaskType.LIGHT,
    "agent_23": TaskType.LIGHT,
    "agent_24": TaskType.LIGHT,
    "agent_25": TaskType.VERIFICATION,
    "agent_26": TaskType.LIGHT,
}


class LLMClientProtocol(Protocol):
    """Interface commune à tous les clients LLM."""

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> tuple[str, int, int]:
        """Retourne (texte, tokens_input, tokens_output)."""
        ...


class LLMFactory:
    """Factory qui route les appels vers le bon fournisseur.

    Usage:
        factory = LLMFactory()
        text, tokens_in, tokens_out = await factory.route(
            system_prompt="...",
            user_message="...",
            agent_id="agent_09",
        )
    """

    def __init__(
        self,
        anthropic_api_key: str = "",
        openai_api_key: str = "",
        deepseek_api_key: str = "",
        gemini_api_key: str = "",
        ollama_base_url: str = "http://localhost:11434",
        dry_run: bool = False,
    ):
        self.dry_run = dry_run
        self._anthropic_key = anthropic_api_key
        self._openai_key = openai_api_key
        self._deepseek_key = deepseek_api_key
        self._gemini_key = gemini_api_key
        self._ollama_url = ollama_base_url

    def _get_available_models(self) -> list[str]:
        """Liste les modèles disponibles selon les clés API configurées."""
        available = []
        if self._anthropic_key:
            available.extend(["claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-7"])
        if self._openai_key:
            available.extend(["gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"])
        if self._deepseek_key:
            available.extend(["deepseek-v4-flash", "deepseek-v4-pro"])
        if self._gemini_key:
            available.append("gemini-3.1-flash-lite")
        if self._ollama_url:
            available.append("ollama-llama4")
        return available

    def select_model(self, agent_id: str, budget_tight: bool = False) -> str:
        """Sélectionne le meilleur modèle disponible pour un agent.

        Ordre : principal > fallback1 > fallback2 > premier disponible.
        """
        task_type = AGENT_TASK_TYPE.get(agent_id, TaskType.LIGHT)
        if budget_tight:
            task_type = TaskType.BUDGET

        candidates = list(TASK_ROUTING[task_type])
        available = self._get_available_models()

        for candidate in candidates:
            if candidate in available:
                return candidate

        # Fallback ultime
        if available:
            return available[0]
        return "ollama-llama4"  # Dernier recours

    async def route(
        self,
        system_prompt: str,
        user_message: str,
        agent_id: str,
        temperature: float | None = None,
        max_tokens: int = 4096,
        budget_tight: bool = False,
    ) -> tuple[str, int, int, str]:
        """Route l'appel vers le modèle approprié avec retry automatique.

        Returns (texte, tokens_input, tokens_output, model_used).
        Retente jusqu'a 3 fois avec backoff exponentiel + jitter
        sur les erreurs transitoires (429, 5xx, timeout, connexion).
        """
        if self.dry_run:
            return self._dry_run_response(agent_id)

        model_name = self.select_model(agent_id, budget_tight)
        config = MODELS.get(model_name)
        if config is None:
            raise ValueError(f"Modèle inconnu: {model_name}")

        if temperature is None:
            temperature = config.temperature

        retryer = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

        # 1. Tenter le modele principal avec retry sur erreurs transitoires
        last_error: Exception | None = None
        try:
            async for attempt in retryer:
                with attempt:
                    try:
                        text, ti, to = await self._call_provider(
                            config, system_prompt, user_message, temperature, max_tokens
                        )
                        return text, ti, to, model_name
                    except Exception as e:
                        last_error = e
                        if _is_retryable(e):
                            logger.warning(
                                f"[{agent_id}] {config.model_id} erreur retryable "
                                f"(tentative {attempt.retry_state.attempt_number}/3): {str(e)[:120]}"
                            )
                        raise  # tenacity decide retry vs stop selon _is_retryable
        except Exception as e:
            last_error = e
            logger.warning(f"[{agent_id}] {model_name} echec definitif: {str(e)[:120]}. Bascule vers fallback.")

        # 2. Bascule vers les fallbacks (auth, key invalide, etc.)
        task_type = AGENT_TASK_TYPE.get(agent_id, TaskType.LIGHT)
        fallbacks = list(TASK_ROUTING[task_type])[1:]  # exclure le principal
        available = self._get_available_models()
        for fallback in fallbacks:
            if fallback in available and fallback != model_name:
                try:
                    fb_config = MODELS[fallback]
                    text, ti, to = await self._call_provider(
                        fb_config, system_prompt, user_message, temperature, max_tokens
                    )
                    logger.info(
                        f"[{agent_id}] Fallback OK vers {fallback} (echec de {model_name})"
                    )
                    return text, ti, to, fallback
                except Exception as fe:
                    logger.warning(f"[{agent_id}] Fallback {fallback} echec: {str(fe)[:100]}")
                    continue

        # 3. Tous les modeles ont echoue
        raise last_error or RuntimeError(f"Tous les modeles ont echoue pour {agent_id}")

    async def _call_provider(
        self,
        config: ModelConfig,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> tuple[str, int, int]:
        """Appelle le fournisseur approprié."""
        if config.provider == ModelProvider.ANTHROPIC:
            return await self._call_anthropic(config, system_prompt, user_message, temperature, max_tokens)
        elif config.provider in (ModelProvider.OPENAI, ModelProvider.DEEPSEEK):
            return await self._call_openai_compatible(config, system_prompt, user_message, temperature, max_tokens)
        elif config.provider == ModelProvider.GEMINI:
            return await self._call_gemini(config, system_prompt, user_message, temperature, max_tokens)
        elif config.provider == ModelProvider.OLLAMA:
            return await self._call_ollama(config, system_prompt, user_message, temperature, max_tokens)
        raise ValueError(f"Provider inconnu: {config.provider}")

    async def _call_anthropic(
        self, config: ModelConfig, system: str, user: str,
        temperature: float, max_tokens: int,
    ) -> tuple[str, int, int]:
        import anthropic
        import httpx
        client = anthropic.AsyncAnthropic(
            api_key=self._anthropic_key,
            timeout=httpx.Timeout(_adaptive_timeout(max_tokens)),
            max_retries=0,  # On gere le retry nous-memes via tenacity
        )
        response = await client.messages.create(
            model=config.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Claude peut renvoyer TextBlock ou ThinkingBlock
        text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                text += block.text
        if not text and response.content:
            text = str(response.content[0])
        return (
            text,
            response.usage.input_tokens if response.usage else 0,
            response.usage.output_tokens if response.usage else 0,
        )

    async def _call_openai_compatible(
        self, config: ModelConfig, system: str, user: str,
        temperature: float, max_tokens: int,
    ) -> tuple[str, int, int]:
        from openai import AsyncOpenAI
        import httpx

        if config.provider == ModelProvider.DEEPSEEK:
            base_url = "https://api.deepseek.com"
            api_key = self._deepseek_key
        else:
            base_url = None
            api_key = self._openai_key

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(_adaptive_timeout(max_tokens)),
            max_retries=0,  # On gere le retry nous-memes
        )
        # OpenAI utilise max_completion_tokens, DeepSeek utilise max_tokens
        params = {
            "model": config.model_id,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if config.provider == ModelProvider.DEEPSEEK:
            params["max_tokens"] = max_tokens
        else:
            params["max_completion_tokens"] = max_tokens
        response = await client.chat.completions.create(**params)
        choice = response.choices[0]
        return (
            choice.message.content or "",
            response.usage.prompt_tokens if response.usage else 0,
            response.usage.completion_tokens if response.usage else 0,
        )

    async def _call_ollama(
        self, config: ModelConfig, system: str, user: str,
        temperature: float, max_tokens: int,
    ) -> tuple[str, int, int]:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": config.model_id,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data.get("message", {}).get("content", "")
            # Ollama ne donne pas le compte de tokens nativement
            estimated = len(system + user + text) // 4
            return text, estimated, estimated

    async def _call_gemini(
        self, config: ModelConfig, system: str, user: str,
        temperature: float, max_tokens: int,
    ) -> tuple[str, int, int]:
        """Appelle l'API Gemini via REST (pas de SDK specifique necessaire)."""
        import httpx
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.model_id}:generateContent"
        )
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                url,
                params={"keyProviders": self._gemini_key},
                json={
                    "systemInstruction": {
                        "parts": [{"text": system}],
                    },
                    "contents": [
                        {"role": "user", "parts": [{"text": user}]},
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens,
                    },
                },
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts)
            usage = data.get("usageMetadata", {})
            return (
                text,
                usage.get("promptTokenCount", 0),
                usage.get("candidatesTokenCount", 0),
            )

    def _dry_run_response(self, agent_id: str) -> tuple[str, int, int, str]:
        """Réponse simulée pour le mode dry-run."""
        return (
            f'{{"message": "Dry-run response for {agent_id}", "status": "simulated"}}',
            0, 0, "dry-run",
        )


def _adaptive_timeout(max_tokens: int) -> float:
    """Timeout adaptatif base sur la formule : max(45, maxTokens/50 + 30).

    Pour 8000 tokens → 190s. Pour 500 tokens → 45s.
    Evite les timeout trop courts sur les longues generations.
    """
    return max(45.0, max_tokens / 50.0 + 30.0)


def _repair_json(text: str) -> dict:
    """Repare le JSON mal forme des LLMs (3 niveaux de defense).

    1. Strict parse
    2. Regex extract from markdown fences
    3. jsonrepair (si installe)
    """
    import json as _json
    import re as _re

    # Niveau 1 : parse strict
    try:
        return _json.loads(text.strip())
    except _json.JSONDecodeError:
        pass

    # Niveau 2 : extraction depuis markdown fences
    match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL)
    if match:
        try:
            return _json.loads(match.group(1))
        except _json.JSONDecodeError:
            pass

    match = _re.search(r"\{.*\}", text, _re.DOTALL)
    if match:
        try:
            return _json.loads(match.group(0))
        except _json.JSONDecodeError:
            pass

    # Niveau 3 : json-repair (si disponible)
    try:
        from json_repair import repair_json
        repaired = repair_json(text)
        return _json.loads(repaired)
    except (ImportError, Exception):
        pass

    return {}


def _is_retryable(exception: Exception) -> bool:
    """Determine si une erreur merite un retry.

    Retry : rate limits (429), erreurs serveur (5xx),
    timeouts, connexion reset, DNS temporaire.
    Pas de retry : erreurs client (4xx sauf 429), auth, validation.
    """
    msg = str(exception).lower()

    # Erreurs NON-retryables (bascule immediate vers fallback)
    non_retryable_markers = [
        "authentication_error",
        "invalid x-api-key",
        "invalid_api_key",
        "incorrect api key",
        "unauthorized",
        "401",
        "403",
        "permission_denied",
        "insufficient_quota",
        "billing",
    ]
    for marker in non_retryable_markers:
        if marker in msg:
            return False

    # Marqueurs textuels d'erreurs retryables
    retryable_markers = [
        "rate limit",
        "rate_limit",
        "too many requests",
        "429",
        "server error",
        "internal server error",
        "503",
        "502",
        "504",
        "timeout",
        "timed out",
        "connection reset",
        "connection error",
        "connection refused",
        "temporarily unavailable",
        "overloaded",
        "service unavailable",
        "try again",
        "retry",
    ]
    for marker in retryable_markers:
        if marker in msg:
            return True

    # Codes HTTP retryables
    try:
        status = getattr(exception, 'status_code', None)
        if status is not None:
            return status in (429, 500, 502, 503, 504)
    except Exception:
        pass

    # httpx.TimeoutException et variantes
    try:
        import httpx
        if isinstance(exception, httpx.TimeoutException):
            return True
        if isinstance(exception, httpx.NetworkError):
            return True
        if isinstance(exception, httpx.RemoteProtocolError):
            return True
    except ImportError:
        pass

    # asyncio.TimeoutError
    if isinstance(exception, asyncio.TimeoutError):
        return True

    return False
