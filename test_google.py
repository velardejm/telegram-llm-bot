import os
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents"]
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("oauth_credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

creds = get_credentials()
drive_service = build("drive", "v3", credentials=creds)
docs_service = build("docs", "v1", credentials=creds)

print("=== TEST: Can Drive API create a Doc? ===")
try:
    file_metadata = {
        "name": "test-delete-me",
        "mimeType": "application/vnd.google-apps.document",
        "parents": [FOLDER_ID]
    }
    file = drive_service.files().create(body=file_metadata, fields="id").execute()
    print(f"SUCCESS — doc created: {file['id']}")
except Exception as e:
    print(f"FAILED — {e}")