"""Gestion du budget tokens et coût pour Hermes SEO.

Arrêt BLOQUANT (pas skip automatique silencieux) si les seuils sont dépassés.
"""

from dataclasses import dataclass, field


@dataclass
class BudgetTracker:
    """Suivi du budget d'une session."""

    token_budget: int
    cost_budget: float
    tokens_used: int = 0
    cost_used: float = 0.0
    warnings: list[str] = field(default_factory=list)

    # Coûts par million de tokens (entrée, sortie)
    MODEL_COSTS: dict = field(default_factory=lambda: {
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-4-5": (1.00, 5.00),
        "claude-opus-4-7": (5.00, 25.00),
        "gpt-5.4": (2.50, 15.00),
        "gpt-5.4-mini": (0.75, 4.50),
        "gpt-5.4-nano": (0.20, 1.25),
        "deepseek-v4-flash": (0.14, 0.28),
        "deepseek-v4-pro": (0.435, 0.87),
    })

    def estimate_cost(self, model: str, tokens_input: int, tokens_output: int) -> float:
        """Estime le coût d'un appel LLM."""
        costs = self.MODEL_COSTS.get(model, (0, 0))
        input_cost = (tokens_input / 1_000_000) * costs[0]
        output_cost = (tokens_output / 1_000_000) * costs[1]
        return input_cost + output_cost

    def can_proceed(self, estimated_input: int, estimated_output: int, model: str) -> tuple[bool, str]:
        """Vérifie si l'appel peut être fait dans le budget.

        Returns (peut_continuer, message).
        """
        estimated_cost = self.estimate_cost(model, estimated_input, estimated_output)
        estimated_total_tokens = self.tokens_used + estimated_input + estimated_output
        estimated_total_cost = self.cost_used + estimated_cost

        if estimated_total_tokens > self.token_budget:
            return False, (
                f"Budget tokens dépassé : {estimated_total_tokens:,} estimés / "
                f"{self.token_budget:,} autorisés. Coût estimé: ${estimated_total_cost:.4f}"
            )

        if estimated_total_cost > self.cost_budget:
            return False, (
                f"Budget coût dépassé : ${estimated_total_cost:.4f} estimés / "
                f"${self.cost_budget:.2f} autorisés."
            )

        if estimated_total_cost > self.cost_budget * 0.8:
            return True, (
                f"Alerte budget : ${estimated_total_cost:.4f} estimés "
                f"(>80% du budget de ${self.cost_budget:.2f})"
            )

        return True, ""

    def record_usage(self, tokens_input: int, tokens_output: int, model: str) -> None:
        """Enregistre la consommation réelle."""
        cost = self.estimate_cost(model, tokens_input, tokens_output)
        self.tokens_used += tokens_input + tokens_output
        self.cost_used += cost

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.token_budget - self.tokens_used)

    @property
    def remaining_cost(self) -> float:
        return max(0.0, self.cost_budget - self.cost_used)

    def summary(self) -> str:
        pct_tokens = (self.tokens_used / self.token_budget * 100) if self.token_budget else 0
        pct_cost = (self.cost_used / self.cost_budget * 100) if self.cost_budget else 0
        return (
            f"Budget: {self.tokens_used:,}/{self.token_budget:,} tokens ({pct_tokens:.0f}%), "
            f"${self.cost_used:.4f}/${self.cost_budget:.2f} ({pct_cost:.0f}%)"
        )
