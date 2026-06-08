# IMDAD ☕️ 

> **Invoice-to-lease financing for the Kingdom's cafés.**
> *Built for Streamathon 2026 · Riyadh · SUB4.0 @ KFUPM*
>
> 📑 **[View the Pitch Deck Slides](docs/imdad-deck.pdf)**

## 📖 The Problem
Every restaurant, café, and bakery in Saudi Arabia is an "Ahmed." Out of 132,383 F&B businesses, **19 out of 20 are unbanked**. They have no collateral, no credit history, and no time to deal with traditional bank bureaucracy. 

Meanwhile, Vision 2030 mandates that SME credit must reach **20%** (up from today's 9.6%). **IMDAD** is the bridge to that reality. 

Instead of lending risky capital, we utilize an invoice-to-lease model: **We buy the equipment they need, and lease it back to them at a markup.** The machine is the collateral. When it's paid off, they own it.

---

## 🤖 The Multi-Agentic System: Four Data Streams, One Decision
IMDAD is not a standard CRUD application; it is a highly asynchronous **multi-agent system (MAS)** managing massive flows of unstructured data to output deterministic, 90-second underwriting decisions. 

```mermaid
graph TD
    %% Ingestion Layer
    subgraph Edge Layer "1. The Ingestion Sentinels"
        D[📄 Drag & Drop Files] --> DocA[Document Agent]
        S[🏦 Simah Login] --> SimA[Credit Agent]
        M[🗺️ Maps Reviews] --> MapA[Sentiment Agent]
    end

    %% Reasoning Layer
    subgraph Reasoning Layer "2. The Governors"
        DocA --> CG[Cashflow Governor]
        SimA --> CG
        MapA --> MG[Market Governor]
        
        CG -.-> |Micro-Risk: Cash Buffer & Ratios| EL
        MG -.-> |Macro-Risk: KSA F&B Envelope| EL
    end

    %% Decision Engine
    subgraph Decision Engine "3. Expert Underwriter"
        EL{Expert LLM}
        EL -->|Threshold Fail| Deny((DENY))
        EL -->|Rules Met| Approve((APPROVE))
    end

    %% Execution Layer
    subgraph Execution Layer "4. Stream.sa Ledger"
        Approve -->|Silent Handoff| API[Stream Orchestrator]
        API --> POST1[POST /consumers]
        API --> POST2[POST /payment-methods]
        API --> POST3[POST /subscriptions]
        
        POST3 --> Ledger[(Ledger: Auto-Billing & ZATCA)]
    end

    %% Colors matching the brand
    classDef primary fill:#FFD600,stroke:#000,stroke-width:2px,color:#000,font-weight:bold
    classDef secondary fill:#000,stroke:#FFD600,stroke-width:2px,color:#FFF
    classDef decision fill:#000,stroke:#FFD600,stroke-width:4px,color:#FFF,font-weight:bold
    classDef alert fill:#FF3B30,stroke:#000,stroke-width:2px,color:#FFF,font-weight:bold
    classDef success fill:#34C759,stroke:#000,stroke-width:2px,color:#FFF,font-weight:bold
    
    class DocA,SimA,MapA secondary
    class CG,MG secondary
    class EL decision
    class API,Ledger primary
    class Deny alert
    class Approve success
```

Here is how the data flows through our agent swarm:

1. **The Ingestion Sentinels (Edge Layer):**
   - **Document Agent:** Parses dragged-and-dropped financial statements and POS CSVs into structured JSON.
   - **Simah Agent:** Hooks into credit profile histories.
   - **Maps Scraper Agent:** Evaluates public sentiment, Google Maps reviews, and community trust.

2. **The Governors (Reasoning Layer):**
   - **Market Governor:** Evaluates macro-risk (e.g., F&B health in Dammam vs. Makkah). 
   - **Cashflow Governor:** Evaluates micro-risk (e.g., tracking buffer days and cash flow ratios against the merchant's portfolio baseline).

3. **The Expert Underwriter (Execution Layer):**
   - Taking the structured outputs from the Sentinels and Governors, a highly prompted LLM makes the final **APPROVE** or **DENY** call. The decision is entirely rules-anchored and audit-traceable.

4. **The Ledger (Stream.sa Integration):**
   - Once approved, IMDAD goes silent. The system fires exactly 3 API calls to **Stream.sa** (`/consumers`, `/payment-methods`, `/subscriptions`) to handle auto-billing, ZATCA invoicing, and card failure recovery automatically. Every decision is a row; every installment is a receipt.

---

## 📊 POS Analyst Outputs: Generating the Rules
How does the Expert Underwriter know what rules to enforce? We utilize a specialized analytical agent (`pos-analyst`) to crunch massive datasets and establish the thresholds. 

Included in the project outputs are two critical reports:
* `current_run_report_raw.md`
* `current_run_report_clean.md`

These reports are the direct output of our **POS Analyst Agent**, which evaluated a synthetic but causally coherent dataset of **180 Saudi F&B merchants across 9 cities over 15 months** (representing SAR 408.4M in net sales).

### What the Reports Prove:
The reports establish the exact hard-coded facts our multi-agent system uses to underwrite leases. The system discovered that:
1. **Risk is highly concentrated:** 99.5% of unpaid obligations sit with just 64 stressed merchants.
2. **The 3-Gate Screening Rule:** The agent concluded that you can catch 100% of stressed merchants by filtering for three things:
   - Payment rate dropping below 90%
   - Cash coverage ratio falling below 15%
   - Net cash burning (Cash flow ratio > 1.0)
3. **Geographic/Archetype Profiling:** Makkah is the safest city; Dammam is the riskiest. Table-service restaurants are the safest; Cafés are the riskiest.

*Note: The `raw` report contains the Agent's `<think>` chain blocks, proving how it reasoned through the 81,900 rows of data. The `clean` report strips the inner monologue for business stakeholder presentation.*

---

## 📁 Repository Structure
* `/apps/frontend` - Main Vite/React dashboard.
* `/apps/imdad-app` - Secondary Vite application.
* `/services/backend` - FastAPI multi-agent orchestrator.
* `/agents/pos-analyst` - The AI data scientist engine.
* `/docs/` - System architecture, pitch decks, and handoff files.
* `/data/dataset` - The synthetic merchant ledgers.

**Let's Ship It. 🚀**
