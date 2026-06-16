"""Comptage de tokens et estimation de coûts."""

from hermes.core.budget import BudgetTracker


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Estime le nombre de tokens d'un texte.

    Utilise tiktoken si disponible, sinon approximation.
    """
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Approximation grossière : ~4 caractères par token
        return len(text) // 4


def estimate_cost(
    model: str,
    tokens_input: int,
    tokens_output: int,
) -> float:
    """Estime le coût d'un appel LLM."""
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return tracker.estimate_cost(model, tokens_input, tokens_output)
