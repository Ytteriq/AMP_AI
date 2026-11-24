# AI_REEL – AI Marketing Report Generation Platform

A professional, enterprise-grade AI-powered **Marketing Report Generation Platform** engineered specifically for digital marketing agencies.

The platform eliminates the conversational chatbot experience in favor of an **executive SaaS analytics and reporting interface**. Agencies can select any client, choose from 7 specialized report types, set customizable reporting periods, and instantly generate client-ready, mathematically verified reports with executive summaries, campaign rankings, creative observations, and evidence-backed recommendations.

---

## 1. Centralized System Architecture

```text
Agency User / Stakeholder (Browser)
             │
             ▼
Centralized FastAPI Backend (Port 8000: main.py)
             │
             ▼
Centralized Orchestration Layer (backend/orchestration/orchestrator.py)
   │
   ├─► Performance Analysis Agent (backend/agents/report_agents.py)
   │     • Ingests verified client marketing records from MongoDB
   │     • Computes deterministic KPIs via Analytics Engine (No LLM math)
   │     • Invokes Groq LLM (openai/gpt-oss-120b) with strict evidentiary rules
   │     • Overlays verified mathematical KPIs onto Pydantic schemas
   │
   ├─► Content Strategy & Calendar Agent (backend/agents/report_agents.py)
   │     • Evaluates client brand guidelines, audience persona, and products
   │     • Formulates monthly themes, content pillars, and ideas (Reels, Carousels, Posts, Stories)
   │     • Builds date-wise publishing calendars and strategic recommendations
   │
   ├─► Legacy Analysis & Storytelling Agents (Preserved for compatibility)
   │
   ▼
Unified JSON Output ──► Rendered in UI / Standalone HTML / Print PDF Export
```

---

## 2. Directory Structure

```text
AI_REEL/
│
├── main.py                               # Centralized server entrypoint (Port 8000)
├── index.html                            # Executive SaaS Dashboard & Report Generation UI
├── requirements.txt                      # Dependencies (FastAPI, PyMongo, LangChain, Groq, etc.)
├── .env                                  # Environment configuration
├── .env.example                          # Template environment variables
├── README.md                             # Documentation & user guide
│
├── backend/
│   ├── app.py                            # FastAPI application factory & router registration
│   ├── index.html                        # Synced frontend dashboard
│   ├── config.py                         # Application configuration
│   │
│   ├── agents/                           # Autonomous Specialized Agents
│   │   ├── __init__.py
│   │   ├── report_agents.py              # Performance, Content Strategy, and Creative Agents
│   │   ├── analysis_agent.py             # Legacy analytics agent
│   │   └── storytelling_agent.py         # Legacy scriptwriter agent
│   │
│   ├── ai/                               # LLM Clients & Prompt Engineering
│   │   ├── __init__.py
│   │   ├── llm_client.py                 # Centralized Groq LLM client
│   │   └── report_prompts.py             # Strict evidence-based report prompts
│   │
│   ├── analytics/                        # Deterministic Mathematical Engine
│   │   ├── __init__.py
│   │   ├── marketing_engine.py           # CTR, CPC, CPM, Conv Rate, CPA, ROAS, Period Changes
│   │   └── metrics.py                    # Legacy reel metrics
│   │
│   ├── database/                         # MongoDB Access Layer
│   │   ├── __init__.py
│   │   ├── connection.py                 # Thread-safe MongoDB client
│   │   └── client_data_service.py        # Isolated queries across clients, campaigns, reports
│   │
│   ├── orchestration/                    # Centralized Request Dispatcher
│   │   ├── __init__.py
│   │   └── orchestrator.py               # Dynamic routing, validation, error handling
│   │
│   ├── routes/                           # FastAPI API Endpoints
│   │   ├── __init__.py
│   │   ├── report_routes.py              # Dashboard, Clients, Generate, Save, Export HTML
│   │   ├── analysis_routes.py            # Legacy analysis routes
│   │   └── storytelling_routes.py        # Legacy storytelling routes
│   │
│   ├── schemas/                          # Pydantic Schemas & Data Contracts
│   │   ├── __init__.py
│   │   └── report_schemas.py             # Strict schemas for all 7 report types
│   │
│   ├── services/                         # Business Logic & Exporters
│   │   ├── __init__.py
│   │   ├── client_data_service.py        # Multi-tenant data querying & fallback resilience
│   │   └── report_renderer.py            # Standalone HTML & Print PDF generator
│   │
│   └── tests/                            # Comprehensive Automated Test Suite (69 Tests)
│       ├── test_report_generation.py     # Deterministic math, API, and agent tests
│       ├── test_orchestrator.py          # Centralized router tests
│       ├── test_metrics.py               # Formula edge cases
│       └── ...
```

