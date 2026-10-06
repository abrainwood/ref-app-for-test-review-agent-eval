# Billing rules

- An invoice's subtotal is the sum of quantity x unit price over its lines. Amounts are rounded to cents (half up) only on the final invoice fields, never per line.
- Volume discount is a rate applied to the whole subtotal, chosen by the subtotal's tier. A subtotal exactly on a tier threshold gets that tier.
- Tax is progressive over the discounted subtotal: 0% up to 1000, 10% from 1000 to 5000, 20% above 5000.
- Payment is due 30 days after the issue date.
- The monthly report lists each customer's total across their invoices, one row per customer, sorted by name, in whole currency units.
