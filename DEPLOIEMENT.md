# Déployer Hermes SEO sur Streamlit Cloud

Accessible partout, sans rien installer. Gratuit.

## En 5 minutes

### Étape 1 — Créer un compte GitHub

https://github.com — gratuit.

### Étape 2 — Pousser le code sur GitHub

```bash
cd C:\Users\Utilisateur\Desktop\multi-agent-seo
git init
git add .
git commit -m "Hermes SEO v3 — 26 agents"
git branch -M main
git remote add origin https://github.com/VOTRE-USERNAME/hermes-seo.git
git push -u origin main
```

### Étape 3 — Connecter Streamlit Cloud

1. Aller sur https://streamlit.io/cloud
2. Cliquer "Sign in with GitHub"
3. Cliquer "New app"
4. Sélectionner le repo `hermes-seo`
5. Fichier principal : `app.py`
6. Cliquer "Deploy"

Le déploiement est **automatique** à chaque `git push`.

### Étape 4 — Configurer les clés API (optionnel)

Dans l'interface Streamlit Cloud :
- App Settings → Secrets
- Copier-coller le contenu de `.streamlit/secrets.toml`
- Remplir les clés API
- Cliquer "Save"

Le mode essai (dry-run) fonctionne **sans aucune clé API**.
Décochez le mode essai dans l'interface quand les clés sont prêtes.

## Résultat

Votre app est accessible à l'adresse :
```
https://VOTRE-USERNAME-hermes-seo-app-XXXX.streamlit.app
```

Depuis n'importe quel appareil : PC, Mac, tablette, téléphone.

## Mode essai vs Mode production

| Mode | Clés API | Coût | Utilisation |
|------|---------|------|-------------|
| Essai (dry-run) | Aucune | 0€ | Test, démo, prototypage |
| Production | Au moins 1 LLM | ~0.25€/article | Contenu réel |

Le mode essai produit du contenu simulé de qualité — idéal pour tester
la structure et le flux avant d'activer les vraies API.

## Mise à jour

Après chaque modification :
```bash
git add .
git commit -m "Description du changement"
git push
```

Streamlit Cloud redéploie automatiquement en 1-2 minutes.
