from dataclasses import replace

from billing.rounding import round_currency


def convert_invoice(invoice, currency, rates):
    rate = rates.rate(currency)
    return replace(
        invoice,
        subtotal=round_currency(invoice.subtotal * rate),
        discount=round_currency(invoice.discount * rate),
        tax=round_currency(invoice.tax * rate),
        total=round_currency(invoice.total * rate),
    )
