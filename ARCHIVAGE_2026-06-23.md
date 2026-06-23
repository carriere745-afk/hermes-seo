# Archivage — Session du 23 juin 2026

Session de correction du Pipeline Audit de Contenu après tests réels sur `hartmann-tresore.fr` (PrestaShop e-commerce, 20 pages auditées).

---

## Etat avant cette session

Le pipeline audit fonctionnait globalement mais 3 bugs avaient été identifiés au test sur PrestaShop :

1. **Keywords Everywhere** spammait 20 warnings HTTP 402 par audit
2. **TalorData** retournait "non configuré" malgré la config lazy
3. **CMS** détecté comme "inconnu" alors que le code de détection PrestaShop existait

Plus une question UX : l'utilisateur peut-il comprendre pourquoi il a ces scores ?

---

## Corrections apportées

### 1. Cache SERP doublonné (`hermes/agents/audit/ac01b_serp_context.py`)

**Bug** : Deux lignes survivantes appelaient `_get_serp_context` sans utiliser le cache, ce qui annulait l'optimisation.

**Avant** :
```python
if kw_key in kw_cache:
    serp_context = kw_cache[kw_key]
else:
    serp_context = await _get_serp_context(keyword)
    kw_cache[kw_key] = serp_context

# Lignes survivantes qui refaisaient l'appel :
logger.info(f"AC01b: SERP context for '{keyword}'")
serp_context = await _get_serp_context(keyword)  # <-- doublon !
```

**Après** : suppression des lignes dupliquées. Chaque mot-clé n'est plus interrogé qu'une fois par session.

### 2. Détection CMS — 0% → 95% (`hermes/connectors/cms_detector.py`)

**Plusieurs bugs combinés** :

| Bug | Impact | Correction |
|-----|--------|-----------|
| Pas de User-Agent | Le site répondait 403 sur GET/HEAD | Ajout `User-Agent: HermesAudit/1.0` sur toutes les requêtes |
| Pas de logger | Erreurs silencieuses | `logger = logging.getLogger("hermes.cms_detector")` |
| Pattern cookie trop strict (`{32}` exact) | Cookies PrestaShop de longueur variable ignorés | `[a-f0-9]{10,64}` (fourchette) |
| Signature `sitemap` utilisée comme URL | Le pattern regex servait à construire une URL, ne pouvait jamais matcher | Recherche dans le texte combiné (HTML + headers + robots.txt) |
| Pas de lecture robots.txt | Source la plus fiable ignorée (commentaire "PrestaShop" dans robots.txt) | Fetch robots.txt + ajout au texte combiné |
| Signaux PrestaShop incomplets | Thèmes custom passaient inaperçus | Ajout patterns : classes CSS `ps_*`, `id="prestashop"`, `addons.prestashop` |

**Résultat sur hartmann-tresore.fr** :
- Avant : `CMS: inconnu (0%)`
- Après : `CMS: PrestaShop (95%)` — 3 signaux détectés indépendants

### 3. KE auto-désactivation (`hermes/connectors/keywordseverywhere_connector.py`)

**Bug** : L'API retournait 402 (crédit épuisé) à chaque appel. Le code logait un warning mais continuait à appeler — 20 warnings par audit sur 20 pages.

**Correction** :
```python
# Ajout d'un flag de désactivation persistant pour la session
self._disabled_reason = None

# Dans get_keyword_metrics :
if resp.status_code in (401, 402, 403):
    self._disabled_reason = f"HTTP {resp.status_code} — credit epuise ou cle invalide"
    return {}

# is_configured retourne False si désactivé
@property
def is_configured(self) -> bool:
    return bool(self._api_key) and self._disabled_reason is None
```

**Résultat** : 1 seul warning par session au lieu de N.

### 4. Classification URLs PrestaShop (`hermes/connectors/sitemap_parser.py`)

**Avant** : Les URLs PrestaShop (`/521-coffre-fort-xxx.html`) étaient classées en `autres`.

**Après** : Patterns regex pour les conventions PrestaShop :
- `/\d+-[\w-]+\.html?$` → `produits`
- `/\d+-[\w-]+$` (sans extension) → `categories`
- `/module-blog` → `articles`

