# 16 · sales

RFM segmentation and cohort retention from a CSV, standard library only.

## Run

```bash
from sales.rfm import Order, build_customers, cohort_retention
```

## Test

```bash
pytest projects/16-sales-analytics -q
```

## What it demonstrates

- Quintile scoring using empirical quantiles, recency scored in reverse
- Named segments (champion / loyal / at risk / lost) an analyst can act on
- Cohort retention matrix keyed on each customer's first purchase month
- Revenue share per segment to prioritise retention spend
