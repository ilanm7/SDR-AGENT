"""
Point d'entrée — Agent Vocal TargetCo (Phase 2)

Modes :
  python start_voice.py --server              → Lance le serveur WebSocket (FastAPI)
  python start_voice.py --campaign FILE.csv   → Lance une campagne d'appels
  python start_voice.py --stats               → Affiche les stats des appels passés

Prérequis .env :
  ANTHROPIC_API_KEY   → déjà présent (Phase 1)
  DEEPGRAM_API_KEY    → déjà présent (Phase 1)
  TWILIO_ACCOUNT_SID  → twilio.com/console
  TWILIO_AUTH_TOKEN   → twilio.com/console
  TWILIO_PHONE_NUMBER → numéro Twilio acheté (ex: +33XXXXXXXXX)
  CARTESIA_API_KEY    → cartesia.ai
  CARTESIA_VOICE_ID   → ID de la voix française dans Cartesia
  PUBLIC_URL          → URL publique du serveur (ex: abc123.ngrok.io)
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def check_env():
    """Vérifie que les variables d'environnement nécessaires sont présentes."""
    import os
    required = [
        "ANTHROPIC_API_KEY",
        "DEEPGRAM_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "CARTESIA_API_KEY",
        "PUBLIC_URL",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"\n[ERREUR] Variables manquantes dans .env :\n  " + "\n  ".join(missing))
        print("\nConsultez le README pour la configuration.\n")
        sys.exit(1)


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Lance le serveur FastAPI + uvicorn."""
    import uvicorn
    from voice_agent.call_server import app

    print(f"\n{'='*55}")
    print("   TARGETCO VOICE AGENT — Serveur WebSocket")
    print(f"{'='*55}")
    print(f"  URL locale  : http://{host}:{port}")
    print(f"  Webhook Twilio : https://$PUBLIC_URL/twiml")
    print(f"{'='*55}\n")
    print("Configurez Twilio pour pointer vers : https://<PUBLIC_URL>/twiml")
    print("Appuyez sur Ctrl+C pour arrêter.\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


def run_campaign(csv_path: str, max_calls: int | None, delay: int):
    """Lance la campagne d'appels depuis un CSV."""
    if not Path(csv_path).exists():
        print(f"\n[ERREUR] Fichier introuvable : {csv_path}")
        sys.exit(1)

    from voice_agent.campaign import run_campaign as _run

    print(f"\n{'='*55}")
    print("   TARGETCO VOICE AGENT — Campagne d'appels")
    print(f"{'='*55}")
    print(f"  CSV      : {csv_path}")
    print(f"  Max      : {max_calls or 'tous'}")
    print(f"  Délai    : {delay}s entre appels")
    print(f"{'='*55}\n")

    asyncio.run(_run(csv_path, max_calls=max_calls, delay_seconds=delay))


def show_stats():
    """Affiche les statistiques des appels enregistrés."""
    from voice_agent.call_logger import CallLogger

    log = CallLogger()
    stats = log.get_stats()
    recent = log.get_recent_calls(10)

    print(f"\n{'='*55}")
    print("   TARGETCO VOICE AGENT — Statistiques")
    print(f"{'='*55}")

    if not stats:
        print("  Aucun appel enregistré.")
    else:
        print("\n  Résultats globaux :")
        for outcome, count in sorted(stats.items(), key=lambda x: -x[1]):
            print(f"    {outcome:<20} {count:>4} appel(s)")

        print("\n  10 derniers appels :")
        for call in recent:
            ts = call["call_timestamp"][:16].replace("T", " ")
            print(
                f"    {ts}  {call['prospect_name']:<25}"
                f"  {call['outcome']:<20}  {call.get('duration_sec', 0)}s"
            )
    print()


def main():
    parser = argparse.ArgumentParser(description="TargetCo Voice Agent — Phase 2")
    parser.add_argument("--server", action="store_true", help="Lancer le serveur WebSocket")
    parser.add_argument("--port", type=int, default=8080, help="Port du serveur (défaut: 8080)")
    parser.add_argument("--campaign", metavar="CSV", help="Lancer une campagne depuis un CSV")
    parser.add_argument("--max", type=int, default=None, metavar="N", help="Nombre max d'appels")
    parser.add_argument("--delay", type=int, default=30, metavar="SEC", help="Délai entre appels (défaut: 30s)")
    parser.add_argument("--stats", action="store_true", help="Afficher les statistiques")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    check_env()

    if args.server:
        run_server(port=args.port)
    elif args.campaign:
        run_campaign(args.campaign, max_calls=args.max, delay=args.delay)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
