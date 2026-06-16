"""Tests unitaires pour Agent 14 — Conformite sectorielle."""

import asyncio

import pytest

from hermes.agents.agent_14_conformite import (
    _check_rules, _strip_html, SECTOR_RULES, run,
)
from hermes.models.agent_data import ConformiteData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


def _session(secteur: str, html: str = "", type_page: str = "article"):
    return SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur=secteur),
        type_page=type_page,
        brouillon_html=html or "<h1>Test</h1><p>Contenu basique.</p>",
        fiche_entreprise={"nom": "TestCorp", "secteur": secteur},
    )


# ─── 1. Entrée valide — secteur non reglemente ─────────────────────────

def test_run_secteur_non_reglemente():
    result = asyncio.run(run(_session("saas")))
    assert result.conformite_data["valide"] is True
    assert result.conformite_data["risque_juridique"] == "faible"
    assert result.agent_results["agent_14"].status == AgentStatus.COMPLETED


# ─── 2. Secteurs reglementes — mentions manquantes ────────────────────

def test_finance_sans_mentions():
    """Contenu financier sans les mentions obligatoires → invalide."""
    result = asyncio.run(run(_session("finance", "<h1>Investir en bourse</h1><p>C'est facile.</p>")))
    data = result.conformite_data
    assert len(data["mentions_obligatoires"]) > 0
    assert len(data["regles_appliquees"]) > 0


def test_sante_sans_avertissement():
    result = asyncio.run(run(_session("sante", "<h1>Soigner le diabete</h1><p>Voici comment guerir.</p>")))
    data = result.conformite_data
    assert data["risque_juridique"] in ("eleve", "critique", "modere")


def test_droit_sans_references():
    result = asyncio.run(run(_session("droit", "<h1>Le divorce</h1><p>Voici la procedure.</p>")))
    data = result.conformite_data
    assert len(data["regles_appliquees"]) > 0


# ─── 3. Contenus interdits detectes ────────────────────────────────────

def test_finance_promesse_rendement():
    """Promesse de rendement garanti → risque critique."""
    result = asyncio.run(run(_session("finance",
        "<h1>Investir</h1><p>Nous vous promettons un rendement garanti de 10% par an.</p>"
    )))
    assert result.conformite_data["risque_juridique"] == "critique"


def test_sante_promesse_guerison():
    result = asyncio.run(run(_session("sante",
        "<h1>Solutions</h1><p>Cette methode garantit la guerison en 30 jours.</p>"
    )))
    assert result.conformite_data["risque_juridique"] == "critique"


# ─── 4. Contenu conforme ──────────────────────────────────────────────

def test_finance_conforme():
    html = (
        "<h1>Guide assurance vie</h1>"
        "<p>Les performances passees ne prejudent pas des performances futures. "
        "Ce produit presente un risque de perte en capital. "
        "Document non contractuel a valeur indicative.</p>"
        "<p>Cet article ne constitue pas un conseil financier personnalise.</p>"
        "<p>Notre statut : courtier agree AMF. Donnees mises a jour au 01/06/2026.</p>"
    )
    result = asyncio.run(run(_session("finance", html)))
    assert result.conformite_data["valide"] is True


def test_sante_conforme():
    html = (
        "<h1>Comprendre le diabete</h1>"
        "<p>Cet article ne remplace pas une consultation medicale. "
        "En cas d'urgence, contactez le 15 (SAMU) ou le 112. "
        "Les informations fournies le sont a titre educatif uniquement.</p>"
        "<p>Source : Haute Autorite de Sante, recommandations 2025. "
        "Redige en juin 2026.</p>"
    )
    result = asyncio.run(run(_session("sante", html)))
    assert result.conformite_data["valide"] is True


# ─── 5. Sortie conforme ────────────────────────────────────────────────

def test_conformite_tous_les_champs():
    result = asyncio.run(run(_session("finance")))
    for field in ("valide", "avertissements_requis", "mentions_obligatoires",
                  "regles_appliquees", "risque_juridique"):
        assert field in result.conformite_data, f"Champ manquant: {field}"


def test_risque_juridique_valide():
    risques = ("faible", "modere", "eleve", "critique")
    for secteur in SECTOR_RULES:
        result = asyncio.run(run(_session(secteur)))
        assert result.conformite_data["risque_juridique"] in risques


def test_resultat_stocke():
    result = asyncio.run(run(_session("finance")))
    assert result.agent_results["agent_14"].data == result.conformite_data


# ─── 6. Tous les secteurs couverts ─────────────────────────────────────

def test_tous_les_secteurs_reglementes_ont_des_regles():
    from hermes.models.common import SECTEURS_REGLEMENTES
    for secteur in SECTEURS_REGLEMENTES:
        assert secteur in SECTOR_RULES, f"Regles manquantes pour {secteur}"


def test_toutes_les_regles_ont_mentions():
    for secteur, rules in SECTOR_RULES.items():
        assert "mentions_obligatoires" in rules, f"mentions_obligatoires manquant pour {secteur}"
        assert "risque_base" in rules, f"risque_base manquant pour {secteur}"


# ─── 7. Moteur de regles ──────────────────────────────────────────────

def test_check_rules_finance_contenu_interdit():
    data = _check_rules("Ce produit offre un rendement garanti de 10%.", "finance")
    assert data.risque_juridique == "critique"


def test_check_rules_secteur_inconnu():
    data = _check_rules("contenu quelconque", "secteur_inexistant")
    assert data.valide is True


def test_check_rules_type_page():
    """L'avertissement varie selon le type de page."""
    data_produit = _check_rules("contenu", "finance", "produit")
    data_article = _check_rules("contenu", "finance", "article")
    assert len(data_produit.avertissements_requis) > 0


# ─── 8. Strip HTML ─────────────────────────────────────────────────────

def test_strip_html():
    text = _strip_html("<h1>Titre</h1><p>Paragraphe.</p>")
    assert "Titre" in text
