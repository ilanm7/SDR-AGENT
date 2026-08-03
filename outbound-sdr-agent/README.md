# Outbound SDR Agent

Agent de prospection commerciale B2B construit avec Claude (API Anthropic),
initialement développé comme étude de cas pour une candidature dans une
scale-up sales-tech. Il automatise une partie du travail d'un SDR (Sales
Development Representative) : trouver des prospects, préparer les appels,
suivre les conversations, et gérer une partie du contact client.

## À quoi ça sert

Un SDR passe énormément de temps sur des tâches répétitives avant même de
parler à un prospect : chercher qui contacter dans une entreprise, préparer
un angle d'appel pertinent, noter ce qui s'est dit, relancer au bon moment.
Ce projet automatise ce pipeline de bout en bout avec un agent Claude qui
sait exécuter 6 tâches (skills) :

1. **Enrichissement de prospect** — à partir d'un nom d'entreprise et d'une
   ville, l'agent fait des recherches web ciblées (site, actualités,
   LinkedIn, registres d'entreprises) pour identifier le bon interlocuteur
   et des informations spécifiques et vérifiables sur ce prospect précis.
2. **Génération de script d'appel** — à partir de la fiche prospect,
   génère une accroche personnalisée et un script d'appel, pas un pitch
   générique.
3. **Coaching post-appel** — transcrit et analyse un enregistrement
   d'appel pour identifier ce qui a fonctionné ou non.
4. **Message de relance** — rédige un message de suivi personnalisé après
   un appel ou un échange.
5. **Dashboard manager** — agrège les résultats de l'équipe (non inclus
   dans ce repo, voir plus bas).
6. **Prospection autonome** — enchaîne recherche, enrichissement et
   génération de script sans intervention manuelle entre chaque étape.

Au-dessus de ce cœur d'agent, trois canaux d'interaction :

- **Bot Telegram** (`bot/`) — interface conversationnelle pour qu'un SDR
  déclenche ces tâches depuis son téléphone, en mode guidé ou en texte
  libre.
- **Agent vocal sortant** (`voice_agent/`) — appelle réellement les
  prospects via Twilio, transcrit en direct (Deepgram), répond avec une
  voix synthétique (Cartesia), et journalise chaque résultat d'appel
  (rendez-vous pris, refus, à rappeler...), avec vérification légale des
  horaires d'appel et gestion des opt-out.
- **Réponse automatique réseaux sociaux** (`social/`) — génère des
  réponses aux commentaires et messages entrants sur Instagram/Facebook,
  dans un ton de marque cohérent.

## Architecture

- `agent/` — cœur de l'agent : recherche web, qualification, génération
  de scripts via l'API Claude (`sdr_agent.py`, `web_search.py`,
  `transcribe.py`)
- `bot/` — bot Telegram, machine à états pour guider un SDR dans les
  différents modes (enrichir, script, coaching, suivi, semi-auto)
- `social/` — réponse automatique aux messages entrants (Meta/Instagram)
- `voice_agent/` — agent vocal sortant (Twilio + Cartesia + Deepgram) :
  composition d'appels, scripts vocaux, vérifications légales, journalisation
- `data/` — exemple de données factices (`sample_prospects.csv`, pharmacies
  et enseignes fictives) et utilitaires d'import/traitement CSV. Aucune
  donnée réelle de prospect, d'appel ou de performance SDR n'est incluse
  dans ce repo.

## Stack

Python, API Anthropic (Claude), Telegram Bot API, Twilio, Deepgram
(transcription), Cartesia (voix), Meta Graph API.

## Configuration

Copier `.env.example` en `.env` et renseigner les clés nécessaires
(Anthropic, Telegram, Twilio, Deepgram, Cartesia, Meta). Deux
environnements virtuels séparés existaient à l'origine (agent principal
et pipeline vocal) ; voir `requirements.txt` et `requirements_voice.txt`.

```
python main.py                        # mode chat interactif
python main.py --bot                  # bot Telegram
python main.py --batch prospects.csv  # traitement en lot d'un CSV
python start_voice.py --campaign data/sample_prospects.csv
```

## Notes importantes

- Les prompts produit (`agent/sdr_agent.py`, `social/responder.py`,
  `voice_agent/voice_prompt.py`) contiennent des **placeholders
  génériques** ("TargetCo", arguments produit fictifs) à remplacer par
  votre propre positionnement avant usage réel — ne pas y insérer de
  vrais noms de clients ou de vraies statistiques d'une entreprise tierce.
- Le tableau de bord de suivi de performance (dashboard SDR) existait dans
  la version originale mais contenait des données de coaching et des noms
  d'agents réels codés en dur ; il n'est pas inclus ici et devrait être
  reconstruit avec des données entièrement synthétiques avant publication.

## Known limitations & roadmap

- Le pipeline vocal (`voice_agent/`) nécessite des comptes tiers payants
  (Twilio, Deepgram, Cartesia) pour tourner de bout en bout.
- La couverture de tests est concentrée sur la couche de traitement de
  données ; l'orchestrateur (`sdr_agent.py`) n'en a pas encore.
