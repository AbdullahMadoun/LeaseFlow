# IMDAD: Multi-Agent Architecture & Workflow Breakdown

This document outlines the system design, agent workflows, and the orchestrator pipeline for the **IMDAD** platform (Invoice-to-lease financing for the Kingdom's cafés).

## 🧑‍💻 The Architect: Your Role

As the **System Designer, Workflow Architect, and Lead Prompt Engineer**, your role is the backbone of the IMDAD pipeline. While the individual agents handle specific micro-tasks, you are responsible for the macro-system:

1. **System & Pipeline Design**: You designed the **"Four Data Streams, One Decision in 90 Seconds"** pipeline. You architected how the data flows from raw inputs (Drag & Drop POS data, Simah Login, Maps Scraper) into the central reasoning engines.
2. **Workflow Architecture (Leaser & Agent Verification)**: You defined the sequence of operations. You structured the exact flow where the `Market Governor` assesses the KSA F&B health risk envelope, passes it to the `Expert LLM`, and finalizes it through the `Cashflow Governor` against portfolio baselines.
3. **Master Prompt Engineer**: The `Expert LLM`'s ability to logically approve or deny leases based on strict, audit-traceable rules is entirely dependent on your prompt engineering. You crafted the complex prompts that turn an unpredictable LLM into a deterministic, financial underwriter that safely evaluates thousands of Riyadh's unbanked cafés.

---

## 🤖 The Multi-Agent Pipeline Breakdown

IMDAD relies on a sophisticated multi-agent pipeline to underwrite 19 out of 20 unbanked cafés in Saudi Arabia. Here is how the agents collaborate:

### 1. Data Ingestion Agents (The Sentinels)
These agents sit at the edge of the pipeline, collecting the four critical data streams.
* **POS & Document Extraction Agent**: Parses dragged-and-dropped bank statements, financial statements, and raw POS data into structured JSON.
* **Simah Credit Agent**: Integrates with the Simah API/Login to retrieve historical loan and credit profiles.
* **Maps Sentiment Scraper Agent**: Crawls Google Maps and public review sites to gauge customer sentiment and public trust for the specific café.

### 2. The Analytical Engine (The Brains)
Once data is collected, the workflow routes it into the core decision engine:
* **The Market Governor Agent**: Analyzes the macro environment. It cross-references the café's data against the broader KSA F&B health and risk envelope.
* **The Cashflow Governor Agent**: Analyzes the micro environment. It checks the specific café's portfolio baseline and financial thresholds to ensure they can meet the 3/6/12/18-month duration payments.
* **The Expert Underwriter (LLM)**: Governed by your strict prompts, this agent takes the outputs of the Governors and the Sentinels to make the final **APPROVE or DENY** call within 90 seconds. Its decisions are rules-anchored and 100% audit-traceable.

### 3. The Execution Layer (The Stream Operators)
If the Expert Underwriter approves the lease, the workflow hands off to the execution layer.
* **Stream Orchestrator**: Makes exactly 3 API calls (`POST /consumers`, `POST /payment-methods`, `POST /subscriptions`).
* **Silent Ledger Agent**: After the 3 calls, this agent goes silent. It monitors the Stream.sa auto-billing, installments engine, ZATCA invoicing, and card failure recovery automatically. Every decision becomes a row; every installment becomes a receipt.

---

## 🔒 Security Operations

As the Architect, you mandated a zero-trust policy for the repository. To enforce this, we have spawned an autonomous swarm of **Security Auditor Agents**:
* **Scanner Agent Alpha**: Currently auditing all repository history, `apps/`, `services/`, and `agents/` directories for exposed Supabase keys, Stream API keys, and Minimax secrets.
* **Deep Directory Agent Beta**: Currently running regex heuristics across all files to catch any `.env.local`, hardcoded passwords, or `Bearer` tokens that might have slipped through git tracking.

*The security agents are currently running in the background and will report back their findings shortly.*
