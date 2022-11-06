# -*- encoding: utf-8 -*-
# utils/strings.py
# This class implements string methods used by the other classes.

from pprint import PrettyPrinter

from src.util.os import log_error
from src.util.arithmetics import to_decimal


def to_decimal_str(value) -> str:
    """Format a reserve amount to a suitable string."""
    return str(to_decimal(value))


def to_wei_str(value) -> str:
    """Parse an order string to wei value."""
    try:
        return str(value)[:-18] + '_' + str(value)[-18:]
    except ValueError as e:
        log_error(f'Cannot convert to wei: {e}')


def to_solution(value) -> str:
    """Format decimal wei with an underscore for easier reading."""
    return to_wei_str(to_decimal_str(value))


def pprint(data) -> None:
    """Print dicts and data in a suitable format"""
    pp = PrettyPrinter(indent=4)
    print()
    pp.pprint(data)
    print()
