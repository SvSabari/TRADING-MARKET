"""MongoDB connection and base document model."""
from __future__ import annotations

import copy
import os
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Annotated, Any, Optional
import uuid

from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pymongo import MongoClient
from pymongo.errors import PyMongoError

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env", override=True)
load_dotenv(ROOT_DIR.parent / ".env", override=True)

MONGO_URL = os.environ.get("MONGO_URL", "").strip() or "mongodb://localhost:27017"
DB_NAME = os.environ.get("DB_NAME", "").strip() or "algo_trading_db"
USE_IN_MEMORY_DB = os.environ.get("USE_IN_MEMORY_DB", "false").strip().lower() in {"1", "true", "yes", "on"}


def _matches(doc: dict, query: Optional[dict]) -> bool:
    if not query:
        return True
    for key, expected in query.items():
        value = doc.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and value not in expected["$in"]:
                return False
            if "$ne" in expected and value == expected["$ne"]:
                return False
        elif value != expected:
            return False
    return True


def _project(doc: dict, projection: Optional[dict]) -> dict:
    out = copy.deepcopy(doc)
    if not projection:
        return out
    excludes = {k for k, v in projection.items() if v == 0}
    includes = {k for k, v in projection.items() if v == 1}
    if includes:
        out = {k: copy.deepcopy(v) for k, v in out.items() if k in includes or k == "_id"}
    for key in excludes:
        out.pop(key, None)
    return out


class InMemoryCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs
        self._idx = 0

    def sort(self, key: str, direction: int = 1):
        reverse = direction < 0
        self._docs.sort(key=lambda d: d.get(key) or "", reverse=reverse)
        return self

    def limit(self, count: int):
        self._docs = self._docs[:count]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._docs):
            raise StopAsyncIteration
        item = self._docs[self._idx]
        self._idx += 1
        return copy.deepcopy(item)


class InMemoryCollection:
    def __init__(self):
        self._docs: list[dict] = []

    async def create_index(self, *args, **kwargs):
        return None

    async def insert_one(self, doc: dict):
        new_doc = copy.deepcopy(doc)
        new_doc.setdefault("_id", str(uuid.uuid4()))
        self._docs.append(new_doc)
        return SimpleNamespace(inserted_id=new_doc["_id"])

    async def find_one(self, query: Optional[dict] = None, projection: Optional[dict] = None):
        for doc in self._docs:
            if _matches(doc, query):
                return _project(doc, projection)
        return None

    def find(self, query: Optional[dict] = None, projection: Optional[dict] = None):
        docs = [_project(doc, projection) for doc in self._docs if _matches(doc, query)]
        return InMemoryCursor(docs)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        for doc in self._docs:
            if _matches(doc, query):
                self._apply_update(doc, update)
                return SimpleNamespace(matched_count=1, modified_count=1, upserted_id=None)
        if upsert:
            new_doc = copy.deepcopy(query)
            self._apply_update(new_doc, update)
            new_doc.setdefault("_id", str(uuid.uuid4()))
            self._docs.append(new_doc)
            return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=new_doc["_id"])
        return SimpleNamespace(matched_count=0, modified_count=0, upserted_id=None)

    async def update_many(self, query: dict, update: dict):
        count = 0
        for doc in self._docs:
            if _matches(doc, query):
                self._apply_update(doc, update)
                count += 1
        return SimpleNamespace(matched_count=count, modified_count=count)

    async def delete_one(self, query: dict):
        for idx, doc in enumerate(self._docs):
            if _matches(doc, query):
                del self._docs[idx]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query: dict):
        before = len(self._docs)
        self._docs = [doc for doc in self._docs if not _matches(doc, query)]
        return SimpleNamespace(deleted_count=before - len(self._docs))

    async def count_documents(self, query: Optional[dict] = None):
        return sum(1 for doc in self._docs if _matches(doc, query))

    @staticmethod
    def _apply_update(doc: dict, update: dict) -> None:
        if "$set" in update:
            doc.update(copy.deepcopy(update["$set"]))
        else:
            doc.update(copy.deepcopy(update))


class InMemoryDatabase:
    def __init__(self):
        self._collections: dict[str, InMemoryCollection] = {}

    def __getattr__(self, name: str) -> InMemoryCollection:
        return self._collections.setdefault(name, InMemoryCollection())

    def __getitem__(self, name: str) -> InMemoryCollection:
        return self.__getattr__(name)


if USE_IN_MEMORY_DB:
    db = InMemoryDatabase()
    sync_db = db
else:
    try:
        # Check connection. If this fails, we want it to raise an error rather than silently falling back to memory.
        _sync_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        _sync_client.admin.command("ping")
        sync_db = _sync_client[DB_NAME]
        
        _client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        db = _client[DB_NAME]
    except PyMongoError as e:
        print(f"CRITICAL: Failed to connect to MongoDB at {MONGO_URL}: {e}")
        # We don't fall back to memory silently. That causes data loss/reappearance bugs!
        raise e


def _to_str(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v) if v is not None else v


PyObjectId = Annotated[str, BeforeValidator(_to_str)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


class BaseDocument(BaseModel):
    """Base for Mongo documents. id is stored as str (uuid4 by default)."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="_id")

    def to_mongo(self) -> dict:
        d = self.model_dump(by_alias=True)
        # serialize datetimes
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        if "_id" in doc and not isinstance(doc["_id"], str):
            doc["_id"] = str(doc["_id"])
        return cls(**doc)
