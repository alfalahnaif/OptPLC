from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_DIR = Path("/app/knowledge_base/patterns")
CHROMA_PERSIST_DIR = Path("/app/rag_db")
COLLECTION_NAME = "plc_patterns_v1"


class RAGService:
    def __init__(self) -> None:
        self._collection = None
        self._ready = False

    def _init_collection(self) -> bool:
        if self._ready:
            return True
        try:
            import chromadb
            from chromadb.utils import embedding_functions

            CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
            self._ready = True
            return True
        except Exception as exc:
            logger.error(f"[RAGService] Init failed: {exc}")
            return False

    def seed(self) -> int:
        if not self._init_collection():
            return 0
        if not KNOWLEDGE_BASE_DIR.exists():
            logger.warning(f"[RAGService] Pattern dir not found: {KNOWLEDGE_BASE_DIR}")
            return 0

        docs: list[str] = []
        metas: list[dict[str, str]] = []
        ids: list[str] = []
        for file_path in KNOWLEDGE_BASE_DIR.glob("*.json"):
            try:
                pattern = json.loads(file_path.read_text(encoding="utf-8"))
                doc = (
                    f"Pattern: {pattern['name']}. "
                    f"Domain: {pattern['domain']}. "
                    f"Type: {pattern['pattern_type']}. "
                    f"{pattern['description']} "
                    f"Tags: {', '.join(pattern.get('tags', []))}. "
                    f"Safety: {pattern.get('safety_notes', '')}."
                )
                docs.append(doc)
                metas.append(
                    {
                        "id": pattern["id"],
                        "name": pattern["name"],
                        "domain": pattern["domain"],
                        "pattern_type": pattern["pattern_type"],
                        "safety_level": pattern.get("safety_level", "medium"),
                    }
                )
                ids.append(pattern["id"])
            except Exception as exc:
                logger.warning(f"[RAGService] Skipping {file_path.name}: {exc}")

        if docs:
            # Upsert keeps seeding idempotent across restarts.
            self._collection.upsert(documents=docs, metadatas=metas, ids=ids)
            logger.info(f"[RAGService] Seeded {len(docs)} patterns.")
        return len(docs)

    def retrieve(
        self,
        query: str,
        domain: str = "",
        n_results: int = 3,
    ) -> list[dict]:
        if not self._init_collection():
            return []
        try:
            count = self._collection.count()
            if count == 0:
                return []
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["documents", "metadatas", "distances"],
            )
            retrieved: list[dict] = []
            for index, meta in enumerate(results["metadatas"][0]):
                similarity = round(1 - results["distances"][0][index], 3)
                if similarity < 0.15:
                    continue

                matches = list(KNOWLEDGE_BASE_DIR.glob(f"{meta['id']}*.json"))
                st_snippet = ""
                safety_notes = ""
                common_mistakes: list[str] = []
                applicable_rules: list[str] = []
                if matches:
                    full = json.loads(matches[0].read_text(encoding="utf-8"))
                    st_snippet = full.get("st_snippet", "")
                    safety_notes = full.get("safety_notes", "")
                    common_mistakes = full.get("common_mistakes", [])
                    applicable_rules = full.get("applicable_rules", [])

                retrieved.append(
                    {
                        "id": meta["id"],
                        "name": meta["name"],
                        "domain": meta["domain"],
                        "patternType": meta["pattern_type"],
                        "similarity": similarity,
                        "stSnippet": st_snippet,
                        "safetyNotes": safety_notes,
                        "commonMistakes": common_mistakes,
                        "applicableRules": applicable_rules,
                    }
                )
            logger.info(
                f"[RAGService] Retrieved {len(retrieved)} patterns "
                f"for domain='{domain}' query='{query[:40]}...'"
            )
            return retrieved
        except Exception as exc:
            logger.error(f"[RAGService] Retrieval failed: {exc}")
            return []


_instance: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _instance
    if _instance is None:
        _instance = RAGService()
    return _instance
