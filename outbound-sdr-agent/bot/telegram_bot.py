"""
Bot Telegram TargetCo SDR — menu interactif, prospection full-auto et semi-auto.
"""
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# États de la machine
# ---------------------------------------------------------------------------
STATE_FREE               = "free"
STATE_ENRICHIR           = "awaiting_enrichir"
STATE_SCRIPT             = "awaiting_script"
STATE_COACHING           = "awaiting_coaching"
STATE_SUIVI              = "awaiting_suivi"
STATE_SEMI_AUTO          = "awaiting_semi_auto_criteria"
STATE_CHANGE_VILLE       = "awaiting_change_ville"

# ---------------------------------------------------------------------------
# Ville par défaut (globale, modifiable par utilisateur)
# ---------------------------------------------------------------------------
DEFAULT_VILLE = "Paris"  # Default city

# ---------------------------------------------------------------------------
# Claviers
# ---------------------------------------------------------------------------

def main_keyboard(ville: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Enrich a prospect",    callback_data="menu_enrichir"),
            InlineKeyboardButton("📞 Call script",           callback_data="menu_script"),
        ],
        [
            InlineKeyboardButton("🎯 Post-call coaching",   callback_data="menu_coaching"),
            InlineKeyboardButton("📧 Follow-up message",    callback_data="menu_suivi"),
        ],
        [
            InlineKeyboardButton("🤖 Full Auto",             callback_data="menu_full_auto"),
            InlineKeyboardButton("🎯 Semi-Auto",             callback_data="menu_semi_auto"),
        ],
        [
            InlineKeyboardButton("📊 SDR Dashboard",         callback_data="menu_dashboard"),
            InlineKeyboardButton(f"📍 City: {ville}",        callback_data="menu_change_ville"),
        ],
        [
            InlineKeyboardButton("🔄 Reset",                 callback_data="menu_reset"),
        ],
    ])

