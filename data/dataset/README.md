# Strema Single-Business Dataset

This folder packages the single restaurant/cafe dataset generator, the expected schema, the simulation strategy, and one generated sample dataset.

## Contents

- `generate_pos_dataset.py`: causal simulator for a single restaurant or cafe by default
- `Schema.md`: target export schema
- `SimulationStrategy.md`: generation logic and modeling rationale
- `sample_dataset/`: generated sample for `Strema Cafe`

## Default packaged sample

The included sample dataset represents one business over time:

- `legal_name`: `Strema Cafe`
- `city`: `Riyadh`
- `archetype`: `neighborhood_cafe`
- `scenario`: `margin_squeezed_merchant`
- `date range`: `2025-01-01` to `2026-03-31`

## Generate a new dataset

From the repo root:

```powershell
python .\strema_single_business_dataset\generate_pos_dataset.py
```

This writes outputs into:

```text
strema_single_business_dataset\generated_output
```

Example with explicit business settings:

```powershell
python .\strema_single_business_dataset\generate_pos_dataset.py `
  --city Riyadh `
  --archetype neighborhood_cafe `
  --scenario margin_squeezed_merchant `
  --legal-name "Strema Cafe"
```

## Output files

- `merchants.csv`
- `merchant_latent_profiles.csv`
- `sales_daily.csv`
- `payments_daily.csv`
- `bank_daily.csv`
- `obligations.csv`
- `restaurant_pos_simulated.sqlite`
- `generation_summary.json`
