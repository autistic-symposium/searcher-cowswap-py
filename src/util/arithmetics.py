# -*- encoding: utf-8 -*-
# utils/arithmetics.py
# This class implements math methods used by the other classes.

from decimal import Decimal, getcontext


def div(dividend, divisor) -> Decimal:
    """Return higher precision division."""
    
    if divisor == 0:
        raise ZeroDivisionError
    return to_decimal(dividend) / to_decimal(divisor)


def to_decimal(value) -> Decimal:
    """Return Decimal value for higher (defined) precision."""
    
    getcontext().prec = 22
    return Decimal(value)
