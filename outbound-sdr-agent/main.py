"""
Point d'entrée principal de l'Agent SDR TargetCo.

Modes disponibles :
  python main.py                   → Mode chat interactif (terminal)
  python main.py --bot             → Lance le bot Telegram interactif
  python main.py --batch prospects.csv  → Traite tous les prospects d'un CSV
  python main.py --get-chat-id     → Affiche les chat_ids Telegram reçus (setup)
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def check_config(require_telegram: bool = False) -> None:
    """Vérifie que les variables d'environnement nécessaires sont présentes."""
    from config import ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN

    if not ANTHROPIC_API_KEY:
        print(
            "\n[ERREUR] ANTHROPIC_API_KEY manquante.\n"
            "  1. Copier .env.example en .env\n"
            "  2. Renseigner votre clé sur console.anthropic.com\n"
        )
        sys.exit(1)

    if require_telegram and not TELEGRAM_BOT_TOKEN:
        print(
            "\n[ERREUR] TELEGRAM_BOT_TOKEN manquant.\n"
            "  1. Ouvrir Telegram → @BotFather → /newbot\n"
            "  2. Copier le token dans .env → TELEGRAM_BOT_TOKEN\n"
        )
        sys.exit(1)


def build_agent():
    from config import ANTHROPIC_API_KEY, CLAUDE_MODEL_RESEARCH, CLAUDE_MODEL_SCRIPT
    from agent.sdr_agent import SDRAgent
    return SDRAgent(
        api_key=ANTHROPIC_API_KEY,
        model_research=CLAUDE_MODEL_RESEARCH,
        model_script=CLAUDE_MODEL_SCRIPT,
    )


# ---------------------------------------------------------------------------
# Mode 1 : Chat interactif en terminal
# ---------------------------------------------------------------------------

def run_chat():
    """Conversation interactive dans le terminal."""
    check_config()
    agent = build_agent()

    print("\n" + "="*60)
    print("   AGENT SDR TARGETCO — Mode chat terminal")
    print("="*60)
    print("Commandes spéciales :")
    print("  /reset  → Effacer l'historique de conversation")
    print("  /quit   → Quitter")
    print("="*60 + "\n")

    history = []
    while True:
        try:
            user_input = input("Vous : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAu revoir !")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("Au revoir !")
            break

        if user_input.lower() == "/reset":
            history = []
            print("→ Conversation réinitialisée.\n")
            continue

        print("\nAgent (en cours de réflexion...)\n")
        try:
            response, history = agent.run(user_input, history)
            print(f"Agent :\n{response}\n")
            print("-" * 60 + "\n")
        except Exception as e:
            print(f"[ERREUR] {e}\n")


# ---------------------------------------------------------------------------
# Mode 2 : Bot Telegram interactif
# ---------------------------------------------------------------------------

def run_telegram_bot():
    """Lance le bot Telegram interactif."""
    check_config(require_telegram=True)
    agent = build_agent()

    from config import TELEGRAM_BOT_TOKEN
    from bot.telegram_bot import run_interactive_bot

    print("\nBot Telegram démarré. Écrivez au bot depuis Telegram.")
    print("Appuyez sur Ctrl+C pour arrêter.\n")
    run_interactive_bot(TELEGRAM_BOT_TOKEN, agent)


# ---------------------------------------------------------------------------
# Mode 3 : Traitement batch d'un CSV
# ---------------------------------------------------------------------------

def run_batch(csv_path: str, send_telegram: bool = False):
    """Traite tous les prospects d'un fichier CSV Salesforce."""
    check_config(require_telegram=send_telegram)
    agent = build_agent()

    from data.csv_processor import load_prospects, format_prospect_for_agent
    prospects = load_prospects(csv_path)

    print(f"\n{len(prospects)} prospects chargés depuis {csv_path}\n")

    from config import TELEGRAM_BOT_TOKEN, TELEGRAM_SDR_CHAT_IDS
    if send_telegram and not TELEGRAM_SDR_CHAT_IDS:
        print("[ATTENTION] Aucun chat_id SDR configuré. Les scripts ne seront pas envoyés.")
        send_telegram = False

    for i, prospect in enumerate(prospects, 1):
        name = prospect.get("account_name") or f"Prospect #{i}"
        print(f"[{i}/{len(prospects)}] Traitement : {name}")

        message = format_prospect_for_agent(prospect)
        try:
            response, _ = agent.run(message)
            print(f"\n--- Résultat pour {name} ---\n{response}\n")

            if send_telegram:
                from bot.telegram_bot import send_script_sync
                header = f"📋 *Script TargetCo — {name}*\n\n"
                for chat_id in TELEGRAM_SDR_CHAT_IDS:
                    ok = send_script_sync(TELEGRAM_BOT_TOKEN, chat_id, header + response)
                    status = "envoyé" if ok else "ÉCHEC"
                    print(f"   → Telegram {chat_id} : {status}")

        except Exception as e:
            print(f"   [ERREUR] {e}")

        print("=" * 60)


# ---------------------------------------------------------------------------
# Mode 4 : Récupérer les chat_ids Telegram (setup initial)
# ---------------------------------------------------------------------------

def run_get_chat_id():
    """Lance un bot temporaire pour afficher les chat_ids des utilisateurs."""
    check_config(require_telegram=True)
    from config import TELEGRAM_BOT_TOKEN
    from telegram import Update
    from telegram.ext import Application, MessageHandler, filters, ContextTypes

    async def show_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
        cid = update.effective_chat.id
        print(f"   → Chat ID reçu : {cid} (utilisateur : {update.effective_user.full_name})")
        await update.message.reply_text(
            f"Votre chat_id : `{cid}`\n\nAjoutez-le dans .env → TELEGRAM_SDR_CHAT_IDS",
            parse_mode="Markdown",
        )

    print("\nBot en attente de messages Telegram...")
    print("Écrivez n'importe quoi au bot pour obtenir votre chat_id.")
    print("Appuyez sur Ctrl+C pour arrêter.\n")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, show_chat_id))
    app.run_polling()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Agent SDR TargetCo")
    parser.add_argument("--bot", action="store_true", help="Lancer le bot Telegram interactif")
    parser.add_argument("--batch", metavar="CSV", help="Traiter un fichier CSV de prospects")
    parser.add_argument("--send-telegram", action="store_true", help="Envoyer les scripts par Telegram (mode batch)")
    parser.add_argument("--get-chat-id", action="store_true", help="Afficher les chat_ids Telegram (setup)")
    args = parser.parse_args()

    if args.get_chat_id:
        run_get_chat_id()
    elif args.bot:
        run_telegram_bot()
    elif args.batch:
        run_batch(args.batch, send_telegram=args.send_telegram)
    else:
        run_chat()


if __name__ == "__main__":
    main()
