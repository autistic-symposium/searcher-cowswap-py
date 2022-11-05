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
            log_debug(f"Surplus: {to_solution(solution['surplus'])}")
            log_debug(f"Initial price: {solution['prior_price']}")
            log_debug(f"Market price: {solution['market_price']}")
            log_debug(f"Exec sell amount: {to_solution(solution['amm_exec_sell_amount'])}")
            log_debug(f"Exec buy amount: {to_solution(solution['amm_exec_buy_amount'])}")
            log_debug(f"Initial sell reserve: {to_solution(solution['prior_sell_token_reserve'])}")
            log_debug(f"Initial buy reserve: {to_solution(solution['prior_buy_token_reserve'])}")
            log_debug(f"Updated sell reserve: {to_solution(solution['updated_sell_token_reserve'])}")
            log_debug(f"Updated buy reserve: {to_solution(solution['updated_buy_token_reserve'])}")
        except KeyError as e:
            log_error(f'Could not print data for "{e}"')

    @staticmethod
    def _print_initial_info_one_leg(sell_amount, sell_token, amm_sell_reserve,
                                        buy_amount, buy_token, amm_buy_reserve) -> None:
        """Print input info from a one-leg trade order."""
        log_info(f"One-leg trade overview:")
        log_info(f"sell {to_solution(sell_amount)} of {sell_token}," + \
                            f" amm reserve: {to_solution(amm_sell_reserve)}")
        log_info(f"buy {to_solution(buy_amount)} of {buy_token}," + \
                            f" amm reserve: {to_solution(amm_buy_reserve)}")

    @staticmethod
    def _print_initial_info_two_legs(leg, trade_strings, sell_amount, 
                                    sell_token, buy_amount, buy_token) -> None:
        """Print input info for first leg of a two-legs trade."""
        log_info(f"{leg} leg trade overview:")
        log_info(f"{trade_strings[0]} {sell_amount} of {sell_token}")
        log_info(f"{trade_strings[1]} {buy_amount} of {buy_token}")

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
            allowing a small aditive err ~ 1/(10^18).
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
            allowing a small aditive err ~ 1/(10^18).
        """
        err = err or 10000 
        if int(exec_sell_amount_leg1) - int(exec_buy_amount_leg2) > err:
            log_error('This message should never appear as it indicates that tokens ' + \
            'are not conserved at 2nd leg: exec_sell_amount_leg1 != exec_buy_amount_leg2')

    @staticmethod
    def _are_tokens_conserved_multiple_execution(order, amms, err=None) -> None:
        """
            Sanity check for token conservation for the entire execution trade, for 
            trades with 2 legs or more, allowing a small aditive err ~ 1/(10^18).
        """
        # TODO: FIX
        if len(amms) < 2:
            return 

        err = err or 10000 
        sum_exec_amount_first_legs = 0
        sum_exec_amount_second_legs = 0

        print(order)

        for amm_leg, amm_data in amms.items():

            # First leg
            if amm_leg[0] == amm_data['buy_token']:
                sum_exec_amount_first_legs = sum_exec_amount_first_legs + \
                                         int(amm_data['exec_sell_amount'])
            # Second leg
            elif amm_leg[-1] == amm_data['sell_token']:
                sum_exec_amount_second_legs = sum_exec_amount_second_legs + \
                                           int(amm_data['exec_buy_amount'])

        print(sum_exec_amount_first_legs, amm_data['exec_sell_amount'])
        print(sum_exec_amount_second_legs, amm_data['exec_buy_amount'])
        print(abs(sum_exec_amount_first_legs - to_decimal(amm_data['exec_sell_amount'])) > err)
        print(abs(sum_exec_amount_second_legs - to_decimal(amm_data['exec_buy_amount'])) > err)
            
        if abs(sum_exec_amount_first_legs - to_decimal(order['exec_sell_amount'])) > err or \
           abs(sum_exec_amount_second_legs - to_decimal(order['exec_buy_amount'])) > err:
                log_error('This message should never appear as it indicates that ' + \
                                            'tokens are not conserved in this trade.')     


    ###########################################
    #     Private methods: One-leg strategy   #
    ###########################################

    def _run_one_leg_trade(self, order, amms_data) -> dict:
        """Perform one-leg trade for an order to a list of pools."""

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
        # Note: amms exec amount have reverse labels wrt order (see uniswapv2.py).
        exec_sell_amount = solution['amm_exec_buy_amount']
        exec_buy_amount = solution['amm_exec_sell_amount']

        # Sanity check
        self._are_tokens_conserved_first_leg(exec_buy_amount, order['sell_amount'])
        self._are_tokens_conserved_first_leg(exec_sell_amount, 
                                        order['buy_amount'], solution['surplus'])

        this_amms =  { 
            leg_label: {
                        'sell_token': order['buy_token'],
                        'buy_token': order['sell_token'],
                        'exec_buy_amount': to_solution(exec_buy_amount),
                        'exec_sell_amount': to_solution(exec_sell_amount),
                     }
        }

        return this_amms


    ###########################################
    #     Private methods: Two-leg strategy   #
    ###########################################

    def _run_two_legs_trade(self, this_order, amms) -> dict:
        """Perform two-legs trade for an order to a list of pools."""

        this_amms = {}
        is_sell_order = bool(this_order['is_sell_order'])

        for amms_data in amms.values():
      
            ########################
            #     Run first leg    #
            ########################

            # Set trade data
            first_leg_order = deep_copy(this_order)
            first_leg_data = amms_data['first_leg']

            first_leg_order['sell_token'] = first_leg_data['sell_token']
            first_leg_order['buy_token'] = first_leg_data['buy_token']

            first_leg_label = first_leg_order['sell_token'] + first_leg_data['buy_token']

            # Log trade input info
            if is_sell_order: 
                trade_strings = ['sell', 'buy']
                buy_info = 'some amount'
                sell_info = to_solution(first_leg_order['sell_amount'])
            else:
                trade_strings = ['buy', 'sell']
                sell_info = 'some amount' 
                buy_info = to_solution(first_leg_order['buy_amount'])

            self._print_initial_info_two_legs('FIRST', trade_strings, sell_info,
                    first_leg_order['sell_token'], buy_info, first_leg_order['buy_token'])

            # Perform trade
            first_leg_trade = ConstantProductAmmApi(first_leg_order, first_leg_data)
            solution_first_leg = first_leg_trade.solve()

            # Log trade output info
            self._print_extra_info(solution_first_leg)

            # Sanity check for token conservation
            self._are_tokens_conserved_first_leg(solution_first_leg['amm_exec_sell_amount'], 
                                first_leg_order['sell_amount'])
            self._are_tokens_conserved_first_leg(solution_first_leg['amm_exec_buy_amount'], 
                                first_leg_order['buy_amount'], solution_first_leg['surplus'])

            # Save results
            # Note: amms exec amount have reverse labels wrt order (see uniswapv2.py).
            this_amms.update({ 
                first_leg_label:
                    {
                        'sell_token': first_leg_data['buy_token'],
                        'buy_token': first_leg_data['sell_token'],
                        'exec_sell_amount': to_solution(solution_first_leg['amm_exec_buy_amount']),
                        'exec_buy_amount': to_solution(solution_first_leg['amm_exec_sell_amount']),
                        'surplus': to_solution(solution_first_leg['surplus'])
                    }})

            ########################
            #     Run second leg   #
            ########################
    
            # Set trade data
            second_leg_order = deep_copy(this_order)
            second_leg_data = amms_data['second_leg']

            second_leg_order['sell_token'] = second_leg_data['sell_token']
            second_leg_order['buy_token'] = second_leg_order['buy_token']

            # Update data from first leg
            # Note: amms exec amount  have reverse labels wrt order (see uniswapv2.py).
            second_leg_order['sell_amount'] = solution_first_leg['amm_exec_buy_amount']
            second_leg_order['buy_amount'] = solution_first_leg['amm_exec_sell_amount']

            second_leg_label = second_leg_data['sell_token'] + second_leg_order['buy_token']

            # Log trade input info
            if is_sell_order: 
                sell_info = to_solution(second_leg_order['sell_amount'])

            self._print_initial_info_two_legs('SECOND', trade_strings, sell_info, 
                second_leg_data['sell_token'], buy_info, second_leg_data['buy_token'])

            # Perform trade
            second_leg_trade = ConstantProductAmmApi(second_leg_order, second_leg_data)
            solution_second_leg = second_leg_trade.solve()

            self._print_extra_info(solution_second_leg)

            # Print total results
            self._print_total_order_surplus(solution_first_leg['surplus'] + \
                                                    solution_second_leg['surplus'])
            
            # Sanity check for token conservation
            self._are_tokens_conserved_first_leg(solution_second_leg['amm_exec_sell_amount'], 
                            second_leg_order['sell_amount'])
            self._are_tokens_conserved_first_leg(solution_second_leg['amm_exec_buy_amount'], 
                            second_leg_order['buy_amount'], solution_second_leg['surplus'])
            self._are_tokens_conserved_second_leg(solution_first_leg['amm_exec_sell_amount'], 
                            solution_second_leg['amm_exec_buy_amount'])

            # Save results
            # Note: amms exec amount have reverse labels wrt order (see uniswapv2.py).
            this_amms.update({
                second_leg_label: 
                    {
                        'sell_token': second_leg_data['buy_token'],
                        'buy_token': second_leg_data['sell_token'],
                        'exec_sell_amount': to_solution(solution_second_leg['amm_exec_buy_amount']),
                        'exec_buy_amount': to_solution(solution_second_leg['amm_exec_sell_amount']),
                        'surplus': to_solution(solution_second_leg['surplus'])
                    }
                })
        
        ab1 = this_amms['AB1']['surplus']
        b1c = this_amms['B1C']['surplus']
        print('ab1 ', ab1)
        print('b1c ', b1c)     
        print(to_solution(int(ab1)+int(b1c)))
        print()
        ab1 = this_amms['AB2']['surplus']
        b1c = this_amms['B2C']['surplus']
        print('ab2 ', ab1)
        print('b2c ', b1c)   
        print(to_solution(int(ab1)+int(b1c)))
        print()
        ab1 = this_amms['AB3']['surplus']
        b1c = this_amms['B3C']['surplus']
        print('ab3 ', ab1)
        print('b3c ', b1c)   
        print(to_solution(int(ab1)+int(b1c)))
        print()
        from src.util.strings import pprint
        #pprint(this_amms)
        import sys
        sys.exit()
        
        return this_amms


    ##################################
    #     Private methods: Utils     #
    ##################################

    @staticmethod
    def _get_total_exec_amount(this_amms, exec_amount_key, final_token) -> tuple:
        """Add all exec amounts for every leg in the trade."""

        legs_exec_amount = 0
        for leg_label, leg_data in this_amms.items():
            if leg_label[-1] == leg_data[final_token]:
                legs_exec_amount = legs_exec_amount + to_decimal(leg_data[exec_amount_key])
        
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
