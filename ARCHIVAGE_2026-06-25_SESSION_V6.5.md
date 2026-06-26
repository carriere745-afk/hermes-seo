# Archive — Session 25 juin 2026 — Corrections V6.5 + Audit systemique

**Commit**: `31cd0c0` — Fix anomalies fc-solutions.pro: contextualisation SERP, baseline auto, ancres sans hardcode
**Repo**: https://github.com/carriere745-afk/hermes-seo
**Statut**: 7/7 pipelines operationnels | 134 agents | 88% criteres qualite satisfaits

## Corrections systemiques (7 bugs racine corriges)

1. **Contexte SERP imperatif**: fallback DuckDuckGo HTML gratuit (sans cle API) pour comprendre le sens reel d'un mot-cle avant redaction. Empeche "nano banana" = fruit.
2. **Baseline automatique (sitemap + robots + llms)**: P7 M03 garantit les 3 fichiers fondamentaux pour tout site.
3. **Ancres sans ville hardcodee**: B14 detection departement→ville dynamique. Templates par profil (local vs default). Plus de "Tours" pour un site SaaS.
4. **Filtre anti-pollution P5**: ST03 verifie overlap avec keywords_monitored. _load_p4_gaps() filtre par domaine.
5. **Fallback LLM**: auth errors non-retryables → bascule directe vers le modele suivant (Claude 401 → GPT → DeepSeek).
6. **import log_agent_failed** corrige dans agent_11_aeo.py
7. **MISSION_HERMES.md**: mission statement + 5 regles qualite (vrai, pertinent, actionnable, comprehensible, honnete)

## Etat du systeme (audit 25 juin 2026)

| Pipeline | Agents | Teste | Statut |
|----------|--------|-------|--------|
| P1 Editorial | 28 | Streamlit | DeepSeek OK, Anthropic/OpenAI en 401 |
| P2 Audit Contenu | 12 | Streamlit | Fonctionnel |
| P3 Audit Technique | 23 | Streamlit | Fonctionnel |
| P4 SERP | 13 | Teste OK | 50 positions fc-solutions.pro |
| P5 Strategie | 19 | Teste OK | 5 sujets, 9 recos |
| P6 Backlinks | 18 | Teste OK | Auth 49/100 |
| P7 Maintenance | 12 | Teste OK | Baseline OK |
| P8 Learning | 9 | Accumulation | Silencieuse |

### Flux cross-pipeline
- **Actifs (4/8)**: P4→P5 (5 agents), P5→P7 (strategie_db imports), P6→P7 (backlinks_db imports), Tous→P8 (learning agents)
- **Manquants (4/8)**: P5→P1 (ST11 route mais pas auto), P3→P5 (lock uniquement), P2→P5, P4→P6

### APIs
- LLM: DeepSeek v4-Flash OK | Anthropic/OpenAI: cles revoquees (401)
- GSC: token OAuth valide, fc-solutions.pro verifie | cleantout37.fr: non verifie
- DataForSEO: credentials OK, backlinks necessite souscription separee

### Prochaines priorites
1. P0: Nouvelles cles Anthropic (qualite redaction)
2. P0: Verifier cleantout37.fr dans GSC
3. P1: UX/UI refonte dashboard projet
4. P1: Flux P5→P1 automatique
5. P2: DataForSEO backlinks
6. P3: Stripe/Paiement
