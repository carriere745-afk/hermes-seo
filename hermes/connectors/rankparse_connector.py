"""Connecteur RankParse — Domain Authority, backlinks, link intersect.

RankParse utilise Common Crawl (mise a jour trimestrielle) pour fournir
des metriques de domaine et backlinks a prix tres bas (~$0.009/credit).
Pay-as-you-go, pas d'abonnement, credits sans expiration.

API : GET avec header X-API-Key
Docs : https://rankparse.com/docs
"""

import logging
from typing import Any, Optional

import httpx

from hermes import config

logger = logging.getLogger("hermes.rankparse")


class RankParseConnector:
    """Client RankParse API v1."""

    BASE_URL = "https://api.rankparse.com/v1"

    def __init__(self):
        self._api_key = self._get_env("RANKPARSE_API_KEY")

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and not self._api_key.startswith("rp_test"))

    def _get_env(self, key: str) -> str:
        try:
            return str(config._cfg._resolve(key))
        except Exception:
            return ""

    async def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """GET generique vers RankParse."""
        if not self.is_configured:
            return {"error": "RankParse non configure"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.BASE_URL}/{endpoint.lstrip('/')}",
                headers={"X-API-Key": self._api_key},
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_domain_authority(self, domain: str) -> dict:
        """Recupere le Domain Authority (0-100) + metriques backlinks.

        Returns: {da, backlinks, referring_domains, rank}
        """
        try:
            data = await self._get("domain-authority", {"domain": domain})
            return {
                "da": data.get("domain_authority", data.get("da", 0)),
                "backlinks": data.get("backlinks", data.get("total_backlinks", 0)),
                "referring_domains": data.get("referring_domains", data.get("ref_domains", 0)),
                "rank": data.get("rank", 0),
            }
        except Exception as e:
            logger.warning(f"RankParse DA failed for {domain}: {e}")
            return {}

    async def batch_domain_authority(self, domains: list[str]) -> dict[str, dict]:
        """DA pour plusieurs domaines en un appel (max 50).

        Returns: {domain: {da, backlinks, referring_domains}}
        """
        try:
            data = await self._get("batch/domain-authority", {"domains": ",".join(domains[:50])})
            result = {}
            for item in data.get("results", data.get("data", [])):
                dom = item.get("domain", "")
                result[dom] = {
                    "da": item.get("domain_authority", item.get("da", 0)),
                    "backlinks": item.get("backlinks", item.get("total_backlinks", 0)),
                    "referring_domains": item.get("referring_domains", item.get("ref_domains", 0)),
                }
            return result
        except Exception as e:
            logger.warning(f"RankParse batch DA failed: {e}")
            return {}

    def interpret_da(self, da: int) -> str:
        """Interprete un score DA en niveau de difficulte."""
        if da >= 80: return "Tres autoritaire — quasi impossible sans backlinks massifs"
        if da >= 60: return "Autoritaire — necessite backlinks + excellent contenu"
        if da >= 40: return "Moyen — atteignable avec un bon contenu et quelques backlinks"
        if da >= 20: return "Faible — atteignable avec un contenu de qualite"
        return "Tres faible — facile a depasser"

    def feasibility_score(self, site_da: int, avg_top10_da: int) -> dict:
        """Calcule un score de faisabilite SEO (0-100)."""
        if avg_top10_da == 0:
            return {"score": 50, "label": "Inconnu", "reco": "Donnees insuffisantes"}

        ratio = site_da / max(1, avg_top10_da)

        if ratio >= 2.0:
            score = 95
            label = "Tres favorable"
            reco = "Votre site domine en autorite. Contenu de qualite + SEO on-page suffisent."
        elif ratio >= 1.2:
            score = 80
            label = "Favorable"
            reco = "Bon ratio d'autorite. Un contenu superieur a la moyenne du top 10 suffit."
        elif ratio >= 0.8:
            score = 65
            label = "Equilibre"
            reco = "Autorite comparable. Contenu excellent + optimisation SEO/AEO/GEO recommandes."
        elif ratio >= 0.4:
            score = 40
            label = "Defavorable"
            reco = f"Autorite 2-3x inferieure. Necessite backlinks (DA 40+) + contenu premium pour compenser."
        elif ratio >= 0.2:
            score = 20
            label = "Tres defavorable"
            reco = f"Autorite 5x inferieure. Priorite backlinks (5-10 liens DA 50+). Contenu seul insuffisant."
        else:
            score = 5
            label = "Quasi impossible"
            reco = f"Autorite {int(avg_top10_da/site_da)}x superieure. Reorientation strategique ou campagne backlinks massive necessaire."

        return {"score": score, "label": label, "reco": reco, "ratio": round(ratio, 2)}


# Singleton
rankparse = RankParseConnector()
