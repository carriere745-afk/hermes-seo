# PROMPT 3 — AUTO-AUDIT & CORRECTION

Utilise ce prompt APRÈS avoir reçu le contenu rédigé (Prompt 2).
Il relit, audite, et corrige automatiquement.

---

## TÂCHE

Audite le contenu HTML suivant sur 10 dimensions et applique toutes les corrections nécessaires :

```html
[COLLER LE HTML PRODUIT PAR LE PROMPT 2]
```

## DIMENSIONS D'AUDIT

### 1. SEO technique
- [ ] Title : 50-60 caractères, mot-clé présent
- [ ] Méta description : 150-160 caractères, unique, CTA naturel
- [ ] 1 seul H1, hiérarchie Hn cohérente (pas de saut H2→H4)
- [ ] URLs suggérées : minuscules, tirets, sans stop words

### 2. SEO éditorial
- [ ] Mot-clé principal présent aux endroits stratégiques sans sur-optimisation
- [ ] Synonymes et entités variés (pas de répétition mécanique)
- [ ] Chaque section répond à une intention précise
- [ ] Pas de contenu « remplissage »

### 3. AEO (Answer Engine Optimization)
- [ ] Bloc « En bref » : 100-200 mots, autonome, répond à « de quoi s'agit-il ? »
- [ ] FAQ : 3-8 questions avec réponses 40-80 mots autonomes (si pertinent)
- [ ] Au moins 3 phrases citables hors contexte
- [ ] Questions PAA couvertes (si détectées au Prompt 1)

### 4. GEO (Generative Engine Optimization)
- [ ] Entités nommées présentes et cohérentes
- [ ] Sources citées pour tout chiffre ou prix
- [ ] Au moins 1 définition autonome (50-80 mots) si le sujet s'y prête
- [ ] Blocs extractibles : checklist, tableau, encadré (si pertinent)

### 5. E-E-A-T
- [ ] Aucun superlatif non prouvé
- [ ] Séparation claire faits / opinion / analyse
- [ ] Mentions légales si secteur réglementé (rappel Prompt 0)

### 6. Conversion
- [ ] CTA principal présent et visible
- [ ] CTA cohérent avec l'objectif business (rappel Prompt 0)
- [ ] CTA secondaire proposé si pertinent

### 7. Lisibilité
- [ ] Paragraphes ≤ 150 mots
- [ ] Phrases ≤ 35 mots
- [ ] Niveau de langage adapté au persona (rappel Prompt 0)

### 8. Anti-hallucination
- [ ] Aucun chiffre inventé (vérifier chaque statistique : d'où vient-elle ?)
- [ ] Aucune étude fictive (vérifier chaque « selon X... »)
- [ ] Aucun prix estimé sans source
- [ ] Aucune loi citée sans référence

### 9. Maillage interne
- [ ] 3-5 liens internes suggérés avec ancres descriptives
- [ ] Pages cibles cohérentes avec le sujet

### 10. Différenciation vs Top 3
- [ ] Le contenu apporte-t-il une réelle valeur ajoutée par rapport aux résultats SERP ?
- [ ] Au moins 1 élément que le Top 3 n'a pas (angle, tableau, exemple, FAQ...)

## FORMAT DE SORTIE

### Audit

| Dimension | Score /10 | Conforme | Corrections appliquées |
|----------|----------|---------|----------------------|
| SEO technique | | ✅/❌ | |
| SEO éditorial | | | |
| AEO | | | |
| GEO | | | |
| E-E-A-T | | | |
| Conversion | | | |
| Lisibilité | | | |
| Anti-hallucination | | | |
| Maillage | | | |
| Différenciation | | | |
| **TOTAL** | **/100** | | |

### Points faibles identifiés
1. 
2. 

### Améliorations apportées
1. 
2. 

### Contenu corrigé
```html
[HTML CORRIGÉ]
```

---

**INSTRUCTION POUR CLAUDE :** Si un critère est non conforme, applique TOUJOURS la correction. Ne te contente pas de signaler le problème. Livre un contenu corrigé, publiable immédiatement.
