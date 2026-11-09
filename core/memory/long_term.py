"""
Long-Term Memory Engine (Features 7 & 14).
Persistent SQLite storage with TF-IDF semantic vector similarity and keyword search.
Supports dynamic learning of user preferences, facts, and immediate 'forget that' removal.
"""

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.config import settings
from core.logger import logger


class LongTermMemory:
    """Persistent database of learned preferences, facts, and user instructions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.memory_db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes SQLite schema and indexes."""
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL DEFAULT 'general',
                        content TEXT NOT NULL,
                        keywords TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize long-term memory DB: {e}")

    def _extract_keywords(self, text: str) -> str:
        """Extracts meaningful alphanumeric words (>=3 chars) as keyword tokens."""
        tokens = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", text.lower())
        # Deduplicate while preserving order
        seen = set()
        unique = [t for t in tokens if not (t in seen or seen.add(t))]
        return " ".join(unique)

    def store(self, content: str, category: str = "general") -> int:
        """Stores a new fact or preference in long-term memory."""
        cleaned = content.strip()
        if not cleaned:
            return -1

        keywords = self._extract_keywords(cleaned)
        now = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO memories (category, content, keywords, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (category.lower().strip(), cleaned, keywords, now, now),
            )
            conn.commit()
            memory_id = cur.lastrowid
            logger.info(f"Stored long-term memory [id={memory_id}, category={category}]: {cleaned[:50]}")
            return memory_id or -1

    def recall(self, query: str, limit: int = 5, min_score: float = 0.05) -> List[Dict[str, Any]]:
        """
        Recalls the most relevant memories using hybrid TF-IDF cosine similarity
        and keyword matching.
        """
        q = query.strip().lower()
        if not q:
            return []

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, category, content, keywords, created_at FROM memories ORDER BY id DESC")
            rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return []

        # If only 1 memory exists, check keyword overlap
        query_words = set(self._extract_keywords(q).split())

        # Hybrid TF-IDF vector ranking
        corpus = [r["content"] for r in rows]
        try:
            vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            tfidf_matrix = vectorizer.fit_transform(corpus + [query])
            corpus_vectors = tfidf_matrix[:-1]
            query_vector = tfidf_matrix[-1:]
            scores = cosine_similarity(query_vector, corpus_vectors)[0]
        except Exception:
            scores = np.zeros(len(rows))

        scored_memories = []
        for i, row in enumerate(rows):
            tfidf_score = float(scores[i]) if i < len(scores) else 0.0

            # Calculate keyword token overlap score
            mem_words = set(row["keywords"].split())
            overlap = len(query_words.intersection(mem_words))
            keyword_score = min(1.0, overlap * 0.25)

            # Combined hybrid score (60% TF-IDF, 40% keyword overlap)
            final_score = (0.6 * tfidf_score) + (0.4 * keyword_score)

            if final_score >= min_score or (overlap > 0 and final_score > 0):
                row_copy = dict(row)
                row_copy["relevance_score"] = round(final_score, 4)
                scored_memories.append((final_score, row_copy))

        # Sort by relevance descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in scored_memories[:limit]]

    def forget_last(self) -> Optional[Dict[str, Any]]:
        """
        Deletes the most recently added memory entry (e.g. for 'Mike, forget that').
        Returns the deleted memory dictionary, or None if empty.
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, category, content, created_at FROM memories ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None

            deleted = dict(row)
            cur.execute("DELETE FROM memories WHERE id = ?", (deleted["id"],))
            conn.commit()
            logger.info(f"Forgot recent memory [id={deleted['id']}]: {deleted['content']}")
            return deleted

    def forget_matching(self, query: str) -> int:
        """Deletes memories that match a topic or query."""
        recalled = self.recall(query, limit=10, min_score=0.1)
        if not recalled:
            return 0

        ids = [m["id"] for m in recalled]
        placeholders = ",".join("?" for _ in ids)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            count = cur.rowcount
            conn.commit()
            logger.info(f"Forgot {count} memories matching query: {query}")
            return count

    def list_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent memories."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, category, content, created_at FROM memories ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM memories")
            return cur.fetchone()[0]

    def clear_all(self) -> int:
        """Wipes all long-term memories."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM memories")
            count = cur.rowcount
            conn.commit()
            return count


# Global long-term memory instance
long_term_memory = LongTermMemory()
