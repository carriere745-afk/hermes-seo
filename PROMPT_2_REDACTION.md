# PROMPT 2 — RÉDACTION SEO / AEO / GEO

Utilise ce prompt APRÈS avoir reçu le Prompt 0 (contexte) et le Prompt 1 (analyse SERP).

---

## TÂCHE

Rédige une page web complète en HTML sémantique pour le mot-clé : **[MOT-CLÉ]**

Tu as déjà reçu le contexte permanent (Prompt 0) et l'analyse SERP (Prompt 1).
Applique les règles ci-dessous.

---

## RÈGLES DE RÉDACTION

### Structure
- **1 seul H1** contenant le mot-clé principal
- **H2 = sections principales** (adaptées à l'intention SERP observée)
- **H3 = sous-sections** développant les H2
- **Paragraphes ≤ 150 mots**, phrases naturelles

### Longueur
- Ne pas viser un nombre de mots arbitraire
- Adapter la profondeur à ce qui est observé dans la SERP
- Chaque section doit mériter d'être lue
- Couper ce qui n'apporte rien

### Mot-clé principal
- Présent dans : H1, premier paragraphe, meta description, 2-3 H2, conclusion
- **Ne jamais forcer sa répétition.** Privilégier synonymes, entités, variantes naturelles.
- Fréquence naturelle uniquement. Aucune cible de densité.

### Titres H2
- Adapter le style à l'intention : questions pour l'informationnel, affirmations pour le transactionnel
- Inclure des entités et mots-clés secondaires quand c'est naturel
- Pas de H2 génériques (« Introduction », « Conclusion »)

### FAQ
- **Uniquement si elle apporte une réelle valeur ajoutée**
- Ne pas créer de FAQ artificielle pour « remplir »
- Si présente : 3-8 questions, réponses 40-80 mots, autonomes

### Ton et style
- Respecter le Prompt 0 (vouvoiement, vocabulaire client, termes à éviter)
- Pas d'anglicismes non justifiés
- Pas de superlatifs non prouvés (« le meilleur », « révolutionnaire », « unique »)
- Ponctuation française : espace avant `: ; ! ?`

---

## RÈGLES ANTI-HALLUCINATION (IMPÉRATIVES)

Avant d'écrire un chiffre, une statistique, un prix, une date, une loi ou une citation,
vérifier mentalement : « Est-ce que je le sais de source sûre ? »

- ❌ Ne JAMAIS inventer un chiffre (ex: « 85% des clients... »)
- ❌ Ne JAMAIS inventer une étude (ex: « Selon une étude de McKinsey... »)
- ❌ Ne JAMAIS inventer une citation (ex: « Comme le disait Steve Jobs... »)
- ❌ Ne JAMAIS estimer un prix sans source (ex: « Comptez environ 150€... »)
- ❌ Ne JAMAIS citer une loi sans référence vérifiable

Si tu n'as pas la donnée :
- Soit tu ne l'écris pas
- Soit tu la remplaces par une formulation générale vraie (ex: « De nombreux clients constatent... » au lieu de « 85% des clients... »)

---

## BLOCS FORTEMENT EXTRACTIBLES (GEO)

Intégrer quand c'est pertinent (jamais forcer) :
- **Définition encadrée** du concept principal (50-80 mots, autonome)
- **Checklist** étape par étape si la page décrit un processus
- **Tableau comparatif** si la page compare des options
- **Encadré « À retenir »** en fin d'article (3-5 points clés)
- **Phrases autonomes** que les IA peuvent citer sans contexte

---

## FORMAT DE SORTIE

### 1. Fiche SEO
```
Mot-clé principal : [X]
Title SEO (50-60 car.) : 
Méta description (150-160 car.) : 
URL recommandée : 
Intention : [rappel Prompt 1]
Schéma(s) recommandé(s) : 
```

### 2. Contenu HTML
```html
<h1>...</h1>
<section id="en-bref"><h2>En bref</h2>...
<section id="..."><h2>...</h2>...
<section id="faq"><h2>Questions fréquentes</h2>...
<footer><h2>Sources</h2>...
```

### 3. Schéma JSON-LD
```json
{ "@context": "https://schema.org", "@type": "..." }
```

### 4. Plan de maillage interne
| Page cible | Ancre suggérée | Priorité | Position conseillée |
|-----------|---------------|----------|-------------------|
| /x/ | ... | P1 | Après le 2e H2 |

### 5. Images recommandées
| Rôle | Prompt IA suggéré | ALT | Format |
|------|------------------|-----|--------|
| Hero | ... | ... | WebP 1200×630 |

### 6. CTA
- **Principal :** [rappel Prompt 0]
- **Emplacement :** [fin d'article + bouton fixe mobile si pertinent]

---

## AUTO-AUDIT (avant livraison)

Avant de livrer le contenu, vérifie et corrige :

| Critère | ✅/❌ | Correction si ❌ |
|---------|-------|-----------------|
| 1 seul H1 | | |
| Title 50-60 car. | | |
| Méta 150-160 car. | | |
| Mots-clés naturels | | |
| Aucun chiffre inventé | | |
| Aucune source fictive | | |
| Aucun anglicisme | | |
| Vouvoiement cohérent | | |
| Ponctuation FR | | |
| FAQ pertinente (pas forcée) | | |
| Schéma JSON-LD valide | | |
| CTA présent | | |
| Maillage interne proposé | | |
| Sections extractibles (si pertinent) | | |
| Supérieur au Top 3 sur au moins 1 critère | | |

Si une correction est nécessaire, **applique-la avant de livrer**.
