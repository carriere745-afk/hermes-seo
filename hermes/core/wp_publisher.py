"""Publisher WordPress — envoi d'article via REST API.

Portage depuis saas-seo/api/wordpress/publish.
Supporte : brouillon, publie, categories, tags, auteur.
"""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger("hermes.wp_publisher")


class WordPressPublisher:
    """Client WordPress REST API pour publication d'articles."""

    def __init__(
        self,
        site_url: str,
        username: str = "",
        password: str = "",
    ):
        self.site_url = site_url.rstrip("/")
        self.api_url = f"{self.site_url}/wp-json/wp/v2"
        self.username = username
        self.password = password

        auth = ""
        if username and password:
            auth = base64.b64encode(
                f"{username}:{password}".encode()
            ).decode()
        self._auth = f"Basic {auth}" if auth else ""

    async def publish_article(
        self,
        title: str,
        html_content: str,
        meta_title: str = "",
        meta_description: str = "",
        slug: str = "",
        category_ids: Optional[list[int]] = None,
        tag_ids: Optional[list[int]] = None,
        status: str = "draft",
        excerpt: str = "",
        author_id: int = 1,
    ) -> dict:
        """Publie un article sur WordPress.

        Args:
            title: Titre de l'article (H1)
            html_content: Contenu HTML complet
            meta_title: Title SEO (si plugin Yoast/RankMath)
            meta_description: Meta description
            slug: Permalien (genere automatiquement si vide)
            category_ids: Liste d'IDs de categories
            tag_ids: Liste d'IDs de tags
            status: 'draft' (brouillon) ou 'publish' (publie)
            excerpt: Extrait
            author_id: ID de l'auteur

        Returns: {"id": post_id, "url": "...", "status": "..."}
        """
        if not self._auth:
            raise ValueError(
                "Identifiants WordPress requis. Configurez WP_USERNAME et "
                "WP_PASSWORD dans .env ou Streamlit Secrets."
            )

        if not slug:
            slug = _slugify(title)

        payload = {
            "title": title,
            "content": html_content,
            "status": status,
            "slug": slug,
            "excerpt": excerpt or title[:160],
            "author": author_id,
        }

        if category_ids:
            payload["categories"] = category_ids
        if tag_ids:
            payload["tags"] = tag_ids
        if meta_title or meta_description:
            payload["meta"] = {}
            if meta_title:
                payload["meta"]["_yoast_wpseo_title"] = meta_title
            if meta_description:
                payload["meta"]["_yoast_wpseo_metadesc"] = meta_description

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.api_url}/posts",
                json=payload,
                headers={
                    "Authorization": self._auth,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            post_id = data.get("id")
            post_url = data.get("link", f"{self.site_url}/?p={post_id}")

            logger.info(f"Article {post_id} publie sur WordPress: {post_url}")
            return {
                "id": post_id,
                "url": post_url,
                "status": data.get("status", status),
            }

    async def get_categories(self) -> list[dict]:
        """Recupere les categories WordPress."""
        if not self._auth:
            return []
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.api_url}/categories?per_page=100",
                headers={"Authorization": self._auth},
            )
            resp.raise_for_status()
            return [
                {"id": c["id"], "name": c["name"], "slug": c["slug"]}
                for c in resp.json()
            ]

    async def get_tags(self) -> list[dict]:
        """Recupere les tags WordPress."""
        if not self._auth:
            return []
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.api_url}/tags?per_page=100",
                headers={"Authorization": self._auth},
            )
            resp.raise_for_status()
            return [
                {"id": t["id"], "name": t["name"], "slug": t["slug"]}
                for t in resp.json()
            ]

    async def check_connection(self) -> bool:
        """Verifie que la connexion WordPress fonctionne."""
        if not self._auth:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.api_url}/users/me",
                    headers={"Authorization": self._auth},
                )
                return resp.status_code == 200
        except Exception:
            return False


def _slugify(title: str) -> str:
    """Cree un slug WordPress a partir d'un titre."""
    import re

    slug = title.lower().strip()
    # Supprimer accents
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a", "ä": "a",
        "ù": "u", "û": "u", "ü": "u",
        "ô": "o", "ö": "o",
        "î": "i", "ï": "i",
        "ç": "c",
        "œ": "oe", "æ": "ae",
    }
    for accented, plain in replacements.items():
        slug = slug.replace(accented, plain)

    # Supprimer tout sauf lettres, chiffres, tirets
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:200].strip("-")
