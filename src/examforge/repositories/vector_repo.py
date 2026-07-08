"""向量库:Chroma 嵌入式客户端。"""

import uuid
from pathlib import Path
from typing import Optional
import chromadb
from chromadb.api.models.Collection import Collection


_globals: dict = {"client": None, "collection": None, "path": None}


def init_vector_store(data_dir: Path, name: str = "examforge") -> Collection:
    """惰性初始化 Chroma,同一目录复用同一 client。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(data_dir))
    collection = client.get_or_create_collection(name=name)
    _globals["client"] = client
    _globals["collection"] = collection
    _globals["path"] = data_dir
    return collection


def reset_for_tests() -> None:
    _globals["client"] = None
    _globals["collection"] = None
    _globals["path"] = None


class VectorRepo:
    def __init__(self, collection: Collection) -> None:
        self.collection = collection

    def add(self, text: str, embedding: list[float]) -> str:
        vec_id = str(uuid.uuid4())
        self.collection.add(
            ids=[vec_id], documents=[text], embeddings=[embedding]
        )
        return vec_id

    def query(self, embedding: list[float], top_k: int = 5) -> list[tuple[str, float]]:
        res = self.collection.query(
            query_embeddings=[embedding], n_results=top_k
        )
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [(ids[i], float(dists[i])) for i in range(len(ids))]

    def get(self, vec_id: str) -> Optional[str]:
        res = self.collection.get(ids=[vec_id])
        docs = res.get("documents", [])
        return docs[0] if docs else None


def vector_repo() -> VectorRepo:
    coll = _globals["collection"]
    if coll is None:
        raise RuntimeError("init_vector_store() 必须先调用")
    return VectorRepo(coll)