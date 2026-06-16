---
agent: agent_00
name: Superviseur central
version: v1
date: 2026-06-16
role: Verifier l'integrite du pipeline avant chaque transition. Ne fait pas d'appel LLM.
expected_input: SessionState complete
expected_output: SupervisorVerdict (valid, blocked_reasons, warnings, next_agent_id, next_action)
model_recommended: none
temperature: N/A
max_tokens: N/A
---

# Agent 00 — Superviseur central

Tu es le garde-fou du pipeline Hermes SEO. Tu ne rediges pas, tu n'analyses pas
— tu verifies. Ton role est d'empecher qu'une donnee invalide ou incoherente
ne se propage dans la chaine.

## Principe

Avant chaque transition entre agents, tu verifies :

1. **Mot-cle present** — un pipeline sans mot-cle n'a pas de raison d'etre
2. **Etat de la session** — une session en echec ne doit pas continuer
3. **Sortie de l'agent precedent** — si l'agent a termine, sa sortie doit
   etre validee contre son modele Pydantic
4. **Dependances satisfaites** — les donnees dont l'agent suivant a besoin
   doivent exister (sauf si l'agent qui les produit a ete volontairement ignore)
5. **Coherence inter-champs** — pas d'intention transactionnelle sur un template
   news, pas de secteur reglemente sans conformite

## Regles de decision

| Situation | Action |
|-----------|--------|
| Tout est OK | `proceed` → l'agent suivant s'execute |
| Erreur bloquante (donnee manquante, agent echoue) | `block` → le pipeline s'arrete |
| Avertissement non bloquant (petite incoherence) | `proceed` avec warning dans les logs |

## Verifications specifiques

### Validation Pydantic
Chaque agent a un modele de sortie attendu. Tu valides systematiquement :
- Agent 01 → FicheEntreprise (nom, secteur, positionnement obligatoires)
- Agent 03 → SerpData (top10 obligatoire)
- Agent 04 → IntentTypeData (intention, type_page obligatoires)
- Agent 07 → TemplateData (template_id, structure obligatoires)
- Agent 09 → Brouillon (html obligatoire)
- Agent 25 → ScoresFinaux (score_total, seuil_atteint obligatoires)
- ... et tous les autres

### Coherence semantique
- `intention` transactionnelle + `type_page` news → avertissement
- `intention` informative + `type_page` fiche_produit → avertissement
- Secteur reglemente sans Agent 14 (Conformite) → avertissement
- Erreurs factuelles critiques detectees → avertissement
- Score qualite < seuil de publication → avertissement

### Dependances
Chaque agent declare ses dependances. Tu verifies que les sorties des agents
dependants existent. Si un agent a ete ignore (skip_user ou skip_auto), la
dependance est levee mais un avertissement est emis.

## Note

Cet agent n'utilise PAS de LLM. C'est du code Python pur avec validation
Pydantic. Il doit etre rapide, deterministe et sans appel reseau.
