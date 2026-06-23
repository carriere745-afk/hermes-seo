# Hermes SEO v3 — Rapport Détaillé

**Date :** 21 juin 2026
**Version :** 0.3 (pré-production)
**Couverture pipeline Rédaction :** ~90%
**Tests :** 656+ passants

---

## 1. Vision Globale

### 1.1 Ce qu'est Hermes SEO

Une usine éditoriale multi-agents orchestrée par IA. L'utilisateur donne un mot-clé, Hermes produit un article complet optimisé SEO, AEO (Answer Engine Optimization pour les IA comme ChatGPT) et GEO (Generative Engine Optimization pour être cité par les LLMs).

### 1.2 Architecture générale

```
┌─────────────────────────────────────────────────┐
│              ORCHESTRATEUR (futur)               │
│  Décide QUOI faire, QUAND, pour QUEL site        │
├─────────────────────────────────────────────────┤
│                                                 │
│  Pipeline Éditorial │ Pipeline Audit │ Pipeline │
│  (26 agents)        │ Technique      │ Backlinks│
│                     │ (15 agents)    │ (7)      │
│                                                 │
│  Pipeline SERP &    │ Pipeline       │ Pipeline │
│  Positions (8)      │ Stratégie (10) │ Maint. (6│
│                                                 │
├─────────────────────────────────────────────────┤
│  Infra partagée : LangGraph, ChromaDB, SQLite,  │
│  SessionManager, ArchiveService, LLMFactory     │
└─────────────────────────────────────────────────┘
```

### 1.3 Les 6 pipelines prévus

| # | Pipeline | Statut | Agents | Description |
|---|----------|--------|--------|-------------|
| 1 | **Éditorial** | 🟡 75-80% | 27 | Rédaction SEO/AEO/GEO |
| 2 | **Audit Technique** | 🔴 0% | ~15 prévus | Crawl, indexation, CWV, structure |
| 3 | **SERP & Positions** | 🔴 0% | ~8 prévus | Suivi positions, analyse concurrentielle |
| 4 | **Stratégie** | 🔴 0% | ~10 prévus | Gaps, opportunités, roadmap |
| 5 | **Maillage & Backlinks** | 🔴 0% | ~7 prévus | Audit liens, recommandations |
| 6 | **Maintenance** | 🔴 0% | ~6 prévus | Obsolescence, mise à jour auto |

---

## 2. Pipeline Éditorial — Agent par Agent

### 2.1 Architecture du pipeline

```
                   00 SUPERVISEUR
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   01 Brief ──► 02 Persona    03 Analyse SERP
        │               │               │
        └───────┬───────┘               │
                │                       │
           04 Intention ◄───────────────┘
                │
        ┌───────┼───────────────┐
        │       │               │
   05 Offre  06 Diff    07 Template
        │       │               │
        └───────┴───────┬───────┘
                        │
                 08 Anti-cannib
                        │
                  09 RÉDACTION ◄── Cœur
                        │
        ┌───────────────┼───────────────┐
        │       │       │       │       │
   10 SEO   11 AEO  12 GEO  13 EEAT 15 Fact-check
        │       │       │       │       │
        └───────┴───────┴───────┴───────┘
                        │
        ┌───────────────┼───────────────┐
   16 Maillage int.  17 Maillage ext.  18 Multiformat
        │               │               │
   19 Test A/B     20 Localisation  22 Images
        │               │               │
        └───────────────┴───────────────┘
                        │
                 21 Schema.org
                        │
                 23 CMS Export
                        │
                 24 Mise à jour
                        │
                 25 Critique Qualité
                        │
                 26 Audit post-pub
```

### 2.2 Agent 00 — Superviseur

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Garde-fou. Vérifie chaque transition entre agents |
| **LLM** | Aucun (code Python pur) |
| **Mode** | Tous |
| **Skippable** | Non (critique) |

**Ce qui est fait (100%) :**
- Validation des dépendances avant chaque transition
- Détection d'agents critiques en échec → arrêt pipeline
- Vérification de cohérence intention vs type_page
- Vérification secteurs réglementés → Agent 14 requis
- Vérification Pydantic des sorties d'agents

**Ce qui manque (0%) :**
- Rien. Cet agent est complet.

**Données produites :**
- `SupervisorVerdict` : valid, blocked_reasons, warnings, next_agent_id, next_action

---

### 2.3 Agent 01 — Brief Entreprise

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Extraire identité, ton, offres, contraintes légales de l'entreprise |
| **LLM** | DeepSeek V4 Flash ($0.0004/requête) |
| **Coût** | ~1850 tokens → $0.0004 |
| **Mode** | Tous |
| **Skippable** | Non (critique) |

**Ce qui est fait (85%) :**
- ✅ Extraction du nom, secteur, positionnement via LLM
- ✅ Déduction du ton de marque depuis le site web
- ✅ Identification des contraintes légales par secteur (9 secteurs réglementés)
- ✅ Guide de déduction du ton dans le prompt système
- ✅ Validation Pydantic (FicheEntreprise)
- ✅ Fallback heuristique si LLM indisponible

