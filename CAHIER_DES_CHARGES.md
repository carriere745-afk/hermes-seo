# HERMES SEO v3 — Cahier des Charges Technique

> **Statut :** En attente de validation  
> **Date :** 2026-06-16  
> **Architecte :** Claude Opus 4.7 (via DeepClaude)

---

## Table des matières

1. [Stack technique](#1-stack-technique)
2. [Arborescence du projet](#2-arborescence-du-projet)
3. [Schéma global de session](#3-schéma-global-de-session)
4. [Contrats Pydantic — entrée/sortie de chaque agent](#4-contrats-pydantic)
5. [Liste des statuts possibles](#5-liste-des-statuts-possibles)
6. [Format des logs](#6-format-des-logs)
7. [Format de sauvegarde](#7-format-de-sauvegarde)
8. [Système de reprise après erreur](#8-système-de-reprise-après-erreur)
9. [Versioning des prompts](#9-versioning-des-prompts)
10. [Stratégie de tests](#10-stratégie-de-tests)
11. [Registre central des agents](#11-registre-central-des-agents)
12. [Modes qualité](#12-modes-qualité)
13. [Gestion du budget](#13-gestion-du-budget)
14. [Système de skip](#14-système-de-skip)
15. [Startup check](#15-startup-check)
16. [Superviseur central](#16-superviseur-central)
17. [Plan d'implémentation](#17-plan-dimplémentation)

---

## 1. Stack technique

### 1.1 Langage et environnement

| Élément | Choix | Justification |
|---------|-------|---------------|
| Langage | Python 3.12+ | Dernière version stable, support `asyncio` mature, typage natif |
| Gestionnaire de paquets | `uv` (par Astral) | 10-100x plus rapide que pip, lock file natif, remplace pip+venv |
| Formateur | `ruff` | 10-100x plus rapide que flake8/black, tout-en-un |
| Typage | `mypy` strict | Obligatoire pour la fiabilité des contrats Pydantic |

### 1.2 Orchestrateur

| Élément | Choix | Version | Justification |
|---------|-------|---------|---------------|
| Orchestrateur | **LangGraph** | ≥0.3.x | Standard 2026 pour systèmes multi-agents production. Points d'interruption natifs, persistance intégrée, async. |
| Pattern recommandé | **Subagents as Tools** | — | Recommandé par l'équipe LangGraph pour les nouveaux projets. Moins de boilerplate que le supervisor library, plus de contrôle. |
| Persistance dev | `SqliteSaver` | Built-in | Zéro infra, idéal pour le développement |
| Persistance prod | `AsyncPostgresSaver` | Built-in | Sessions concurrentes, scaling horizontal |

### 1.3 Mémoire persistante

| Type | Technologie | Justification |
|------|-------------|---------------|
| État du pipeline | SQLite (via LangGraph SqliteSaver) | Persistance native LangGraph, checkpointing automatique |
| Mémoire sémantique | **ChromaDB** | Meilleur rapport simplicité/performance pour le prototypage. API Python native. Passage à Qdrant en production sans refonte. |
| Fichiers de session | JSON (dossier `sessions/`) | Snapshots lisibles, reprise après erreur, debug facile |
| Prompts | Fichiers Markdown (dossier `prompts/`) | Versionnés, reviewables, éditables sans code |

### 1.4 Stratégie LLM multi-modèle

Hermes SEO utilise **4 fournisseurs** routés selon le type de tâche. DeepSeek est le fer de lance économique (54× moins cher que Claude Sonnet en output), Claude Sonnet reste le maître de la rédaction française naturelle, GPT excelle en structuré, et Haiku sert les vérifications rapides.

| Type de tâche | Modèle principal | Modèle fallback | Input $/1M | Output $/1M | Ratio vs Sonnet |
|---------------|------------------|-----------------|------------|-------------|-----------------|
| **Rédaction longue** (Agents 09, 18, 20) | Claude Sonnet 4.6 | GPT-5.4 | $3.00 | $15.00 | Baseline |
| **Analyse structurée** (Agents 03, 04, 10, 19, 21) | GPT-5.4 | DeepSeek V4 Flash | $2.50 | $15.00 | 1× |
| **Vérification rapide** (Agents 13, 14, 15, 25) | Claude Haiku 4.5 | DeepSeek V4 Flash | $1.00 | $5.00 | 3× moins cher |
| **Tâches légères** (Agents 02, 05, 06, 07, 08, 16, 17, 22, 24) | **DeepSeek V4 Flash** | GPT-5.4 Mini | **$0.14** | **$0.28** | **54× moins cher** |
| **Budget serré / faible enjeu** | **DeepSeek V4 Flash** | Ollama local | $0.14 | $0.28 | — |
| **Dry-run / Local** | Ollama (Llama 4) | — | Gratuit | Gratuit | — |

**DeepSeek V4 Flash — le détail qui compte :**
- 284B paramètres totaux, 13B activés, contexte 1M tokens
- Prompt caching automatique → input en cache à **$0.0028/M** (98% de réduction)
- Sortie max 384K tokens — idéal pour génération d'articles
- Pas de vision (pas d'analyse d'image) — l'Agent 22 (Images) nécessitera un autre modèle si analyse visuelle requise
- Limitations : latence plus élevée depuis l'Europe (infra Chine), rate limits à vérifier, benchmarks français à valider en conditions réelles
- Les alias legacy (`deepseek-chat`, `deepseek-reasoner`) expirent le **24 juillet 2026** — utiliser les noms V4

**Règles de routage :**
- Prompt caching activé partout où c'est possible (économise ~90% sur les inputs répétitifs, 98% chez DeepSeek)
- Batch API pour les tâches non urgentes (économise ~50%)
- Si budget < seuil → dégradation automatique vers DeepSeek V4 Flash d'abord, puis Ollama local
- Si fallback indisponible → dégradation vers Ollama local (si installé)
- **Rédaction française :** Claude Sonnet prioritaire. DeepSeek testé comme fallback, qualité français à valider

### 1.5 Librairies Python

| Librairie | Version min | Usage | Licence | Coût |
|-----------|-------------|-------|---------|------|
| `langgraph` | ≥0.3.0 | Orchestration du workflow | MIT | Gratuit |
| `langgraph-supervisor` | ≥0.0.10 | Handoffs entre agents | MIT | Gratuit |
| `pydantic` | ≥2.0 | Contrats de données | MIT | Gratuit |
| `chromadb` | ≥0.5.0 | Mémoire vectorielle sémantique | Apache 2.0 | Gratuit |
| `loguru` | ≥0.7.0 | Logging structuré JSON | MIT | Gratuit |
| `tenacity` | ≥8.0 | Retry avec backoff exponentiel | Apache 2.0 | Gratuit |
| `anthropic` | ≥0.40.0 | SDK Claude | MIT | Gratuit (SDK) |
| `openai` | ≥1.60.0 | SDK GPT + DeepSeek (compatible API) | MIT | Gratuit (SDK) |
| `tiktoken` | ≥0.7.0 | Comptage de tokens | MIT | Gratuit |
| `rich` | ≥13.0 | Affichage CLI (progression, tableaux) | MIT | Gratuit |
| `pytest` | ≥8.0 | Tests unitaires + intégration | MIT | Gratuit |
| `pytest-mock` | ≥3.0 | Mocking pour dry-run | MIT | Gratuit |
| `pytest-asyncio` | ≥0.24.0 | Tests async | MIT | Gratuit |
| `pytest-cov` | ≥5.0 | Couverture de code | MIT | Gratuit |
| `pyyaml` | ≥6.0 | Parsing du registre YAML | MIT | Gratuit |
| `httpx` | ≥0.27.0 | HTTP async pour appels API | BSD | Gratuit |
| `python-dotenv` | ≥1.0 | Gestion variables d'environnement | MIT | Gratuit |

**Librairies optionnelles (intégration CMS) :**
| Librairie | Usage | Coût |
|-----------|-------|------|
| `python-wordpress-xmlrpc` | Export WordPress | Gratuit |
| `shopify-api-py` | Export Shopify | Gratuit |

**Services API externes (payants) :**
| Service | Usage | Prix approximatif |
|---------|-------|-------------------|
| HasData SERP API | Agent 03 (Analyse SERP) | ~$30/mois pour 5000 requêtes |
| Serpstack | Alternative SERP | ~$29/mois pour 5000 requêtes |
| Claude API | Rédaction, analyse | Variable (cf. tableau LLM) |
| OpenAI API | Analyse structurée | Variable (cf. tableau LLM) |

---

## 2. Arborescence du projet

```
hermes-seo/
├── CAHIER_DES_CHARGES.md          # Ce document
├── README.md                      # Doc utilisateur (généré en fin de projet)
├── pyproject.toml                 # Dépendances + config outils
├── uv.lock                        # Lock file (reproductible)
├── .env.example                   # Template variables d'environnement
├── .gitignore
│
├── hermes/                        # Package principal
│   ├── __init__.py
│   ├── main.py                    # Point d'entrée CLI
│   ├── config.py                  # Configuration centrale (env, chemins, modèles)
│   ├── startup_check.py           # Vérification pré-démarrage (Phase 0)
│   │
│   ├── models/                    # Modèles Pydantic partagés
│   │   ├── __init__.py
│   │   ├── session.py             # Session, SessionState
│   │   ├── entreprise.py          # Fiche entreprise
│   │   ├── persona.py             # Fiche persona
│   │   ├── serp.py                # Données SERP
│   │   ├── contenu.py             # Brouillon, ContenuFinal
│   │   ├── scores.py              # Grille de scoring Agent 25
│   │   └── common.py              # Types partagés (Status, Mode, etc.)
│   │
│   ├── agents/                    # 1 fichier par agent
│   │   ├── __init__.py
│   │   ├── agent_00_supervisor.py
│   │   ├── agent_01_brief_entreprise.py
│   │   ├── agent_02_persona.py
│   │   ├── agent_03_analyse_serp.py
│   │   ├── agent_04_intention.py
│   │   ├── agent_05_offre_conversion.py
│   │   ├── agent_06_differenciation.py
│   │   ├── agent_07_template.py
│   │   ├── agent_08_anti_cannibalisation.py
│   │   ├── agent_09_redaction.py
│   │   ├── agent_10_seo.py
│   │   ├── agent_11_aeo.py
│   │   ├── agent_12_geo.py
│   │   ├── agent_13_eeat.py
│   │   ├── agent_14_conformite.py
│   │   ├── agent_15_fact_checking.py
│   │   ├── agent_16_maillage_interne.py
│   │   ├── agent_17_maillage_externe.py
│   │   ├── agent_18_multiformat.py
│   │   ├── agent_19_test_ab.py
│   │   ├── agent_20_localisation.py
│   │   ├── agent_21_schema_org.py
│   │   ├── agent_22_images.py
│   │   ├── agent_23_cms_export.py
│   │   ├── agent_24_mise_a_jour.py
│   │   ├── agent_25_critique_qualite.py
│   │   └── agent_26_audit_post_publication.py
│   │
│   ├── core/                      # Infrastructure partagée
│   │   ├── __init__.py
│   │   ├── workflow.py            # Construction du graphe LangGraph
│   │   ├── transitions.py         # Logique de transition conditionnelle
│   │   ├── llm.py                 # Factory LLM multi-modèle + routage
│   │   ├── memory.py              # Interface ChromaDB + SQLite
│   │   ├── logging.py             # Configuration Loguru JSON
│   │   ├── budget.py              # Gestion budget tokens/coût
│   │   ├── session_manager.py     # Sauvegarde/restauration sessions
│   │   └── exceptions.py          # Exceptions métier personnalisées
│   │
│   ├── connectors/                # Connecteurs externes
│   │   ├── __init__.py
│   │   ├── serp_api.py            # HasData / Serpstack
│   │   ├── wordpress.py           # WordPress XML-RPC / REST
│   │   ├── shopify.py             # Shopify API
│   │   └── gsc.py                 # Google Search Console API
│   │
│   └── utils/                     # Utilitaires
│       ├── __init__.py
│       ├── text.py                # Flesch français, densité sémantique
│       ├── tokens.py              # Comptage tokens, estimation coûts
│       └── validators.py          # Validateurs Pydantic personnalisés
│
├── prompts/                       # Prompts système versionnés
│   ├── agent_01_brief_entreprise/
│   │   └── v1/
│   │       ├── system.md          # Prompt système
│   │       └── CHANGELOG.md       # Historique des modifications
│   ├── agent_02_persona/
│   │   └── v1/
│   │       ├── system.md
│   │       └── CHANGELOG.md
│   ├── ... (1 dossier par agent)
│   └── agent_26_audit/
│       └── v1/
│           ├── system.md
│           └── CHANGELOG.md
│
├── tests/                         # Tests
│   ├── __init__.py
│   ├── conftest.py                # Fixtures partagées
│   ├── fixtures/                  # Données de test
│   │   ├── sessions/              # Sessions JSON pré-enregistrées
│   │   ├── serp/                  # Réponses SERP mockées
│   │   └── llm/                   # Réponses LLM mockées
│   ├── unit/                      # Tests unitaires (1 par agent)
│   │   ├── test_agent_00.py
│   │   ├── test_agent_01.py
│   │   ├── ...
│   │   └── test_agent_26.py
│   └── integration/               # Tests d'intégration
│       ├── test_pipeline_full.py   # Pipeline complet 01→26
│       ├── test_pipeline_reprise.py # Reprise après erreur
│       └── test_dry_run.py         # Mode dry-run complet
│
├── sessions/                      # Sessions sauvegardées (runtime)
│   └── .gitkeep
│
├── logs/                          # Logs JSON (runtime)
│   └── .gitkeep
│
├── data/                          # Données persistantes
│   ├── chroma/                    # Base vectorielle ChromaDB
│   │   └── .gitkeep
│   └── sqlite/                    # Base SQLite
│       └── .gitkeep
│
├── fixtures/                      # Données pour mode dry-run/replay
│   ├── session_replay.json        # Session complète rejouable
│   └── .gitkeep
│
└── agents_registry.yaml           # Registre central des 26 agents
```

---

## 3. Schéma global de session

### 3.1 Modèle Pydantic central

```python
# hermes/models/session.py

from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import uuid4
from enum import Enum

class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

class QualityMode(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"
    COMPLIANCE = "compliance"
    DEBUG = "debug"

class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED_AUTO = "skipped_auto"
    SKIPPED_USER = "skipped_user"
    FAILED = "failed"
    BLOCKED = "blocked"
    REQUIRES_REVIEW = "requires_review"

class AgentResult(BaseModel):
    """Résultat d'exécution d'un agent."""
    agent_id: str
    status: AgentStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_estimated: Optional[float] = None
    prompt_version: Optional[str] = None
    model_used: Optional[str] = None
    skip_reason: Optional[str] = None
    skip_impact: Optional[str] = None
    data: Optional[dict[str, Any]] = None  # Sortie validée de l'agent

class SessionConfig(BaseModel):
    """Configuration d'une session."""
    mode: QualityMode = QualityMode.STANDARD
    dry_run: bool = False
    replay_session_id: Optional[str] = None
    token_budget: int = 1_000_000
    cost_budget: float = 5.0
    target_url: Optional[str] = None
    target_cms: Optional[str] = None
    target_locales: list[str] = Field(default_factory=list)
    user_skipped_agents: list[str] = Field(default_factory=list)
    secteur: Optional[str] = None  # Pour conformité sectorielle

class SessionState(BaseModel):
    """État complet d'une session."""
    session_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    status: SessionStatus = SessionStatus.CREATED
    config: SessionConfig = Field(default_factory=SessionConfig)
    keyword: Optional[str] = None
    site_url: Optional[str] = None
    objectif: Optional[str] = None
    contraintes: list[str] = Field(default_factory=list)

    # Résultats de chaque agent
    agent_results: dict[str, AgentResult] = Field(default_factory=dict)

    # Données accumulées (sorties validées)
    fiche_entreprise: Optional[dict] = None
    fiche_persona: Optional[dict] = None
    serp_data: Optional[dict] = None
    intention: Optional[str] = None
    type_page: Optional[str] = None
    offre_conversion_data: Optional[dict] = None
    angles_differenciants: Optional[dict] = None
    template_data: Optional[dict] = None
    anti_cannib_data: Optional[dict] = None
    brouillon_html: Optional[str] = None
    seo_data: Optional[dict] = None
    aeo_blocks: Optional[dict] = None
    geo_data: Optional[dict] = None
    score_eeat: Optional[dict] = None
    conformite_data: Optional[dict] = None
    fact_check_data: Optional[dict] = None
    internal_links: Optional[dict] = None
    external_links: Optional[dict] = None
    multiformat_data: Optional[dict] = None
    variants_ab: Optional[dict] = None
    localised_data: Optional[dict] = None
    ld_json: Optional[dict] = None
    image_plan: Optional[dict] = None
    export_data: Optional[dict] = None
    plan_refresh: Optional[dict] = None
    scores: Optional[dict] = None
    feedback_data: Optional[dict] = None

    # Métadonnées de session
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    current_agent_id: Optional[str] = None
    last_completed_agent_id: Optional[str] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    error_count: int = 0
    warnings: list[str] = Field(default_factory=list)
```

### 3.2 Exemple JSON de session

```json
{
  "session_id": "a1b2c3d4e5f6",
  "status": "running",
  "config": {
    "mode": "standard",
    "dry_run": false,
    "token_budget": 1000000,
    "cost_budget": 5.0
  },
  "keyword": "assurance vie temporaire",
  "site_url": "https://monassureur.fr",
  "objectif": "Générer un article pilier sur l'assurance vie temporaire",
  "agent_results": {
    "agent_01": {
      "agent_id": "agent_01",
      "status": "completed",
      "started_at": "2026-06-16T10:00:00Z",
      "finished_at": "2026-06-16T10:00:05Z",
      "duration_ms": 5000,
      "tokens_input": 1200,
      "tokens_output": 800,
      "cost_estimated": 0.015,
      "prompt_version": "v1",
      "model_used": "claude-haiku-4-5"
    }
  },
  "fiche_entreprise": { "...": "..." }
}
```

---

## 4. Contrats Pydantic — Entrée/Sortie de chaque agent

> Chaque agent reçoit une `SessionState` complète en entrée et retourne un `AgentResult` avec son champ `data` typé.

### Agent 00 — Superviseur central
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | État complet de la session |
| Sortie | `SupervisorVerdict` | `{ valid: bool, blocked_reasons: list[str], warnings: list[str], next_action: str }` |

### Agent 01 — Brief Entreprise
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `site_url`, `secteur` |
| Sortie | `FicheEntreprise` | `{ nom, secteur, positionnement, offres: list, ton_marque, preuves: list, contraintes_legales: list, mots_cles_interdits: list, elements_differenciants: list }` |

### Agent 02 — Persona
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `fiche_entreprise`, `keyword` |
| Sortie | `FichePersona` | `{ nom_persona, maturite, vocabulaire_recommande, canal_acquisition, objectif_lecture, freins: list, questions_typiques: list, niveau_expertise }` |

### Agent 03 — Analyse SERP
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `keyword` |
| Sortie | `SerpData` | `{ top10: list[SerpResult], paa: list[str], featured_snippets: list, ai_overviews: list, concurrents_directs: list[str], mots_cles_associes: list }` |

### Agent 04 — Intention & Type
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `keyword`, `serp_data` |
| Sortie | `IntentTypeData` | `{ intention: str, type_page: str, justification: str, serp_consensus: str }` |

### Agent 05 — Offre & Conversion
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `fiche_entreprise`, `fiche_persona`, `intention` |
| Sortie | `OffreConversion` | `{ benefices: list, objections: list, preuves: list, cta_principal: str, cta_secondaire: str, valeur_ajoutee_unique: str }` |

### Agent 06 — Différenciation
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `serp_data`, `offre_conversion_data` |
| Sortie | `DifferenciationData` | `{ angles_faibles: list, opportunites_uniques: list, angle_principal: str, facteurs_differenciation: list }` |

### Agent 07 — Template
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `type_page`, `intention` |
| Sortie | `TemplateData` | `{ template_id: str, nom: str, structure: list[Section], nb_sections: int, notes: str }` |

### Agent 08 — Anti-cannibalisation
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `keyword`, `angles_differenciants` |
| Sortie | `AntiCannibData` | `{ conflit_detecte: bool, pages_concurrentes: list, recommandation: str, action: str }` |

### Agent 09 — Rédaction
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Tous les agents précédents |
| Sortie | `Brouillon` | `{ html: str, word_count: int, titre: str, meta_description: str, sections: list[str] }` |

### Agent 10 — SEO
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html` |
| Sortie | `SeoData` | `{ title_optimise: str, meta_description_optimise: str, hn_structure: dict, densite_mots_cles: dict, suggestions_maillage: list }` |

### Agent 11 — AEO
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html` |
| Sortie | `AeoBlocks` | `{ en_bref: str, h2_questions: list[str], faq: list[dict], definitions: list[dict] }` |

### Agent 12 — GEO
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `serp_data` |
| Sortie | `GeoData` | `{ sources_primaires: list, entites_nommees: list, phrases_citables: list, chunks: list[dict] }` |

### Agent 13 — EEAT
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `fiche_entreprise` |
| Sortie | `EeatScore` | `{ score_expertise: int, score_experience: int, score_autorite: int, score_fiabilite: int, score_global: int, recommandations: list[str] }` |

### Agent 14 — Conformité sectorielle
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `config.secteur` |
| Sortie | `ConformiteData` | `{ valide: bool, avertissements_requis: list[str], mentions_obligatoires: list[str], regles_appliquees: list[str], risque_juridique: str }` |

### Agent 15 — Fact-checking
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `serp_data` |
| Sortie | `FactCheckData` | `{ erreurs: list[dict], corrections: list[dict], score_fiabilite: int, sources_verifiees: list }` |

### Agent 16 — Maillage interne
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html` + mémoire ChromaDB |
| Sortie | `InternalLinks` | `{ liens_proposes: list[dict], ancres_suggerees: list[str], pages_pilier: list[str] }` |

### Agent 17 — Maillage externe
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `serp_data` |
| Sortie | `ExternalLinks` | `{ liens_sortants: list[dict], sources_autorite: list[str], pages_orphelines: list[str] }` |

### Agent 18 — Multiformat
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html` (final) |
| Sortie | `MultiformatData` | `{ thread_linkedin: str, script_youtube: str, newsletter: str, social_posts: list[str], session_parent: str }` |

### Agent 19 — Test A/B
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `seo_data` |
| Sortie | `VariantsAB` | `{ variants: list[dict], ctr_predit: list[float], variante_recommandee: str }` |

### Agent 20 — Localisation
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `config.target_locales` |
| Sortie | `LocalisedData` | `{ versions: dict[str, str], hreflang_tags: str, adaptations: list[str] }` |

### Agent 21 — Schema.org
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `type_page`, contenu final |
| Sortie | `SchemaData` | `{ ld_json: str, type_schema: str, validation_errors: list[str] }` |

### Agent 22 — Images
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html` |
| Sortie | `ImagePlan` | `{ images: list[dict], prompts: list[str], textes_alt: list[str] }` |

### Agent 23 — CMS Export
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient contenu final, `config.target_cms` |
| Sortie | `ExportData` | `{ format: str, contenu_formate: str, metadata: dict, fichier: str }` |

### Agent 24 — Mise à jour / Fraîcheur
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `brouillon_html`, `fact_check_data` |
| Sortie | `RefreshPlan` | `{ date_prochaine_revision: str, criteres_obsolescence: list, sources_a_surveiller: list }` |

### Agent 25 — Critique Qualité
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient tout le contenu final |
| Sortie | `ScoresFinaux` | `{ scores: dict[str, int], score_total: int, seuil_atteint: bool, recommandation: str, blocages: list[str] }` |

### Agent 26 — Audit post-publication
| Direction | Modèle | Description |
|-----------|--------|-------------|
| Entrée | `SessionState` | Contient `session_id`, URL publiée |
| Sortie | `FeedbackData` | `{ data_gsc: dict, correlation: dict, apprentissages: list[str], ajustements_memoire: list[str] }` |

---

## 5. Liste des statuts possibles

### 5.1 Statuts de session

| Statut | Description |
|--------|-------------|
| `created` | Session initiée, aucun agent exécuté |
| `running` | Pipeline en cours d'exécution |
| `completed` | Tous les agents actifs terminés avec succès |
| `failed` | Un agent a échoué (bloquant) |
| `blocked` | Superviseur a bloqué la progression |
| `cancelled` | Annulée par l'utilisateur |

### 5.2 Statuts d'agent

| Statut | Description | Progression possible ? |
|--------|-------------|------------------------|
| `pending` | En attente d'exécution | Oui |
| `running` | En cours d'exécution | Non (état transitoire) |
| `completed` | Terminé avec succès | Oui |
| `skipped_auto` | Ignoré automatiquement (non pertinent) | Oui |
| `skipped_user` | Ignoré manuellement par l'utilisateur | Oui (avec avertissement) |
| `failed` | Échec d'exécution | Non (sauf reprise) |
| `blocked` | Bloqué par le superviseur | Non (correction requise) |
| `requires_review` | En attente de validation humaine | Non (validation requise) |

---

## 6. Format des logs

### 6.1 Structure d'une entrée de log

```json
{
  "timestamp": "2026-06-16T10:00:05.123Z",
  "level": "INFO",
  "session_id": "a1b2c3d4e5f6",
  "agent_id": "agent_01",
  "agent_name": "Brief Entreprise",
  "event": "agent_completed",
  "duration_ms": 5000,
  "status": "completed",
  "tokens_input": 1200,
  "tokens_output": 800,
  "tokens_total": 2000,
  "cost_estimated": 0.015,
  "prompt_version": "v1",
  "model_used": "claude-haiku-4-5",
  "skip_type": null,
  "skip_reason": null,
  "error_message": null,
  "error_traceback": null,
  "mode": "standard",
  "dry_run": false
}
```

### 6.2 Événements loggés

Chaque agent produit au minimum 2 entrées :
1. `agent_started` — au début de l'exécution
2. `agent_completed` / `agent_failed` / `agent_skipped` — à la fin

Le superviseur produit :
- `supervisor_check` — avant chaque transition
- `supervisor_blocked` — si blocage
- `pipeline_started` / `pipeline_completed` / `pipeline_failed`

### 6.3 Stockage

- Fichier JSON Lines : `logs/hermes_{session_id}.jsonl`
- Rotation automatique par session
- Format Loguru avec `serialize=True`

---

## 7. Format de sauvegarde

### 7.1 Snapshot de session

Après chaque agent, la `SessionState` complète est sauvegardée :

```
sessions/{session_id}.json
```

Contenu : sérialisation JSON complète de `SessionState` (via `model_dump_json()`).

### 7.2 Fréquence

- Sauvegarde automatique après chaque `agent_completed`
- Sauvegarde après chaque `agent_failed` (pour reprise)
- Sauvegarde après chaque `agent_skipped`

### 7.3 Répertoire des sauvegardes

```
sessions/
├── a1b2c3d4e5f6.json          # Session active
├── a1b2c3d4e5f6_backup.json   # Backup avant reprise
└── ...
```

---

## 8. Système de reprise après erreur

### 8.1 Principe

Si un agent échoue (statut `failed`) :
1. Le pipeline s'arrête proprement
2. L'erreur est loggée avec traceback
3. La session conserve son état (tous les résultats des agents précédents)
4. `current_agent_id` pointe sur l'agent échoué
5. `last_completed_agent_id` pointe sur le dernier agent réussi

### 8.2 Commande de reprise

```bash
python -m hermes.main resume --session-id a1b2c3d4e5f6
```

Le système :
1. Charge la session depuis `sessions/{session_id}.json`
2. Identifie `last_completed_agent_id`
3. Reprend le pipeline depuis l'agent suivant
4. Réutilise tous les résultats déjà calculés

### 8.3 Reprise depuis un agent spécifique

```bash
python -m hermes.main resume --session-id a1b2c3d4e5f6 --from agent_09
```

Force la reprise depuis un agent précis (utile pour ré-exécuter une partie du pipeline).

---

## 9. Versioning des prompts

### 9.1 Structure

```
prompts/
├── agent_01_brief_entreprise/
│   ├── v1/
│   │   ├── system.md       # Le prompt système
│   │   └── CHANGELOG.md    # Historique des modifications
│   ├── v2/
│   │   ├── system.md
│   │   └── CHANGELOG.md
│   └── latest              # Symlink ou fichier pointant vers la version courante
```

### 9.2 Format de `system.md`

```markdown
---
agent: agent_01
version: v1
date: 2026-06-16
role: Collecter le positionnement, les offres, le ton, les preuves et les contraintes légales
expected_input: site_url, secteur
expected_output: FicheEntreprise (JSON)
model_recommended: claude-haiku-4-5
---

[Contenu du prompt système ici]
```

### 9.3 Format de `CHANGELOG.md`

```markdown
# Changelog — Agent 01 Brief Entreprise

## v2 — 2026-07-01
- Ajout de la détection automatique du secteur via le contenu du site
- Correction du parsing des offres (issue #42)

## v1 — 2026-06-16
- Version initiale
```

### 9.4 Règles

- **Ne jamais modifier un prompt en production sans incrémenter sa version**
- La version utilisée est enregistrée dans les logs (champ `prompt_version`)
- Le changelog doit être rempli à chaque modification
- `latest` pointe toujours vers la version de production

---

## 10. Stratégie de tests

### 10.1 Niveaux de test

| Niveau | Dossier | Description | Exécution |
|--------|---------|-------------|-----------|
| **Unitaire** | `tests/unit/` | 1 fichier par agent. Teste entrée valide, invalide, sortie conforme, erreur contrôlée | `pytest tests/unit/` |
| **Intégration** | `tests/integration/` | Pipeline complet, reprise après erreur, session incomplète | `pytest tests/integration/` |
| **Dry-run** | Via `--dry-run` | Pipeline complet sans appel API externe réel | `python -m hermes.main run --dry-run` |

### 10.2 Obligations par agent

Chaque agent DOIT avoir :

1. **test_entree_valide** : Vérifie qu'une entrée Pydantic valide est acceptée
2. **test_entree_invalide** : Vérifie qu'une entrée invalide lève une `ValidationError`
3. **test_sortie_conforme** : Vérifie que la sortie respecte le modèle Pydantic attendu
4. **test_erreur_controlee** : Vérifie le comportement en cas d'erreur API simulée

### 10.3 Fixtures

Les données de test sont dans `tests/fixtures/` :
- `sessions/session_minimale.json` — Session valide minimale
- `sessions/session_complete.json` — Session avec tous les champs remplis
- `serp/response_google.json` — Réponse SERP mockée (Google)
- `serp/response_empty.json` — Réponse SERP vide
- `llm/claude_response.json` — Réponse LLM mockée (format Claude)
- `llm/gpt_response.json` — Réponse LLM mockée (format GPT)

### 10.4 Mode replay

```bash
python -m hermes.main replay --session-id a1b2c3d4e5f6
```

Rejoue une session entière depuis les données sauvegardées sans aucun appel API externe.
**C'est le mode de débogage par défaut pendant tout le développement.**

---

## 11. Registre central des agents

Fichier : `agents_registry.yaml`

```yaml
# HERMES SEO v3 — Registre central des agents
# Version: 1.0
# Date: 2026-06-16

agents:
  - id: agent_00
    name: Superviseur central
    file: hermes/agents/agent_00_supervisor.py
    prompt_version: v1
    dependencies: []
    skippable: false
    skippable_reason: "Agent critique — vérifie l'intégrité du pipeline"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: none  # Pas de LLM, pure logique Python
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_01
    name: Brief Entreprise
    file: hermes/agents/agent_01_brief_entreprise.py
    prompt_version: v1
    dependencies: []
    skippable: false
    skippable_reason: "Fondation de tout le pipeline — données entreprise requises"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: haiku  # Tâche légère d'extraction
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_02
    name: Persona / Lecteur cible
    file: hermes/agents/agent_02_persona.py
    prompt_version: v1
    dependencies: [agent_01]
    skippable: true
    skippable_reason: "Peut être ignoré si le persona est déjà connu ou standard"
    mode_required: [standard, premium, compliance, debug]
    model_preference: deepseek  # Tâche légère → DeepSeek V4 Flash
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_03
    name: Analyse SERP
    file: hermes/agents/agent_03_analyse_serp.py
    prompt_version: v1
    dependencies: []
    skippable: true
    skippable_reason: "Peut être ignoré si pas de budget API SERP"
    mode_required: [standard, premium, compliance, debug]
    model_preference: gpt  # Analyse structurée
    conditional_mandatory: true
    conditional_trigger: "actualité, comparatif, pilier"

  - id: agent_04
    name: Intention & Type de page
    file: hermes/agents/agent_04_intention.py
    prompt_version: v1
    dependencies: [agent_03]
    skippable: false
    skippable_reason: "Détermine tout le reste du pipeline"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_05
    name: Offre & Conversion
    file: hermes/agents/agent_05_offre_conversion.py
    prompt_version: v1
    dependencies: [agent_01, agent_02, agent_04]
    skippable: true
    skippable_reason: "Non essentiel pour du contenu informatif pur sans objectif commercial"
    mode_required: [standard, premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_06
    name: Différenciation concurrentielle
    file: hermes/agents/agent_06_differenciation.py
    prompt_version: v1
    dependencies: [agent_03, agent_05]
    skippable: true
    skippable_reason: "Moins critique si le sujet est très niche sans concurrence"
    mode_required: [standard, premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_07
    name: Template
    file: hermes/agents/agent_07_template.py
    prompt_version: v1
    dependencies: [agent_04]
    skippable: false
    skippable_reason: "Structure obligatoire pour la rédaction"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_08
    name: Anti-cannibalisation avancé
    file: hermes/agents/agent_08_anti_cannibalisation.py
    prompt_version: v1
    dependencies: [agent_03, agent_06]
    skippable: true
    skippable_reason: "Inutile si le site n'a pas encore de contenu publié"
    mode_required: [standard, premium, compliance, debug]
    model_preference: haiku  # Analyse sémantique rapide
    conditional_mandatory: true
    conditional_trigger: "site avec contenus existants dans la mémoire Hermes"

  - id: agent_09
    name: Rédaction
    file: hermes/agents/agent_09_redaction.py
    prompt_version: v1
    dependencies: [agent_01, agent_02, agent_03, agent_04, agent_05, agent_06, agent_07, agent_08]
    skippable: false
    skippable_reason: "Cœur du pipeline — produit le brouillon"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: sonnet  # Meilleur pour la rédaction longue
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_10
    name: SEO
    file: hermes/agents/agent_10_seo.py
    prompt_version: v1
    dependencies: [agent_09]
    skippable: false
    skippable_reason: "Essentiel pour le référencement"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: gpt
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_11
    name: AEO
    file: hermes/agents/agent_11_aeo.py
    prompt_version: v1
    dependencies: [agent_09]
    skippable: false
    skippable_reason: "Essentiel pour l'Answer Engine Optimization"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_12
    name: GEO
    file: hermes/agents/agent_12_geo.py
    prompt_version: v1
    dependencies: [agent_09, agent_03]
    skippable: true
    skippable_reason: "GEO moins critique pour du contenu hors actualité"
    mode_required: [standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_13
    name: EEAT
    file: hermes/agents/agent_13_eeat.py
    prompt_version: v1
    dependencies: [agent_09, agent_01]
    skippable: true
    skippable_reason: "Peut être ignoré pour du contenu non-Your Money Your Life"
    mode_required: [standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_14
    name: Conformité sectorielle
    file: hermes/agents/agent_14_conformite.py
    prompt_version: v1
    dependencies: [agent_09, agent_01]
    skippable: false  # Non skippable pour les secteurs réglementés
    skippable_reason: "Obligatoire pour secteurs réglementés"
    mode_required: [premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: true
    conditional_trigger: "droit, finance, santé, RH, données_personnelles, cybersécurité, enfants, véhicules, produits_réglementés"

  - id: agent_15
    name: Fact-checking
    file: hermes/agents/agent_15_fact_checking.py
    prompt_version: v1
    dependencies: [agent_09, agent_03]
    skippable: false
    skippable_reason: "Critique pour la fiabilité du contenu"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_16
    name: Maillage interne
    file: hermes/agents/agent_16_maillage_interne.py
    prompt_version: v1
    dependencies: [agent_09]
    skippable: true
    skippable_reason: "Nécessite une mémoire de contenus existants"
    mode_required: [standard, premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_17
    name: Maillage externe / Netlinking
    file: hermes/agents/agent_17_maillage_externe.py
    prompt_version: v1
    dependencies: [agent_09, agent_03]
    skippable: true
    skippable_reason: "Optionnel si la stratégie netlinking n'est pas activée"
    mode_required: [premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_18
    name: Multiformat / Recyclage
    file: hermes/agents/agent_18_multiformat.py
    prompt_version: v1
    dependencies: [agent_09]  # Attend le brouillon final (après SEO, AEO, GEO)
    skippable: true
    skippable_reason: "Optionnel si seul l'article web est nécessaire"
    mode_required: [premium, compliance, debug]
    model_preference: sonnet  # Rédaction créative multi-format
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_19
    name: Test A/B titre & meta
    file: hermes/agents/agent_19_test_ab.py
    prompt_version: v1
    dependencies: [agent_10]
    skippable: true
    skippable_reason: "Optionnel si les tests A/B ne sont pas activés"
    mode_required: [premium, compliance, debug]
    model_preference: gpt
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_20
    name: Localisation / Internationalisation
    file: hermes/agents/agent_20_localisation.py
    prompt_version: v1
    dependencies: [agent_09]
    skippable: true
    skippable_reason: "Inutile si le contenu est monolingue/mono-région"
    mode_required: [premium, compliance, debug]
    model_preference: sonnet  # Qualité de traduction naturelle
    conditional_mandatory: true
    conditional_trigger: "cible régionale ou internationale"

  - id: agent_21
    name: Schema.org avancé
    file: hermes/agents/agent_21_schema_org.py
    prompt_version: v1
    dependencies: [agent_04, agent_09]
    skippable: true
    skippable_reason: "Moins critique pour du contenu sans rich snippet visé"
    mode_required: [standard, premium, compliance, debug]
    model_preference: gpt  # Meilleur pour JSON-LD structuré
    conditional_mandatory: true
    conditional_trigger: "fiche_produit, FAQ, service_local, article"

  - id: agent_22
    name: Images
    file: hermes/agents/agent_22_images.py
    prompt_version: v1
    dependencies: [agent_09]
    skippable: true
    skippable_reason: "Optionnel si les visuels sont gérés manuellement"
    mode_required: [standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_23
    name: CMS / Export
    file: hermes/agents/agent_23_cms_export.py
    prompt_version: v1
    dependencies: [agent_09, agent_10, agent_11, agent_21]
    skippable: true
    skippable_reason: "Optionnel si l'export est manuel"
    mode_required: [standard, premium, compliance, debug]
    model_preference: none  # Pas de LLM, formatting pur
    conditional_mandatory: true
    conditional_trigger: "publication directe vers CMS"

  - id: agent_24
    name: Mise à jour / Fraîcheur
    file: hermes/agents/agent_24_mise_a_jour.py
    prompt_version: v1
    dependencies: [agent_09, agent_15]
    skippable: true
    skippable_reason: "Optionnel si pas de stratégie de mise à jour planifiée"
    mode_required: [premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_25
    name: Critique Qualité
    file: hermes/agents/agent_25_critique_qualite.py
    prompt_version: v1
    dependencies: [agent_09, agent_10, agent_11, agent_12, agent_13, agent_14, agent_15]
    skippable: false
    skippable_reason: "Dernier rempart avant publication — obligatoire"
    mode_required: [fast, standard, premium, compliance, debug]
    model_preference: haiku
    conditional_mandatory: false
    conditional_trigger: null

  - id: agent_26
    name: Audit post-publication
    file: hermes/agents/agent_26_audit_post_publication.py
    prompt_version: v1
    dependencies: []  # S'exécute indépendamment, après publication
    skippable: true
    skippable_reason: "Optionnel si GSC non configuré ou contenu non encore publié"
    mode_required: [premium, compliance, debug]
    model_preference: mini
    conditional_mandatory: false
    conditional_trigger: null
```

---

## 12. Modes qualité

### 12.1 Modes disponibles

| Mode | Agents activés | Coût estimé/article (sans DeepSeek) | Coût estimé/article (avec DeepSeek) | Usage typique |
|------|---------------|--------------------------------------|-------------------------------------|---------------|
| **fast** | 00, 01, 04, 07, 09, 10, 11, 15, 25 | ~$0.10-0.20 | **~$0.03-0.06** | Blog rapide, faible enjeu |
| **standard** | fast + 02, 03, 05, 06, 08, 12, 13, 16, 21, 22, 23 | ~$0.30-0.60 | **~$0.08-0.15** | Blog professionnel, SEO actif |
| **premium** | standard + 14, 17, 18, 19, 20, 24, 26 | ~$0.60-1.20 | **~$0.15-0.35** | Contenu stratégique, haute compétition |
| **compliance** | premium + renforcement agent 14, double fact-check, validation humaine | ~$0.80-1.50 | **~$0.20-0.45** | Secteurs réglementés |
| **debug** | Tous les agents + logs détaillés | ~$0 (dry-run) | ~$0 (dry-run) | Développement, débogage |

### 12.2 Sélection du mode

```bash
# Mode explicite
python -m hermes.main run --mode premium --keyword "assurance vie"

# Mode auto-déduit
python -m hermes.main run --keyword "assurance vie" --secteur finance
# → Déduit automatiquement le mode compliance
```

---

## 13. Gestion du budget

### 13.1 Champs de budget dans SessionConfig

```python
class SessionConfig(BaseModel):
    token_budget: int = 1_000_000      # Budget max en tokens
    cost_budget: float = 5.0           # Budget max en USD
```

### 13.2 Comportement

1. Avant chaque agent, le système estime le coût (basé sur la longueur du prompt + historique de l'agent)
2. Si `cout_estime_cumulatif + cout_estime_agent > cost_budget` → **arrêt bloquant**
3. Message affiché : `"Budget estimé dépassé (coût cumulé: $X.XX / budget: $Y.YY). Continuer ? (o/n)"`
4. L'utilisateur DOIT confirmer explicitement pour continuer
5. Même mécanisme pour `token_budget`

### 13.3 Ce n'est PAS un skip automatique silencieux

C'est un **arrêt bloquant** avec demande de validation explicite. La décision est loggée.

---

## 14. Système de skip

### 14.1 Skip automatique

Le système décide de skipper un agent si :
- Le mode qualité ne l'inclut pas
- Le type de page ne le nécessite pas
- Les données requises sont manquantes
- L'agent est conditionnel et la condition n'est pas remplie

Statut : `skipped_auto`. Enregistré dans les logs avec raison et impact.

### 14.2 Skip manuel

L'utilisateur peut forcer le skip via :
```bash
python -m hermes.main run --skip agent_12 --skip agent_17
```

Le système :
1. Affiche un avertissement : *"Vous avez choisi d'ignorer l'agent [nom]. Cette étape peut réduire la fiabilité, la conformité ou la performance du contenu. La décision est enregistrée et la responsabilité de cette exclusion vous revient."*
2. Demande une confirmation explicite (sauf si `--yes` est passé)
3. Enregistre `skipped_user` dans les logs
4. Ajuste les scores finaux à la baisse
5. Ajoute une note dans le rapport final listant ce qui n'a pas été vérifié

### 14.3 Agents non skippables (même par l'utilisateur)

Sauf en mode `debug` explicitement activé :
- Agent 00 (Superviseur)
- Agent 01 (Brief Entreprise)
- Agent 04 (Intention & Type)
- Agent 07 (Template)
- Agent 15 (Fact-checking)
- Agent 25 (Critique Qualité)
- Validation Pydantic, logs, sauvegarde session

---

## 15. Startup check

### 15.1 Script : `hermes/startup_check.py`

Exécuté automatiquement avant tout lancement de pipeline.

```python
class StartupCheck:
    """Vérifie que l'environnement est prêt avant tout démarrage."""

    checks = [
        "api_keys_present",       # Vérifie .env et variables d'env
        "database_accessible",    # Vérifie SQLite + ChromaDB
        "prompts_exist",          # Vérifie prompts/*/v*/system.md
        "dependencies_installed", # Vérifie imports Python
        "directories_writable",   # Vérifie sessions/, logs/, data/
        "models_importable",      # Vérifie que tous les modèles Pydantic s'importent
        "registry_valid",         # Vérifie agents_registry.yaml
    ]
```

### 15.2 Comportement en cas d'échec

Si un check échoue → **arrêt immédiat** avec message explicite :

```
❌ Startup check FAILED: API keys missing
   Missing: ANTHROPIC_API_KEY, SERP_API_KEY
   Fix: cp .env.example .env && edit .env
   Pipeline cannot start.
```

---

## 16. Superviseur central

### 16.1 Rôle de l'Agent 00

Le superviseur s'exécute **avant chaque transition** entre agents. Il vérifie :

1. **État global de la session** : `session.status` est cohérent
2. **Présence des sorties attendues** : chaque champ requis par l'agent suivant est présent
3. **Intégrité des champs** : validation Pydantic des données de l'agent précédent
4. **Statuts** : l'agent précédent est bien `completed` (ou `skipped_*`)
5. **Cohérence** : pas d'incohérence entre les données (ex: intention transactionnelle mais template news)
6. **Budget** : pas de dépassement sans confirmation

### 16.2 Comportement

```python
class SupervisorVerdict(BaseModel):
    valid: bool
    blocked_reasons: list[str] = []
    warnings: list[str] = []
    next_agent_id: str
    next_action: str  # "proceed", "block", "retry", "skip"
```

Si `valid: false` → la progression est bloquée, l'utilisateur est notifié.

---

## 17. Plan d'implémentation

### Phase 0 — Cahier des charges (EN COURS)
- [x] Stack technique validée
- [ ] Arborescence validée
- [ ] Schémas Pydantic validés
- [ ] Registre des agents validé
- [ ] **Validation explicite par l'utilisateur**

### Phase 1 — Squelette technique
1. `pyproject.toml` + dépendances
2. `hermes/models/` — Tous les modèles Pydantic
3. `hermes/core/` — workflow LangGraph, logging, mémoire, budget
4. `hermes/startup_check.py`
5. `agents_registry.yaml`
6. Structure des dossiers `prompts/`, `tests/fixtures/`

### Phase 2 — Agents (par ordre de dépendance)
1. Agent 00 — Superviseur
2. Agent 01 — Brief Entreprise
3. Agent 02 — Persona
4. Agents 03-07 — Pipeline cœur
5. Agent 09 — Rédaction
6. Agents 10-15 — Optimisation
7. Agent 25 — Critique Qualité
8. Agents 16-24 — Enrichissement
9. Agent 26 — Audit post-publication

### Phase 3 — Intégration
1. Tests d'intégration complets
2. Mode dry-run complet
3. Mode replay

### Phase 4 — Connecteurs
1. WordPress
2. Shopify (optionnel)
3. GSC (optionnel)

### Phase 5 — Mise en production
1. Documentation utilisateur
2. Packaging (pip install)
3. CI/CD

---

> **Prochaine étape :** Validation de ce cahier des charges par l'utilisateur avant tout codage.
