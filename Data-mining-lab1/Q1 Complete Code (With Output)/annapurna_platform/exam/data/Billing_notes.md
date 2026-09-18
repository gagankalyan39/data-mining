# Billing Vendor Notes

## Line Types
Each sales file contains rows with a `line_type` column. Not all rows are revenue lines:

| line_type | Meaning |
|-----------|---------|
| `SALE`    | A genuine sale — count this toward revenue |
| `VOID`    | A voided line — the sale was cancelled at the till, **exclude from revenue** |
| `RETURN`  | Customer return — **exclude from revenue** |
| `DISCOUNT`| Discount applied — **exclude from revenue** (already reflected in unit_price) |

**Only `SALE` lines should be counted as revenue.**

## Re-sends
When a store's POS crashes or loses connectivity, the billing system re-sends the **entire day's file** the next morning.
Re-sent files have the **same store, same date** but arrive as a new file.
Duplicate detection must be by `(bill_number, product_code, timestamp)` — not by filename.

## Product Code Reuse
Product codes are recycled. A code retired before 2023-01-01 may be reissued to a completely different product after that date.
Always join on `(product_code, effective_date_range)` — never on product_code alone.

## Timestamps
All timestamps in the sales files are **UTC**. Store local time is IST (UTC+5:30).
