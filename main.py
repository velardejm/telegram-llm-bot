import os
import logging
import base64
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from openai import OpenAI
import httpx
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Google API setup
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


def get_today_filename():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def find_todays_doc():
    filename = get_today_filename()
    query = f"name='{filename}' and '{FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def create_todays_doc():
    filename = get_today_filename()
    file_metadata = {
        "name": filename,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [FOLDER_ID]
    }
    file = drive_service.files().create(body=file_metadata, fields="id").execute()
    doc_id = file["id"]
    logger.info(f"Created new doc: {filename} ({doc_id})")
    return doc_id


def get_or_create_doc():
    doc_id = find_todays_doc()
    if not doc_id:
        doc_id = create_todays_doc()
    return doc_id


def append_to_doc(doc_id: str, entry: str):
    timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
    line = f"[{timestamp}] {entry}\n"

    doc = docs_service.documents().get(documentId=doc_id).execute()
    end_index = doc["body"]["content"][-1]["endIndex"] - 1

    requests = [{
        "insertText": {
            "location": {"index": end_index},
            "text": line
        }
    }]
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests}
    ).execute()
    logger.info(f"Appended to doc: {line.strip()}")


async def interpret_and_log(message_type: str, content: str, doc_id: str):
    prompt = f"""You are a construction site log assistant.
A site engineer sent a {message_type} message. Summarize it as a single concise log entry (1-2 sentences max).
Start directly with the content, no preamble.

Input: {content}"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    summary = response.choices[0].message.content.strip()
    entry = f"{message_type.upper()} | {summary}"
    append_to_doc(doc_id, entry)
    return summary


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[TEXT] {user_text}")
    doc_id = get_or_create_doc()
    summary = await interpret_and_log("text", user_text, doc_id)
    await update.message.reply_text(f"✅ Logged: {summary}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.get(file.file_path)
        audio_bytes = response.content

    transcription = client.audio.transcriptions.create(
        model="whisper-1",
        file=("voice.ogg", audio_bytes, "audio/ogg"),
    )
    text = transcription.text
    print(f"[VOICE] {text}")

    doc_id = get_or_create_doc()
    summary = await interpret_and_log("voice", text, doc_id)
    await update.message.reply_text(f"✅ Logged: {summary}")


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    async with httpx.AsyncClient(timeout=30.0) as http:
        response = await http.get(file.file_path)
        image_b64 = base64.standard_b64encode(response.content).decode("utf-8")

    caption = update.message.caption or "No caption provided"
    print(f"[IMAGE] caption: {caption}")

    vision_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
                },
                {"type": "text", "text": f"You are a construction site log assistant. Describe what you see in this site photo as a concise log entry (1-2 sentences). Caption from engineer: {caption}"}
            ]
        }],
        max_tokens=150,
    )
    description = vision_response.choices[0].message.content.strip()
    print(f"[IMAGE DESCRIPTION] {description}")

    doc_id = get_or_create_doc()
    entry = f"IMAGE | {description}"
    append_to_doc(doc_id, entry)
    await update.message.reply_text(f"✅ Logged: {description}")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(token).request(request).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()