import os
import streamlit as st
from dotenv import load_dotenv

from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

load_dotenv(".env.local")

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

def upsert_score(team_name: str, delta_score: int) -> dict:
    _, databases, database_id, collection_id = get_appwrite()
    res = databases.list_documents(
        database_id,
        collection_id,
        [Query.equal("team_name", team_name), Query.limit(1)],
    )
    if int(res.get("total", 0)) > 0 and len(res.get("documents", [])) > 0:
        doc = res["documents"][0]
        current_score = int(doc.get("score", 0))
        new_score = current_score + int(delta_score)
        updated = databases.update_document(
            database_id,
            collection_id,
            doc["$id"],
            {"score": new_score},
        )
        return {"status": "updated", "id": updated.get("$id"), "score": new_score}
    # Create new team
    created = databases.create_document(
        database_id,
        collection_id,
        ID.unique(),
        {"team_name": team_name, "score": int(delta_score)},
    )
    return {"status": "created", "id": created.get("$id"), "score": int(delta_score)}
