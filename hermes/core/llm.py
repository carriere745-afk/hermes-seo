"""Factory LLM multi-modèle avec routage intelligent.

Supporte Claude, GPT, DeepSeek, et Ollama (fallback local).
Chaque type de tâche a un modèle principal et un fallback.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol


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
        """Route l'appel vers le modèle approprié.

        Returns (texte, tokens_input, tokens_output, model_used).
        """
        if self.dry_run:
            return self._dry_run_response(agent_id)

        model_name = self.select_model(agent_id, budget_tight)
        config = MODELS.get(model_name)
        if config is None:
            raise ValueError(f"Modèle inconnu: {model_name}")

        if temperature is None:
            temperature = config.temperature

        try:
            text, ti, to = await self._call_provider(
                config, system_prompt, user_message, temperature, max_tokens
            )
            return text, ti, to, model_name
        except Exception as e:
            # Essayer le fallback
            task_type = AGENT_TASK_TYPE.get(agent_id, TaskType.LIGHT)
            fallbacks = list(TASK_ROUTING[task_type])[1:]
            available = self._get_available_models()
            for fallback in fallbacks:
                if fallback in available and fallback != model_name:
                    try:
                        fb_config = MODELS[fallback]
                        text, ti, to = await self._call_provider(
                            fb_config, system_prompt, user_message, temperature, max_tokens
                        )
                        return text, ti, to, fallback
                    except Exception:
                        continue
            raise  # Aucun fallback n'a fonctionné

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
        client = anthropic.AsyncAnthropic(api_key=self._anthropic_key)
        response = await client.messages.create(
            model=config.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = response.content[0].text if response.content else ""
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

        if config.provider == ModelProvider.DEEPSEEK:
            base_url = "https://api.deepseek.com"
            api_key = self._deepseek_key
        else:
            base_url = None
            api_key = self._openai_key

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=config.model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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
