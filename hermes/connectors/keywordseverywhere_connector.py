"""Connecteur Keywords Everywhere — volume, CPC, competition, trend.

Porte depuis saas-seo/lib/keywordseverywhere.js (85 lignes).
API simple avec Bearer token.
"""

import logging
from typing import Any, Optional

import httpx

from hermes import config

logger = logging.getLogger("hermes.keywordseverywhere")

# Map pays → devise
CURRENCY_MAP = {
    "fr": "EUR", "be": "EUR", "ch": "EUR", "de": "EUR", "es": "EUR", "it": "EUR",
    "gb": "GBP", "us": "USD", "ca": "CAD", "au": "AUD", "nz": "NZD",
}


class KeywordsEverywhereConnector:
    """Client Keywords Everywhere API."""

    BASE_URL = "https://api.keywordseverywhere.com/v1"

    def __init__(self):
        self._api_key = self._get_env("KEYWORDS_EVERYWHERE_API_KEY")
        self._disabled_reason = None  # Si non-null, l'API a echoue de facon permanente

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key) and self._disabled_reason is None

    def _get_env(self, key: str) -> str:
        try:
            return str(config._cfg._resolve(key))
        except Exception:
            return ""

    async def get_keyword_metrics(
        self, keywords: list[str], country: str = "fr"
    ) -> dict[str, dict]:
        """Recupere les metriques pour une liste de mots-cles.

        Args:
            keywords: liste de mots-cles (max 20 par appel)
            country: code pays (fr, us, gb...)

        Returns: {"keyword": {vol, cpc, currency, competition, trend}}
        """
        if not self.is_configured:
            logger.warning("Keywords Everywhere non configure")
            return {}

        currency = CURRENCY_MAP.get(country, "EUR")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Keywords Everywhere utilise form-urlencoded
                params = [("kw[]", kw) for kw in keywords[:20]]
                params.append(("country", country))
                params.append(("currency", currency))
                params.append(("dataSource", "gsc"))

                resp = await client.post(
                    f"{self.BASE_URL}/get_keyword_data",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Accept": "application/json",
                    },
                    data=dict(params),
                )
                # Desactiver definitivement si quota epuise ou cle invalide
                if resp.status_code in (401, 402, 403):
                    self._disabled_reason = f"HTTP {resp.status_code} — credit epuise ou cle invalide"
                    logger.warning(f"Keywords Everywhere desactive pour cette session: {self._disabled_reason}")
                    return {}
                resp.raise_for_status()
                data = resp.json()

                result = {}
                for item in data.get("data", []):
                    kw = item.get("keyword", "").lower()
                    result[kw] = {
                        "vol": item.get("vol", 0),
                        "cpc": float(item.get("cpc", {}).get("value", 0)) if isinstance(item.get("cpc"), dict) else 0,
                        "currency": currency,
                        "competition": item.get("competition", 0),
                        "trend": item.get("trend", []),
                    }
                return result
        except Exception as e:
            logger.warning(f"Keywords Everywhere failed: {e}")
            return {}

    def format_vol(self, vol: int) -> str:
        """Formate un volume : 1200 → '1.2k', 45000 → '45k'."""
        if not vol:
            return "0"
        if vol >= 1_000_000:
            return f"{vol / 1_000_000:.1f}".replace(".0", "") + "M"
        if vol >= 1_000:
            return f"{vol / 1_000:.1f}".replace(".0", "") + "k"
        return str(vol)

    @staticmethod
    def comp_label(competition: float) -> str:
        """Label de competition (0-1)."""
        if competition <= 0.33:
            return "Faible"
        if competition <= 0.66:
            return "Moyenne"
        return "Elevee"

    def trend_direction(self, trend: list) -> Optional[int]:
        """Tendance sur 3 derniers mois vs 3 precedents.

        Returns: pourcentage de variation (+ ou -) ou None
        """
        if not trend or len(trend) < 6:
            return None
        try:
            recent = sum(item.get("value", 0) for item in trend[-3:]) / 3
            prev = sum(item.get("value", 0) for item in trend[-6:-3]) / 3
            if prev == 0:
                return None
            return round(((recent - prev) / prev) * 100)
        except (TypeError, ZeroDivisionError):
            return None


# Singleton
keywordseverywhere = KeywordsEverywhereConnector()
