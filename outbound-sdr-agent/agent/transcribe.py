"""
Skill de transcription audio/vidéo — faster-whisper (gratuit, offline)
Supporte : MP3, MP4, M4A, WAV, OGG, FLAC, WEBM
Multilingue : FR, EN, ES, IT, DE, PT (auto-détection)
Usage :
    from agent.transcribe import transcribe_file, transcribe_drive_file
"""

import os
import time
import re
import tempfile
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────
MODEL_SIZE   = "small"          # "small" = rapide (< 2 min/call), "medium" = meilleur
COMPUTE_TYPE = "int8"           # Max vitesse CPU
DEVICE       = "cpu"
CPU_THREADS  = 4                # Sweet spot pour i7
BEAM_SIZE    = 5
CACHE_DIR    = os.path.expanduser("~/.cache/faster-whisper")
# ──────────────────────────────────────────────────────────────────────────

_model = None  # singleton — chargé une seule fois


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        print(f"[Transcribe] Chargement modèle '{MODEL_SIZE}' (1ère fois = téléchargement)...")
        _model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            cpu_threads=CPU_THREADS,
            download_root=CACHE_DIR,
        )
        print("[Transcribe] Modèle prêt ✓")
    return _model


def transcribe_file(audio_path: str, language: str = None) -> dict:
    """
    Transcrit un fichier audio/vidéo local.

    Args:
        audio_path : chemin vers MP3, MP4, M4A, WAV, etc.
        language   : code langue ('fr', 'en', 'es') ou None pour auto-detect

    Returns:
        {
          "text"     : transcription complète,
          "language" : langue détectée,
          "segments" : [{"start", "end", "text"}, ...],
          "duration" : durée en secondes,
          "elapsed"  : temps de traitement en secondes
        }
    """
    model = _get_model()

    t0 = time.time()
    segments_gen, info = model.transcribe(
        audio_path,
        beam_size=BEAM_SIZE,
        language=language,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    segments = list(segments_gen)  # flush le générateur paresseux
    elapsed = time.time() - t0

    duration = segments[-1].end if segments else 0
    full_text = " ".join(s.text.strip() for s in segments)

    return {
        "text":     full_text,
        "language": info.language,
        "duration": round(duration, 1),
        "elapsed":  round(elapsed, 1),
        "rtf":      round(duration / elapsed, 1) if elapsed > 0 else 0,
        "segments": [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
        ],
    }


def transcribe_drive_file(file_id: str, language: str = None) -> dict:
    """
    Télécharge un fichier Google Drive par son ID et le transcrit.
    Le fichier doit être partagé "Tous ceux qui ont le lien".

    Args:
        file_id  : ID du fichier Drive (ex: '1BjFZSLU8SJ2yL5y8iXqsSwwmsaRC2ptn')
        language : code langue ou None

    Returns:
        dict transcription (voir transcribe_file)
    """
    import gdown

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, f"{file_id}.audio")
        url = f"https://drive.google.com/uc?id={file_id}"

        print(f"[Drive] Téléchargement du fichier {file_id}...")
        try:
            gdown.download(url, out_path, quiet=False, fuzzy=True)
        except Exception as e:
            return {"error": f"Échec téléchargement Drive : {e}"}

        if not os.path.exists(out_path):
            return {"error": "Fichier non téléchargé — vérifier partage public"}

        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"[Drive] Téléchargé ({size_mb:.1f} MB) → transcription...")

        result = transcribe_file(out_path, language=language)
        result["file_id"] = file_id
        return result


def transcribe_and_analyze(audio_path: str, language: str = None) -> str:
    """
    Transcrit ET analyse un call Aircall.
    Retourne un rapport structuré utilisable directement par l'agent SDR.
    """
    result = transcribe_file(audio_path, language=language)

    if "error" in result:
        return f"Erreur transcription : {result['error']}"

    text = result["text"]
    lang = result["language"]
    duration_min = result["duration"] / 60

    # Analyse basique du call
    rapport = f"""
═══════════════════════════════════════════════════
TRANSCRIPTION CALL — {os.path.basename(audio_path)}
Langue : {lang.upper()} | Durée : {duration_min:.1f} min | Traitement : {result['elapsed']}s ({result['rtf']}x temps réel)
═══════════════════════════════════════════════════

TRANSCRIPTION COMPLÈTE :
{text}

═══════════════════════════════════════════════════
ANALYSE SDR :
{_analyze_call(text, lang)}
═══════════════════════════════════════════════════
"""
    return rapport.strip()


def _analyze_call(text: str, lang: str) -> str:
    """Analyse rapide du contenu d'un call pour extraction SDR."""
    text_lower = text.lower()

    # Détection objections courantes
    objection_keywords = {
        "fr": ["pas intéressé", "on a déjà", "trop cher", "pas le moment", "rappeler", "budget",
               "pas de problème de vol", "déjà des caméras"],
        "en": ["not interested", "already have", "too expensive", "budget", "not now",
               "call back", "no theft problem", "already cameras"],
        "es": ["no me interesa", "ya tenemos", "demasiado caro", "presupuesto", "no es el momento"],
    }

    keywords = objection_keywords.get(lang, objection_keywords["en"])
    found_objections = [kw for kw in keywords if kw in text_lower]

    # Durée et estimation
    word_count = len(text.split())

    analysis_lines = [
        f"• Mots transcrits    : {word_count}",
        f"• Objections détectées : {', '.join(found_objections) if found_objections else 'aucune détectée'}",
        f"• Ton général        : {'positif' if not found_objections else 'résistance prospect'}",
    ]

    return "\n".join(analysis_lines)


# ── CLI direct ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m agent.transcribe <fichier_audio>          # fichier local")
        print("  python -m agent.transcribe drive:<FILE_ID>          # fichier Google Drive")
        print("  python -m agent.transcribe <fichier> --lang fr      # forcer la langue")
        sys.exit(1)

    source = sys.argv[1]
    lang = None
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        lang = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    if source.startswith("drive:"):
        file_id = source.replace("drive:", "")
        result = transcribe_drive_file(file_id, language=lang)
        print(result.get("text", result.get("error")))
    else:
        rapport = transcribe_and_analyze(source, language=lang)
        print(rapport)

        # Sauvegarde
        out = Path(source).stem + "_transcript.txt"
        Path(out).write_text(rapport, encoding="utf-8")
        print(f"\n✓ Sauvegardé : {out}")
