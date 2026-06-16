"""Exceptions métier Hermes SEO."""


class HermesError(Exception):
    """Exception de base pour toutes les erreurs Hermes."""


class StartupCheckError(HermesError):
    """Échec du startup check — le pipeline ne peut pas démarrer."""


class AgentError(HermesError):
    """Erreur lors de l'exécution d'un agent."""

    def __init__(self, agent_id: str, message: str, original_error: Exception | None = None):
        self.agent_id = agent_id
        self.original_error = original_error
        super().__init__(f"[{agent_id}] {message}")


class SupervisorBlockError(HermesError):
    """Le superviseur a bloqué la progression."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__(f"Pipeline bloqué: {'; '.join(reasons)}")


class BudgetExceededError(HermesError):
    """Budget token ou coût dépassé — confirmation requise."""


class ValidationError_(HermesError):
    """Erreur de validation Pydantic dans le pipeline."""


class MemoryError_(HermesError):
    """Erreur d'accès à la mémoire persistante."""


class LLMError(HermesError):
    """Erreur d'appel à une API LLM."""


class SerpAPIError(HermesError):
    """Erreur d'appel à l'API SERP."""


class CMSExportError(HermesError):
    """Erreur d'export vers le CMS."""


class SessionNotFoundError(HermesError):
    """Session introuvable."""


class AgentNotFoundError(HermesError):
    """Agent non trouvé dans le registre."""


class SkipBlockedError(HermesError):
    """Tentative de skip d'un agent non skippable."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(
            f"L'agent {agent_id} n'est pas skippable. "
            f"Passez en mode debug pour forcer le skip."
        )
