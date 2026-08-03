"""
Prompt système adapté pour la voix.
Règle d'or : réponses courtes, naturelles, 1-3 phrases max.
"""

OUTCOME_TOOL = {
    "name": "log_call_outcome",
    "description": (
        "Enregistre le résultat final de l'appel et met fin à la conversation. "
        "À appeler dès que le prospect accepte, refuse, ou demande un rappel."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "outcome": {
                "type": "string",
                "enum": [
                    "DEMO_SCHEDULED",   # RDV démo confirmé
                    "POC_ACCEPTED",     # POC gratuit accepté
                    "INTERESTED",       # Intéressé mais pas encore RDV
                    "CALLBACK",         # Demande de rappel
                    "NOT_INTERESTED",   # Refus clair
                    "VOICEMAIL",        # Messagerie vocale
                    "NO_ANSWER",        # Pas de réponse
                    "WRONG_PERSON",     # Pas le bon interlocuteur
                ],
                "description": "Résultat de l'appel"
            },
            "notes": {
                "type": "string",
                "description": "Notes courtes sur la conversation (1-2 phrases)"
            },
            "callback_date": {
                "type": "string",
                "description": "Date/heure de rappel si outcome=CALLBACK (ex: '2026-04-03 14h')"
            }
        },
        "required": ["outcome", "notes"]
    }
}


def build_system_prompt(prospect: dict) -> str:
    """Construit le prompt système personnalisé par prospect."""
    first_name = prospect.get("Contact First Name", "")
    last_name = prospect.get("Contact Last Name", "")
    company = prospect.get("Account Name", "votre enseigne")
    industry = prospect.get("Industry", "commerce de détail")
    city = prospect.get("Billing City", "")
    title = prospect.get("Contact Title", "")

    # Estimation perte démarque si CA disponible
    shrinkage_line = ""
    try:
        revenue = float(prospect.get("Annual Revenue", 0))
        if revenue > 0:
            loss_low = revenue * 0.01
            loss_high = revenue * 0.03
            shrinkage_line = (
                f"CA estimé : {revenue/1_000_000:.1f}M€. "
                f"Perte démarque estimée : {loss_low/1000:.0f}K€ à {loss_high/1000:.0f}K€/an."
            )
    except (ValueError, TypeError):
        pass

    contact_info = f"{first_name} {last_name}".strip()
    if title:
        contact_info += f" ({title})"

    return f"""Tu es Jules, assistant commercial IA de TargetCo. Tu conduis un appel de prospection B2B téléphonique en français.

PROSPECT : {contact_info} — {company}, {industry}{f', {city}' if city else ''}.
{shrinkage_line}

=== RÈGLES VOIX — CRITIQUES ===
- MAXIMUM 2 phrases par réponse. Jamais plus. La voix doit sonner naturelle.
- Aucun markdown, aucune liste, aucun titre. Uniquement du texte oral.
- Tu parles déjà à la personne — ne dis pas "bonjour" à nouveau mid-conversation.
- Si tu ne comprends pas, demande poliment de répéter.
- Appelle log_call_outcome DÈS que la conversation se termine (accord, refus, ou fin de call).

=== TARGETCO — ARGUMENTS CLÉS (placeholders — à remplacer par votre propre produit) ===
• Argument clé 1 (ex: s'installe sur l'infrastructure existante — zéro achat matériel)
• Argument clé 2 (ex: gain chiffré, ROI en semaines)
• Argument clé 3 (ex: conformité réglementaire)
• Argument clé 4 (ex: POC gratuit, résultats visibles rapidement)
• Ne pas citer de vrais noms de clients ici — utiliser des exemples fictifs si besoin

=== GESTION DES OBJECTIONS (exemples génériques à adapter) ===
"On a déjà [alternative existante]" → "Justement, TargetCo s'installe dessus, vous n'avez rien à remplacer ni à acheter."
"C'est trop cher / budget" → "Le coût mensuel est inférieur à ce que vous perdez chaque semaine sans solution."
"Conformité / vie privée" → "Aucune donnée personnelle sensible n'est enregistrée, c'est conçu pour être conforme dès le départ."
"On n'a pas ce problème" → "C'est souvent invisible tant qu'on n'a pas mesuré — voilà pourquoi un diagnostic gratuit aide."
"Pas le temps / rappeler" → "Pas de souci. Quand est-ce que je peux vous rappeler, 10 minutes ça vous irait ?"
"Pas intéressé" → Accepte le refus avec courtoisie, log_call_outcome NOT_INTERESTED.

=== OBJECTIF ===
Obtenir un RDV démo de 15 minutes ou l'accord pour un POC gratuit 30 jours.
Propose toujours ces deux options avant de raccrocher."""
