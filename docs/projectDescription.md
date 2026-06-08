# Project Description

## Overview

`stream-hacka` is best understood as an AI-assisted underwriting system for lease-to-own equipment financing in the Saudi food and beverage market. Instead of acting like a generic lending app, it is designed to decide whether a restaurant or cafe should be approved, denied, or sent to manual review for financing. The merchant uploads business documents, the system analyzes both internal and external signals, and it produces a decision with reasoning, an approved amount, and a repayment path.

The business model is also important: the platform is not framed as a conventional cash loan. It buys the equipment for the merchant and leases it back with a markup. That makes the product much more specific and much more realistic than a vague "AI finance app."

## How The System Works

The project is built around a multi-stage underwriting pipeline.

First, the merchant uploads documents such as bank statements, POS exports, invoices, and financial statements. These documents are parsed and turned into structured machine-readable reports.

Then the system runs several decision dimensions in parallel:

- `financial_docs`: analyzes bank statements and financial statements, computes affordability, and derives DSCR and consistency checks.
- `pos`: evaluates operational health from sales behavior, ticket size, refund rate, void rate, and revenue trends.
- `simah`: represents the merchant's credit profile, loan history, defaults, and inquiry behavior.
- `sentiment`: uses Google Maps reviews to estimate customer sentiment, business quality, and customer loyalty signals.
- `industry`: adds business-segment and market-context reasoning.

Alongside those merchant-level signals, the platform also considers lender-side governance inputs:

- current market state
- the lender's own portfolio exposure and cashflow appetite

Those external governance signals are combined into a risk snapshot, so the app is not only asking "is this merchant good?" but also "is this the right time for us to take this risk?"

Finally, an expert synthesis layer combines all dimension outputs into a final decision:

- `approved`
- `denied`
- `manual_review`

## What Is Impressive About It

The most impressive thing about the project is that it does not use AI as a black box. The architecture separates structured extraction, dimension-level scoring, deterministic risk rules, and final LLM synthesis. That is a much stronger design than simply prompting a model with uploaded files and asking whether to approve the merchant.

Several parts stand out:

### 1. It combines internal and external underwriting signals well

The project blends internal merchant evidence with external context:

- internal: financial documents, POS data, credit profile, invoice data
- external: Google review sentiment, industry context, market conditions, and lender cashflow posture

That makes the decision engine feel closer to a real underwriting workflow than a demo classifier.

### 2. It keeps deterministic control over high-risk decisions

The system does not fully hand the decision to the model. Core rules such as DSCR thresholds and credit-default checks are handled deterministically. The LLM is used as a synthesis and reasoning layer, not as the sole authority. In guardrail mode, the model can downgrade a decision, but it cannot freely upgrade a weak application into an approval.

This is a strong design choice because it reduces hallucination risk in a financial product.

### 3. It is built for explainability

Every major step is traceable. The pipeline records document extraction, scoring steps, rule triggers, and LLM outputs into an audit trail. That means admins can understand why a merchant was approved or rejected instead of being forced to trust a hidden model output.

For a financing product, this is one of the strongest parts of the system.

### 4. It feels like a real product, not just a model demo

The project covers the full operational flow:

- merchant onboarding
- document upload
- asynchronous analysis
- approval or rejection
- repayment scheduling
- payment collection through Stream
- admin visibility into risk and overrides

That end-to-end thinking is impressive because the project connects underwriting logic to real payment and operations flows.

## Why The Architecture Is Strong

The codebase reflects a clear decision pipeline:

1. Extract raw uploaded documents into structured reports.
2. Score different dimensions in parallel.
3. Apply deterministic scoring and hard-floor rules.
4. Let the LLM synthesize reasoning inside a guarded framework.
5. Persist the outcome with audit data and repayment details.

This layered architecture is exactly what makes the project credible. It uses AI where AI is useful, but it still anchors the system in explicit rules, typed outputs, and operational controls.

## Important Caveat

Some parts are still prototype-grade rather than production-grade. In particular, `SIMAH` is currently stubbed, and some market and industry inputs are mocked or simplified. So the strongest claim is not that this is already a production underwriting engine, but that it is a very solid and thoughtful architecture for one.

## Summary

`stream-hacka` is impressive because it turns a difficult financial decision into a structured, explainable, multi-source analysis pipeline. It combines uploaded business documents, customer sentiment, credit signals, market context, and lender risk posture into a financing decision that is both automated and auditable. The most notable achievement is not just that it uses AI, but that it uses AI carefully, with real risk controls, traceability, and end-to-end product design.
