from __future__ import annotations
import sqlite3, time
from pathlib import Path


# ---------------------------------------------------------------------------
# Lazy-loaded embedding singleton
# ---------------------------------------------------------------------------

class Embedder:
    """Thin wrapper around sentence-transformers; loaded on first use."""
    _instance: "Embedder | None" = None
    _model = None

    @classmethod
    def get(cls) -> "Embedder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, text: str):
        """Return a float32 numpy vector for *text*."""
        import numpy as np
        self._ensure_model()
        vec = self._model.encode(text, normalize_embeddings=True)
        return np.array(vec, dtype=np.float32)


# ---------------------------------------------------------------------------
# Cosine similarity helper
# ---------------------------------------------------------------------------

def _cosine(a, b) -> float:
    import numpy as np
    # vectors are already L2-normalised by sentence-transformers when
    # normalize_embeddings=True, so dot product == cosine similarity.
    return float(np.dot(a, b))


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class Store:
    def __init__(self, path: str = "data/zero.db") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, ts REAL, text TEXT, source TEXT);"
            "CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, ts REAL, role TEXT, text TEXT);")
        # Migrate: add embedding column if not present yet
        try:
            self._db.execute("ALTER TABLE memories ADD COLUMN embedding BLOB")
            self._db.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

    def remember(self, text: str, source: str = "explicit") -> None:
        import numpy as np
        vec = Embedder.get().encode(text)
        self._db.execute(
            "INSERT INTO memories(ts,text,source,embedding) VALUES(?,?,?,?)",
            (time.time(), text, source, vec.tobytes()))
        self._db.commit()

    def recall(self, query: str, limit: int = 5) -> list[str]:
        """Return up to *limit* memories ranked by cosine similarity to *query*."""
        import numpy as np
        rows = self._db.execute("SELECT text, embedding FROM memories ORDER BY ts DESC").fetchall()
        if not rows:
            return []
        q_vec = Embedder.get().encode(query)
        scored: list[tuple[float, str]] = []
        for text, emb_bytes in rows:
            if emb_bytes is None:
                # Legacy row without embedding: skip for semantic ranking
                continue
            mem_vec = np.frombuffer(emb_bytes, dtype=np.float32)
            score = _cosine(q_vec, mem_vec)
            if score >= 0.25:
                scored.append((score, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:limit]]

    def log_turn(self, role: str, text: str) -> None:
        self._db.execute("INSERT INTO messages(ts,role,text) VALUES(?,?,?)", (time.time(), role, text))
        self._db.commit()

    def recent_turns(self, limit: int = 6) -> list[tuple[str, str]]:
        rows = self._db.execute("SELECT role,text FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return list(reversed(rows))


from claude_agent_sdk import tool, create_sdk_mcp_server

def build_memory_mcp(store: "Store"):
    @tool("remember", "Store a durable fact Ahmad told you", {"fact": str})
    async def remember(args):
        store.remember(args["fact"], source="explicit")
        return {"content": [{"type": "text", "text": f"Noted: {args['fact']}"}]}

    @tool("recall", "Recall facts relevant to a query", {"query": str})
    async def recall(args):
        hits = store.recall(args["query"])
        return {"content": [{"type": "text", "text": "\n".join(hits) or "Nothing relevant remembered."}]}

    return create_sdk_mcp_server(name="memory", version="1.0.0", tools=[remember, recall])
