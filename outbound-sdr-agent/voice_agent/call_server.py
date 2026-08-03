"""
Serveur FastAPI — cœur de l'agent vocal TargetCo.

Pipeline par appel :
  Twilio Media Stream (WebSocket, mulaw 8kHz)
      ↕
  Deepgram Nova-2 (STT streaming, French)
      ↓  transcription
  Claude Haiku   (LLM streaming, 150 tokens max)
      ↓  texte réponse
  Cartesia       (TTS streaming, PCM 8kHz → mulaw)
      ↕
  Twilio Media Stream

Points clés :
- Barge-in : si le prospect parle pendant que l'agent parle, l'agent s'arrête.
- Greeting automatique dès que le stream Twilio démarre.
- log_call_outcome → fin de session + log SQLite.
"""
import asyncio
import base64
import json
import logging
import os
from typing import Optional

import httpx
import websockets
from anthropic import AsyncAnthropic
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from .call_logger import CallLogger
from .outbound_caller import end_call
from .voice_prompt import OUTCOME_TOOL, build_system_prompt

# ---------------------------------------------------------------------------
# Compat audioop (stdlib Python ≤3.12 / audioop-lts pour 3.13+)
# ---------------------------------------------------------------------------
try:
    import audioop
except ImportError:
    try:
        import audioop_lts as audioop  # type: ignore
    except ImportError:
        audioop = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_VOICE_ID = os.getenv("CARTESIA_VOICE_ID", "a167e0f3-df7e-4d52-a786-6f58e0927727")
PUBLIC_URL = os.getenv("PUBLIC_URL", "localhost:8080")

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
MAX_CALL_DURATION = 300  # 5 min max

DEEPGRAM_WS_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=mulaw&sample_rate=8000&language=fr"
    "&model=nova-2&endpointing=400&utterance_end_ms=1000"
    "&interim_results=false&smart_format=true"
)

CARTESIA_TTS_URL = "https://api.cartesia.ai/tts/bytes"

# ---------------------------------------------------------------------------
# App & shared state
# ---------------------------------------------------------------------------
app = FastAPI(title="TargetCo Voice Agent")
call_logger = CallLogger()
anthropic = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# Prospect data indexed by call_sid (populated before Twilio calls back)
_prospect_store: dict[str, dict] = {}


def register_prospect(call_sid: str, prospect: dict):
    """Enregistre les données prospect AVANT que Twilio rappelle /twiml."""
    _prospect_store[call_sid] = prospect


# ---------------------------------------------------------------------------
# HTTP endpoints (appelés par Twilio)
# ---------------------------------------------------------------------------

@app.post("/twiml")
async def twiml_handler(request: Request):
    """
    Retourne le TwiML qui connecte l'appel au Media Stream WebSocket.
    Twilio appelle cet endpoint quand le prospect décroche.
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    answered_by = form.get("AnsweredBy", "human")

    # Messagerie vocale détectée par AMD → raccrocher proprement
    if answered_by in ("machine_start", "machine_end_beep", "machine_end_silence"):
        logger.info(f"[{call_sid}] Voicemail detected — hanging up")
        prospect = _prospect_store.pop(call_sid, {})
        asyncio.create_task(
            call_logger.log(call_sid, prospect, "VOICEMAIL", "Messagerie vocale détectée", "")
        )
        return Response(
            content="<?xml version='1.0'?><Response><Hangup/></Response>",
            media_type="application/xml",
        )

    ws_url = f"wss://{PUBLIC_URL}/media-stream/{call_sid}"
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}">
            <Parameter name="callSid" value="{call_sid}"/>
        </Stream>
    </Connect>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.post("/call-status")
async def call_status(request: Request):
    """Reçoit les mises à jour de statut Twilio (answered, completed, etc.)."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    status = form.get("CallStatus", "")
    duration = int(form.get("CallDuration", 0))
    logger.info(f"Call status: {call_sid} → {status} ({duration}s)")
    return Response(content="OK")


