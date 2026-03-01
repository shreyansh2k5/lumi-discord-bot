# services/database.py
# Owns Firebase initialisation. Called once from main.py at startup.
# Passes the async Firestore client to modules that need it.

import os
import json

import firebase_admin
from firebase_admin import credentials
from google.cloud.firestore_v1.async_client import AsyncClient
from google.oauth2 import service_account

from moderation.automod import set_firestore_db
from economy.transactions import set_economy_db


def init_firebase():
    """
    Initialises Firebase Admin SDK and creates an async Firestore client.
    Reads credentials from the FIREBASE_SERVICE_ACCOUNT_KEY env variable.
    """
    key_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
    if not key_json:
        print("❌ FIREBASE_SERVICE_ACCOUNT_KEY is not set.")
        raise SystemExit(1)

    try:
        service_account_info = json.loads(key_json)
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin SDK initialised.")

        project_id = service_account_info["project_id"]
        auth_creds = service_account.Credentials.from_service_account_info(service_account_info)
        db = AsyncClient(project=project_id, credentials=auth_creds)

        set_firestore_db(db)
        set_economy_db(db)
        print("✅ Async Firestore client ready.")

    except Exception as e:
        print(f"❌ Firebase initialisation failed: {e}")
        raise SystemExit(1)
