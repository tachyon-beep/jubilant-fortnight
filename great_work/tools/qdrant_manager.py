#!/usr/bin/env python3
"""Qdrant vector database manager for The Great Work.

Adds embedding support via sentence-transformers and upserts vectors.
"""

import json
import logging
import os
from typing import Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

try:
    from sentence_transformers import SentenceTransformer
except Exception as e:  # pragma: no cover - import error surfaced at runtime if used
    SentenceTransformer = None  # type: ignore[assignment]
    _st_import_error = e

logger = logging.getLogger(__name__)

# Default configuration matching .mcp.json
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "great-work-knowledge"
DEFAULT_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


class QdrantManager:
    """Manages Qdrant collections for The Great Work game knowledge."""

    def __init__(
        self,
        url: str = QDRANT_URL,
        collection: str = COLLECTION_NAME,
        model_name: str = DEFAULT_MODEL,
    ):
        """Initialize Qdrant client, embedding model, and collection settings."""
        self.client = QdrantClient(url=url)
        self.collection_name = collection
        if SentenceTransformer is None:
            raise RuntimeError(
                f"sentence-transformers not available: {_st_import_error}. "
                "Install dependencies and retry."
            )
        self.model_name = model_name
        self.model = SentenceTransformer(self.model_name)
        try:
            self.vector_size = int(self.model.get_sentence_embedding_dimension())
        except Exception:
            # Fallback if attribute missing (older versions)
            self.vector_size = len(self.model.encode(["test"], normalize_embeddings=True)[0])

    def setup_collection(self) -> bool:
        """Create or verify the knowledge collection exists."""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                # Create collection with vector configuration
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    ),
                )
                logger.info(f"Created collection: {self.collection_name}")
                return True
            else:
                logger.info(f"Collection already exists: {self.collection_name}")
                return False
        except Exception as e:
            logger.error(f"Failed to setup collection: {e}")
            raise

    def _embed(self, text: str) -> List[float]:
        """Encode text into an embedding vector."""
        vec = self.model.encode(text, normalize_embeddings=True)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)

    def _point(self, pid: int | str, vector: List[float], payload: Dict) -> PointStruct:
        return PointStruct(id=pid, vector=vector, payload=payload)

    def index_game_knowledge(self, items: Optional[List[Dict]] = None) -> None:
        """Index core game knowledge into Qdrant with embeddings."""
        self.setup_collection()
        knowledge_items = items or [
            {
                "id": 1,
                "category": "mechanics",
                "title": "Confidence Wager System",
                "content": "Players declare confidence levels: Suspect (+2/-1), Certain (+5/-7), Stake My Career (+15/-25). High stakes trigger recruitment cooldowns.",
            },
            {
                "id": 2,
                "category": "mechanics",
                "title": "Expedition Types",
                "content": "Three expedition types: Think Tanks (low cost theoretical work), Field Expeditions (medium cost primary sources), Great Projects (high cost new domains).",
            },
            {
                "id": 3,
                "category": "mechanics",
                "title": "Five-Faction Influence",
                "content": "Influence is a 5D vector: Academic, Government, Industry, Religious, Foreign. Soft caps rise with reputation to prevent monopolies.",
            },
            {
                "id": 4,
                "category": "mechanics",
                "title": "Scholar Memory Model",
                "content": "Scholars track Facts (timestamped events) and Feelings (decaying emotions). Major betrayals create permanent Scars that never decay.",
            },
            {
                "id": 5,
                "category": "mechanics",
                "title": "Spectacular Failures",
                "content": "Failed expeditions can yield sideways discoveries. Deep preparation unlocks meaningful alternate progress paths.",
            },
            {
                "id": 6,
                "category": "gameplay",
                "title": "Public-Only Moves",
                "content": "All actions are public and permanent. Every move generates press releases. Secret actions are impossible.",
            },
            {
                "id": 7,
                "category": "gameplay",
                "title": "Time Scale",
                "content": "One real day equals one in-game year. Gazette digests publish twice daily at 13:00 and 21:00.",
            },
            {
                "id": 8,
                "category": "gameplay",
                "title": "Weekly Symposiums",
                "content": "Friday symposiums force public stances on controversial topics. Community votes determine consensus.",
            },
            {
                "id": 9,
                "category": "implementation",
                "title": "Discord Commands",
                "content": "Core commands: /submit_theory, /expedition, /recruit, /status, /wager, /gazette, /export_log, /table_talk. Missing: /conference, /mentor, /gw_admin.",
            },
            {
                "id": 10,
                "category": "implementation",
                "title": "Data Persistence",
                "content": "SQLite stores players, scholars, theories, expeditions, events, press, relationships, offers, followups. Full event sourcing for replay.",
            },
        ]

        points: List[PointStruct] = []
        for item in knowledge_items:
            text = f"{item.get('title', '')}\n\n{item.get('content', '')}"
            vector = self._embed(text)
            points.append(self._point(item["id"], vector, payload=item))

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info("Indexed %d knowledge items into Qdrant", len(points))
        except Exception as e:
            logger.error(f"Failed to index knowledge: {e}")
            raise

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Semantic search over indexed items using vector similarity."""
        try:
            query_vec = self._embed(query)
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vec,
                limit=limit,
            )
            out: List[Dict] = []
            for r in results:
                out.append({
                    "id": getattr(r, "id", None),
                    "score": getattr(r, "score", None),
                    "payload": getattr(r, "payload", None),
                })
            return out
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def store_press(
        self,
        press_id: str | int,
        headline: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Store a press release as an embedded point in Qdrant."""
        self.setup_collection()
        payload = {
            "id": str(press_id),
            "category": "press",
            "title": headline,
            "content": content,
        }
        if metadata:
            payload["metadata"] = metadata
        text = f"{headline}\n\n{content}"
        vector = self._embed(text)
        point = self._point(press_id, vector, payload=payload)
        try:
            self.client.upsert(collection_name=self.collection_name, points=[point])
            logger.info("Stored press %s", press_id)
        except Exception as e:
            logger.error(f"Failed to store press: {e}")
            raise

    def get_stats(self) -> Dict:
        """Get collection statistics."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "collection": self.collection_name,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance,
                "points_count": collection_info.points_count,
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


def main():
    """CLI for managing Qdrant collection."""
    import argparse

    parser = argparse.ArgumentParser(description="Manage Qdrant for The Great Work")
    parser.add_argument("--setup", action="store_true", help="Setup collection")
    parser.add_argument("--index", action="store_true", help="Index game knowledge with embeddings")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="SentenceTransformer model name")
    parser.add_argument("--stats", action="store_true", help="Show collection stats")
    parser.add_argument("--url", default=QDRANT_URL, help="Qdrant URL")
    parser.add_argument("--collection", default=COLLECTION_NAME, help="Collection name")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    manager = QdrantManager(url=args.url, collection=args.collection, model_name=args.model)

    if args.setup:
        manager.setup_collection()

    if args.index:
        manager.index_game_knowledge()

    if args.stats:
        stats = manager.get_stats()
        print(json.dumps(stats, indent=2))

    if not any([args.setup, args.index, args.stats]):
        parser.print_help()


if __name__ == "__main__":
    main()
