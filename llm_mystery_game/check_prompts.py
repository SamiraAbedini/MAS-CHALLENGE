from appwrite.client import Client
from appwrite.services.databases import Databases

ENDPOINT = "https://fra.cloud.appwrite.io/v1"
PROJECT  = "ctf-dn"
API_KEY  = "standard_ca0037c350c3ed6c3501e10dc93ff712c4941062452ec4d281238cfa01d711261db3c3f7646c9c4af2bfd1529c4c9124cb4652bb4009b7c0932d115da3039f21588ec97229b7c14e39024cb6e2611ee856b15744156297c3bff73ffe6e1571b2768089117ed78f4a815cc68c7e3794ff699a45302beb5f567a524849d5516e82"
DB_ID    = "68aeb43e0002f79c45dc"
COLL_ID  = "prompts"

client = Client().set_endpoint(ENDPOINT).set_project(PROJECT).set_key(API_KEY)
db = Databases(client)

res = db.list_documents(DB_ID, COLL_ID)  # default limit ~25
print(f"Total docs listed: {res['total']}")
for d in res["documents"]:
    print("-" * 40)
    print("team_name:", d.get("team_name"))
    print("level:", d.get("level"))
    print("isSuccess:", d.get("isSuccess"))
    print("prompt:", (d.get("prompt") or "")[:200].replace("\n", "\\n"), "...")