**Ce qui manque (15%) :**
- ❌ Lecture réelle du site web (l'URL est passée au LLM mais pas crawlée)
- ❌ Détection automatique du secteur si "autre" (heuristic basique, pas de classification LLM)
- ❌ Pas de cache : refait l'analyse même si le site n'a pas changé

**Données produites :**
```json
{
  "nom": "Clean Tout 37",
  "secteur": "autre",
  "positionnement": "Nettoyage pro et particuliers à Tours",
  "offres": ["Nettoyage bureaux", "Nettoyage particuliers"],
  "ton_marque": "Professionnel et rassurant",
  "preuves": ["10 ans d'expérience"],
  "contraintes_legales": [],
  "mots_cles_interdits": [],
  "elements_differenciants": ["Sans sous-traitance", "Produits écologiques"]
}
```

**Réinjectable dans :** Agent 02 (Persona), Agent 05 (Offre), Agent 09 (Rédaction), Agent 13 (EEAT), Agent 14 (Conformité)

---

### 2.4 Agent 02 — Persona

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Modéliser le lecteur idéal |
| **LLM** | DeepSeek V4 Flash ($0.0005/requête) |
| **Coût** | ~2100 tokens → $0.0005 |
| **Mode** | Standard, Premium, Compliance, Debug |
| **Skippable** | Oui |

**Ce qui est fait (80%) :**
- ✅ Profilage du persona (nom, maturité, expertise, canal)
- ✅ Vocabulaire recommandé (5 termes)
- ✅ Questions typiques (3-5)
- ✅ Freins psychologiques

**Ce qui manque (20%) :**
- ❌ Pas de distinction maturité vs expertise (confondues)
- ❌ Canal d'acquisition basique (search par défaut)
- ❌ Pas d'adaptation au type de page détecté (Agent 04 pas encore exécuté)

**Données produites :** FichePersona → Agent 05, Agent 09

---

### 2.5 Agent 03 — Analyse SERP

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Analyser le top 10 Google, PAA, AI Overviews |
| **LLM** | GPT-5.4 + API TalorData |
| **Coût** | ~636 tokens LLM + $0.0003 API SERP = $0.004 |
| **Mode** | Standard, Premium, Compliance, Debug |
| **Skippable** | Oui |

**Ce qui est fait (70%) :**
- ✅ Connexion TalorData fonctionnelle (POST Bearer, json=2)
- ✅ Extraction top 10 organique (position, titre, URL, domaine)
- ✅ Extraction PAA (People Also Ask)
- ✅ Extraction snack pack (entreprises locales Google Maps)
- ✅ Normalisation JSON structurée → format Hermes
- ✅ Fallback heuristique si API down

**Ce qui manque (30%) :**
- ❌ Word count des pages concurrentes non extrait (l'API ne le fournit pas)
- ❌ H2 count des pages concurrentes non extrait
- ❌ Featured snippet non parsé correctement
- ❌ AI Overview non détecté (structure API à confirmer)
- ❌ Search volume non estimé (l'API ne le fournit pas)
- ❌ Keyword difficulty non calculé
- ❌ Données SERP non affichées dans l'UI Session Detail
- ❌ Pas de cache SERP (refait l'appel à chaque pipeline)

**Données produites :** SerpData (top10, paa, snack_pack, etc.) → Agent 04, 06, 08, 09, 10, 11, 12

---

### 2.6 Agent 04 — Intention & Type de page

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Classifier l'intention de recherche et le type de page |
| **LLM** | DeepSeek V4 Flash + heuristiques |
| **Coût** | ~564 tokens → $0.0003 |
| **Mode** | Tous |
| **Skippable** | Non (critique) |

**Ce qui est fait (85%) :**
- ✅ Classification heuristique (mots-clés par intention)
- ✅ Base de données des villes/régions françaises pour détection locale
- ✅ Pattern "entreprise de [métier] + [ville]" → service_local
- ✅ Classification LLM en fallback (si SERP dispo)
- ✅ 10 types de page supportés

**Ce qui manque (15%) :**
- ❌ Confirmation SERP pas toujours fiable (si API down)
- ❌ Pas de détection de l'intention "navigationnelle"
- ❌ Certains mots-clés ambigus mal classés ("assurance vie temporaire" → locale au lieu d'informative)

**Données produites :** IntentTypeData → Agent 05, 07, 09, 21, 25

---

### 2.7 Agent 05 — Offre & Conversion

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Définir bénéfices, objections, preuves, CTA |
| **LLM** | DeepSeek V4 Flash |
| **Coût** | ~1040 tokens → $0.0003 |
| **Mode** | Standard, Premium, Compliance |
| **Skippable** | Oui |

**Ce qui est fait (80%) :**
- ✅ Transformation offres → bénéfices
- ✅ Objections adaptées aux freins du persona
- ✅ CTA adapté à l'intention
- ✅ CTA secondaire

**Ce qui manque (20%) :**
- ❌ Pas de CTA dynamique par type de page (table existante mais pas appliquée)
- ❌ Preuves pas toujours extraites de la fiche entreprise
- ❌ Valeur ajoutée unique parfois générique

**Données produites :** OffreConversion → Agent 06, 09

---

### 2.8 Agent 06 — Différenciation

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Identifier les failles concurrentielles |
| **LLM** | DeepSeek V4 Flash |
| **Coût** | ~709 tokens → $0.0002 |
| **Mode** | Standard, Premium, Compliance |
| **Skippable** | Oui |

**Ce qui est fait (75%) :**
- ✅ Angles faibles des concurrents
- ✅ Opportunités uniques
- ✅ Angle principal

**Ce qui manque (25%) :**
- ❌ Pas d'analyse fine du top 10 (juste titres, pas le contenu)
- ❌ Facteurs de différenciation parfois génériques
- ❌ Pas de comparaison avec les éléments différenciants réels de l'entreprise

**Données produites :** DifferenciationData → Agent 09

---

### 2.9 Agent 07 — Template

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Structurer le contenu avant rédaction |
| **LLM** | DeepSeek V4 Flash (enrichissement seulement) |
| **Coût** | ~1319 tokens → $0.0003 |
| **Mode** | Tous |
| **Skippable** | Non (critique) |

**Ce qui est fait (85%) :**
- ✅ Bibliothèque de 10 templates (article, pilier, service_local, comparatif, landing, fiche_produit, faq, news, glossaire, temoignage)
- ✅ Sections obligatoires/optionnelles par type
- ✅ Ordre logique des sections
- ✅ Guides de rédaction par section

**Ce qui manque (15%) :**
- ❌ Templates non personnalisés au mot-clé (titres restent génériques)
- ❌ Pas d'adaptation du nombre de sections selon la longueur cible
- ❌ Guides de rédaction parfois trop vagues

**Données produites :** TemplateData (structure avec sections ordonnées) → Agent 09

---

### 2.10 Agent 08 — Anti-cannibalisation

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Détecter les contenus existants similaires |
| **LLM** | Claude Haiku 4.5 + ChromaDB |
| **Coût** | ~150 tokens → $0.0001 |
| **Mode** | Standard, Premium, Compliance |
| **Skippable** | Oui (auto si pas de contenu) |

**Ce qui est fait (70%) :**
- ✅ Recherche vectorielle dans ChromaDB
- ✅ Matrice de décision (merge, enrich, proceed...)
- ✅ Seuil de similarité configurable

**Ce qui manque (30%) :**
- ❌ ChromaDB vide en pratique (jamais alimenté après publication)
- ❌ Pas de fingerprint sémantique d'angle
- ❌ Pas de détection de cannibalisation réelle via GSC

**Données produites :** AntiCannibData → Agent 09

---

### 2.11 Agent 09 — Rédaction ★ CŒUR DU PIPELINE

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Produire le brouillon HTML complet |
| **LLM** | Claude Sonnet 4.6 |
| **Coût** | ~5206 tokens → $0.056 (60% du coût total) |
| **Mode** | Tous |
| **Skippable** | Non (critique) |

**Ce qui est fait (80%) :**
- ✅ Prompt système riche (3K tokens) avec toutes les données des agents 01-08
- ✅ Consignes par type de page (10 types)
- ✅ Anti-placeholder rules strictes
- ✅ Règles de format HTML
- ✅ Gestion des contraintes légales
- ✅ Gestion des mots interdits
- ✅ Fallback HTML si JSON mal formé
- ✅ Extraction HTML multi-format

**Ce qui manque (20%) :**
- ❌ Pas de word count cible basé sur la SERP (problème critique)
- ❌ Pas de few-shot examples dans le prompt
- ❌ Prompt non versionné (toujours v1)
- ❌ Pas de mode "rewrite" (modifier l'existant au lieu de créer)
- ❌ Pas de mode "expand" (enrichir une section spécifique)
- ❌ La réponse est parfois tronquée (max_tokens=8000 pour 5000 mots → insuffisant)

**Données produites :** Brouillon (html, word_count, titre, meta_description, sections) → Agents 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 25

---

### 2.12 Agent 10 — SEO On-Page

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Optimiser title, meta, Hn, densité, maillage |
| **LLM** | GPT-5.4 |
| **Coût** | ~1072 tokens → $0.009 |
| **Mode** | Tous |
| **Skippable** | Non |

**Ce qui est fait (80%) :**
- ✅ Title optimisé (50-65 car.)
- ✅ Meta description (140-160 car.)
- ✅ Structure Hn analysée
- ✅ Densité mots-clés

**Ce qui manque (20%) :**
- ❌ Maillage interne suggéré mais non contextualisé
- ❌ Pas d'analyse de la concurrence pour le title
- ❌ Title parfois générique

**Données produites :** SeoData → Agent 11, 19, 21, 23, 25

---

### 2.13 Agent 11 — AEO

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Optimiser pour les moteurs de réponse IA |
| **LLM** | Claude Haiku 4.5 |
| **Coût** | ~1946 tokens → $0.006 |
| **Mode** | Tous |
| **Skippable** | Non |

**Ce qui est fait (80%) :**
- ✅ Bloc "En bref" (Featured Snippet)
- ✅ Reformulation H2 en questions
- ✅ FAQ structurée (3-8 Q/R)
- ✅ Définitions de termes techniques
- ✅ Exemple concret dans le prompt

**Ce qui manque (20%) :**
- ❌ Pas de validation que la FAQ couvre les PAA réels
- ❌ Bullets parfois vides au lieu d'être informationnels
- ❌ Pas de score AEO par page

**Données produites :** AeoBlocks → Agent 09, 25

---

### 2.14 Agent 12 — GEO

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Rendre le contenu citable par les IA génératives |
| **LLM** | Claude Haiku 4.5 |
| **Coût** | ~2605 tokens → $0.008 |
| **Mode** | Standard, Premium, Compliance |
| **Skippable** | Oui |

**Ce qui est fait (85%) :**
- ✅ Profils GEO par type de page (10 types)
- ✅ Sources primaires avec hiérarchie de crédibilité (A-B-C-D)
- ✅ Entités nommées extraites
- ✅ Phrases citables générées
- ✅ Chunks autonomes

**Ce qui manque (15%) :**
- ❌ Sources pas toujours vérifiables (URLs non testées)
- ❌ Pas de vérification Wikidata pour les entités
- ❌ Pas de score de citabilité

**Données produites :** GeoData → Agent 25

---

### 2.15 Agent 13 — EEAT

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Évaluer Expertise, Expérience, Autorité, Fiabilité |
| **LLM** | Claude Haiku 4.5 |
| **Coût** | ~1805 tokens → $0.005 |
| **Mode** | Standard, Premium, Compliance |
| **Skippable** | Oui |

**Ce qui est fait (80%) :**
- ✅ 4 scores (0-4) → score global /16
- ✅ Détection YMYL (santé, finance, droit)
- ✅ Recommandations par critère

**Ce qui manque (20%) :**
- ❌ Pas de vérification de la bio auteur
- ❌ Pas de page auteur dédiée
- ❌ Pas de vérification de la page "À propos"

**Données produites :** EeatScore → Agent 25

---

### 2.16 Agent 14 — Conformité

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Vérifier conformité légale sectorielle |
| **LLM** | Claude Haiku 4.5 (si secteur sensible) |
| **Mode** | Premium, Compliance |
| **Skippable** | Non (si secteur réglementé) |

**Ce qui est fait (80%) :**
- ✅ Table des obligations par secteur (9 secteurs)
- ✅ Détection des mots interdits
- ✅ Niveaux de risque (faible à critique)

**Ce qui manque (20%) :**
- ❌ Pas de vérification automatique des mentions légales obligatoires
- ❌ Niveaux de risque non appliqués en pratique

**Données produites :** ConformiteData → Agent 25

---

### 2.17 Agent 15 — Fact-checking

| Attribut | Valeur |
|----------|--------|
| **Rôle** | Vérifier les faits, chiffres, dates |
| **LLM** | Claude Haiku 4.5 |
| **Coût** | ~1582 tokens → $0.005 |
| **Mode** | Tous |
| **Skippable** | Non (critique) |

**Ce qui est fait (75%) :**
- ✅ Détection des affirmations non sourcées
- ✅ Score de fiabilité /10
- ✅ Niveaux de gravité (critique à faible)

**Ce qui manque (25%) :**
- ❌ Pas de vérification croisée avec des sources externes
- ❌ Pas de base de connaissances pour valider les chiffres
- ❌ Gravité "modérée" et "faible" non différenciées

**Données produites :** FactCheckData → Agent 24, 25

---

### 2.18 Agents 16-26 (Résumé)

| Agent | Fait | Manque principal |
|-------|------|-----------------|
| **16 Maillage interne** | 70% | ChromaDB souvent vide, ancres pas contextualisées |
| **17 Maillage externe** | 70% | Sources pas toujours vérifiées |
| **18 Multiformat** | 80% | Formats OK, ton parfois uniforme entre formats |
| **19 Test A/B** | 75% | CTR prédit théorique, pas de test réel |
| **20 Localisation** | 60% | Jamais testé en conditions réelles |
| **21 Schema.org** | 85% | Validation Google Rich Results non intégrée |
| **22 Images** | 65% | Prompts de génération, pas d'images réelles produites |
| **23 CMS Export** | 70% | WordPress + HTML OK, autres CMS non testés |
| **24 Mise à jour** | 75% | Plan de révision OK, déclencheurs non automatisés |
| **25 Critique Qualité** | 85% | 9 critères OK, seuils par mode OK, recommandations parfois vagues |
| **26 Audit post-pub** | 30% | GSC non connecté, mémoire ChromaDB non alimentée |

---

## 3. Flux de Données Inter-Agents

### 3.1 Données qui traversent tout le pipeline

```
SessionState (objet partagé)
├── keyword ──────────────────────► Tous les agents
├── site_url ─────────────────────► Agent 01, 03, 09
├── objectif ─────────────────────► Agent 02, 04, 09
├── fiche_entreprise (Agent 01) ──► Agent 02, 05, 06, 09, 13, 14
├── fiche_persona (Agent 02) ─────► Agent 05, 09
├── serp_data (Agent 03) ─────────► Agent 04, 06, 08, 09, 10, 11, 12
├── intention (Agent 04) ─────────► Agent 05, 07, 09, 21, 25
├── type_page (Agent 04) ─────────► Agent 07, 09, 10, 11, 12, 21, 25
├── offre_conversion (Agent 05) ──► Agent 06, 09
├── angles_differenciants (06) ───► Agent 09
├── template_data (Agent 07) ─────► Agent 09
├── anti_cannib_data (Agent 08) ──► Agent 09
├── brouillon_html (Agent 09) ────► Agent 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 22, 23, 25
├── seo_data (Agent 10) ──────────► Agent 11, 19, 21, 23, 25
├── aeo_blocks (Agent 11) ────────► Agent 25
├── geo_data (Agent 12) ──────────► Agent 25
├── score_eeat (Agent 13) ────────► Agent 25
├── conformite_data (Agent 14) ───► Agent 25
├── fact_check_data (Agent 15) ───► Agent 24, 25
└── scores (Agent 25) ────────────► Agent 26
```

### 3.2 Données réinjectables entre pipelines (futur)

| Donnée | Source | Cible | Usage |
|--------|--------|-------|-------|
| **serp_data** | Pipeline Éditorial | Pipeline SERP & Positions | Comparer analyse initiale vs positions réelles |
| **brouillon_html** | Pipeline Éditorial | Pipeline Maintenance | Détecter obsolescence du contenu |
| **scores** | Pipeline Éditorial | Pipeline Stratégie | Identifier contenus à réviser en priorité |
| **top10 SERP** | Pipeline SERP | Pipeline Éditorial | Réanalyse concurrentielle avant mise à jour |
| **crawl_results** | Pipeline Audit | Pipeline Stratégie | Identifier pages orphelines, thin content |
| **backlinks** | Pipeline Backlinks | Pipeline Stratégie | Prioriser les contenus à forte autorité |
| **gsc_data** | Pipeline Éditorial (26) | Pipeline SERP | Corréler positions prédites vs réelles |
| **chromadb** | Tous | Agent 08 (Anti-cannib) | Mémoire des contenus publiés |

---

## 4. Autres Pipelines (listing rapide)

### 4.1 Pipeline Audit Technique (~15 agents)

| # | Agent | Rôle | LLM |
|---|-------|------|-----|
| T01 | Crawler | Parcourt le site (URLs, status codes, Hn) | Aucun |
| T02 | Indexation | Statut GSC par URL | API GSC |
| T03 | Performance | Core Web Vitals (LCP, INP, CLS) | CrUX/Lighthouse |
| T04 | Structure | H1, title, meta, canonical, OG | Aucun |
| T05 | Contenu | Thin content, duplicats, orphelines | Embeddings |
| T06 | Schema | Validation JSON-LD | Rich Results API |
| T07 | Sitemap | robots.txt + sitemap XML | Aucun |
| T08 | Mobile | Responsive, viewport | Screenshots auto |
| T09 | Sécurité | HTTPS, mixed content, headers | Aucun |
| T10 | International | hreflang, cohérence multilingue | Aucun |
| T11 | Synthèse | Agrège les rapports | LLM (synthèse) |
| T12 | Priorisation | Classe problèmes par impact × effort | LLM |
| T13 | Roadmap | Plan d'action priorisé | LLM |
| T14 | Superviseur Audit | Garde-fou | Aucun |
| T15 | Export Audit | Rapport PDF/HTML/JSON | Aucun |

**Input :** URL du site
**Output :** Rapport d'audit complet avec priorités

### 4.2 Pipeline SERP & Positions (~8 agents)

| # | Agent | Rôle |
|---|-------|------|
| S01 | Rank Tracker | Suivi positions via GSC API |
| S02 | Volatilité | Détection variations > seuil |
| S03 | SERP Features | Featured snippet, PAA, vidéo, AI Overview |
| S04 | Concurrent Monitor | Suivi des concurrents définis |
| S05 | Gap Content | Ce que le top 3 a que notre page n'a pas |
| S06 | Quick Wins | Pages en position 4-15 |
| S07 | Alertes | Perte >5 places, gain top 10 |
| S08 | Superviseur SERP | Garde-fou |

### 4.3 Pipeline Stratégie (~10 agents)

| # | Agent | Rôle |
|---|-------|------|
| ST01 | Cartographie | Sujets couverts vs manquants |
| ST02 | Cannibalisation | Détection paires cannibales via GSC |
| ST03 | Opportunités | Requêtes sans page dédiée |
| ST04 | Gap Concurrentiel | Sujets que les concurrents couvrent et pas nous |
| ST05 | Scoring Business | Pages par potentiel (trafic × intent × conversion) |
| ST06 | Roadmap Éditoriale | Plan de contenu priorisé |
| ST07 | Silos | Détection silos sans pilier |
| ST08 | Fusion/Separation | Recommandations structurelles |
| ST09 | Revue Humaine | File de validation pour sujets sensibles |
| ST10 | Superviseur Stratégie | Garde-fou |

### 4.4 Pipeline Maillage & Backlinks (~7 agents)

| # | Agent | Rôle |
|---|-------|------|
| B01 | Import Backlinks | Via Ahrefs/Semrush API |
| B02 | Qualité Domaines | Score par domaine référent |
| B03 | Toxiques | Détection liens suspects |
| B04 | Gap Analysis | Domaines concurrents non acquis |
| B05 | Link Reclamation | Mentions non linkées de la marque |
| B06 | Recommandations | Priorisées par impact |
| B07 | Superviseur Backlinks | Garde-fou |

### 4.5 Pipeline Maintenance (~6 agents)

| # | Agent | Rôle |
|---|-------|------|
| M01 | Fraîcheur | Score d'obsolescence par page |
| M02 | Déclencheurs | Core update, changement loi, annonce concurrent |
| M03 | File de Révision | Priorisée par impact |
| M04 | Réécriture | Mise à jour automatique (réutilise Agent 09 modifié) |
| M05 | Planification | Calendrier de révision |
| M06 | Superviseur Maintenance | Garde-fou |

---

## 5. Recommandations — Priorités

### 5.1 Court terme (cette semaine)

1. **Afficher les données SERP dans le Session Detail** — 3h — L'utilisateur voit sur quoi le contenu se base
2. **Word count cible automatique** — 2h — L'Agent 09 reçoit l'objectif de longueur depuis le SERP
3. **Paramètre tone of voice** — 1h — L'utilisateur peut choisir "Plus technique" ou "Plus commercial"

### 5.2 Moyen terme (ce mois)

4. **Page "Analyser la SERP" sans rédaction** — 3h — Nouveau use case
5. **Refonte UI (cartes d'action, champ central)** — 7h — Interface intuitive
6. **Few-shot examples dans les prompts** — 5h — Qualité de rédaction ×2
7. **Prompt versioning (v2)** — 3h — A/B testing des prompts

### 5.3 Long terme (3-6 mois)

8. **Pipeline Audit Technique MVP** (T01 + T04 + T05 + T11) — 20h
9. **Pipeline SERP & Positions** (S01 + S02 + S05) — 15h
10. **Orchestrateur inter-pipelines** — 25h
11. **Connexion GSC réelle** — 8h
12. **API REST SaaS** — 15h

---

## 6. Architecture Technique

### 6.1 Stack

| Composant | Technologie |
|-----------|------------|
| Orchestration | LangGraph 1.2.5+ |
| Mémoire vectorielle | ChromaDB |
| État pipeline | SQLite (SqliteSaver) + JSON (SessionManager) |
| Validation | Pydantic 2.0 |
| LLMs | Claude Sonnet 4.6, GPT-5.4, Haiku 4.5, DeepSeek V4 Flash |
| SERP API | TalorData (POST Bearer, json=2) |
| Logging | Loguru JSONL |
| CLI | Click + Rich |
| UI | Streamlit 1.32+ |
| Tests | pytest 8.0 (656 tests) |

### 6.2 Coûts opérationnels

| Mode | Agents | Coût/article | Coût/100 articles |
|------|--------|-------------|-------------------|
| Fast | 9 | ~$0.50 | ~$50 |
| Standard | 20 | ~$0.60 | ~$60 |
| Premium | 26 | ~$0.80 | ~$80 |

### 6.3 Fichiers clés

| Fichier | Rôle |
|---------|------|
| `hermes/agents/` | 27 fichiers, 1 par agent |
| `hermes/core/workflow.py` | Graphe LangGraph + AGENT_ORDER |
| `hermes/core/llm.py` | Factory LLM multi-fournisseur |
| `hermes/connectors/serp_api.py` | Client TalorData |
| `hermes/core/pipeline_guard.py` | Arrêt sur échec critique |
| `hermes/core/archive_service.py` | Archivage global |
| `hermes/core/guard.py` | Anti-injection, mots bloqués |
| `hermes/models/session.py` | SessionState (objet partagé) |
| `prompts/agent_XX_nom/v1/system.md` | 27 prompts système |
| `agents_registry.yaml` | Registre central (source de vérité) |
| `app.py` | Interface Streamlit |
| `pages/` | archive_page, session_detail_page, strategy_panel |

---

## 9. Audit des Projets Frères — Features à Récupérer

### 9.1 Projet 1 : `saas-seo` (Next.js + Supabase + DataForSEO)

**Stack** : Next.js 16, Claude SDK, DataForSEO, Supabase, Cheerio, Vercel
**Statut** : 117 API routes, 45 pages frontend, multi-projet, scoring adaptatif
**Maturité** : Avancée (production-grade), Stripe billing intégré

#### Features à récupérer (sans copier l'architecture Next.js)

| # | Feature | Complexité | Intégration Hermes |
|---|---------|-----------|-------------------|
| 1 | **DataForSEO** (6 fonctions : domain metrics, related keywords, position check, suggestions, Moz DA) | 🟡 | Remplacer/augmenter TalorData par DataForSEO pour la profondeur |
| 2 | **Scoring adaptatif par type de page** (`page-type-rules.js`, 545 lignes) — 11 types × 25 dimensions, Required/Valued/Neutral/Penalty | 🔴 | Portage Python de cette logique → `hermes/core/scoring_rules.py` |
| 3 | **Déterministe avant LLM** — `html-extractor.js` (Cheerio, 50+ champs, $0) → `audit-parser.js` (score, $0) → LLM (seulement nuance) | 🟡 | Principe déjà partiellement appliqué (agents 21, 23, 25 sans LLM). Généraliser |
| 4 | **LLM Guard anti-hallucination** (`llm-guard.js`, 268 lignes) : `buildFactualInventory`, `verifyLLMClaims`, `pageTypeAwareGuard` | 🟡 | Portage → `hermes/core/llm_guard.py` — cross-check LLM vs déterministe |
| 5 | **JSON Repair 3 niveaux** : strict parse → regex extract → jsonrepair | 🟢 | Intégrer `jsonrepair` dans `LLMFactory.route()` |
| 6 | **Timeout adaptatif** : `max(45, maxTokens/50 + 30)` | 🟢 | Remplacer le timeout fixe de 600s par cette formule |
| 7 | **Geo-Grid Rank Tracking** (`local-grid.js`, 353 lignes) — DataForSEO Maps Live, heatmap SVG, ATRP/SoLV | 🔴 | Futur pipeline Local SEO |
| 8 | **GBP 40-point checklist** (`local-seo-rules.js`, 599 lignes) — Whitespark 2026, scoring pondéré | 🔴 | Futur pipeline Local SEO |
| 9 | **Content decay detection** — pages dont le trafic baisse progressivement | 🔴 | Futur pipeline Maintenance |
| 10 | **Multi-projet localStorage scoping** (`project-scope.js`, 213 lignes) — clés scopées, cache cleanup | 🟡 | Adapter pour Hermes : sessions scopées par projet |
| 11 | **GSC + GA4 connectés** (routes API réelles) | 🟡 | Brancher l'Agent 26 sur une vraie connexion GSC |
| 12 | **WordPress auto-publish** (route `api/wordpress/publish`) | 🟡 | Ajouter à l'Agent 23 (CMS Export), déjà partiellement fait |
| 13 | **Stripe billing** (checkout, portal, webhook) | 🔴 | Long terme — monétisation SaaS |
| 14 | **Calendrier éditorial** (kanban + vue mois) | 🟡 | UI future — planning de contenu |
| 15 | **Rapports mensuels IA** (génération + historique) | 🟡 | Agent 26 étendu — rapport de performance |
| 16 | **Content gap analysis** — croisement domaines concurrents, mots-clés manquants | 🟡 | Nouveau pipeline Stratégie |
| 17 | **Topical map** — carte thématique IA | 🟡 | Nouveau pipeline Stratégie |
| 18 | **Duplicate content detection** — Dice coefficient, string-similarity | 🟢 | Améliorer Agent 08 au-delà de ChromaDB |
| 19 | **Checklist SEO 60+ points** interactive | 🟢 | Page UI dédiée |

#### Ce qu'il ne faut PAS copier
- L'architecture Next.js/React (Hermes est Streamlit + LangGraph, rester sur Python)
- Supabase comme unique DB (Hermes utilise SQLite + ChromaDB + JSON)
- Le pattern "API routes" au lieu d'agents autonomes
- L'absence de pipeline multi-agent (le projet 1 a des routes indépendantes, pas un graphe)

---

### 9.2 Projet 2 : `fc-solutions-ai-site` (WordPress + Node.js + o2switch)

**Stack** : WordPress, plugin métier `fc-ai-engine`, scripts Node.js, cron serveur
**Statut** : Production active sur `fc-solutions.pro`, 1 article/jour automatique
**Maturité** : Production — flux quotidien complet (veille → rédaction → images → publication → suivi)

#### Features à récupérer (sans copier l'architecture WordPress)

| # | Feature | Complexité | Intégration Hermes |
|---|---------|-----------|-------------------|
| 1 | **Pipeline éditorial complet** : veille RSS → sélection sujet → brief → rédaction → enrichissement SEO/AEO/GEO → images → garde-fous → publication → GSC/GA4 | 🟢 | Hermes a déjà la partie rédaction. Manque : veille, garde-fous pré-publication, suivi post-publication |
| 2 | **Brief stratégique** avec SERP attachée — sujet, mot-clé, audience, intention, angle, sources, CTA, risques | 🟡 | Nouvel agent "Brief Stratégique" (pré-Agent 01) ou enrichissement Agent 01 |
| 3 | **Garde-fous pré-publication** : checklist 60+ points, blocage si structure manquante, vérification sources, détection contenu faible | 🟡 | Renforcer Agent 25 (Critique Qualité) avec les règles du projet 2 |
| 4 | **Mémoire interne / Content Knowledge** : indexation titres, statuts, H2/H3, FAQ, sources, entités, liens internes. Détection cannibalisation + couverture sémantique | 🟡 | ChromaDB existe déjà. Ajouter : couverture sémantique, détection d'opportunités |
| 5 | **Système de sources structuré** : stockage en métadonnées, vérification liens, distinction source principale/secondaire/institutionnelle, exigence institutionnelle pour YMYL | 🟡 | Enrichir Agent 12 (GEO) + Agent 15 (Fact-checking) avec cette logique |
| 6 | **Pipeline images 3 niveaux** : hero (arrière-plan titre) + milieu (entre H2) + infographie (fin d'article). Logo overlay officiel systématique | 🟡 | Agent 22 (Images) déjà là. Ajouter : overlay logo, placement intelligent selon H2 |
| 7 | **Extraits de cartes optimisés clic** : smartSnippet() → phrases complètes, pas tronquées, pas "En bref" recopié | 🟢 | Ajouter à l'Agent 09 (Rédaction) — génération d'extrait |
| 8 | **Détection contenu interne exposé** : "Position 0", "RAG", "ce brouillon", "avant publication", "sources à vérifier", scores internes | 🟢 | Ajouter à l'Agent 15 (Fact-checking) — pattern matching |
| 9 | **Content freshness scoring** : date de dernière modification + pertinence temporelle du sujet | 🟡 | Agent 24 (Mise à jour) — enrichir avec score de péremption |
| 10 | **Multi-site cloning** : config/site.json → duplication WordPress + runner | 🔴 | Long terme — packaging produit |
| 11 | **Cron serveur** avec verrou anti-chevauchement, statut JSON, persistance WordPress | 🟡 | Remplacer par l'Orchestrateur (futur) |
| 12 | **Quotas de publication** : news 1/jour, outil 1/jour, batch limit 1/cycle | 🟢 | Ajouter à la config Hermes |
| 13 | **Tableau de bord WordPress** : scores, positions GSC, audience GA4, fraîcheur, mémoire, briefs, rapports PDF | 🔴 | Équivalent Streamlit déjà fait. Ajouter : rapports PDF exportables |
| 14 | **RAG éditorial versionné** : politique éditoriale, règles anti-prompt, profils sectoriels, simulation avant activation | 🔴 | Long terme — gestion centralisée des prompts |
| 15 | **Workflow article stratégique** : back-office → brief → SERP attachée → brouillon → enrichissement → images → garde-fous → publication manuelle | 🟡 | Ajouter le mode "stratégique" au pipeline (vs "automatique" quotidien) |

#### Ce qu'il ne faut PAS copier
- L'architecture WordPress/PHP (Hermes est Python, rester en Python)
- Les scripts Node.js éparpillés (Hermes a un graphe LangGraph unifié)
- Le cron serveur bash (l'Orchestrateur Python sera plus robuste)
- La dépendance à o2switch (Hermes est cloud-agnostique)
- Le flux "veille IA uniquement" (Hermes est généraliste, pas limité à l'IA)

---

### 9.3 Synthèse — Top 15 Features à Implémenter en Priorité

Classées par impact × facilité d'intégration :

| # | Feature | Source | Effort | Impact |
|---|---------|--------|--------|--------|
| 1 | **Déterministe avant LLM** systématisé | saas-seo | 5h | $$$ — réduit coûts API |
| 2 | **JSON Repair 3 niveaux** dans LLMFactory | saas-seo | 2h | $$ — réduit échecs |
| 3 | **Timeout LLM adaptatif** (maxTokens/50+30) | saas-seo | 1h | $$ — fiabilité |
| 4 | **Garde-fous pré-publication enrichis** (60+ points du projet 2) | fc-solutions | 3h | $$$ — qualité |
| 5 | **Détection contenu interne exposé** (anti "ce brouillon", "RAG"... | fc-solutions | 1h | $$ — proprété |
| 6 | **Système de sources structuré** (principal/secondaire/institutionnel) | fc-solutions | 3h | $$$ — E-E-A-T |
| 7 | **Scoring adaptatif par type de page** (11 types × Required/Valued/Neutral) | saas-seo | 8h | $$$ — précision |
| 8 | **Extraits de cartes optimisés** (smartSnippet) | fc-solutions | 1h | $ — UX |
| 9 | **Pipeline images 3 niveaux** + logo overlay | fc-solutions | 3h | $$ — qualité visuelle |
| 10 | **Content decay detection** via GSC | saas-seo | 5h | $$$ — maintenance |
| 11 | **DataForSEO** (remplacer/augmenter TalorData) | saas-seo | 4h | $$$ — données SERP |
| 12 | **LLM Guard anti-hallucination** (cross-check) | saas-seo | 5h | $$$ — fiabilité |
| 13 | **Brief stratégique** (pré-Agent 01) | fc-solutions | 6h | $$ — structuration |
| 14 | **GSC + GA4 connexion réelle** | saas-seo + fc-solutions | 6h | $$$ — suivi |
| 15 | **WordPress auto-publish** (Agent 23 étendu) | saas-seo | 3h | $$ — intégration |

**Total estimé** : ~56h de développement pour les 15 features.
**Impact cumulé** : transformation de 75% → 90%+ sur le pipeline éditorial.
