"""Tests unitaires pour les modèles Pydantic."""

import pytest
from pydantic import ValidationError

from hermes.models.common import AgentStatus, QualityMode, SessionStatus
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.models.agent_data import (
    FicheEntreprise, FichePersona, SerpData, Brouillon,
    GrilleScores, ScoresFinaux, FactCheckData, ErreurFactuelle,
)


class TestSessionState:
    """Tests pour SessionState."""

    def test_creation_minimale(self):
        state = SessionState(keyword="test")
        assert state.keyword == "test"
        assert len(state.session_id) == 12
        assert state.status == SessionStatus.CREATED

    def test_session_id_unique(self):
        s1 = SessionState()
        s2 = SessionState()
        assert s1.session_id != s2.session_id

    def test_config_defaults(self):
        state = SessionState()
        assert state.config.mode == QualityMode.STANDARD
        assert state.config.token_budget == 1_000_000
        assert state.config.cost_budget == 5.0

    def test_agent_results_empty(self):
        state = SessionState()
        assert state.agent_results == {}


class TestAgentResult:
    """Tests pour AgentResult."""

    def test_creation(self):
        result = AgentResult(agent_id="agent_01", agent_name="Test")
        assert result.status == AgentStatus.PENDING

    def test_with_data(self):
        result = AgentResult(
            agent_id="agent_01",
            agent_name="Test",
            tokens_input=100,
            tokens_output=50,
            cost_estimated=0.001,
            model_used="deepseek-v4-flash",
        )
        assert result.tokens_input == 100
        assert result.tokens_output == 50


class TestFicheEntreprise:
    """Tests pour FicheEntreprise (Agent 01)."""

    def test_valide(self):
        fiche = FicheEntreprise(
            nom="TestCorp",
            secteur="saas",
            positionnement="Leader du marché",
        )
        assert fiche.nom == "TestCorp"
        assert fiche.offres == []

    def test_invalide(self):
        with pytest.raises(ValidationError):
            FicheEntreprise()  # nom et secteur requis


class TestBrouillon:
    """Tests pour Brouillon (Agent 09)."""

    def test_valide(self):
        b = Brouillon(html="<h1>Test</h1><p>Contenu</p>", word_count=10)
        assert b.html == "<h1>Test</h1><p>Contenu</p>"
        assert b.word_count == 10

    def test_invalide_sans_html(self):
        with pytest.raises(ValidationError):
            Brouillon()


class TestScoresFinaux:
    """Tests pour ScoresFinaux (Agent 25)."""

    def test_default(self):
        scores = ScoresFinaux()
        assert scores.score_total == 0
        assert scores.seuil_publication == 75
        assert not scores.seuil_atteint

    def test_above_threshold(self):
        scores = ScoresFinaux(
            scores=GrilleScores(
                lisibilite=8, densite_semantique=12, reponse_paa=18,
                originalite=12, fraicheur=8, respect_aeo=8,
                respect_geo=7, absence_erreurs=6, naturalite=3,
            ),
            score_total=82,
            seuil_atteint=True,
        )
        assert scores.score_total == 82
        assert scores.seuil_atteint


class TestFactCheckData:
    """Tests pour FactCheckData (Agent 15)."""

    def test_sans_erreurs(self):
        data = FactCheckData(score_fiabilite=10)
        assert data.score_fiabilite == 10
        assert data.erreurs == []

    def test_avec_erreurs(self):
        data = FactCheckData(
            erreurs=[
                ErreurFactuelle(
                    emplacement="Introduction",
                    texte_original="Le taux est de 5%",
                    correction="Le taux est de 3.5%",
                    source="https://service-public.fr",
                    gravite="moderee",
                )
            ],
            score_fiabilite=8,
        )
        assert len(data.erreurs) == 1
        assert data.score_fiabilite == 8
