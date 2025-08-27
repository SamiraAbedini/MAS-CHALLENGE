import os
import streamlit as st
from dotenv import load_dotenv

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

load_dotenv(".env.local")  # ok if missing; env can also come from Streamlit Secrets

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
    # Match teammate's schema: booleans named easy/medium/hard, plus score
    return {
        "team_name": team_name,
        "score": 0,
        "easy": False,
        "medium": False,
        "hard": False,
        # no bonus_awarded field in schema
    }

def _base_points(easy: bool, medium: bool, hard: bool) -> int:
    return (POINTS["easy"] if easy else 0) + \
           (POINTS["medium"] if medium else 0) + \
           (POINTS["hard"] if hard else 0)

def submit_level_result(team_name: str, level: str, won: bool) -> dict:
    """
    Idempotent scoring using fields: easy/medium/hard (bools). No bonus field required.
    Logic:
      - First time a level is won -> add that level's points and set the flag.
      - If after this all three flags are True, and score < base_points + 100, add +100 once.
      - If level already won or won is False -> points_added = 0.
    Returns: {status, id, points_added, total_score, won_levels, bonus_awarded}
    """
    assert level in {"easy", "medium", "hard"}
    _, databases, database_id, collection_id = get_appwrite()

    # Find existing doc
    res = databases.list_documents(
        database_id, collection_id, [Query.equal("team_name", team_name), Query.limit(1)]
    )

    if int(res.get("total", 0)) > 0 and res.get("documents"):
        doc = res["documents"][0]
        doc_id = doc["$id"]
        current_score = int(doc.get("score", 0))
        easy_flag = bool(doc.get("easy", False))
        medium_flag = bool(doc.get("medium", False))
        hard_flag = bool(doc.get("hard", False))
    else:
        # Create a new doc with blank state
        blank = _blank_entry(team_name)
        created = databases.create_document(database_id, collection_id, ID.unique(), blank)
        doc_id = created["$id"]
        current_score = 0
        easy_flag = False
        medium_flag = False
        hard_flag = False

    points_added = 0
    updates: dict = {}

    if won:
        # Level-specific idempotency
        if level == "easy" and not easy_flag:
            easy_flag = True
            updates["easy"] = True
            points_added += POINTS["easy"]
        elif level == "medium" and not medium_flag:
            medium_flag = True
            updates["medium"] = True
            points_added += POINTS["medium"]
        elif level == "hard" and not hard_flag:
            hard_flag = True
            updates["hard"] = True
            points_added += POINTS["hard"]

        # Provisional score after possible level points
        provisional_score = current_score + points_added

        # Compute base points implied by flags AFTER updates
        base_after = _base_points(easy_flag, medium_flag, hard_flag)

        # If all three flags are now true and bonus hasn't effectively been applied yet, add it now
        bonus_awarded_now = False
        if easy_flag and medium_flag and hard_flag:
            # If provisional_score already >= base_after + BONUS, assume bonus previously granted
            if provisional_score < base_after + BONUS_ALL_WINS:
                points_added += BONUS_ALL_WINS
                bonus_awarded_now = True
                # no schema field to store; score itself reflects the bonus

        if points_added > 0:
            updates["score"] = provisional_score + (BONUS_ALL_WINS if "bonus_awarded_now" in locals() and bonus_awarded_now else 0)

    if updates:
        updated = databases.update_document(database_id, collection_id, doc_id, updates)
        total_score = int(updated.get("score", current_score))
        won_levels = [lvl for lvl, flag in
                      [("easy", updated.get("easy", easy_flag)),
                       ("medium", updated.get("medium", medium_flag)),
                       ("hard", updated.get("hard", hard_flag))] if flag]
        # bonus_awarded (this run) is inferred, not stored
        return {
            "status": "updated",
            "id": doc_id,
            "points_added": points_added,
            "total_score": total_score,
            "won_levels": won_levels,
            "bonus_awarded": (points_added >= BONUS_ALL_WINS),  # True only if bonus added this call
        }

    # No changes (e.g., repeat win on same level, or won=False)
    total_score = current_score
    won_levels = [lvl for lvl, flag in
                  [("easy", easy_flag), ("medium", medium_flag), ("hard", hard_flag)] if flag]
    return {
        "status": "noop",
        "id": doc_id,
        "points_added": 0,
        "total_score": total_score,
        "won_levels": won_levels,
        "bonus_awarded": False,
    }