@app.post("/amd-status")
async def amd_status(request: Request):
    """Reçoit le résultat de l'AMD (Answering Machine Detection) asynchrone."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    answered_by = form.get("AnsweredBy", "")
    logger.info(f"AMD: {call_sid} → {answered_by}")
    return Response(content="OK")


# ---------------------------------------------------------------------------
# WebSocket endpoint (Twilio Media Streams)
# ---------------------------------------------------------------------------

@app.websocket("/media-stream/{call_sid}")
async def media_stream_handler(websocket: WebSocket, call_sid: str):
    await websocket.accept()
    prospect = _prospect_store.get(call_sid, {})
    logger.info(f"[{call_sid}] WebSocket opened — prospect: {prospect.get('Account Name', '?')}")

    session = CallSession(websocket, call_sid, prospect)
    try:
        await asyncio.wait_for(session.run(), timeout=MAX_CALL_DURATION)
    except asyncio.TimeoutError:
        logger.warning(f"[{call_sid}] Max call duration reached")
        session.call_result = "TIMEOUT"
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"[{call_sid}] Unexpected error: {e}")
    finally:
        await session.close()
        _prospect_store.pop(call_sid, None)
        logger.info(f"[{call_sid}] Session closed → {session.call_result}")


# ---------------------------------------------------------------------------
# CallSession — orchestration complète d'un appel
# ---------------------------------------------------------------------------

class CallSession:

    def __init__(self, ws: WebSocket, call_sid: str, prospect: dict):
        self.ws = ws
        self.call_sid = call_sid
        self.prospect = prospect
        self.stream_sid: Optional[str] = None

        # Audio queues
        self._audio_to_dg: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._audio_to_twilio: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=500)

        # Transcript pipeline
        self._transcript_queue: asyncio.Queue[str] = asyncio.Queue()

        # Call state
        self.call_result = "NO_ANSWER"
        self.call_notes = ""
        self.callback_date = ""
        self._call_ended = asyncio.Event()
        self._agent_speaking = False
        self._conversation_history: list[dict] = []

        self._http = httpx.AsyncClient(timeout=15.0)
        self._start_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(self):
        tasks = [
            asyncio.create_task(self._twilio_reader(), name="twilio_reader"),
            asyncio.create_task(self._twilio_writer(), name="twilio_writer"),
            asyncio.create_task(self._deepgram_task(), name="deepgram"),
            asyncio.create_task(self._conversation_loop(), name="conversation"),
        ]
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            # Surface any exception from completed tasks
            for task in done:
                if task.exception():
                    logger.error(f"Task {task.get_name()} failed: {task.exception()}")
        finally:
            import time
            duration = int(time.time() - self._start_time) if self._start_time else 0
            await call_logger.log(
                call_sid=self.call_sid,
                prospect=self.prospect,
                outcome=self.call_result,
                notes=self.call_notes,
                transcript=self._get_transcript(),
                duration=duration,
                callback_date=self.callback_date,
            )

    # ------------------------------------------------------------------
    # Task 1 — Twilio reader (inbound audio → Deepgram queue)
    # ------------------------------------------------------------------

    async def _twilio_reader(self):
        import time
        async for raw in self._iter_ws():
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "start":
                self.stream_sid = msg["start"]["streamSid"]
                self._start_time = time.time()
                logger.info(f"[{self.call_sid}] Stream SID: {self.stream_sid}")
                # Greeting asynchrone — ne bloque pas le reader
                asyncio.create_task(self._send_greeting())

            elif event == "media":
                mulaw = base64.b64decode(msg["media"]["payload"])
                # Barge-in : si l'agent parle et que le prospect parle → interrompre
                if self._agent_speaking:
                    self._interrupt_agent()
                try:
                    self._audio_to_dg.put_nowait(mulaw)
                except asyncio.QueueFull:
                    pass  # Drop frame rather than block

            elif event == "stop":
                self._call_ended.set()
                break

    async def _iter_ws(self):
        while not self._call_ended.is_set():
            try:
                yield await self.ws.receive_text()
            except WebSocketDisconnect:
                break

    # ------------------------------------------------------------------
    # Task 2 — Twilio writer (TTS audio → Twilio)
    # ------------------------------------------------------------------

    async def _twilio_writer(self):
        while not self._call_ended.is_set():
            try:
                chunk = await asyncio.wait_for(self._audio_to_twilio.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if chunk is None:
                continue
            if not self.stream_sid:
                continue
            payload = base64.b64encode(chunk).decode()
            await self.ws.send_text(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": payload},
            }))

    # ------------------------------------------------------------------
    # Task 3 — Deepgram STT (WebSocket streaming)
    # ------------------------------------------------------------------

    async def _deepgram_task(self):
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        async with websockets.connect(DEEPGRAM_WS_URL, extra_headers=headers) as dg:

            async def _send():
                while not self._call_ended.is_set():
                    try:
                        chunk = await asyncio.wait_for(self._audio_to_dg.get(), timeout=1.0)
                        await dg.send(chunk)
                    except asyncio.TimeoutError:
                        continue

            async def _recv():
                async for raw in dg:
                    data = json.loads(raw)
                    if data.get("type") != "Results":
                        continue
                    alts = data.get("channel", {}).get("alternatives", [])
                    if not alts:
                        continue
                    text = alts[0].get("transcript", "").strip()
                    if text and data.get("speech_final"):
                        logger.info(f"[{self.call_sid}] Prospect: {text}")
                        await self._transcript_queue.put(text)

            await asyncio.gather(_send(), _recv())

    # ------------------------------------------------------------------
    # Task 4 — Conversation loop (transcript → Claude → Cartesia)
    # ------------------------------------------------------------------

    async def _conversation_loop(self):
        # Wait until the stream is alive
        while not self.stream_sid and not self._call_ended.is_set():
            await asyncio.sleep(0.05)

        while not self._call_ended.is_set():
            try:
                transcript = await asyncio.wait_for(
                    self._transcript_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            self._conversation_history.append({"role": "user", "content": transcript})

            response_text, outcome = await self._call_claude()

            if response_text:
                await self._speak(response_text)

            if outcome:
                self.call_result = outcome.get("outcome", "UNKNOWN")
                self.call_notes = outcome.get("notes", "")
                self.callback_date = outcome.get("callback_date", "")
                self._call_ended.set()

    # ------------------------------------------------------------------
    # Greeting (sent once, right after stream starts)
    # ------------------------------------------------------------------

    async def _send_greeting(self):
        first = self.prospect.get("Contact First Name", "")
        company = self.prospect.get("Account Name", "votre enseigne")

        greeting = (
            f"Bonjour{f' {first}' if first else ''}, je m'appelle Jules, "
            f"je suis un assistant IA de TargetCo. "
            f"Je vous contacte car nous aidons des enseignes comme {company} "
            f"à récupérer jusqu'à 3% du chiffre d'affaires perdu en démarque inconnue "
            f"sans toucher à vos caméras. Vous avez deux minutes ?"
        )
        self._conversation_history.append({"role": "assistant", "content": greeting})
        await self._speak(greeting)

    # ------------------------------------------------------------------
    # Claude Haiku — generate response
    # ------------------------------------------------------------------

    async def _call_claude(self) -> tuple[str, Optional[dict]]:
        system = build_system_prompt(self.prospect)
        try:
            resp = await anthropic.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=150,
                system=system,
                tools=[OUTCOME_TOOL],
                messages=self._conversation_history,
            )
        except Exception as e:
            logger.error(f"Claude error: {e}")
            return "Je suis désolé, pouvez-vous répéter ?", None

        text = ""
        outcome = None

        for block in resp.content:
            if hasattr(block, "text") and block.text:
                text = block.text.strip()
            elif getattr(block, "type", "") == "tool_use" and block.name == "log_call_outcome":
                outcome = block.input

        if text:
            self._conversation_history.append({"role": "assistant", "content": text})

        logger.info(f"[{self.call_sid}] Agent: {text or '[tool call]'}")
        return text, outcome

    # ------------------------------------------------------------------
    # Cartesia TTS — synthesize and stream to Twilio
    # ------------------------------------------------------------------

    async def _speak(self, text: str):
        if not text or self._call_ended.is_set():
            return

        self._agent_speaking = True
        try:
            async with self._http.stream(
                "POST",
                CARTESIA_TTS_URL,
                headers={
                    "X-API-Key": CARTESIA_API_KEY,
                    "Cartesia-Version": "2024-06-10",
                    "Content-Type": "application/json",
                },
                json={
                    "model_id": "sonic-multilingual",
                    "transcript": text,
                    "voice": {"mode": "id", "id": CARTESIA_VOICE_ID},
                    "output_format": {
                        "container": "raw",
                        "encoding": "pcm_s16le",
                        "sample_rate": 8000,
                    },
                    "language": "fr",
                },
            ) as response:
                if response.status_code != 200:
                    logger.error(f"Cartesia error {response.status_code}")
                    return
                async for chunk in response.aiter_bytes(chunk_size=320):
                    if not chunk or not self._agent_speaking:
                        break
                    mulaw = self._pcm_to_mulaw(chunk)
                    try:
                        self._audio_to_twilio.put_nowait(mulaw)
                    except asyncio.QueueFull:
                        pass
        except Exception as e:
            logger.error(f"Cartesia speak error: {e}")
        finally:
            self._agent_speaking = False

    def _pcm_to_mulaw(self, pcm_s16le: bytes) -> bytes:
        """Convertit PCM signed 16-bit LE → G.711 μ-law (requis par Twilio)."""
        if audioop is not None:
            return audioop.lin2ulaw(pcm_s16le, 2)
        # Fallback si audioop manquant : retourne le PCM brut (dégradé)
        return pcm_s16le

    # ------------------------------------------------------------------
    # Barge-in
    # ------------------------------------------------------------------

    def _interrupt_agent(self):
        """Interrompt immédiatement la synthèse vocale en cours."""
        self._agent_speaking = False
        # Vider la queue audio pour arrêter la lecture côté Twilio
        while not self._audio_to_twilio.empty():
            try:
                self._audio_to_twilio.get_nowait()
            except asyncio.QueueEmpty:
                break

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_transcript(self) -> str:
        lines = []
        for msg in self._conversation_history:
            label = "Agent" if msg["role"] == "assistant" else "Prospect"
            lines.append(f"{label}: {msg['content']}")
        return "\n".join(lines)

    async def close(self):
        await self._http.aclose()
        end_call(self.call_sid)
