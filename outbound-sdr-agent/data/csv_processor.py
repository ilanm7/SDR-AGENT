"""
Processeur de fichiers Salesforce CSV.
Lit les prospects et les formate pour l'agent SDR.
"""
import pandas as pd
from pathlib import Path


def load_prospects(csv_path: str) -> list[dict]:
    """
    Charge un export Salesforce CSV et retourne une liste de dicts normalisés.
    Compatible avec les exports Salesforce standard.
    """
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    prospects = []
    for _, row in df.iterrows():
        prospect = {
            "account_name": _get(row, ["Account Name", "Compte", "Enseigne"]),
            "contact_name": _build_contact_name(row),
            "title": _get(row, ["Contact Title", "Titre", "Fonction"]),
            "phone": _get(row, ["Phone", "Téléphone", "Mobile"]),
            "email": _get(row, ["Email", "E-mail"]),
            "address": _get(row, ["Billing Street", "Adresse"]),
            "city": _get(row, ["Billing City", "Ville"]),
            "postal_code": _get(row, ["Billing Postal Code", "Code postal"]),
            "industry": _get(row, ["Industry", "Secteur", "Type de commerce"]),
            "num_locations": _get(row, ["Number of Locations", "Nb points de vente"]),
            "annual_revenue": _get(row, ["Annual Revenue", "Chiffre d'affaires"]),
            "description": _get(row, ["Description", "Notes"]),
        }
        prospects.append(prospect)
    return prospects


def format_prospect_for_agent(prospect: dict) -> str:
    """
    Formate un prospect en message naturel pour l'agent SDR.
    C'est ce texte qui est envoyé comme premier message à l'agent.
    """
    lines = [f"Enrichis ce prospect et génère sa fiche :"]
    if prospect.get("account_name"):
        lines.append(f"- Enseigne : {prospect['account_name']}")
    if prospect.get("contact_name"):
        lines.append(f"- Contact : {prospect['contact_name']}")
    if prospect.get("title"):
        lines.append(f"- Fonction : {prospect['title']}")
    if prospect.get("city"):
        city_info = prospect["city"]
        if prospect.get("postal_code"):
            city_info += f" ({prospect['postal_code']})"
        lines.append(f"- Ville : {city_info}")
    if prospect.get("address"):
        lines.append(f"- Adresse : {prospect['address']}")
    if prospect.get("industry"):
        lines.append(f"- Secteur : {prospect['industry']}")
    if prospect.get("num_locations"):
        lines.append(f"- Nombre de points de vente : {prospect['num_locations']}")
    if prospect.get("annual_revenue"):
        lines.append(f"- CA estimé : {prospect['annual_revenue']}€")
    if prospect.get("description"):
        lines.append(f"- Notes : {prospect['description']}")

    lines.append("\nUne fois la fiche prête, génère également le script d'appel personnalisé.")
    return "\n".join(lines)


def _get(row, keys: list) -> str:
    """Essaie plusieurs noms de colonnes possibles (Salesforce FR/EN)."""
    for key in keys:
        if key in row and pd.notna(row[key]):
            return str(row[key]).strip()
    return ""


def _build_contact_name(row) -> str:
    first = _get(row, ["Contact First Name", "Prénom"])
    last = _get(row, ["Contact Last Name", "Nom"])
    if first and last:
        return f"{first} {last}"
    return _get(row, ["Contact Name", "Nom complet", "Full Name"])
