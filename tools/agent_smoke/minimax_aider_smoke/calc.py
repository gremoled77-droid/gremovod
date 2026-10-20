def total_with_tax(amount_cents: int, tax_percent: int) -> int:
    """Return integer cents with tax added; round down partial cents."""
    if amount_cents < 0 or tax_percent < 0:
        raise ValueError("Inputs must be non-negative")
    return amount_cents + (amount_cents * tax_percent) // 100