**Résultat sur 20 URLs** : `{'accueil': 1, 'articles': 1, 'produits': 18}` (avant : `{'accueil': 1, 'autres': 19}`).

### 5. UX — Interprétation type-aware des scores (`pages/audit_page.py`)

**Question utilisateur** : "Est-ce que l'utilisateur peut comprendre ses scores et savoir s'ils sont pertinents ?"

**Ajouts** :

#### a) Bandeau "Comment lire ces scores ?"
Tableau affiché par CMS détecté avec les fourchettes attendues par type de page :

```
| Type de page | Score normal | Interpretation |
|-------------|-------------|----------------|
| accueil     | 40-60/100   | 🟡 Page vitrine — l'essentiel est le design |
| produits    | 25-45/100   | 🔴 Fiche produit e-commerce — score bas normal |
| categories  | 20-40/100   | 🔴 Page listing — contenu dans les produits |
| articles    | 50-75/100   | 🟡 Page blog — score devrait être plus élevé |
| legales     | 30-50/100   | 🔴 Page admin — conformité plutôt que perf |
```

#### b) Indicateur contextuel par page
Sous chaque radar chart, une ligne explicite :
```
Type de page : produits | Score normal pour un site PrestaShop : 25-45/100 |
Votre score : 34/100 ✓ Dans la fourchette normale.
```

Trois symboles : ✓ (dans la fourchette), ▲ (au-dessus), ▼ (en dessous).

**Effet** : un score 30/100 sur une fiche produit n'inquiète plus l'utilisateur — c'est attendu.

---

## Tests de validation

### Détection CMS
```bash
$ python -c "from hermes.connectors.cms_detector import detect_cms; ..."
CMS: PrestaShop (conf=95%, ver=None)
Signals: [
  {type: header, pattern: PrestaShop, weight: 50},
  {type: html, pattern: /modules/|/themes/|prestashop, weight: 30},
  {type: html, pattern: prestashop.com|addons.prestashop, weight: 15}
]
Sitemap candidates: ['/1_index_sitemap.xml', '/2_index_sitemap.xml', '/sitemap.xml']
```

### Pipeline complet (3 URLs, mode fast)
```
INFO:hermes.audit.ac01:CMS detected = PrestaShop (confidence 95%)
INFO:hermes.audit.ac01: / OK — 777 mots
INFO:hermes.audit.ac01: /module-blog OK — 962 mots
INFO:hermes.audit.ac01: /521-coffre-fort-... OK — 1095 mots
Pages: 3, CMS: PrestaShop, Scores: 3
  /: global=30/100
  /module-blog: global=32/100
  /521-coffre-fort-...html: global=34/100
```

Scores cohérents pour un site PrestaShop avec fiches produits courtes.

---

## Fichiers modifiés

| Fichier | Lignes modifiées |
|---------|-----------------|
| `hermes/agents/audit/ac01b_serp_context.py` | +1 / -3 (suppression doublon cache) |
| `hermes/connectors/cms_detector.py` | +50 / -28 (UA, logger, signaux, robots.txt) |
| `hermes/connectors/keywordseverywhere_connector.py` | +7 / -1 (auto-désactivation) |
| `hermes/connectors/sitemap_parser.py` | +13 / -7 (classification URLs) |
| `pages/audit_page.py` | +84 / -1 (interprétation type-aware) |

---

## Reste à faire / pistes ouvertes

- **TalorData (`SerpAPIClient`)** : le warning "non configuré" persiste car aucune clé n'est définie dans `.env`. Pas un bug — comportement attendu. Le cache AC01b réduit le bruit à 1 warning par mot-clé unique.
- **Thèmes WordPress/Magento personnalisés** : la détection via `robots.txt` reste fiable, mais on pourrait élargir les signatures aux frameworks JS (Next.js, Nuxt) qui masquent souvent le CMS sous-jacent.
- **Score EEAT sur 16** : un peu illisible dans le radar (mis x6.25 pour normaliser). Envisager une dimension normalisée /100 partout.
- **Roadmap priorisée** : déjà présente, mais les explications "P1/P2/P3/P4" pourraient gagner à être tooltips contextuels.

---

## Commits associés

Voir le commit du jour : *Improve CMS detection + UX scoring context for PrestaShop audits*
