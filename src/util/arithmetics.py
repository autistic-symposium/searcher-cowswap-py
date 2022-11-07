# -*- encoding: utf-8 -*-
# utils/arithmetics.py
# This class implements math methods used by the other classes.

import scipy
from decimal import Decimal, getcontext
from src.util.strings import log_error


def div(dividend, divisor) -> Decimal:
    """Return higher precision division."""

    if divisor == 0:
        raise ZeroDivisionError
    return to_decimal(dividend) / to_decimal(divisor)


def to_decimal(value) -> Decimal:
    """Return Decimal value for higher (defined) precision."""

    getcontext().prec = 22
    return Decimal(value)


def nelder_mead_simplex_optimization(equation, boundary_max, initial_guess=None) -> float:
    """
        Run a simple form of the Nelder-Mead optimization solver,  
        that minimizes a scalar function of one or more variables.
    """

    # If initial guess (x0) is None, set to the middle.
    initial_guess = initial_guess or int(div(boundary_max, 2))

    # Optimize to find a min of the negative of the original equation.
    lambda_equation = lambda x: - equation(x)

    # Run Nelder-Mead solver.
    solution_for_max = scipy.optimize.fmin(lambda_equation, initial_guess, disp=False)

    try:
        return int(to_decimal(solution_for_max[0]))
    except ValueError as e:
        log_error(f'Could not find a optimization solution: {e}')
