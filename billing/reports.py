from decimal import Decimal

from billing.rounding import CENT


def _customer_name(customer):
    return customer


def _aggregate(invoices):
    names = {}
    totals = {}
    for invoice in invoices:
        if invoice.customer not in names:
            names[invoice.customer] = _customer_name(invoice.customer)
        name = names[invoice.customer]
        totals[name] = totals.get(name, Decimal("0")) + Decimal(str(invoice.total))
    return {customer: total.quantize(CENT) for customer, total in totals.items()}


def _format_rows(totals):
    return "\n".join(
        f"{customer:<20}{total:>10.0f}" for customer, total in sorted(totals.items())
    )


def build_report(invoices):
    return _format_rows(_aggregate(invoices))
