import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("credentials/firebase-service-account.json")
        firebase_admin.initialize_app(cred)
    except Exception as e:
        print(f"Error initializing Firebase: {e}")


def get_youtube_api_key():
    """Fetch YouTube API key from Firestore."""
    try:
        db = firestore.client()
        doc = db.collection("config").document("youtube_api").get()
        if doc.exists:
            api_key = doc.to_dict().get("api_key")
            if api_key:
                print("YouTube API key fetched successfully.")
                return api_key
        print("YouTube API key not found in Firestore.")
        return None
    except Exception as e:
        print(f"Error fetching YouTube API key: {e}")
        return None
