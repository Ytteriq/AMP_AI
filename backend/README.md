# AI Reel Performance Analyst

An AI-powered performance analytics service that connects directly to a live **MongoDB Atlas** database, leverages **LangChain** + **LangGraph** with **Groq API** (`openai/gpt-oss-120b`), and uses **ChromaDB** with local **HuggingFace Embeddings** to answer complex natural-language inquiries about Instagram Reels, campaigns, agency performance, and marketing strategies.

---

## 1. System Architecture

```text
backend/
├── main.py                     # FastAPI app entrypoint, CORS, lifespan, /health endpoints
├── requirements.txt            # Production dependencies
├── .env.example                # Environment variable template
├── .gitignore                  # Git exclusions for secrets, venvs, and cache
│
├── database/                   # MongoDB Atlas Connection
│   ├── __init__.py
│   └── connection.py           # PyMongo client pool, health validation, index ensuring
│
├── analytics/                  # Trusted Mathematical Formulas
│   ├── __init__.py
│   └── metrics.py              # Exact profit, ROI, engagement rate, agency aggregate metrics
│
├── tools/                      # Registered LangChain Tools
│   ├── __init__.py
│   ├── database_tools.py       # query_reel_data: Live structured data from MongoDB Atlas
│   ├── analytics_tools.py      # analyze_performance: Mathematical formulas & rankings
│   └── rag_tools.py            # search_knowledge: ChromaDB unstructured strategy retrieval
│
├── rag/                        # ChromaDB & Vector Knowledge
│   ├── __init__.py
│   ├── embeddings.py           # Local HuggingFaceEmbeddings (all-MiniLM-L6-v2)
│   └── vector_store.py         # Persistent ChromaDB store with strategy documents
│
├── ai/                         # LLM & Prompts
│   ├── __init__.py
│   ├── llm_client.py           # ChatGroq client with tool-calling verification
│   └── prompts.py              # Strict system instructions preventing data invention
│
├── agent/                      # LangGraph StateGraph Workflow
│   ├── __init__.py
│   ├── state.py                # Typed AgentState schema
│   └── graph.py                # StateGraph with conditional tool routing and loops
│
├── api/                        # FastAPI Route Handlers
│   ├── __init__.py
│   └── routes_chat.py          # POST /api/chat with Pydantic validation
│
└── tests/                      # Automated Unit & Integration Tests
    ├── __init__.py
    ├── test_metrics.py         # Unit tests for formulas, edge cases, zero spend
    ├── test_analytics_tools.py # Unit tests for analytics operations & validation
    └── test_agent.py           # Tests for LangGraph routing, RAG, and response synthesis
```

---

## 2. Technology Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn
- **Database**: MongoDB Atlas, PyMongo
- **AI & Coordination**: LangChain, LangGraph
- **LLM**: Groq API (`openai/gpt-oss-120b`) with native tool calling
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface` (runs locally on CPU)
- **Vector Database**: ChromaDB (`langchain-chroma`)
- **Validation**: Pydantic v2
- **Testing**: Pytest

---

## 3. Real MongoDB Schema

The system connects to your MongoDB database (`ai_reels_analytics`) collection (`reels`). Documents follow this schema:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `reel_id` | String (Unique) | Primary reel identifier (e.g., `REEL_IND_001`) |
| `reel_name` | String | Reel campaign hook / creative description |
| `agency_name` | String | Agency managing the reel (e.g., `PulseMedia Digital`, `Apex Growth Lab`) |
| `campaign_name` | String | Marketing campaign identifier |
| `published_at` | Date / DateTime | UTC publication timestamp |
| `views` | Integer | Total reel video views |
| `likes` | Integer | Total likes received |
| `comments` | Integer | Total comments |
| `shares` | Integer | Total shares |
| `saves` | Integer | Total saves |
| `ad_spend` | Float | Advertising expenditure in INR |
| `attributed_revenue` | Float | Direct attributed revenue in INR |
| `other_costs` | Float | Production and influencer fees in INR |
| `currency` | String | Currency code (`INR`) |
| `profit` | Float | Calculated net profit (`revenue - spend - other_costs`) |
| `roi_percentage` | Float | Calculated percentage ROI (`(profit / ad_spend) * 100`) |

---

## 4. Mathematical Rules & Metric Definitions

1. **Net Profit**:
   $$\text{Profit} = \text{Attributed Revenue} - \text{Ad Spend} - \text{Other Costs}$$
   *Rule: Never impute missing costs or revenue as zero.*

2. **ROI (%)**:
   $$\text{ROI (\%)} = \left(\frac{\text{Profit}}{\text{Ad Spend}}\right) \times 100 \quad (\text{when } \text{Ad Spend} > 0)$$
   *Rule: Handle zero or negative denominators safely; zero spend yields `None` / `0.0` with explanatory note.*

3. **Engagement Rate (%)**:
   $$\text{Engagement Rate (\%)} = \left(\frac{\text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}}{\text{Views}}\right) \times 100$$

4. **Aggregate Agency ROI Rule**:
   $$\text{Aggregate Agency ROI} = \left(\frac{\sum \text{Agency Profit}}{\sum \text{Agency Ad Spend}}\right) \times 100$$
   *CRITICAL: Agency ROI is NEVER calculated by averaging the individual reel ROI percentages.*

---

## 5. Three LangChain Tools

1. **`query_reel_data`** (`backend/tools/database_tools.py`):
   - Queries live records from MongoDB Atlas.
   - Supports filtering by `reel_id`, `agency_name`, `campaign_name`, `start_date`, and `end_date`.
   - Returns structured records, total matches, reporting period boundaries, and data freshness timestamps.

2. **`analyze_performance`** (`backend/tools/analytics_tools.py`):
   - Single unified tool supporting operations:
     `rank_by_profit`, `rank_by_roi`, `calculate_profit`, `calculate_roi`, `calculate_engagement_rate`, `compare_reels`, `compare_agencies`, `compare_campaigns`, `compare_periods`, `summarize_performance`, `find_high_views_low_profit`.
   - Guaranteed trusted mathematical calculations.

3. **`search_knowledge`** (`backend/tools/rag_tools.py`):
   - Queries ChromaDB vector store for playbooks, campaign briefs, guidelines, and strategy context.
   - Returns passage excerpts with document titles, sources, and similarity scores.
   - Explicitly reports when no relevant documents exist.

---

## 6. Setup & Execution Instructions

### Step 1: Environment Variables
Create or verify your `.env` file in the root or `backend/` directory:

```env
# MongoDB Atlas Connection
MONGODB_URI=mongodb+srv://@cluster0.vzu6ofc.mongodb.net/?appName=Cluster0
MONGODB_DATABASE=ai_reels_analytics

# Groq API Key
GROQ_API_KEY=

# ChromaDB & Models
CHROMA_PERSIST_DIRECTORY=./chroma_db
CHROMA_COLLECTION_NAME=campaign_knowledge
LLM_MODEL=openai/gpt-oss-120b
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Step 2: Activate Virtual Environment
```powershell
# In PowerShell:
.\backend\env\Scripts\Activate.ps1

# In Command Prompt (cmd):
backend\env\Scripts\activate.bat
```

### Step 3: Run the FastAPI Server
```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- Swagger UI: **http://127.0.0.1:8000/docs**
- ReDoc: **http://127.0.0.1:8000/redoc**

---

## 7. Running Tests

Run the full automated test suite (23 unit tests):

```powershell
.\backend\env\Scripts\python.exe -m pytest backend/tests -v
```
