# Outils Open-Source SEO/AEO/GEO — Hermes SEO

Fonctionnalites installees provisoirement pour les futurs pipelines.
Tous les outils sont Python, MIT/Apache/BSD, pip installables.

## Pipeline Redaction — Deja Integres

| Outil | Version | Usage |
|-------|---------|-------|
| textstat | 0.7.13 | Flesch multilingue (40+ langues, support FR natif) |
| yake | 0.7.3 | Extraction mots-cles non supervisee |
| schorg | 0.7.5 | Schema.org Pydantic models |
| json-repair | 0.61.0 | Reparation JSON LLM 3e niveau |
| protego | 0.6.1 | robots.txt parser (Google-compatible) |

## Pipeline Audit Technique — A Installer

```bash
pip install crawlee advertools mcp-seo seokar ultimate-sitemap-parser
```

| Outil | Version | Usage |
|-------|---------|-------|
| crawlee | 1.7.2 | Crawler JS rendering, robots.txt, sitemap |
| advertools | 0.17 | Kit SEO complet (sitemaps, robots, logs, keywords) |
| mcp-seo | 0.3.0 | 18 MCP tools, Lighthouse, Core Web Vitals |
| seokar | 1.0.0 | Analyse on-page, score sante 0-100% |
| ultimate-sitemap-parser | 1.7 | Parser sitemap XML (1M URLs teste) |

## Pipeline SERP & Positions — A Installer

```bash
pip install openserp searchconsole-mcp seo-monster-mcp seo-pilot
```

| Outil | Version | Usage |
|-------|---------|-------|
| openserp | 0.8.3 | SERP self-hosted, multi-engine |
| searchconsole-mcp | latest | GSC analytics, sitemap, URL inspection |
| seo-monster-mcp | 0.1.0 | GSC + GA4 + PSI + Cloudflare (22 tools) |
| seo-pilot | 0.1.0 | GSC auto-fix, scoring, low-hanging fruit |

## Pipeline Maillage & Backlinks — A Installer

```bash
pip install seotools dataseo-mcp
```

| Outil | Version | Usage |
|-------|---------|-------|
| seotools | 0.1.2 | PageRank interne, pages orphelines, liens |
| dataseo-mcp | latest | Ahrefs backlinks gratuit via MCP |

## Pipeline GEO / AEO — A Installer

```bash
pip install geo-optimizer-skill georankpy
```

| Outil | Version | Usage |
|-------|---------|-------|
| geo-optimizer-skill | 4.15 | 47 methodes, 1720 tests, scoring AI readiness |
| georankpy | 0.1.0 | Chunks semantiques, entites, llms.txt |

## Autres Utilitaires

```bash
pip install langchain-hreflang keybert textstat
```

| Outil | Version | Usage |
|-------|---------|-------|
| langchain-hreflang | 0.1.0 | Validation hreflang |
| keybert | latest | Keywords BERT (plus precis que YAKE) |

## Licence

Tous les outils listes sont MIT, Apache 2.0, ou BSD.
Aucune dependance GPL.
