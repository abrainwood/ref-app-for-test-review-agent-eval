BRACKETS = (
    (0, 0.0),
    (1000, 0.10),
    (5000, 0.20),
)


def progressive_tax(amount):
    tax = 0.0
    for index, (lower, rate) in enumerate(BRACKETS):
        if amount <= lower:
            break
        next_index = index + 1
        upper = BRACKETS[next_index][0] if next_index < len(BRACKETS) else amount
        tax += (min(amount, upper) - lower) * rate
    return tax
