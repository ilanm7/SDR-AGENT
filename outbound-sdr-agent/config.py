import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_SDR_CHAT_IDS = [
    cid.strip()
    for cid in os.getenv("TELEGRAM_SDR_CHAT_IDS", "").split(",")
    if cid.strip()
]

CLAUDE_MODEL_RESEARCH = os.getenv("CLAUDE_MODEL_RESEARCH", "claude-haiku-4-5-20251001")
CLAUDE_MODEL_SCRIPT = os.getenv("CLAUDE_MODEL_SCRIPT", "claude-sonnet-4-6")

GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
DEEPGRAM_API_KEY  = os.getenv("DEEPGRAM_API_KEY", "")
