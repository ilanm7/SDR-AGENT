"""
Module de recherche web — utilise ddgs (successeur officiel de duckduckgo_search).
"""
from ddgs import DDGS


def search_web(query: str, max_results: int = 8) -> str:
    """
    Effectue une recherche web et retourne les résultats formatés.
    Utilisé par l'agent pour l'enrichissement prospect (Skill 1).
    max_results augmenté à 8 pour donner plus de chance de trouver des contacts.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"Aucun résultat trouvé pour : « {query} »"

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"[Résultat {i}]\n"
                f"Titre : {r.get('title', 'Sans titre')}\n"
                f"Résumé : {r.get('body', '')}\n"
                f"Source : {r.get('href', '')}"
            )
        return "\n\n---\n\n".join(lines)

    except Exception as e:
        return f"Erreur lors de la recherche « {query} » : {str(e)}"
