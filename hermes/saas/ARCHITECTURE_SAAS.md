# Hermes SEO SaaS — Architecture Document

## Modele Economique

```
┌──────────────────────────────────────────────────────────────┐
│                    HERMES SEO SAAS                            │
│                                                               │
│  OUTILS GRATUITS (freemium)    ABONNEMENT PRO (paie)         │
│  ┌────────────────────────┐   ┌──────────────────────────┐   │
│  │ 12+ outils SEO gratuits│   │ 8 pipelines SEO/AEO/GEO   │   │
│  │ Sans inscription       │   │ 109+ agents               │   │
│  │ Limites volontaires    │   │ Audits illimites          │   │
│  │ → Lead generation      │   │ Rapports PDF/HTML/JSON    │   │
│  │ → Capture email        │   │ CRM netlinking            │   │
│  └────────────────────────┘   │ Support prioritaire       │   │
│                                └──────────────────────────┘   │
│  BLOG WORDPRESS (SEO)        PRIX                           │
│  ┌────────────────────────┐   ┌──────────────────────────┐   │
│  │ Articles SEO/AEO/GEO   │   │ Essai 7j gratuit           │   │
│  │ Genere par P1           │   │ Starter: 29 euros/mois     │   │
│  │ Guides, etudes de cas  │   │ Pro: 79 euros/mois         │   │
│  │ Actualites Google       │   │ Agency: 199 euros/mois    │   │
│  └────────────────────────┘   └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Stack Technique SaaS

| Composant | Technologie | Note |
|-----------|------------|------|
| Frontend | Streamlit (Python) | Page unique, pas de React/Next.js |
| Backend | Python 3.12 | Hermes SEO core |
| Base de donnees | SQLite (4 bases, 24 tables) | Suffisant pour <1000 utilisateurs |
| Paiement | Stripe Checkout | Integration via stripe.com |
| Emails | Resend / SendGrid | Emails transactionnels |
| Blog | WordPress | Sur /blog, contenu genere par P1 |
| Domaines | Nom de domaine principal + sous-domaine app | Ex: hermes-seo.fr + app.hermes-seo.fr |
| Hebergement | VPS (Hetzner/OVH) ou Streamlit Cloud | Docker ready |

## Structure des Pages

```
hermes-seo.fr
├── /                           Landing page (WordPress)
├── /outils-seo/                Outils SEO gratuits (Streamlit)
├── /blog/                      Blog SEO (WordPress)
├── /tarifs/                    Page de prix (WordPress)
├── /contact/                   Contact (WordPress)
├── /app/                       Dashboard SaaS (Streamlit, auth required)
│   ├── /app/projet/{id}        Projet client
│   ├── /app/audit/             Audit SEO
│   └── /app/rapports/          Rapports
└── /api/                       API REST (optionnel)
```

## Plan Tarifaire

| Fonctionnalite | Starter (29euros/m) | Pro (79euros/m) | Agency (199euros/m) |
|---------------|---------------------|-----------------|---------------------|
| Sites/projets | 1 | 5 | 25 |
| Pipelines | P2, P3, P4 | P1-P6 | P1-P8 |
| Articles/mois | 5 | 20 | 100 |
| Audits backlinks | 1 | 5 | 25 |
| CRM netlinking | ❌ | ✅ | ✅ |
| LLM | Haiku (standard) | Haiku + Sonnet | Haiku + Sonnet + Opus |
| Rapports PDF | ❌ | ✅ | ✅ |
| Support | Email | Email + Chat | Prioritaire |
| API | ❌ | ❌ | ✅ |

## Authentification & Paiement

```python
# Flow utilisateur:
# 1. Utilisateur cree un compte (email + password)
# 2. Essai 7 jours gratuit sans CB
# 3. Pour continuer → Stripe Checkout
# 4. Webhook Stripe → activation compte
# 5. Acces dashboard SaaS avec son projet

# Tables:
#   users: id, email, password_hash, plan, stripe_customer_id,
#          trial_ends_at, created_at
#   user_projects: user_id, project_id, role (owner/admin/viewer)
#   subscriptions: id, user_id, plan, status, stripe_subscription_id,
#                 current_period_end, created_at
```

## Free Tools → Lead Capture

Les outils gratuits sont le principal canal d'acquisition.
Chaque outil a une limite volontaire qui pousse a l'inscription:

| Outil | Limite gratuite | Upsell |
|-------|----------------|--------|
| SERP Preview | 10/jour | Analyse SERP complete (P4) |
| Word Counter | Texte < 5000 mots | Analyse editoriale (P2) |
| Heading Analyzer | 1 page | Audit complet (P2 + P3) |
| Schema Generator | FAQ/Article seulement | Tous les schemas + validation |
| Meta Analyzer | 3/jour | Audit on-page complet |
| Quick SEO Score | 5/jour | Score complet 7 dimensions |
| Keyword Density | 1 mot-cle | Analyse semantique complete |
| robots.txt Gen | Gratuit illimite | — (lead magnet) |

## WordPress Integration

Le blog est auto-alimente par P1:
1. P5 genere la roadmap editoriale
2. P1 redige l'article (Claude Sonnet)
3. P7 M06 publie sur WordPress via XML-RPC
4. P7 M06 notifie IndexNow + soumet sitemap

Les outils gratuits sont integres en WordPress via shortcode:
```php
[hermes_tool name="serp_preview"]
```

## Deploiement

```bash
# Option 1: Docker (recommandee)
docker-compose up -d

# Option 2: VPS direct
bash deploy.sh vps

# Option 3: Streamlit Cloud (gratuit)
# Push to GitHub → connect Streamlit Cloud
```

## Prochaines Etapes

1. [ ] Configurer nom de domaine + DNS
2. [ ] Installer WordPress sur le domaine principal
3. [ ] Deployer Streamlit sur app.domaine.com
4. [ ] Configurer Stripe (API keys + webhooks)
5. [ ] Creer les pages WordPress (landing, tarifs, blog)
6. [ ] Integrer les outils gratuits en shortcode WordPress
7. [ ] Configurer email (Resend/SendGrid)
8. [ ] Lancer le blog avec 10 articles generes par P1
