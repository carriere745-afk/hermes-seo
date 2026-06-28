# Hermes SEO v3 — Resume de Reprise

**Date :** 28 juin 2026  
**Commit :** `a2bef07`  
**Repo :** `https://github.com/carriere745-afk/hermes-seo`

---

## 1. Comment lancer le projet

```bash
git clone https://github.com/carriere745-afk/hermes-seo.git
cd hermes-seo
pip install -r requirements.txt
cp .env .env  # configurer les cles API
streamlit run app.py  # UI sur localhost:8501
python -m hermes.headless --pipeline all --site https://URL  # Mode headless
```

## 2. Fichiers essentiels a lire

| Ordre | Fichier | Pourquoi |
|--------|---------|---------|
| 1 | `RAPPORT_FINAL_28JUIN.html` | Vue d'ensemble complete : 138 agents, 8 pipelines, scores, roadmap |
| 2 | `MISSION_HERMES.md` | Ce qu'est Hermes, regles qualite (5 regles) |
| 3 | `hermes/saas/ARCHITECTURE_SAAS.md` | Modele economique, tarifs, stack, WP, Stripe |
| 4 | `audit_final/PLAN_ACTION_630_COMPLET.html` | Taches restantes par module (630 items) |
| 5 | `audit_final/GAP_ANALYSIS_630.html` | Couverture vs Mega-Reference 630 |

## 3. Etat du projet (28 juin 2026, 23h00)

**Note globale : 85/100 (roadmap V7). 138 agents, 103 tests OK. ~75% couverture Mega-Reference 630.**

| Pipeline | Agents | Statut |
|----------|--------|--------|
| P1 Editorial | 50 | Operationnel — Claude Sonnet 4.6 pour redaction |
| P2 Audit Contenu | 12 | Operationnel |
| P3 Audit Technique | 23 | Operationnel |
| P4 SERP Visibility | 16 | Operationnel — GSC actif, AEO PAA, benchmark |
| P5 Strategie | 24 | Operationnel — P5->P1 auto, CTR, content gaps |
| P6 Backlinks | 18 | Operationnel — mock data (DataForSEO non souscrit) |
| P7 Maintenance | 15 | Operationnel — sitemap+robots+llms auto, CMS 13 actions |
| P8 Learning | 9 | Accumulation silencieuse active |
| **TOTAL** | **138** | **8 pipelines coordonnes** |

### APIs
- LLM : Anthropic Sonnet ✅ | OpenAI ✅ | DeepSeek ✅ (fallback chain)
- GSC : token OK, 8 sites verifies, cleantout37.fr NON verifie
- DataForSEO : credentials OK, backlinks besoin souscription ($20/m)
- Keywords Everywhere : 402 credit epuise
- DuckDuckGo HTML : fallback gratuit (3 endpoints, 3 UAs)

### UX/UI
- Sidebar inspirée Linear/Stripe : logo Hermes, projet actif (green dot), welcome screen avec input URL + bouton Demo
- Diagnostic complet 1-clic (P4→P5→P6→P7)
- 12 pages adaptatives (CTA si pas de projet)
- Disclaimers footer permanent

### Deploiement
- Docker + docker-compose + deploy.sh
- Headless mode (`python -m hermes.headless --pipeline all --site URL`)
- DB backup (`python -m hermes.core.backup`)

## 4. Ce qui reste a faire (~22h, ~$30/mois)

| Priorite | Action | Effort |
|----------|--------|--------|
| P0 | DataForSEO Backlinks ($20/mois) + Keywords Everywhere ($10) | 1h |
| P1 | Stripe / Paiement | 4h |
| P1 | WordPress test reel (publier via XML-RPC) | 1h |
| P1 | Mode sombre + responsive | 2h |
| P1 | Crawl multi-pages P5 | 1.5h |
| P2 | P2/P3 → P5 integration | 3h |
| P2 | Export PDF (weasyprint) | 1h |
| P2 | Barre de progression par agent | 1.5h |
| P2 | GSC Auto-Disavow | 1.5h |
| P3 | Onboarding wizard 8 etapes | 2h |
| P3 | Tests resilience + UI | 2.5h |

## 5. Ce que le nouveau terminal doit savoir

- Les prompts de redaction (`PROMPT_0` a `PROMPT_3`) sont independants d'Hermes — utilises pour livrer du contenu client en attendant le SaaS
- Le journal de la conversation est dans `ARCHIVAGE_2026-06-25_SESSION_V6.5.md` et `ARCHIVAGE_2026-06-24_PIPELINE5.md`
- Tous les fichiers d'audit sont dans `audit_final/`
- Les tests : `python -m pytest tests/test_strategie.py tests/test_backlinks.py tests/test_maintenance_learning.py tests/test_cross_pipeline.py` → 103/103 OK
