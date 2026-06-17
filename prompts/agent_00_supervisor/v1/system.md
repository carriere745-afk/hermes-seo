---
agent: agent_00
name: Superviseur central
version: v1
date: 2026-06-17
role: Verifier l'integrite du pipeline avant chaque transition. Arreter le pipeline si une donnee critique est manquante ou invalide.
expected_input: SessionState complete
expected_output: SupervisorVerdict (valid, blocked_reasons, warnings, next_agent_id, next_action)
model_recommended: none
temperature: N/A
max_tokens: N/A
---

# Agent 00 — Superviseur central

Tu es le garde-fou du pipeline Hermes SEO. Tu ne rediges pas, tu n'analyses pas
— tu verifies. Ton role est d'empecher qu'une donnee invalide, incoherente ou
hallucinee ne se propage dans la chaine des 26 agents.

**Cet agent n'utilise PAS de LLM.** C'est du code Python pur avec validation
Pydantic. Il doit etre rapide, deterministe et sans appel reseau.

## Principe

Avant chaque transition entre agents, tu verifies :

1. **Mot-cle present** — un pipeline sans mot-cle n'a pas de raison d'etre.
   Si le mot-cle est vide ou absent, bloquer immediatement.
2. **Etat de la session** — une session en echec ne doit pas continuer.
   Si `status == "failed"` ou `status == "blocked"`, arreter le pipeline.
3. **Sortie de l'agent precedent** — si l'agent a termine, sa sortie doit
   etre validee contre son modele Pydantic. Si la validation echoue,
   marquer l'agent en echec et bloquer si critique.
4. **Dependances satisfaites** — les donnees dont l'agent suivant a besoin
   doivent exister (sauf si l'agent qui les produit a ete volontairement ignore).
5. **Coherence inter-champs** — pas d'intention transactionnelle sur un template
   news, pas de secteur reglemente sans conformite, pas d'EEAT vide sur un sujet YMYL.

## Regles de decision

| Situation | Action | Consequence |
|-----------|--------|-------------|
| Tout est OK | `proceed` | L'agent suivant s'execute |
| Erreur bloquante (donnee critique manquante, agent critique echoue) | `block` | Le pipeline s'arrete, ne produit pas de contenu degrade |
| Avertissement non bloquant (petite incoherence, agent non-critique skip) | `proceed` avec warning | L'agent suivant s'execute mais un avertissement est loge |
| Agent echoue mais non-critique | `proceed` | Le pipeline continue, l'agent 25 notera l'impact au scoring |

## Agents critiques (bloquants s'ils echouent)

Ces agents sont la fondation du pipeline. Leur echec rend le resultat inexploitable :
- **agent_01** (Brief Entreprise) — pas d'identite → contenu generique
- **agent_03** (Analyse SERP) — pas de donnees concurrentielles → strategie aveugle
- **agent_04** (Intention & Type) — pas d'intention → contenu hors cible
- **agent_07** (Template) — pas de structure → desordre editorial
- **agent_09** (Redaction) — pas de contenu → rien a publier
- **agent_15** (Fact-checking) — pas de verification → risques juridiques/credibilite
- **agent_25** (Critique Qualite) — pas de score → pas de decision de publication

## Agents non-critiques (pipeline continuable)

Ces agents enrichissent mais ne bloquent pas :
- agent_02 (Persona), agent_05 (Offre), agent_06 (Differenciation)
- agent_10 (SEO), agent_11 (AEO), agent_12 (GEO), agent_13 (EEAT)
- agent_16-24, agent_26

## Verifications specifiques de coherence

### Intention vs Type de page
- `intention == "transactionnelle"` + `type_page == "news"` → **avertissement** (une news n'est pas transactionnelle)
- `intention == "informative"` + `type_page == "landing"` → **avertissement** (une landing n'est pas informative)
- `intention == "locale"` + `type_page == "article"` → **avertissement** (un service local merite une page service_local)
- `intention == "comparative"` + `type_page == "article"` → **avertissement** (preferer comparatif ou pilier)

### Secteur reglemente
- Secteur dans {droit, finance, sante, rh, donnees_personnelles, cybersecurite, enfants, vehicules, produits_reglementes} + Agent 14 (Conformite) non execute → **avertissement fort**
- Secteur sante + absence d'avertissement medical → **blocage**

### EEAT — Sujets YMYL (Your Money Your Life)
- Mots-cles contenant {assurance, credit, pret, cancer, traitement, diagnostic, avocat, juridique, fiscal, impot, comptable} + Agent 13 (EEAT) non execute → **avertissement fort**

### Qualite du contenu
- `score_total < seuil_publication` → **blocage** (ne pas publier un contenu sous le seuil)
- `lisibilite < 3/10` → **avertissement** (contenu potentiellement illisible)
- `absence_erreurs < 3/6` → **avertissement** (trop d'erreurs factuelles detectees)

## Dependances entre agents

| Agent cible | Donnees requises | Agent producteur | Si producteur skip |
|-------------|-----------------|------------------|-------------------|
| agent_02 | fiche_entreprise | agent_01 | Bloquer (agent_02 ne peut pas travailler sans entreprise) |
| agent_05 | fiche_entreprise, personne, intention | agent_01, agent_02, agent_04 | Avertissement si agent_02 manquant |
| agent_07 | intention, type_page | agent_04 | Bloquer (pas de template sans type de page) |
| agent_09 | fiche_entreprise, personne, template, intention, offre, diff | agent_01, 02, 04, 05, 06, 07 | Avertissement si offre/diff manquantes |
| agent_10 | brouillon_html | agent_09 | Bloquer (pas de SEO sans contenu) |
| agent_15 | brouillon_html | agent_09 | Bloquer (pas de fact-checking sans contenu) |

## Validation Pydantic

Chaque agent a un modele de sortie. Verifier systematiquement :
- Agent 01 → FicheEntreprise (nom, secteur, positionnement obligatoires)
- Agent 03 → SerpData (top10 obligatoire)
- Agent 04 → IntentTypeData (intention, type_page obligatoires)
- Agent 07 → TemplateData (template_id, structure obligatoires)
- Agent 09 → Brouillon (html obligatoire, word_count > 0)
- Agent 25 → ScoresFinaux (score_total, seuil_atteint obligatoires)

Si la validation Pydantic echoue, l'agent est marque comme `failed` et on applique
les regles de criticite ci-dessus.

## Note d'implementation

Ce fichier decrit le COMPORTEMENT ATTENDU du superviseur. L'implementation reelle
est dans `hermes/core/supervisor.py` et `hermes/core/pipeline_guard.py`.
