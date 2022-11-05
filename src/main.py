#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# src/main.py
# Entry point for msol.

import argparse

from src.apis.orders import OrdersApi
from src.strategies.spread_solver import SpreadSolverApi
from src.util.os import load_config, set_output, save_output, log_info


def run_menu() -> argparse.ArgumentParser:

    parser = argparse.ArgumentParser(description='✨🐮 MSOL 👾✨')
    parser.add_argument('-a', dest='amms', nargs=1,
                        help="List amms data in a given order instance. \
                        Example: msol -a <order file>")
    parser.add_argument('-o', dest='orders', nargs=1,
                        help="List orders data in a given order instance. \
                        Example: msol -a <order file>")
    parser.add_argument('-s', dest='spread', nargs=1,
                        help="Solve input orders with a spread strategy. \
                        Example: msol -s <order file>")
    return parser


def run() -> None:
    """Entry point for this module."""

    env_vars = load_config()
    parser = run_menu()
    args = parser.parse_args()

    if args.amms:

        input_file = args.amms[0]
        log_info(f'AMMs available for {input_file}')

        oa = OrdersApi(input_file)
        oa.amms_data

    elif args.orders:

        input_file = args.orders[0]
        log_info(f'Orders for {input_file}')

        oa = OrdersApi(input_file)
        oa.orders_data

    elif args.spread:

        input_file = args.spread[0]
        output_destination = set_output(env_vars, input_file)
        log_info(f'Solving {input_file} with spread strategy.')

        # Create an instance for the entire input file
        oa = OrdersApi(input_file)
        
        result = {
            'amms': {},
            'orders': {}
        }
        
        for order_num, order in oa.orders.items():

            order = oa.parse_order_for_spread_trade(order, order_num)
            amms = oa.parse_amms_for_spread_trade(order)

            # Create an instance for each order
            solver = SpreadSolverApi(amms)
            solution = solver.solve(order)

            result['amms'].update(solution['amms']) 
            result['orders'].update(solution['orders']) 

        save_output(output_destination, result)
        log_info(f'Results saved at {output_destination}.')
    
    else:
        parser.print_help()


if __name__ == "__main__":
    run()
    