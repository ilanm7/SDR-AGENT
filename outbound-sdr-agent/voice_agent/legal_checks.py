"""
Vérifications de conformité légale pour les appels automatisés en France.

Références :
- Code de la consommation L. 223-1 (Bloctel, horaires)
- RGPD / CNIL — base légale intérêt légitime B2B
- Règles horaires : lun-ven 8h-20h, sam 8h-19h, dim/fériés interdit
"""
from datetime import datetime
from pathlib import Path
import json

# Jours fériés France 2026
_JOURS_FERIES_2026 = {
    "2026-01-01",  # Jour de l'An
    "2026-04-06",  # Lundi de Pâques
    "2026-05-01",  # Fête du Travail
    "2026-05-08",  # Victoire 1945
    "2026-05-14",  # Ascension
    "2026-05-25",  # Lundi de Pentecôte
    "2026-07-14",  # Fête Nationale
    "2026-08-15",  # Assomption
    "2026-11-01",  # Toussaint
    "2026-11-11",  # Armistice
    "2026-12-25",  # Noël
}

# Fichier opt-out local (numéros à ne jamais rappeler)
_OPTOUT_FILE = Path(__file__).parent.parent / "data" / "optout.json"


def is_legal_call_time(dt: datetime | None = None) -> tuple[bool, str]:
    """
    Vérifie si l'heure actuelle est légalement autorisée pour un appel B2B France.
    Retourne (autorisé, raison).
    """
    if dt is None:
        dt = datetime.now()

    date_str = dt.strftime("%Y-%m-%d")
    if date_str in _JOURS_FERIES_2026:
        return False, f"Jour férié ({date_str})"

    weekday = dt.weekday()  # 0=lun, 6=dim
    hour = dt.hour

    if weekday == 6:
        return False, "Dimanche — appels interdits"
    if weekday == 5:  # Samedi
        if not (8 <= hour < 19):
            return False, "Samedi hors horaires (8h–19h)"
    else:  # Lundi–Vendredi
        if not (8 <= hour < 20):
            return False, "Hors horaires semaine (8h–20h)"

    return True, "OK"


def next_legal_slot(dt: datetime | None = None) -> datetime:
    """Retourne la prochaine fenêtre légale d'appel."""
    from datetime import timedelta

    if dt is None:
        dt = datetime.now()

    # Essayer heure par heure sur 7 jours max
    for _ in range(7 * 24):
        ok, _ = is_legal_call_time(dt)
        if ok:
            return dt
        dt = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    raise RuntimeError("Impossible de trouver une fenêtre légale dans les 7 prochains jours")


def is_opted_out(phone: str) -> bool:
    """Vérifie si le numéro est dans la liste opt-out locale."""
    if not _OPTOUT_FILE.exists():
        return False
    try:
        data = json.loads(_OPTOUT_FILE.read_text())
        return _normalize_phone(phone) in {_normalize_phone(p) for p in data}
    except (json.JSONDecodeError, OSError):
        return False


def add_to_optout(phone: str):
    """Ajoute un numéro à la liste opt-out locale."""
    existing: list = []
    if _OPTOUT_FILE.exists():
        try:
            existing = json.loads(_OPTOUT_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    normalized = _normalize_phone(phone)
    if normalized not in existing:
        existing.append(normalized)
        _OPTOUT_FILE.write_text(json.dumps(existing, indent=2))


def _normalize_phone(phone: str) -> str:
    """Normalise un numéro : garde uniquement les chiffres + '+'."""
    return "".join(c for c in phone if c.isdigit() or c == "+")
