import os
import streamlit as st
from dotenv import load_dotenv

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

load_dotenv(".env.local")  # harmless if missing; env vars can also come from Streamlit Secrets

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
    return {
        "team_name": team_name,
        "score": 0,
        # new fields to prevent duplicate scoring per level across sessions:
        "won_easy": False,
        "won_medium": False,
        "won_hard": False,
        "bonus_awarded": False,
    }

def submit_level_result(team_name: str, level: str, won: bool) -> dict:
    """
    Idempotent scoring:
      - If won is False: returns doc unchanged.
      - If won is True and this level was *not* yet won: add that level's points.
      - If this completes all three levels (won_* all True) and bonus not awarded: add +100 once.
      - If level already won: adds 0.
    Returns {status, id, points_added, total_score, won_levels, bonus_awarded}
    """
    assert level in {"easy", "medium", "hard"}
    _, databases, database_id, collection_id = get_appwrite()

    # 1) Find existing doc (by team_name)
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
            "won_easy": bool(doc.get("won_easy", False)),
            "won_medium": bool(doc.get("won_medium", False)),
            "won_hard": bool(doc.get("won_hard", False)),
            "bonus_awarded": bool(doc.get("bonus_awarded", False)),
        }
    else:
        # create a new doc with blank state
        blank = _blank_entry(team_name)
        created = databases.create_document(
            database_id, collection_id, ID.unique(), blank
        )
        doc_id = created["$id"]
        current = blank

    points_added = 0
    updates: dict = {}

    if won:
        level_flag = f"won_{level}"
        already_won_level = bool(current.get(level_flag, False))

        if not already_won_level:
            # first time winning this level -> add points & set flag
            points_added += POINTS[level]
            updates[level_flag] = True
            updates["score"] = int(current["score"]) + points_added
        else:
            # level already scored previously -> no additional points
            pass

        # Evaluate bonus AFTER potentially setting this level's flag
        won_easy = updates.get("won_easy", current.get("won_easy", False))
        won_medium = updates.get("won_medium", current.get("won_medium", False))
        won_hard = updates.get("won_hard", current.get("won_hard", False))
        bonus_awarded = updates.get("bonus_awarded", current.get("bonus_awarded", False))

        if won_easy and won_medium and won_hard and not bonus_awarded:
            points_added += BONUS_ALL_WINS
            updates["bonus_awarded"] = True
            updates["score"] = int(updates.get("score", current["score"])) + BONUS_ALL_WINS

    if updates:
        updated = databases.update_document(database_id, collection_id, doc_id, updates)
        total_score = int(updated.get("score", current["score"]))
        won_levels = [
            lvl for lvl in ["easy", "medium", "hard"]
            if updated.get(f"won_{lvl}", current.get(f"won_{lvl}", False))
        ]
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
        # nothing changed (e.g., won=False or level already counted)
        won_levels = [
            lvl for lvl in ["easy", "medium", "hard"]
            if current.get(f"won_{lvl}", False)
        ]
        return {
            "status": "noop",
            "id": doc_id,
            "points_added": 0,
            "total_score": int(current["score"]),
            "won_levels": won_levels,
            "bonus_awarded": bool(current.get("bonus_awarded", False)),
        }
