"""
Runner de campagne d'appels.
Lit un CSV de prospects, vérifie la conformité légale, déclenche les appels Twilio.

Usage :
  python start_voice.py --campaign data/sample_prospects.csv
  python start_voice.py --campaign data/sample_prospects.csv --max 5 --delay 45
"""
import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path

from .call_logger import CallLogger
from .legal_checks import add_to_optout, is_legal_call_time, is_opted_out, next_legal_slot
from .outbound_caller import make_outbound_call
from .call_server import register_prospect

logger = logging.getLogger(__name__)

DEFAULT_DELAY = 30   # secondes entre deux appels
MAX_RETRIES   = 1    # rappels en cas de NO_ANSWER (0 = aucun retry)


async def run_campaign(
    csv_path: str,
    max_calls: int | None = None,
    delay_seconds: int = DEFAULT_DELAY,
):
    """
    Lance la campagne d'appels depuis un CSV.

    Paramètres
    ----------
    csv_path     : chemin vers le fichier CSV de prospects
    max_calls    : nombre max d'appels à passer (None = tous)
    delay_seconds: pause entre deux appels (défaut 30s)
    """
    prospects = _load_csv(csv_path)
    total = len(prospects)
    logger.info(f"Campagne démarrée — {total} prospects dans {csv_path}")

    call_log = CallLogger()
    calls_made = 0
    skipped = 0

    for idx, prospect in enumerate(prospects, start=1):
        if max_calls and calls_made >= max_calls:
            logger.info("Nombre max d'appels atteint.")
            break

        name = _prospect_name(prospect)
        phone = prospect.get("Phone", "").strip()

        # Validation basique
        if not phone:
            logger.warning(f"[{idx}/{total}] {name} — numéro manquant, ignoré")
            skipped += 1
            continue

        # Vérification opt-out
        if is_opted_out(phone):
            logger.info(f"[{idx}/{total}] {name} — opt-out, ignoré")
            skipped += 1
            continue

        # Attente si hors horaires légaux
        ok, reason = is_legal_call_time()
        if not ok:
            next_slot = next_legal_slot()
            wait_sec = max(0, (next_slot - datetime.now()).total_seconds())
            logger.warning(
                f"Hors horaires légaux ({reason}). "
                f"Prochain créneau : {next_slot.strftime('%H:%M')}. "
                f"Pause de {wait_sec/60:.1f} min."
            )
            await asyncio.sleep(wait_sec)

        logger.info(f"[{idx}/{total}] Appel → {name} ({phone})")

        try:
            call_sid = make_outbound_call(
                call_sid_token=f"targetco_{idx}_{call_sid_safe(name)}",
                to_phone=phone,
            )
            register_prospect(call_sid, prospect)
            calls_made += 1
            logger.info(f"  SID: {call_sid}")
        except Exception as e:
            logger.error(f"  Erreur Twilio : {e}")
            skipped += 1
            continue

        # Pause entre appels
        if idx < total:
            await asyncio.sleep(delay_seconds)

    # Résumé final
    stats = call_log.get_stats()
    logger.info(
        f"\n{'='*50}\n"
        f"Campagne terminée\n"
        f"  Appels lancés : {calls_made}\n"
        f"  Ignorés       : {skipped}\n"
        f"  Résultats     : {stats}\n"
        f"{'='*50}"
    )
    return {"calls_made": calls_made, "skipped": skipped, "stats": stats}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _prospect_name(p: dict) -> str:
    return f"{p.get('Contact First Name', '')} {p.get('Contact Last Name', '')}".strip() \
           or p.get("Account Name", "Inconnu")


def call_sid_safe(name: str) -> str:
    """Sanitise un nom pour l'utiliser dans un token URL-safe."""
    return "".join(c if c.isalnum() else "_" for c in name)[:20]
