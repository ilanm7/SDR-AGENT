"""
Déclenche les appels sortants via l'API REST Twilio.
Gère aussi la détection de messagerie (AMD) et les callbacks de statut.
"""
import os
import logging
from twilio.rest import Client

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "")  # ex: "abc123.ngrok.io" (sans https://)


def make_outbound_call(call_sid_token: str, to_phone: str) -> str:
    """
    Lance un appel sortant Twilio vers `to_phone`.

    - Twilio appellera /twiml?token={call_sid_token} quand le prospect décroche.
    - AMD activé : si messagerie détectée, Twilio appellera /twiml?token=...&amd=voicemail.
    - Retourne le call_sid Twilio (str).
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, PUBLIC_URL]):
        raise EnvironmentError(
            "Variables manquantes dans .env : "
            "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, PUBLIC_URL"
        )

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    twiml_url = f"https://{PUBLIC_URL}/twiml?token={call_sid_token}"
    status_url = f"https://{PUBLIC_URL}/call-status"

    call = client.calls.create(
        to=to_phone,
        from_=TWILIO_PHONE_NUMBER,
        url=twiml_url,
        method="POST",
        # Answering Machine Detection — évite de parler à une messagerie
        machine_detection="DetectMessageEnd",
        machine_detection_timeout=30,
        async_amd=True,
        async_amd_status_callback=f"https://{PUBLIC_URL}/amd-status",
        async_amd_status_callback_method="POST",
        # Suivi statut d'appel
        status_callback=status_url,
        status_callback_method="POST",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        # Timeout si pas de réponse après 30s (~ 5 sonneries)
        timeout=30,
    )

    logger.info(f"Call initiated → {to_phone} | SID: {call.sid}")
    return call.sid


def end_call(call_sid: str):
    """Raccroche un appel en cours (utile pour les timeouts agent-side)."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        client.calls(call_sid).update(status="completed")
        logger.info(f"Call {call_sid} terminated")
    except Exception as e:
        logger.warning(f"Could not end call {call_sid}: {e}")
