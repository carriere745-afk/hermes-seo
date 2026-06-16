"""Tests unitaires pour Agent 22 — Images."""

import asyncio, pytest
from hermes.agents.agent_22_images import _mock_images, _extract_json, run
from hermes.models.agent_data import ImagePlan
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        type_page="article",
        fiche_entreprise={"nom": "MonAssureur"},
        brouillon_html="<h1>Guide Assurance Vie</h1><p>Contenu complet sur l'assurance vie temporaire.</p>",
        agent_results={"agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED)},
    )


def test_run_3_images(session_valide):
    result = asyncio.run(run(session_valide))
    assert len(result.image_plan["images"]) == 3
    assert result.agent_results["agent_22"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    ImagePlan.model_validate(asyncio.run(run(session_valide)).image_plan)


def test_roles_featured_supporting_infographie(session_valide):
    result = asyncio.run(run(session_valide))
    roles = {img["role"] for img in result.image_plan["images"]}
    assert "featured" in roles
    assert "supporting" in roles
    assert "infographie" in roles


def test_chaque_image_a_prompt_et_alt(session_valide):
    result = asyncio.run(run(session_valide))
    for img in result.image_plan["images"]:
        assert img["prompt"]
        assert img["texte_alt"]
        assert img["dimensions"]


def test_dimensions_featured_1200x630(session_valide):
    result = asyncio.run(run(session_valide))
    featured = [i for i in result.image_plan["images"] if i["role"] == "featured"][0]
    assert featured["dimensions"] == "1200x630"


def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert len(result.image_plan["images"]) == 3


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_22"].data == result.image_plan


def test_mock_produit_role_featured():
    session = SessionState(keyword="enceinte", type_page="fiche_produit",
                           fiche_entreprise={"nom": "Test"}, config=SessionConfig(dry_run=True))
    plan = _mock_images(session)
    featured = plan.images[0]
    assert featured.role == "featured"
    assert "product" in featured.nom.lower()


def test_mock_article_3_images():
    session = SessionState(keyword="test", fiche_entreprise={"nom": "Test"})
    plan = _mock_images(session)
    assert len(plan.images) == 3


def test_extract_json_valide():
    data = _extract_json('{"images": [{"nom": "test", "role": "featured", "prompt": "...", "texte_alt": "...", "dimensions": "1200x630"}]}')
    assert len(data["images"]) == 1
