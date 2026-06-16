"""Interface de mémoire persistante Hermes SEO.

Deux couches :
1. ChromaDB — mémoire vectorielle sémantique (anti-cannibalisation, entités,
   historique éditorial)
2. SQLite — état du pipeline (via LangGraph SqliteSaver)
"""

from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings


class MemoryStore:
    """Mémoire vectorielle ChromaDB pour Hermes SEO.

    Stocke :
    - Les contenus déjà publiés (pour anti-cannibalisation)
    - Les entités nommées extraites
    - L'historique des décisions éditoriales
    """

    def __init__(self, persist_directory: str = "./data/chroma"):
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """Crée les collections si elles n'existent pas."""
        existing = self._client.list_collections()
        existing_names = {c.name for c in existing}

        if "published_content" not in existing_names:
            self._client.create_collection(
                name="published_content",
                metadata={"description": "Contenus publiés pour anti-cannibalisation"},
            )
        if "entities" not in existing_names:
            self._client.create_collection(
                name="entities",
                metadata={"description": "Entités nommées extraites"},
            )
        if "editorial_decisions" not in existing_names:
            self._client.create_collection(
                name="editorial_decisions",
                metadata={"description": "Historique des décisions éditoriales"},
            )

    def _collection(self, name: str):
        return self._client.get_collection(name)

    def add_content(
        self,
        content_id: str,
        text: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Ajoute un contenu publié à la mémoire."""
        coll = self._collection("published_content")
        coll.add(
            documents=[text],
            ids=[content_id],
            metadatas=[metadata or {}],
        )

    def search_similar(
        self,
        query: str,
        n_results: int = 5,
        collection: str = "published_content",
    ) -> dict[str, Any]:
        """Recherche les contenus similaires."""
        coll = self._collection(collection)
        results = coll.query(query_texts=[query], n_results=n_results)
        return results

    def add_entities(
        self,
        doc_id: str,
        entities: list[str],
    ) -> None:
        """Stocke les entités nommées d'un document."""
        if not entities:
            return
        coll = self._collection("entities")
        coll.add(
            documents=entities,
            ids=[f"{doc_id}_{i}" for i in range(len(entities))],
        )

    def get_similar_entities(self, query: str, n: int = 10) -> list[str]:
        """Récupère les entités similaires à une requête."""
        coll = self._collection("entities")
        results = coll.query(query_texts=[query], n_results=n)
        documents = results.get("documents", [[]])
        return documents[0] if documents else []

    def record_decision(
        self,
        session_id: str,
        decision: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Enregistre une décision éditoriale."""
        coll = self._collection("editorial_decisions")
        coll.add(
            documents=[decision],
            ids=[session_id],
            metadatas=[metadata or {}],
        )

    def count_published(self) -> int:
        """Nombre de contenus en mémoire."""
        try:
            coll = self._collection("published_content")
            return coll.count()
        except Exception:
            return 0

    def has_existing_content(self) -> bool:
        """Vérifie si le site a déjà des contenus (utile pour l'Agent 08)."""
        return self.count_published() > 0
