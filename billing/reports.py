from decimal import Decimal

from billing.rounding import CENT


def _aggregate(invoices):
    totals = {}
    for invoice in invoices:
        totals[invoice.customer] = totals.get(invoice.customer, Decimal("0")) + Decimal(str(invoice.total))
    return {customer: total.quantize(CENT) for customer, total in totals.items()}


def _format_rows(totals):
    return "\n".join(
        f"{customer:<20}{total:>10.0f}" for customer, total in sorted(totals.items())
    )


def build_report(invoices):
    return _format_rows(_aggregate(invoices))
