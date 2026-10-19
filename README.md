# Customer Relations WhatsApp Bot

A self-hosted, multi-branch **WhatsApp Business CRM** with an AI assistant, payments, support
ticketing, and a role-based admin dashboard. Built on the official **Meta WhatsApp Cloud API**.

## Features

**AI Assistant (LangChain + Gemini/DeepSeek)**
- Per-user conversational agents with sliding context window and automatic history compaction
- Tool-calling agent grounded in your live business data — never guesses prices or locations
- Location-aware branch recommendation ("which branch is closest to me?")
- RAG knowledge base (ChromaDB) over documents & structured Q&A uploaded from the dashboard

**Commerce & Operations**
- Package catalogue with categories, schedules, durations, and pricing
- Interactive WhatsApp Flows for registration and support tickets (with in-chat fallback)
- Paystack payment integration with automatic verification, webhooks, and WhatsApp confirmations
- Add-on / pass-through fee management (mandatory vs optional)

**Admin Dashboard**
- Role-Based Access Control: Super Admin (full control) vs Branch Admin (scoped, read-mostly)
- Live agent chat — pause the AI and take over a conversation directly from the dashboard
- AI lead scoring (hot / warm / cold) and conversation summaries per chat
- Marketing insights report generated from recent message logs
- Targeted broadcasts filtered by package or branch
- Manage branches, packages, fees, knowledge base, users, registrations, and tickets

## Tech Stack

| Layer | Technology |
|---|---|
| API / Server | FastAPI + Uvicorn |
| AI | LangChain, Google Gemini (LLM + embeddings) or DeepSeek (OpenAI-compatible) |
| Vector store | ChromaDB |
| Database | SQLite (SQLAlchemy-style repository layer) |
| Messaging | Meta WhatsApp Cloud API (webhooks + messages + Flows) |
| Payments | Paystack |
| Frontend | Vanilla JS + HTML/CSS dashboard (served by FastAPI), Chart.js |

## Project Structure

```
├── webhook_server.py     # FastAPI app: WhatsApp webhooks, admin API, dashboard
├── session_manager.py    # Per-user agent sessions, context compaction
├── agent.py              # LangChain agent builder + LLM factory (Gemini/DeepSeek)
├── repository.py         # Data access layer (SQLite + JSON stores)
├── database.py           # Schema, seeding, auth helpers
├── rag_engine.py         # ChromaDB ingestion & retrieval
├── workers.py            # Background session cleanup
├── tools/                # Agent tools (branches, packages, fees, KB, tickets, ...)
├── static/               # Admin dashboard (HTML/JS/CSS)
└── .env.example          # Environment configuration template
```

## Setup

### 1. Prerequisites
- Python 3.10+
- A [Meta Developer App](https://developers.facebook.com/) with the **WhatsApp** product enabled
- A Google Gemini API key (or a DeepSeek API key)
- A [Paystack](https://paystack.com/) account (optional — set `USE_PAYSTACK=false` to disable)

### 2. Install

```bash
git clone https://github.com/HaroldDagadu/customer-relations-whatsapp-bot.git
cd customer-relations-whatsapp-bot
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Then fill in your keys:

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini API key (LLM + embeddings) |
| `LLM_PROVIDER` | `gemini` (default) or `deepseek` |
| `DEEPSEEK_API_KEY` | Only if using DeepSeek |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Any string — must match the one in your Meta webhook config |
| `WHATSAPP_API_TOKEN` | Permanent system-user token from Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | Your WhatsApp business phone number ID |
| `PAYSTACK_SECRET_KEY` / `PAYSTACK_PUBLIC_KEY` | Paystack credentials |
| `USE_PAYSTACK` | `true` / `false` |
| `REGISTRATION_FLOW_ID` / `TICKET_FLOW_ID` | WhatsApp Flow IDs (leave blank + `DISABLE_WHATSAPP_FLOWS=true` to use in-chat fallback forms) |

### 4. Run

```bash
uvicorn webhook_server:app --reload
```

Or on Windows: double-click `start_server.bat`.

- Dashboard: `http://localhost:8000/`
- WhatsApp webhook URL (set in Meta dashboard): `https://<your-domain>/webhook`

> **Default admin credentials:** `admin` / `admin123` — **change this immediately** after first login.

### 5. First-run data

On first start the system seeds placeholder branches, packages, and fees. Replace them with your
real data from the dashboard (**Branches**, **Packages**, **Add-On Fees** panels), or by editing
the generated `branches.json` / `packages.json` / `fees.json` files.

## Customizing the Assistant

The agent's behavior is defined by `DEFAULT_SYSTEM_PROMPT` in `session_manager.py` and the tool
docstrings in `tools/`. Adapt the wording, categories, and guardrails to your business domain.

## Notes

- All user data (chats, registrations, documents) is stored locally in `whatsapp.db`, `chroma_db/`,
  and `uploads/` — none of it is sent anywhere except your configured LLM/WhatsApp/Paystack providers.
- Meta charges per-message fees for the WhatsApp Business API; those are billed by Meta directly.

## License

All rights reserved. Contact the author before reusing this codebase.
