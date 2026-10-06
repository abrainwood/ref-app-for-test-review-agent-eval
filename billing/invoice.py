from dataclasses import dataclass
from datetime import date, timedelta

from billing.discounts import discount_rate
from billing.rounding import round_currency
from billing.tax import progressive_tax

PAYMENT_TERMS = timedelta(days=30)


@dataclass(frozen=True)
class Line:
    description: str
    quantity: int
    unit_price: float


@dataclass(frozen=True)
class Invoice:
    customer: str
    subtotal: float
    discount: float
    tax: float
    total: float
    due: date


def price_invoice(customer, lines, issued_on):
    subtotal = sum(line.quantity * line.unit_price for line in lines)
    discount = subtotal * discount_rate(subtotal)
    taxable = subtotal - discount
    tax = progressive_tax(taxable)
    return Invoice(
        customer=customer,
        subtotal=round_currency(subtotal),
        discount=round_currency(discount),
        tax=round_currency(tax),
        total=round_currency(taxable + tax),
        due=issued_on + PAYMENT_TERMS,
    )
