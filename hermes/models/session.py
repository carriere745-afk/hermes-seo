"""État complet d'une session Hermes SEO."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from hermes.models.common import (
    AgentStatus,
    QualityMode,
    SessionStatus,
    generate_session_id,
)


class AgentResult(BaseModel):
    """Résultat d'exécution d'un agent."""

    agent_id: str
    agent_name: str = ""
    status: AgentStatus = AgentStatus.PENDING
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_estimated: Optional[float] = None
    prompt_version: Optional[str] = None
    model_used: Optional[str] = None
    skip_reason: Optional[str] = None
    skip_impact: Optional[str] = None
    data: Optional[dict[str, Any]] = None


class SessionConfig(BaseModel):
    """Configuration d'une session."""

    mode: QualityMode = QualityMode.STANDARD
    dry_run: bool = False
    replay_session_id: Optional[str] = None
    token_budget: int = Field(default=1_000_000, ge=0)
    cost_budget: float = Field(default=5.0, ge=0.0)
    target_url: Optional[str] = None
    target_cms: Optional[str] = None
    target_locales: list[str] = Field(default_factory=list)
    user_skipped_agents: list[str] = Field(default_factory=list)
    secteur: Optional[str] = None
    skip_confirmed: bool = False  # True si l'utilisateur a confirmé les skips


class SessionState(BaseModel):
    """État complet d'une session Hermes SEO."""

    session_id: str = Field(default_factory=generate_session_id)
    status: SessionStatus = SessionStatus.CREATED
    config: SessionConfig = Field(default_factory=SessionConfig)

    # Entrée utilisateur
    keyword: Optional[str] = None
    site_url: Optional[str] = None
    objectif: Optional[str] = None
    contraintes: list[str] = Field(default_factory=list)

    # Résultats de chaque agent
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)

    # Données accumulées (sorties validées de chaque agent)
    fiche_entreprise: Optional[dict[str, Any]] = None
    fiche_persona: Optional[dict[str, Any]] = None
    serp_data: Optional[dict[str, Any]] = None
    intention: Optional[str] = None
    type_page: Optional[str] = None
    offre_conversion_data: Optional[dict[str, Any]] = None
    angles_differenciants: Optional[dict[str, Any]] = None
    template_data: Optional[dict[str, Any]] = None
    anti_cannib_data: Optional[dict[str, Any]] = None
    brouillon_html: Optional[str] = None
    seo_data: Optional[dict[str, Any]] = None
    aeo_blocks: Optional[dict[str, Any]] = None
    geo_data: Optional[dict[str, Any]] = None
    score_eeat: Optional[dict[str, Any]] = None
    conformite_data: Optional[dict[str, Any]] = None
    fact_check_data: Optional[dict[str, Any]] = None
    internal_links: Optional[dict[str, Any]] = None
    external_links: Optional[dict[str, Any]] = None
    multiformat_data: Optional[dict[str, Any]] = None
    variants_ab: Optional[dict[str, Any]] = None
    localised_data: Optional[dict[str, Any]] = None
    ld_json: Optional[dict[str, Any]] = None
    image_plan: Optional[dict[str, Any]] = None
    export_data: Optional[dict[str, Any]] = None
    plan_refresh: Optional[dict[str, Any]] = None
    scores: Optional[dict[str, Any]] = None
    feedback_data: Optional[dict[str, Any]] = None

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    current_agent_id: Optional[str] = None
    last_completed_agent_id: Optional[str] = None
    last_successful_agent_id: Optional[str] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    error_count: int = 0
    warnings: list[str] = Field(default_factory=list)

    def get_agent_result(self, agent_id: str) -> Optional[AgentResult]:
        return self.agent_results.get(agent_id)

    def agent_completed(self, agent_id: str) -> bool:
        result = self.get_agent_result(agent_id)
        return result is not None and result.status == AgentStatus.COMPLETED

    def agent_failed(self, agent_id: str) -> bool:
        result = self.get_agent_result(agent_id)
        return result is not None and result.status == AgentStatus.FAILED
