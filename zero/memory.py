from __future__ import annotations
import sqlite3, time
from pathlib import Path


class Store:
    def __init__(self, path: str = "data/zero.db") -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, ts REAL, text TEXT, source TEXT);"
            "CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, ts REAL, role TEXT, text TEXT);")
        self._db.commit()

    def remember(self, text: str, source: str = "explicit") -> None:
        self._db.execute("INSERT INTO memories(ts,text,source) VALUES(?,?,?)", (time.time(), text, source))
        self._db.commit()

    def recall(self, query: str, limit: int = 5) -> list[str]:
        # MVP: score by overlap of query words; Plan 2 replaces with embeddings.
        words = [w.lower() for w in query.split() if len(w) > 2]
        rows = self._db.execute("SELECT text FROM memories ORDER BY ts DESC").fetchall()
        scored = []
        for (text,) in rows:
            lt = text.lower()
            scored.append((sum(w in lt for w in words), text))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for s, t in scored if s > 0][:limit]

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
