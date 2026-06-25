# Hermes SEO — Mission

## Ce qu'Hermes SEO est

Hermes SEO est une **plateforme multi-agent autonome** qui prend en charge l'intégralité de la stratégie SEO/AEO/GEO d'un site web :
- de l'audit (technique, contenu, backlinks, SERP)
- à la stratégie éditoriale (roadmap, opportunités, kill list)
- à la production de contenu (articles SEO optimisés)
- à l'exécution (génération llms.txt, schémas, emails CRM, publication CMS)
- à la maintenance (content decay, Core Updates recovery)
- à l'apprentissage (calibration des prédictions, patterns)

Le tout via 8 pipelines coordonnés, ~110 agents, avec confidence scoring et decision trace explicable.

## À qui c'est destiné

- **TPE/PME** qui n'ont pas les moyens d'une équipe SEO interne ou d'une agence à 3000€/mois
- **Agences SEO** qui veulent automatiser leur diagnostic et leur production de contenu
- **Sites e-commerce/SaaS/locaux** qui veulent un suivi continu sans dépendre de Semrush/Ahrefs

## Ce qu'il doit faire (et qu'il fait mal ou pas)

### ✅ Fait bien
- Audit technique 12 dimensions (P3)
- Audit de contenu 7 dimensions (P2)
- Suivi des positions GSC + DataForSEO (P4)
- Stratégie éditoriale avec Confidence Score (P5)
- Audit backlinks + CRM (P6)
- Génération de contenu structuré (P1)

### ❌ Fait mal aujourd'hui (à corriger)
- **Ne contextualise pas les mots-clés** — il prend "nano banana" pour un fruit
- **Recommandations P5 polluées** — propose "accompagnement OpenAI" pour un site local
- **Ancres hardcodées Tours** — alors que le site n'est ni local ni à Tours
- **Pas de génération sitemap.xml / robots.txt** — alors que llms.txt OUI
- **Disclaimers présents mais pas mis en valeur dans le rapport client**
- **Section "Prioritaires P0-P1" montre des P2** — incohérence d'affichage
- **Rapport de comparaison en anglais** — incompréhensible pour un client français

### ❌ Le bug racine
**Hermes ne sait pas ce que représente un mot-clé.** Il prend les mots à la lettre.  
- "nano banana" → fruit (au lieu du modèle d'IA Google Gemini)
- "Tours" hardcodé partout pour n'importe quel site
- Aucune recherche web pour valider la sémantique d'un mot-clé

**Le fix structurel** : avant toute génération de contenu, Hermes doit faire une recherche web sur le mot-clé pour comprendre ce que c'est. C'est ce que ChatGPT et Perplexity font naturellement. C'est ce que P1 agent_03 (Analyse SERP) DEVRAIT faire mais ne fait pas en production parce que TalorData/DataForSEO ne sont pas configurés sur les bons endpoints.

## Engagement de qualité

Un rapport Hermes SEO doit être :
1. **Vrai** — les données affichées sont exactes, ou explicitement marquées comme estimées
2. **Pertinent** — le contenu correspond au site analysé, pas à un mock générique
3. **Actionnable** — chaque recommandation a un cout, un délai, une priorité, une action concrète
4. **Compréhensible** — en français, sans jargon technique, avec disclaimers
5. **Honnête** — sur les limites (GSC manquant, mots-clés non contextualisés)
