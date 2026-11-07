# Outbound SDR Agent

A B2B outbound sales agent built with Claude (Anthropic API), originally
developed as a case study for a job application at a sales-tech scale-up.
It automates a large part of what a Sales Development Representative (SDR)
does day to day: finding prospects, preparing calls, running the
conversation, and handling part of the customer contact.

## What it does

Most of an SDR's time before ever talking to a prospect goes into
repetitive work: finding the right person to contact at a company,
preparing a relevant angle for the call, taking notes on what was said,
following up at the right moment. This project automates that pipeline
end to end with a Claude agent that handles 6 skills:

1. **Prospect enrichment** — given a company name and city, the agent
   runs targeted web searches (company site, news, LinkedIn, business
   registries) to identify the right contact and specific, verifiable
   facts about that exact prospect.
2. **Call script generation** — turns the prospect sheet into a
   personalized opening line and call script, not a generic pitch.
3. **Post-call coaching** — transcribes and analyzes a call recording to
   identify what worked and what didn't.
4. **Follow-up message** — writes a personalized follow-up after a call
   or exchange.
5. **Manager dashboard** — aggregates team results (not included in this
   repo, see below).
6. **Autonomous prospecting** — chains research, enrichment, and script
   generation without manual intervention between steps.

On top of this core agent, three interaction channels:

- **Telegram bot** (`bot/`) — a conversational interface so an SDR can
  trigger these tasks from their phone, either guided or in free text.
- **Outbound voice agent** (`voice_agent/`) — actually calls prospects via
  Twilio, transcribes live (Deepgram), replies with a synthetic voice
  (Cartesia), and logs every call outcome (meeting booked, refusal,
  callback...), with legal call-time checks and opt-out handling.
- **Social media auto-responder** (`social/`) — generates replies to
  incoming comments and messages on Instagram/Facebook, in a consistent
  brand tone.

## Architecture

- `agent/` — the agent's core: web search, qualification, script
  generation via the Claude API (`sdr_agent.py`, `web_search.py`,
  `transcribe.py`)
- `bot/` — Telegram bot, a state machine that guides an SDR through the
  different modes (enrich, script, coaching, follow-up, semi-auto)
- `social/` — auto-replies to incoming messages (Meta/Instagram)
- `voice_agent/` — outbound voice agent (Twilio + Cartesia + Deepgram):
  call dialing, voice scripts, legal checks, logging
- `data/` — sample fictional data (`sample_prospects.csv`, made-up
  pharmacies and retail chains) and CSV import/processing utilities. No
  real prospect, call, or SDR performance data is included in this repo.

## Stack

Python, Anthropic API (Claude), Telegram Bot API, Twilio, Deepgram
(transcription), Cartesia (voice), Meta Graph API.

## Setup

Copy `outbound-sdr-agent/.env.example` to `outbound-sdr-agent/.env` and fill in the required keys (Anthropic,
Telegram, Twilio, Deepgram, Cartesia, Meta). The original project used two
separate virtual environments (main agent and voice pipeline); see
`requirements.txt` and `requirements_voice.txt`.

```
python main.py                        # interactive chat mode
python main.py --bot                  # Telegram bot
python main.py --batch prospects.csv  # batch-process a CSV
python start_voice.py --campaign data/sample_prospects.csv
```

## Notes

- The product prompts (`agent/sdr_agent.py`, `social/responder.py`,
  `voice_agent/voice_prompt.py`) contain **generic placeholders**
  ("TargetCo", fictional product claims) meant to be replaced with your
  own positioning before real use. Do not insert real client names or
  real third-party statistics there.
- The performance dashboard existed in the original version but had real
  agent names and coaching data hardcoded into it. It's not included here
  and would need to be rebuilt with fully synthetic data before
  publishing.

## Known limitations & roadmap

- The voice pipeline (`voice_agent/`) requires paid third-party accounts
  (Twilio, Deepgram, Cartesia) to run end to end.
- There are no automated tests yet.
