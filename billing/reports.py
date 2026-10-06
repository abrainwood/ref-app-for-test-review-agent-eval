def _aggregate(invoices):
    totals = {}
    for invoice in invoices:
        totals[invoice.customer] = totals.get(invoice.customer, 0.0) + invoice.total
    return totals


def _format_rows(totals):
    return "\n".join(
        f"{customer:<20}{total:>10.0f}" for customer, total in sorted(totals.items())
    )


def build_report(invoices):
    return _format_rows(_aggregate(invoices))