def full_auto_keyboard(ville: str) -> InlineKeyboardMarkup:
    """Submenu shown when the user clicks on Full Auto."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🚀 Launch in {ville}",         callback_data="full_auto_go"),
        ],
        [
            InlineKeyboardButton("📍 Change city",                callback_data="full_auto_change_ville"),
            InlineKeyboardButton("🌍 Change country",             callback_data="full_auto_change_pays"),
        ],
        [
            InlineKeyboardButton("⬅️ Back to menu",               callback_data="menu_back"),
        ],
    ])

MENU_TEXT = (
    "*TargetCo SDR Agent* — What would you like to do?\n\n"
    "🔍 *Enrich* — Full profile on a prospect\n"
    "📞 *Script* — Personalized call script\n"
    "🎯 *Coaching* — Post-call analysis\n"
    "📧 *Follow-up* — Email / WhatsApp after a call\n"
    "🤖 *Full Auto* — I find and prospect on my own\n"
    "🎯 *Semi-Auto* — I prospect based on your criteria\n"
    "📊 *Dashboard* — SDR metrics\n"
    "📍 *City* — Change the default city\n"
)

STATE_PROMPTS = {
    STATE_ENRICHIR:    "📋 Give me the store name and city:\n_Ex: Central Pharmacy, Lyon 6th_",
    STATE_SCRIPT:      "📋 Give me the store name:\n_Ex: Carrefour City, Paris 12th_",
    STATE_COACHING:    "📋 Paste the call transcript or your call notes:",
    STATE_SUIVI:       "📋 Describe the call context:\n_Ex: Call with Mr. Dupont, pharmacy Paris 19th. Interested but hesitated on price._",
    STATE_SEMI_AUTO:   (
        "🎯 *Semi-Auto Prospecting*\n\n"
        "Give me your criteria:\n"
        "_Ex: Find 5 pharmacies in the 13th arrondissement_\n"
        "_Ex: Look for supermarkets in central Lyon_\n"
        "_Ex: Prospect bakeries in 75019_"
    ),
    STATE_CHANGE_VILLE: "📍 Enter the new city or country:\n_Ex: Lyon, Marseille, Bordeaux, Brussels, Madrid..._",
}

STATE_AGENT_PREFIX = {
    STATE_ENRICHIR:  "Enrich this prospect: ",
    STATE_SCRIPT:    "Generate the call script for: ",
    STATE_COACHING:  "Post-call coaching — analyze this call: ",
    STATE_SUIVI:     "Write a follow-up message for: ",
    STATE_SEMI_AUTO: "",
}

# ---------------------------------------------------------------------------
# Envoi push (utilisé par main.py --batch)
# ---------------------------------------------------------------------------

async def send_script(bot_token: str, chat_id: str, script_text: str) -> bool:
    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        chunks = [script_text[i:i+4000] for i in range(0, len(script_text), 4000)]
        for chunk in chunks:
            await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.MARKDOWN)
        return True
    except Exception as e:
        logger.error(f"Erreur envoi Telegram à {chat_id}: {e}")
        return False


def send_script_sync(bot_token: str, chat_id: str, script_text: str) -> bool:
    return asyncio.run(send_script(bot_token, chat_id, script_text))


# ---------------------------------------------------------------------------
# Construction du bot
# ---------------------------------------------------------------------------

def build_interactive_bot(bot_token: str, agent) -> Application:

    # Données par utilisateur : historique, état, ville configurée
    user_data: dict[int, dict] = {}

    def get_user(user_id: int) -> dict:
        if user_id not in user_data:
            user_data[user_id] = {
                "history": [],
                "state":   STATE_FREE,
                "ville":   DEFAULT_VILLE,
            }
        return user_data[user_id]

    # -----------------------------------------------------------------------
    # /start
    # -----------------------------------------------------------------------
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = get_user(update.effective_user.id)
        await update.message.reply_text(
            f"Hello\\! I am the *TargetCo SDR Agent*\\.\n"
            f"Your chat\\_id: `{update.effective_chat.id}`\n\n"
            f"Type /menu to get started\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    # -----------------------------------------------------------------------
    # /menu
    # -----------------------------------------------------------------------
    async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = get_user(update.effective_user.id)
        user["state"] = STATE_FREE
        await update.message.reply_text(
            MENU_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(user["ville"]),
        )

    # -----------------------------------------------------------------------
    # /reset
    # -----------------------------------------------------------------------
    async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = get_user(update.effective_user.id)
        user["history"] = []
        user["state"]   = STATE_FREE
        await update.message.reply_text(
            "🔄 Conversation reset.\nType /menu to start again."
        )

    # -----------------------------------------------------------------------
    # Callbacks boutons
    # -----------------------------------------------------------------------
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user  = get_user(query.from_user.id)
        data  = query.data
        ville = user["ville"]

        # --- Retour au menu ---
        if data in ("menu_back", "menu_reset"):
            user["history"] = []
            user["state"]   = STATE_FREE
            await query.message.reply_text(
                MENU_TEXT,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(ville),
            )
            return

        # --- Dashboard (pas besoin d'input) ---
        if data == "menu_dashboard":
            user["state"] = STATE_FREE
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
            response, user["history"] = agent.run("Display the SDR dashboard", user["history"])
            await _send_chunks(context.bot, query.message.chat_id, response)
            await query.message.reply_text("— Anything else?", reply_markup=main_keyboard(ville))
            return

        # --- Change city (from main menu) ---
        if data == "menu_change_ville":
            user["state"] = STATE_CHANGE_VILLE
            await query.message.reply_text(
                STATE_PROMPTS[STATE_CHANGE_VILLE],
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --- Full Auto: show submenu ---
        if data == "menu_full_auto":
            await query.message.reply_text(
                f"🤖 *Full Auto Prospecting*\n\n"
                f"I will search, enrich and generate scripts automatically.\n"
                f"Configured city: *{ville}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=full_auto_keyboard(ville),
            )
            return

        # --- Full Auto: change city from submenu ---
        if data == "full_auto_change_ville":
            user["state"] = STATE_CHANGE_VILLE
            await query.message.reply_text(
                "📍 Enter the new city:\n_Ex: Lyon, Marseille, Bordeaux..._",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --- Full Auto: change country from submenu ---
        if data == "full_auto_change_pays":
            user["state"] = STATE_CHANGE_VILLE
            await query.message.reply_text(
                "🌍 Enter the country or foreign city:\n_Ex: Brussels, Madrid, Milan, London..._",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --- Full Auto: GO (launch automatic prospecting) ---
        if data == "full_auto_go":
            user["state"] = STATE_FREE
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")
            await query.message.reply_text(
                f"🤖 Autonomous prospecting launched in *{ville}*\\.\\.\\. ⏳\n"
                f"Searching, enriching and generating scripts\\. This may take 1\\-2 minutes\\.",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            agent_message = (
                f"Automatically prospect in {ville}: "
                f"find 5 varied retail businesses (pharmacies, supermarkets, bakeries, "
                f"local shops) with high TargetCo potential. "
                f"Enrich the top 3 and generate their call scripts."
            )
            response, user["history"] = agent.run(agent_message, user["history"])
            await _send_chunks(context.bot, query.message.chat_id, response)
            await query.message.reply_text("— Anything else?", reply_markup=main_keyboard(ville))
            return

        # --- Semi-Auto ---
        if data == "menu_semi_auto":
            user["state"] = STATE_SEMI_AUTO
            await query.message.reply_text(
                STATE_PROMPTS[STATE_SEMI_AUTO],
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # --- Skills simples (enrichir, script, coaching, suivi) ---
        state_map = {
            "menu_enrichir": STATE_ENRICHIR,
            "menu_script":   STATE_SCRIPT,
            "menu_coaching": STATE_COACHING,
            "menu_suivi":    STATE_SUIVI,
        }
        if data in state_map:
            user["state"] = state_map[data]
            await query.message.reply_text(
                STATE_PROMPTS[user["state"]],
                parse_mode=ParseMode.MARKDOWN,
            )

    # -----------------------------------------------------------------------
    # Messages texte
    # -----------------------------------------------------------------------
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        user    = get_user(user_id)
        text    = update.message.text.strip()
        state   = user.get("state", STATE_FREE)
        ville   = user["ville"]

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # --- City change ---
        if state == STATE_CHANGE_VILLE:
            user["ville"]  = text
            user["state"]  = STATE_FREE
            await update.message.reply_text(
                f"✅ City updated: *{text}*\n\nFull Auto will now use *{text}* by default.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_keyboard(text),
            )
            return

        # --- Tous les autres états → envoyer à l'agent ---
        prefix        = STATE_AGENT_PREFIX.get(state, "")
        agent_message = prefix + text if prefix else text
        user["state"] = STATE_FREE

        try:
            response, user["history"] = agent.run(agent_message, user["history"])
            await _send_chunks(context.bot, update.effective_chat.id, response)
            await update.message.reply_text("— Anything else?", reply_markup=main_keyboard(ville))
        except Exception as e:
            logger.error(f"Agent error user {user_id}: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred. Type /reset to start again."
            )

    # -----------------------------------------------------------------------
    # Utilitaire : découper les longs messages
    # -----------------------------------------------------------------------
    async def _send_chunks(bot, chat_id: int, text: str) -> None:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            try:
                await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await bot.send_message(chat_id=chat_id, text=chunk)

    # -----------------------------------------------------------------------
    # Assemblage
    # -----------------------------------------------------------------------
    app = Application.builder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu",  menu_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def run_interactive_bot(bot_token: str, agent) -> None:
    app = build_interactive_bot(bot_token, agent)
    logger.info("Telegram bot started. Press Ctrl+C to stop.")
    app.run_polling()
