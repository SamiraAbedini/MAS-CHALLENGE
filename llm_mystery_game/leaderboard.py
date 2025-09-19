import os
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

# Load .env (uses the file named ".env" by default)
load_dotenv()

POINTS = {"level1": 20, "level2": 30, "level3": 50, "level4": 50, "level5": 50}
BONUS_ALL_WINS = 100


def get_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def get_appwrite() -> Databases:
    client = Client()
    client.set_endpoint(get_env("APPWRITE_ENDPOINT"))
    client.set_project(get_env("APPWRITE_PROJECT_ID"))   # uses APPWRITE_PROJECT_ID from .env
    client.set_key(get_env("APPWRITE_API_KEY"))
    return Databases(client)


def _blank_entry(team_name: str) -> dict:
    # Booleans named level1..level5, plus score
    return {
        "team_name": team_name,
        "score": 0,
        "level1": False,
        "level2": False,
        "level3": False,
        "level4": False,
        "level5": False,
    }


def submit_level_result(team_name: str, level: str, won: bool) -> dict:
    """
    Idempotent scoring:
    - Awards points for first win of a level.
    - Awards one-time +100 bonus when all five levels are won.
    Returns dict with status, points_added, total_score, won_levels, bonus_awarded.
    """
    assert level in {"level1", "level2", "level3", "level4", "level5"}

    db = get_appwrite()
    db_id = get_env("APPWRITE_DATABASE_ID")        # uses APPWRITE_DATABASE_ID from .env
    coll_id = get_env("APPWRITE_COLLECTION_ID")

    # Fetch or create team document
    res = db.list_documents(db_id, coll_id, [Query.equal("team_name", team_name), Query.limit(1)])
    if res["total"] == 0:
        # create new document
        doc = _blank_entry(team_name)
        created = db.create_document(db_id, coll_id, ID.unique(), doc)
        doc_id = created["$id"]
        l1 = l2 = l3 = l4 = l5 = False
        current_score = 0
    else:
        doc = res["documents"][0]
        doc_id = doc["$id"]
        current_score = int(doc.get("score", 0))
        l1 = bool(doc.get("level1", False))
        l2 = bool(doc.get("level2", False))
        l3 = bool(doc.get("level3", False))
        l4 = bool(doc.get("level4", False))
        l5 = bool(doc.get("level5", False))

    updates = {}
    points_added = 0

    if won:
        # Level-specific idempotency
        if level == "level1" and not l1:
            l1 = True
            updates["level1"] = True
            points_added += POINTS["level1"]
        elif level == "level2" and not l2:
            l2 = True
            updates["level2"] = True
            points_added += POINTS["level2"]
        elif level == "level3" and not l3:
            l3 = True
            updates["level3"] = True
            points_added += POINTS["level3"]
        elif level == "level4" and not l4:
            l4 = True
            updates["level4"] = True
            points_added += POINTS["level4"]
        elif level == "level5" and not l5:
            l5 = True
            updates["level5"] = True
            points_added += POINTS["level5"]

    base_after = (
        (POINTS["level1"] if l1 else 0)
        + (POINTS["level2"] if l2 else 0)
        + (POINTS["level3"] if l3 else 0)
        + (POINTS["level4"] if l4 else 0)
        + (POINTS["level5"] if l5 else 0)
    )

    bonus_awarded_now = False
    if l1 and l2 and l3 and l4 and l5:
        expected_total = base_after + BONUS_ALL_WINS
        if current_score + points_added < expected_total:
            bonus_awarded_now = True
            points_added += BONUS_ALL_WINS

    if points_added > 0:
        updates["score"] = current_score + points_added
        updated = db.update_document(db_id, coll_id, doc_id, updates)
        total_score = int(updated.get("score", current_score))
        won_levels = [
            lvl
            for lvl, flag in [
                ("level1", updated.get("level1", l1)),
                ("level2", updated.get("level2", l2)),
                ("level3", updated.get("level3", l3)),
                ("level4", updated.get("level4", l4)),
                ("level5", updated.get("level5", l5)),
            ]
            if flag
        ]
        return {
            "status": "updated",
            "id": doc_id,
            "points_added": points_added,
            "total_score": total_score,
            "won_levels": won_levels,
            "bonus_awarded": bonus_awarded_now,
        }
    else:
        # No points to add (duplicate win on same level, or won=False)
        total_score = current_score
        won_levels = [
            lvl
            for lvl, flag in [
                ("level1", l1),
                ("level2", l2),
                ("level3", l3),
                ("level4", l4),
                ("level5", l5),
            ]
            if flag
        ]
        return {
            "status": "noop",
            "id": doc_id,
            "points_added": 0,
            "total_score": total_score,
            "won_levels": won_levels,
            "bonus_awarded": False,
        }

# ---------- Prompt logging (new) ----------

def log_prompt_attempt(team_name: str, level: str, prompt: str, is_success: bool) -> str:
    """
    Write one row into the 'prompts' collection with:
      team_name (string), isSuccess (boolean), level (int), prompt (string)

    Uses env vars you already have:
      APPWRITE_ENDPOINT, APPWRITE_PROJECT_ID, APPWRITE_API_KEY,
      APPWRITE_DATABASE_ID; collection id is literally "prompts".
    """
    db = get_appwrite()
    db_id = get_env("APPWRITE_DATABASE_ID")
    prompts_coll_id = "prompts"  # per your teammate: collection ID is 'prompts'

    # Convert UI level like "level3" -> 3
    try:
        level_int = int(str(level).replace("level", "").strip())
    except Exception:
        level_int = 0  # fallback if someone passes a weird value

    doc = {
        "team_name": team_name,
        "isSuccess": bool(is_success),
        "level": level_int,
        "prompt": prompt or "",
    }
    created = db.create_document(db_id, prompts_coll_id, ID.unique(), doc)
    return created["$id"]
