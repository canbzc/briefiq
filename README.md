# BriefIQ

An AI-powered freelance brief analyzer. Paste any client brief and get instant risk analysis, pricing guidance, and a tailored proposal — in seconds.

Built with Flask and Groq (Llama 3.3 70B).

## Features

- **Requirements extraction** — project type, features, budget, deadline, tech stack
- **Risk analysis** — low/medium/high risk, red flags (Low Budget, Tight Budget, Tight Deadline, Unclear Requirements)
- **Proposal strategy** — market rate comparison, suggested price range, hourly equivalent, proposal tone
- **Should I Apply? score** — 0–100 score based on budget fit, deadline, clarity, and risk
- **Brief Gaps** — proactive warnings about missing info (no budget, no deadline, vague scope)
- **Cover letter generator** — ready-to-use Upwork cover letter (EN/TR)
- **Negotiation script** — for medium/high risk briefs, a polite counter-offer message (EN/TR)
- **Hourly rate calculator** — input your rate, see if the budget works for you
- **Compare two briefs** — analyze side by side, get a winner recommendation
- **Analysis history** — SQLite-backed, last 20 analyses saved and reloadable
- **Application tracking** — mark analyses as Applied / Won / Lost
- **Stats page** — win rate, avg apply score, best project type
- **PDF & text export** — export full analysis as PDF or plain text
- **Auth system** — register/login, each user sees only their own data

## Tech Stack

- **Backend:** Python, Flask, Flask-Login, Groq API (Llama 3.3 70B)
- **Frontend:** Vanilla JS, no framework
- **Database:** SQLite
- **PDF:** jsPDF (CDN)

## Setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/briefiq.git
cd briefiq
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file in the root:

```
GROQ_API_KEY=your_groq_api_key_here
SECRET_KEY=your_secret_key_here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

### 3. Run

```bash
python app.py
```

Open `http://localhost:5000`

## Agent Architecture

```
Brief Input
    │
    ▼
RequirementsAgent  →  extracts structured data (project type, budget, features...)
    │
    ▼
RiskAgent          →  detects red flags, computes risk level deterministically
    │
    ▼
ProposalAgent      →  market rate lookup, price suggestion, apply score, brief gaps
    │
    ▼
CoverLetterAgent   →  on demand, EN or TR
NegotiationAgent   →  on demand, only for medium/high risk
```

Key design decision: **pricing and risk logic is deterministic Python** (not LLM). LLM is only used for generating readable text. This makes the tool fast and consistent.

## Market Data

Prices based on Upwork 2024–2025 data:

| Project Type | Price Range | Timeline |
|---|---|---|
| Simple landing page | $50–$300 | 1–5 days |
| Custom landing page | $200–$800 | 3–10 days |
| Advanced landing page | $500–$2,000 | 7–21 days |
| E-commerce (Shopify/WC) | $300–$1,500 | 7–30 days |
| Mobile app | $1,000–$5,000 | 30–60 days |
| Logo & branding | $100–$1,000 | 3–14 days |
| Dashboard / admin panel | $500–$5,000 | 14–60 days |

## License

MIT
