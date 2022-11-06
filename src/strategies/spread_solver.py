# -*- encoding: utf-8 -*-
# strategies/spread_solver.py
# This class implements a solver for spread arbitrage.

from src.util.strings import to_solution
from src.util.arithmetics import to_decimal
from src.apis.uniswapv2 import ConstantProductAmmApi
from src.util.os import log_debug, log_error, log_info, deep_copy


class SpreadSolverApi(object):

    def __init__(self, amms):

        self.__amms = amms


    ###########################################
    #     Private methods: Pretty print       #
    ###########################################

    @staticmethod
    def _print_extra_info(solution) -> None:
        """Print debug info from solution."""
        
        try:
            log_debug(f"  Surplus: {to_solution(solution['surplus'])}")
            log_debug(f"  Prior sell price {solution['prior_sell_price']}")
            log_debug(f"  Market sell price {solution['market_sell_price']}")
            log_debug(f"  Prior buy price {solution['prior_buy_price']}")
            log_debug(f"  Market buy price {solution['market_buy_price']}")
            log_debug(f"  Exec sell amount: {to_solution(solution['amm_exec_sell_amount'])}")
            log_debug(f"  Exec buy amount: {to_solution(solution['amm_exec_buy_amount'])}")
            log_debug(f"  Prior sell reserve: {to_solution(solution['prior_sell_token_reserve'])}")
            log_debug(f"  Initial buy reserve: {to_solution(solution['prior_buy_token_reserve'])}")
            log_debug(f"  Updated sell reserve: {to_solution(solution['updated_sell_token_reserve'])}")
            log_debug(f"  Updated buy reserve: {to_solution(solution['updated_buy_token_reserve'])}")
            log_debug(f"  Can fill: {solution['can_fill']}")

        except KeyError as e:
            log_error(f'Could not print data for "{e}"')

    @staticmethod
    def _print_initial_info_one_leg(sell_amount, sell_token, amm_sell_reserve,
                                        buy_amount, buy_token, amm_buy_reserve) -> None:
        """Print input info from a one-leg trade order."""

        log_info(f"One-leg trade overview:")
        log_info(f"➖ sell {to_solution(sell_amount)} of {sell_token}," + \
                            f" amm reserve: {to_solution(amm_sell_reserve)}")
        log_info(f"➕ buy {to_solution(buy_amount)} of {buy_token}," + \
                            f" amm reserve: {to_solution(amm_buy_reserve)}")
            

    @staticmethod
    def _print_initial_info_two_legs(leg_info, order_data, leg_data) -> None:
        """Print input info for first leg of a two-legs trade."""

        log_info(f"{leg_info} trade overview:")   
        if bool(order_data['is_sell_order']):
            sell_amount = to_solution(order_data['sell_amount'])
            log_info(f"➖ sell {sell_amount} of {leg_data['sell_token']}")
            log_info(f"➕ buy some amount of {leg_data['buy_token']}")
        else:
            buy_amount = to_solution(order_data['buy_amount'])
            log_info(f"➖ sell {buy_amount} of {leg_data['buy_token']}")
            log_info(f"➕ buy some amount of {leg_data['sell_token']}")


    @staticmethod
    def _print_total_order_surplus(total_surplus) -> None:
        """Pretty print total surplus for 2-legs trade."""
        log_info(f'Total order surplus: {to_solution(total_surplus)}')


    ###########################################
    #   Private methods: Token conservation   #
    ###########################################

    @staticmethod
    def _are_tokens_conserved_first_leg(exec_amount, amount, 
                                                surplus=0, err=None) -> None:
        """
            Sanity check for token conservation for first leg trade,
            allowing a small additive err ~ 1/(10^18).
        """
        err = err or 10000 
        if int(exec_amount) - (int(amount) + surplus) > err:
            log_error('This message should never appear as it indicates that tokens ' + \
                      'are not conserved at 1st leg: exec_amount != amount + surplus')
                            
    @staticmethod                        
    def _are_tokens_conserved_second_leg(exec_sell_amount_leg1, 
                                             exec_buy_amount_leg2, err=None) -> None:
        """
            Sanity check for token conservation for second leg trade,
            allowing a small additive err ~ 1/(10^18).
        """
        err = err or 10000 
        if int(exec_sell_amount_leg1) - int(exec_buy_amount_leg2) > err:
            log_error('This message should never appear as it indicates that tokens ' + \
            'are not conserved at 2nd leg: exec_sell_amount_leg1 != exec_buy_amount_leg2')


    ###########################################
    #     Private methods: One-leg strategy   #
    ###########################################

    def _run_one_leg_trade(self, order, amms_data) -> dict:
        """
            Perform one-leg trade for an order to a list of pools.
            This can be also used as a baseline for more advanced trades.
        """

        # Set trade data
        leg_label = order['sell_token'] + order['buy_token'] 

        # Log trade input info
        self._print_initial_info_one_leg( 
                order['sell_amount'], order['sell_token'], amms_data['sell_reserve'],
                order['buy_amount'], order['buy_token'], amms_data['buy_reserve'])

        # Perform trade
        this_trade = ConstantProductAmmApi(order, amms_data)
        solution = this_trade.solve()

        # Log trade output info
        self._print_extra_info(solution)

        # Save results
        # Note: amms exec amount has reverse labels wrt order (see uniswapv2.py).
        exec_sell_amount = solution['amm_exec_buy_amount']
        exec_buy_amount = solution['amm_exec_sell_amount']

        # Sanity check
        self._are_tokens_conserved_first_leg(exec_buy_amount, order['sell_amount'])
        self._are_tokens_conserved_first_leg(exec_sell_amount, 
                                        order['buy_amount'], solution['surplus'])

        return { leg_label: {
                        'sell_token': order['buy_token'],
                        'buy_token': order['sell_token'],
                        'exec_buy_amount': to_solution(exec_buy_amount),
                        'exec_sell_amount': to_solution(exec_sell_amount),
                     }
                }


    ###########################################
    #     Private methods: Two-legs strategy  #
    ###########################################

    def _run_two_legs_simulation(self, this_order, amms) -> dict:
        """Perform a multi-path simulation for a two-legs trade."""
        
        this_amms = {}

        ##############################################
        #       Simulate best trade paths            #
        ##############################################

        for amms_data in amms.values():
      
            ##################################
            #     Run first leg simulation   #
            ##################################

            # Set trade data
            first_leg_order = deep_copy(this_order)
            first_leg_data = amms_data['first_leg']

            # Log trade input info
            self._print_initial_info_two_legs('FIRST LEG', first_leg_order, first_leg_data)

            # Perform trade simulation
            first_leg_trade = ConstantProductAmmApi(first_leg_order, first_leg_data)
            solution_first_leg = first_leg_trade.solve()

            # Sanity check for token conservation
            self._are_tokens_conserved_first_leg(solution_first_leg['amm_exec_sell_amount'], 
                                first_leg_order['sell_amount'])
            self._are_tokens_conserved_first_leg(solution_first_leg['amm_exec_buy_amount'], 
                                first_leg_order['buy_amount'], solution_first_leg['surplus'])

            # Log trade output info
            self._print_extra_info(solution_first_leg)

            ##################################
            #    Run second leg simulation   #
            ##################################
    
            # Set trade data
            second_leg_order = deep_copy(this_order)
            second_leg_data = amms_data['second_leg']

            # Update data from first leg
            second_leg_order['sell_amount'] = solution_first_leg['amm_exec_buy_amount']
            second_leg_order['buy_amount'] = solution_first_leg['amm_exec_sell_amount']

            # Log trade input info
            self._print_initial_info_two_legs('SECOND LEG', second_leg_order, second_leg_data)

            # Perform trade simulation
            second_leg_trade = ConstantProductAmmApi(second_leg_order, second_leg_data)
            solution_second_leg = second_leg_trade.solve()

            # Sanity check for token conservation
            self._are_tokens_conserved_first_leg(solution_second_leg['amm_exec_sell_amount'], 
                            second_leg_order['sell_amount'])
            self._are_tokens_conserved_first_leg(solution_second_leg['amm_exec_buy_amount'], 
                            second_leg_order['buy_amount'], solution_second_leg['surplus'])
            self._are_tokens_conserved_second_leg(solution_first_leg['amm_exec_sell_amount'], 
                            solution_second_leg['amm_exec_buy_amount'])


            # calculate surplus (if it's negative, trade is not fillable so skip)
            total_surplus = solution_first_leg['surplus'] + solution_second_leg['surplus']
            if total_surplus < 0:
                continue

            # Print results
            self._print_extra_info(solution_second_leg)
            self._print_total_order_surplus(total_surplus)
            
            # Save results

            solution_first_leg['amm_buy_token'] = first_leg_data['buy_token']
            solution_first_leg['amm_sell_token'] = first_leg_data['sell_token']
            first_leg_label = solution_first_leg['amm_sell_token'] + solution_first_leg['amm_buy_token'] 

            solution_second_leg['amm_buy_token'] = second_leg_data['buy_token']
            solution_second_leg['amm_sell_token'] = second_leg_data['sell_token']
            second_leg_label = solution_second_leg['amm_sell_token'] + solution_second_leg['amm_buy_token'] 

            this_amms.update(
                { 
                    first_leg_label: solution_first_leg,
                    second_leg_label: solution_second_leg 
                })

        return this_amms


    #######
    #######
    #######


    def _calculate_best_trade_path(self, simulated_amms) -> dict:
        """fff"""
        from src.util.strings import pprint

        from src.util.arithmetics import div, to_decimal
        from decimal import Decimal

        pprint(simulated_amms)

        def _calculate_limit_price(sell_amount, buy_amount) -> Decimal:
            """Calculate the limit price of a given order."""
            return div(sell_amount, buy_amount)

        #for amm_name, amm_data in simulated_amms.items():
        ab1_exec_buy = to_solution(simulated_amms['AB1']['amm_exec_buy_amount'])
        ab1_exec_sell = to_solution(simulated_amms['AB1']['amm_exec_sell_amount'])
        ab1_prior_price = simulated_amms['AB1']['prior_buy_price']
        ab1_market_price = simulated_amms['AB1']['market_buy_price']
        ab1_surplus = simulated_amms['AB1']['surplus']
        ab1_buy_reserve = to_solution(simulated_amms['AB1']['prior_buy_token_reserve'])
        ab1_sell_reserve =   to_solution(simulated_amms['AB1']['prior_sell_token_reserve'])
        ab1_limit_price = _calculate_limit_price(ab1_exec_sell, ab1_exec_buy)


        b1c_exec_buy = to_solution(simulated_amms['B1C']['amm_exec_buy_amount'])
        b1c_exec_sell = to_solution(simulated_amms['B1C']['amm_exec_sell_amount'])
        b1c_prior_price = simulated_amms['B1C']['prior_buy_price']
        b1c_market_price = simulated_amms['B1C']['market_buy_price']
        b1c_surplus = simulated_amms['B1C']['surplus']
        b1c_buy_reserve = to_solution(simulated_amms['B1C']['prior_buy_token_reserve'])
        b1c_sell_reserve =   to_solution(simulated_amms['B1C']['prior_sell_token_reserve'])
        b1c_limit_price = _calculate_limit_price(b1c_exec_sell, b1c_exec_buy)

        ab3_exec_buy = to_solution(simulated_amms['AB3']['amm_exec_buy_amount'])
        ab3_exec_sell = to_solution(simulated_amms['AB3']['amm_exec_sell_amount'])
        ab3_prior_price = simulated_amms['AB3']['prior_buy_price']
        ab3_market_price = simulated_amms['AB3']['market_buy_price']
        ab3_surplus = simulated_amms['AB3']['surplus']
        ab3_buy_reserve = to_solution(simulated_amms['AB3']['prior_buy_token_reserve'])
        ab3_sell_reserve =   to_solution(to_solution(simulated_amms['AB3']['prior_sell_token_reserve']))
        ab3_limit_price = _calculate_limit_price(ab3_exec_sell, ab3_exec_buy)        

        b3c_exec_buy = to_solution(simulated_amms['B3C']['amm_exec_buy_amount'])
        b3c_exec_sell = to_solution(simulated_amms['B3C']['amm_exec_sell_amount'])
        b3c_prior_price = simulated_amms['B3C']['prior_buy_price']
        b3c_market_price = simulated_amms['B3C']['market_buy_price']
        b3c_surplus = simulated_amms['B3C']['surplus']
        b3c_buy_reserve = to_solution(simulated_amms['B3C']['prior_buy_token_reserve'])
        b3c_sell_reserve =   to_solution(simulated_amms['B3C']['prior_sell_token_reserve'])
        b3c_limit_price = _calculate_limit_price(b3c_exec_sell, b3c_exec_buy)

        print('ab1_limit_price', ab1_limit_price, to_solution(ab1_surplus))
        print('b1c_limit_price', b1c_limit_price, to_solution(b1c_surplus))
        print('ab3_limit_price', ab3_limit_price, to_solution(ab3_surplus))
        print('b3c_limit_price', b3c_limit_price, to_solution(b3c_surplus))
        print()

        utility_ab1 = ab1_surplus * ab1_prior_price 
        utility_b1c = b1c_surplus * b1c_prior_price 
        utility_ab3 = ab3_surplus * ab3_prior_price 
        utility_b3c = b3c_surplus * b3c_prior_price 

        print('utility_ab1', utility_ab1, ab1_prior_price)
        print('utility_b1c', utility_b1c, b1c_prior_price)
        print('utility_ab3', utility_ab3, ab3_prior_price)
        print('utility_b3c', utility_b3c, b3c_prior_price)

        print(1 - ab1_prior_price / b1c_prior_price)
        print(1 -ab3_prior_price / b3c_prior_price)


        return simulated_amms

    #######
    #######    #######
    #######    #######
    #######
    #######
    #######



    def _run_two_legs_trade(self, this_order, amms) -> dict:
        """
            Run a two-legs simulation trade for an order to a list of pools, 
            for either one or multiple execution paths, then calculate the
            most optimal path for this trade, returning the final solution.
        """

        solution = {}
        simulated_amms = self._run_two_legs_simulation(this_order, amms) 

        # If this two-legs trade has multiple paths, optimize for them.
        if len(simulated_amms) > 2:
            simulated_amms = self._calculate_best_trade_path(simulated_amms)

        # Save the amms solution to a suitable format.
        for amm_name, amm_data in simulated_amms.items():
            solution.update( 
                { amm_name: 
                    {
                        'sell_token': amm_data['amm_buy_token'],
                        'buy_token': amm_data['amm_sell_token'],
                        'exec_sell_amount': to_solution(amm_data['amm_exec_buy_amount']),
                        'exec_buy_amount': to_solution(amm_data['amm_exec_sell_amount'])
                    }
            })

        return solution


    ##################################
    #     Private methods: Utils     #
    ##################################

    @staticmethod
    def _get_total_exec_amount(this_amms, exec_amount_key, final_token) -> tuple:
        """Add all exec amounts for every leg in the trade."""

        legs_exec_amount = 0
        for leg_label, leg_data in this_amms.items():
            if leg_label[-1] == leg_data[final_token]:
                legs_exec_amount += to_decimal(leg_data[exec_amount_key])
        
        return legs_exec_amount

    def _to_order_solution(self, this_order, this_amms) -> dict:
        """Format order dict to save as the result solution."""
        
        this_order['sell_amount'] = to_solution(this_order['sell_amount'])
        this_order['buy_amount'] = to_solution(this_order['buy_amount'])

        order_num = this_order['order_num']

        if bool(this_order['is_sell_order']):
            exec_sell_amount = this_order['sell_amount']
            exec_buy_amount = self._get_total_exec_amount(this_amms,
                                             'exec_sell_amount', 'sell_token')
            
        else:
            exec_buy_amount = this_order['buy_amount']
            exec_sell_amount = self._get_total_exec_amount(this_amms,
                                            'exec_buy_amount', 'buy_token')
            
        this_order['exec_buy_amount'] = to_solution(exec_buy_amount)
        this_order['exec_sell_amount'] = to_solution(exec_sell_amount)

        del this_order['order_num']
        
        return { order_num: this_order }


    ###########################
    #   Public methods        #
    ###########################

    def solve(self, order) -> dict:
        """Entry point for this class."""

        amms_solution = {}
        orders_solution = {}

        for trade_type, amms_data in self.__amms.items():     
            this_amms = {}

            if trade_type == 'one_leg_trade':
                this_amms = self._run_one_leg_trade(order, amms_data)
    
            elif trade_type == 'two_legs_trade':
                this_amms = self._run_two_legs_trade(order, amms_data)
                
            else:
                log_error(f'No valid reserve or support for"{trade_type}"')

            # Format order dict to add results from executed trade.    
            this_order = self._to_order_solution(order, this_amms)

            amms_solution.update(this_amms)
            orders_solution.update(this_order)

        return {
            'amms': amms_solution,
            'orders': orders_solution
        }