---

## 3. Strict Mathematical Analytics Engine

The platform guarantees **100% mathematical accuracy**. The LLM is **never** permitted to calculate, extrapolate, or hallucinate metrics.

All calculations execute deterministically in `backend/analytics/marketing_engine.py`:

| Metric | Exact Formula | Zero-Denominator / Edge Handling |
| :--- | :--- | :--- |
| **CTR (%)** | `(Clicks / Impressions) * 100` | Returns `0.0%` if Impressions $\le 0$ |
| **CPC** | `Spend / Clicks` | Returns `None` (`N/A`) if Clicks $\le 0$ |
| **CPM** | `(Spend / Impressions) * 1000` | Returns `None` (`N/A`) if Impressions $\le 0$ |
| **Conversion Rate (%)** | `(Conversions / Clicks) * 100` | Returns `0.0%` if Clicks $\le 0$ |
| **CPA** | `Spend / Conversions` | Returns `None` (`N/A`) if Conversions $\le 0$ |
| **ROAS** | `Revenue / Spend` | **Strict Rule**: If Spend is `0`, returns `None` (`N/A`). Never `0` or crash. |
| **Percentage Change** | `((Current - Previous) / Previous) * 100` | Returns `+100.0%` if Previous $= 0$ & Current $> 0$; `0.0%` if both $0$ |

Aggregates are calculated from **total sums**, never by averaging percentages or individual ratios.

---

## 4. Supported Report Types

1. **Performance Analysis** (`performance_analysis`): Comprehensive account overview, period-over-period comparison, campaign rankings, creative observations, and strategic next steps.
2. **Campaign Performance** (`campaign_performance`): Deep-dive into top and bottom performing campaigns with diagnosis and optimization actions.
3. **Creative Performance** (`creative_performance`): Evaluation of hooks, formats (Reels, Carousels, Static Posts), fatigue, and recommendations.
4. **Monthly Marketing Report** (`monthly_marketing`): Executive-level monthly recap for C-level presentation.
5. **Content Strategy** (`content_strategy`): Theme formulation, audience capture positioning, structured content ideas table, and pillar distribution.
6. **Content Calendar** (`content_calendar`): Date-wise publishing roadmap with objectives, formats, topics, and captions.
7. **Advertising Strategy** (`advertising_strategy`): Paid ad concepts, budget allocation guidelines, and testing frameworks.

---

## 5. MongoDB Collections & Data Isolation

Data isolation is enforced via `agency_id` and `client_id` across the following collections:

1. `agencies`: Agency credentials and administrative profiles.
2. `clients`: Client metadata, industry, target audience, brand guidelines, and product catalogs.
3. `campaigns`: Campaign-level daily ad spend, impressions, clicks, conversions, and attributed revenue.
4. `creatives`: Creative formats, headlines, media URLs, and engagement records.
5. `content_calendar`: Scheduled post records, platform targets, and publishing statuses.
6. `reports`: Generated reports with full JSON payloads, reporting periods, and creation dates.
7. `platform_connections`: OAuth tokens, connection health, and account sync timestamps.

*Resilience Note*: If collections are newly initialized or the database cluster DNS is resolving, the service seamlessly falls back to pre-configured client baselines (`client_scentora`, `client_pulsefit`, `client_chaipoint`), ensuring zero downtime.

---

## 6. How to Run the Platform

### A. Activate Environment & Run Single Backend Server

Run on **Port 8000** with a single command:

```bash
# Windows PowerShell
$env:PYTHONPATH="c:\Users\91772\AI_REEL"
& "backend/env/Scripts/python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### B. Access the SaaS Dashboard

Open your browser and navigate to:
```text
http://127.0.0.1:8000/
```

- **Overview Cards**: Displays Total Clients, Campaigns, Advertising Spend, Revenue, and Average ROAS.
- **Client Selection**: Select any client from the dropdown to automatically view their industry, products, brand guidelines, and connected channels.
- **Report Generator**: Select report type, marketing platform, and date range, then click **Generate Report**.
- **Interactive Actions**: View the report in the dashboard, copy JSON to clipboard, export as standalone HTML, or print/save as PDF.

---

## 7. Running the Test Suite

Execute the full suite of **69 automated unit and integration tests**:

```bash
$env:PYTHONPATH="c:\Users\91772\AI_REEL"
& "backend/env/Scripts/python.exe" -m pytest backend/tests -v
```

All 69 tests pass with zero warnings or errors.
