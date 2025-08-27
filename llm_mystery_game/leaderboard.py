import os
import streamlit as st
from dotenv import load_dotenv

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

load_dotenv(".env.local")  # ok if missing; Streamlit Secrets can provide env too

POINTS = {"easy": 20, "medium": 30, "hard": 50}
BONUS_ALL_WINS = 100

def get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value

@st.cache_resource(show_spinner=False)
def get_appwrite() -> tuple[Client, Databases, str, str]:
    endpoint = get_env("APPWRITE_ENDPOINT")
    project_id = get_env("APPWRITE_PROJECT_ID")
    api_key = get_env("APPWRITE_API_KEY")
    database_id = get_env("APPWRITE_DATABASE_ID")
    collection_id = get_env("APPWRITE_COLLECTION_ID")
    client = Client().set_endpoint(endpoint).set_project(project_id).set_key(api_key)
    databases = Databases(client)
    return client, databases, database_id, collection_id

def _blank_entry(team_name: str) -> dict:
    # Match teammate's columns: easy/medium/hard booleans
    return {
        "team_name": team_name,
        "score": 0,
        "easy": False,
        "medium": False,
        "hard": False,
        "bonus_awarded": False,
    }

def submit_level_result(team_name: str, level: str, won: bool) -> dict:
    """
    Idempotent scoring against Appwrite with fields: easy/medium/hard (bools).
    Returns: {status, id, points_added, total_score, won_levels, bonus_awarded}
    """
    assert level in {"easy", "medium", "hard"}
    _, databases, database_id, collection_id = get_appwrite()

    # Find existing doc
    res = databases.list_documents(
        database_id,
        collection_id,
        [Query.equal("team_name", team_name), Query.limit(1)],
    )

    if int(res.get("total", 0)) > 0 and res.get("documents"):
        doc = res["documents"][0]
        doc_id = doc["$id"]
        current = {
            "score": int(doc.get("score", 0)),
            "easy": bool(doc.get("easy", False)),
            "medium": bool(doc.get("medium", False)),
            "hard": bool(doc.get("hard", False)),
            "bonus_awarded": bool(doc.get("bonus_awarded", False)),
        }
    else:
        # Create a new doc with blank state
        blank = _blank_entry(team_name)
        created = databases.create_document(database_id, collection_id, ID.unique(), blank)
        doc_id = created["$id"]
        current = blank

    points_added = 0
    updates: dict = {}

    if won:
        already_won_level = bool(current.get(level, False))
        if not already_won_level:
            # First time winning this level -> add points & set flag
            points_added += POINTS[level]
            updates[level] = True
            updates["score"] = int(current["score"]) + points_added

        # Evaluate bonus AFTER potentially setting this level's flag
        easy_done = updates.get("easy", current.get("easy", False))
        med_done = updates.get("medium", current.get("medium", False))
        hard_done = updates.get("hard", current.get("hard", False))
        bonus_done = updates.get("bonus_awarded", current.get("bonus_awarded", False))

        if easy_done and med_done and hard_done and not bonus_done:
            points_added += BONUS_ALL_WINS
            updates["bonus_awarded"] = True
            updates["score"] = int(updates.get("score", current["score"])) + BONUS_ALL_WINS

    if updates:
        updated = databases.update_document(database_id, collection_id, doc_id, updates)
        total_score = int(updated.get("score", current["score"]))
        won_levels = [lvl for lvl in ["easy", "medium", "hard"]
                      if updated.get(lvl, current.get(lvl, False))]
        bonus = bool(updated.get("bonus_awarded", current.get("bonus_awarded", False)))
        return {
            "status": "updated",
            "id": doc_id,
            "points_added": points_added,
            "total_score": total_score,
            "won_levels": won_levels,
            "bonus_awarded": bonus,
        }
    else:
        won_levels = [lvl for lvl in ["easy", "medium", "hard"] if current.get(lvl, False)]
        return {
            "status": "noop",
            "id": doc_id,
            "points_added": 0,
            "total_score": int(current["score"]),
            "won_levels": won_levels,
            "bonus_awarded": bool(current.get("bonus_awarded", False)),
        }
