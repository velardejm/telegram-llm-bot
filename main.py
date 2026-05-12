import os
import logging
import base64
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from openai import OpenAI
import httpx

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def ask_openai(messages: list) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        max_tokens=1024,
    )
    return response.choices[0].message.content


# async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_text = update.message.text
#     logger.info(f"Text received: {user_text}")
#     reply = await ask_openai([{"role": "user", "content": user_text}])
#     await update.message.reply_text(reply)


# async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     voice = update.message.voice
#     file = await context.bot.get_file(voice.file_id)

#     async with httpx.AsyncClient() as http:
#         response = await http.get(file.file_path)
#         audio_bytes = response.content

#     transcription = client.audio.transcriptions.create(
#         model="whisper-1",
#         file=("voice.ogg", audio_bytes, "audio/ogg"),
#     )
#     text = transcription.text
#     logger.info(f"Transcribed: {text}")

#     reply = await ask_openai([{"role": "user", "content": text}])
#     await update.message.reply_text(f'🎙️ I heard: "{text}"\n\n{reply}')


# async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     photo = update.message.photo[-1]
#     file = await context.bot.get_file(photo.file_id)

#     async with httpx.AsyncClient() as http:
#         response = await http.get(file.file_path)
#         image_b64 = base64.standard_b64encode(response.content).decode("utf-8")

#     caption = update.message.caption or "What's in this image?"

#     reply = await ask_openai([{
#         "role": "user",
#         "content": [
#             {
#                 "type": "image_url",
#                 "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
#             },
#             {"type": "text", "text": caption}
#         ]
#     }])
#     await update.message.reply_text(reply)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()