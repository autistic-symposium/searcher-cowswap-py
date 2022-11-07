# -*- encoding: utf-8 -*-
# strategies/spread_solver.py
# This class implements a solver for spread arbitrage.

from src.util.strings import to_solution
from src.util.arithmetics import to_decimal, div
from src.apis.uniswapv2 import ConstantProductAmmApi
from src.util.os import log_debug, log_error, log_info, deep_copy


class SpreadSolverApi(object):

    def __init__(self, amms):

        self.__amms = amms
        self.__supplus_ranking = {}

    ###########################################
    #     Private methods: Pretty prints      #
    ###########################################

    @staticmethod
    def _print_extra_info(solution) -> None:
        """Print debug info from solution."""
        
        try:
            log_debug(f"  Prior sell reserve: {to_solution(solution['prior_sell_token_reserve'])}")
            log_debug(f"  Prior buy reserve: {to_solution(solution['prior_buy_token_reserve'])}")
            log_debug(f"  Prior sell price {solution['prior_sell_price']}")
            log_debug(f"  Prior buy price {solution['prior_buy_price']}")
            log_debug(f"  AMM exec sell amount: {to_solution(solution['amm_exec_sell_amount'])}")
            log_debug(f"  AMM exec buy amount: {to_solution(solution['amm_exec_buy_amount'])}")
            log_debug(f"  Updated sell reserve: {to_solution(solution['updated_sell_token_reserve'])}")
            log_debug(f"  Updated buy reserve: {to_solution(solution['updated_buy_token_reserve'])}")
            log_debug(f"  Market sell price {solution['market_sell_price']}")
            log_debug(f"  Market buy price {solution['market_buy_price']}")
            log_debug(f"  Can fill: {solution['can_fill']}")
            log_debug(f"  Surplus: {to_solution(solution['surplus'])}")

        except KeyError as e:
            log_error(f'Could not print data for "{e}"')

    @staticmethod
    def _print_initial_info_one_leg(sell_amount, sell_token, amm_sell_reserve,
                                        buy_amount, buy_token, amm_buy_reserve) -> None:
        """Print input info from a one-leg trade order."""

        log_info("One-leg trade overview:")
        log_info(f"➖ sell {to_solution(sell_amount)} of {sell_token}," + 
                            f" amm reserve: {to_solution(amm_sell_reserve)}")
        log_info(f"➕ buy {to_solution(buy_amount)} of {buy_token}," + 
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

        log_info(f'TOTAL ORDER SURPLUS: {to_solution(total_surplus)}')


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
            log_error('This message should never appear as it indicates that tokens ' + 
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
            log_error('This message should never appear as it indicates that tokens ' + 
            'are not conserved at 2nd leg: exec_sell_amount_leg1 != exec_buy_amount_leg2')

    ###########################################
    #     Private methods: One-leg strategy   #
    ###########################################

    def _run_one_leg_trade(self, order, amms_data) -> dict:
        """
            Perform one-leg trade for an order to a list of pools, 
            i.e., A -> C. Can be a baseline for advanced trades.
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

        return {leg_label: {
                        'sell_token': order['buy_token'],
                        'buy_token': order['sell_token'],
                        'exec_buy_amount': to_solution(exec_buy_amount),
                        'exec_sell_amount': to_solution(exec_sell_amount),
                     }
                }

    ###########################################
    #     Private methods: Two-legs strategy  #
    ###########################################

    def _run_two_leg_trade(self, this_order, amms, simulation=False) -> dict:
        """
            Perform a multi-path simulation for a two-legs trade,
            i.e. A -> C through A -> Ti -> C, where i E [1, 2+].
        """
        
        this_amms = {}
        self.__supplus_ranking[this_order['order_num']] = {}

        ##############################################
        #       Simulate best trade paths            #
        ##############################################

        for amm_token, amm_data in amms.items():
      
            ##################################
            #     Run first leg simulation   #
            ##################################

            # Set trade data
            first_leg_order = deep_copy(this_order)
            first_leg_data = amm_data['first_leg']

            # Perform trade simulation
            first_leg_trade = ConstantProductAmmApi(first_leg_order, first_leg_data)
            solution_first_leg = first_leg_trade.solve()
            
            if not simulation:
                # Log trade input info
                self._print_initial_info_two_legs('FIRST LEG', first_leg_order, first_leg_data)

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
            second_leg_data = amm_data['second_leg']

            # Update data from first leg
            second_leg_order['sell_amount'] = solution_first_leg['amm_exec_buy_amount']
            second_leg_order['buy_amount'] = solution_first_leg['amm_exec_sell_amount']

            # Perform trade simulation
            second_leg_trade = ConstantProductAmmApi(second_leg_order, second_leg_data)
            solution_second_leg = second_leg_trade.solve()
            

            if not simulation:
                # Log trade input info
                self._print_initial_info_two_legs('SECOND LEG', second_leg_order, second_leg_data)

                # Sanity check for token conservation
                self._are_tokens_conserved_first_leg(solution_second_leg['amm_exec_sell_amount'], 
                                second_leg_order['sell_amount'])
                self._are_tokens_conserved_first_leg(solution_second_leg['amm_exec_buy_amount'], 
                                second_leg_order['buy_amount'], solution_second_leg['surplus'])
                self._are_tokens_conserved_second_leg(solution_first_leg['amm_exec_sell_amount'], 
                                solution_second_leg['amm_exec_buy_amount'])


            # calculate surplus (if it's negative, trade is not fillable so skip)
            total_surplus = solution_first_leg['surplus'] + solution_second_leg['surplus']
            self.__supplus_ranking[this_order['order_num']][amm_token] = total_surplus
            #if total_surplus < 0:
            #    continue

            if not simulation:
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

    def _optimize_for_2_legs_2_pools(self, amm1, amm2, this_order) -> dict:
        """ Optimize for two pool paths for a two-legs trade order,
            i.e., A -> C through A -> T1 -> C AND A -> T2 -> C.
        """

        order_sell_amount = int(this_order['sell_amount'])   #1000000000000000000000 # sell A
        order_buy_amount = int(this_order['buy_amount'])    #900000000000000000000 # buy C


        ab1_sell_reserve = int(amm1['first_leg']['sell_reserve'])           #10000000000000000000000 # order sell A
        ab1_buy_reserve = int(amm1['first_leg']['buy_reserve'])           #120000000000000000000000 # order buy B3
        b1c_sell_reserve = int(amm1['second_leg']['sell_reserve'])  #order sell B1
        b1c_buy_reserve = int(amm1['second_leg']['buy_reserve'])  # order buy C

        ab3_sell_reserve = int(amm2['first_leg']['sell_reserve'])      # 112000000000000000000000 # order sell A
        ab3_buy_reserve= int(amm2['first_leg']['buy_reserve'])   # 112000000000000000000000 # order buy B3
        b3c_sell_reserve_cte = int(amm2['second_leg']['sell_reserve'])  # order sell B3
        b3c_buy_reserve_cte = int(amm2['second_leg']['buy_reserve']) # order buy C

        limit_price_cte = order_sell_amount / order_buy_amount

        # a -> b
        ab1_buy_amount = 289034099526748718745
        ab1_buy_amount_max = order_sell_amount
        ab1_buy_amount_min = 0
        
        def surplus_equation(ab1_buy_amount):
            return (b1c_buy_reserve * (ab1_buy_reserve * ab1_buy_amount) / \
                    (ab1_sell_reserve + ab1_buy_amount)) / (b1c_sell_reserve + \
                    (ab1_buy_reserve * ab1_buy_amount) / (ab1_sell_reserve + ab1_buy_amount)) + \
                    (b3c_buy_reserve_cte * (ab3_buy_reserve * (order_sell_amount - ab1_buy_amount)) / \
                    (ab3_sell_reserve + (order_sell_amount - ab1_buy_amount))) / \
                    (b3c_sell_reserve_cte + (ab3_buy_reserve * (order_sell_amount - ab1_buy_amount)) / \
                    (ab3_sell_reserve + (order_sell_amount - ab1_buy_amount))) - \
                    order_sell_amount / limit_price_cte

        print(surplus_equation(ab1_buy_amount))
        from src.util.arithmetics import nelder_mead_simplex_optimization

        boundary = (ab1_buy_amount_min, ab1_buy_amount_max)
        solution = nelder_mead_simplex_optimization(surplus_equation, boundary)
        print(int(to_decimal(solution)))
        print(int(to_decimal(order_sell_amount - solution)))

        exec_buy_amount_t1 = int(to_decimal(solution))
        exec_buy_amount_t2 = int(to_decimal(order_sell_amount - solution))

        #amm1['first_leg']['exec_buy_amount'] = int(to_decimal(solution))
        #amm2['first_leg']['exec_buy_amount'] = int(to_decimal(order_sell_amount - solution))


        return exec_buy_amount_t1, exec_buy_amount_t2
      

    def _run_two_legs_trade(self, this_order, amms) -> dict:
        """
            Run a two-legs simulation trade for an order to a list of pools,
            for either one or multiple execution paths, then calculate the
            most optimal path for this trade, returning the final solution.
        """
        from src.util.strings import pprint
        solution = {}

        if len(amms) == 1:
            this_amms = self._run_two_leg_trade(this_order, amms, simulation=False)
        
            pprint(this_amms)
            import sys
            sys.exit()

        elif len(amms) > 1:
            # Solve for two-legs trade with multiple execution pools.
            log_debug('Using the best two execution simulations by surplus yield.')            
            _ = self._run_two_leg_trade(this_order, amms, simulation=True)

            suplus_rank = self.__supplus_ranking[this_order['order_num']]
            sorted_ = [k for k, v in sorted(suplus_rank.items(), key=lambda item: item[1], reverse=True)]

            # TODO SELL ORDERS VS BUY ORDERS
            midtoken1 = sorted_[0]
            midtoken2 = sorted_[1]
            key1 = this_order['sell_token'] + midtoken1
            key2 = midtoken1 + this_order['buy_token'] 
            key3 = this_order['sell_token'] + midtoken2
            key4 = midtoken2 + this_order['buy_token'] 


            amms1 = amms[midtoken1]
            amms2 = amms[midtoken2]
    
            exec_buy_amount_t1, exec_buy_amount_t2 = self._optimize_for_2_legs_2_pools(amms1, amms2, this_order)



            order1 = deep_copy(this_order)
            order1['sell_amount'] = exec_buy_amount_t1
            order2 = deep_copy(this_order)
            order2['sell_amount'] = exec_buy_amount_t2

            #amms1 = {midtoken1: amms1}
            #amms2 = {midtoken2: amms2}

            # solution_first_leg_path1
            first_leg_order_path1 = deep_copy(order1)
            first_leg_path1 = ConstantProductAmmApi(first_leg_order_path1, amms1['first_leg'])
            solution_first_leg_path1 = first_leg_path1.solve()

            # solution_second_leg_path1
            second_leg_order_path1 = deep_copy(order1)
            second_leg_order_path1['sell_amount'] = solution_first_leg_path1['amm_exec_buy_amount']
            second_leg_order_path1['buy_amount'] = solution_first_leg_path1['amm_exec_sell_amount']
            
            second_leg_path1 = ConstantProductAmmApi(second_leg_order_path1, amms1['second_leg'])
            solution_second_leg_path1 = second_leg_path1.solve()

            # solution_first_leg_path2
            first_leg_order_path2 = deep_copy(order2)
            first_leg_path2 = ConstantProductAmmApi(first_leg_order_path2, amms2['first_leg'])
            solution_first_leg_path2 = first_leg_path2.solve()

            # solution_second_leg_path2
            second_leg_order_path2 = deep_copy(order2)
            second_leg_order_path2['sell_amount'] = solution_first_leg_path2['amm_exec_buy_amount']
            second_leg_order_path2['buy_amount'] = solution_first_leg_path2['amm_exec_sell_amount']
            
            second_leg_trade = ConstantProductAmmApi(second_leg_order_path2, amms2['second_leg'])
            solution_second_leg_path2 = second_leg_trade.solve()

            ####
            solution_first_leg_path1['amm_buy_token'] = amms1['first_leg']['buy_token']
            solution_first_leg_path1['amm_sell_token'] = amms1['first_leg']['sell_token']

            solution_second_leg_path1['amm_buy_token'] = amms1['second_leg']['buy_token']
            solution_second_leg_path1['amm_sell_token'] = amms1['second_leg']['sell_token']


            solution_first_leg_path2['amm_buy_token'] = amms2['first_leg']['buy_token']
            solution_first_leg_path2['amm_sell_token'] = amms2['first_leg']['sell_token']

            solution_second_leg_path2['amm_buy_token'] = amms2['second_leg']['buy_token']
            solution_second_leg_path2['amm_sell_token'] = amms2['second_leg']['sell_token']

            log_info('EXECUTION PATH1')
            log_info('1️⃣ FIRST LEG trade overview:')
            self._print_extra_info(solution_first_leg_path1)
            log_info('1️⃣ SECOND LEG trade overview:')
            self._print_extra_info(solution_second_leg_path1)
            log_info('EXECUTION PATH2')
            log_info('2️⃣ FIRST LEG trade overview:')
            self._print_extra_info(solution_first_leg_path2)
            log_info('2️⃣ SECOND LEG trade overview:')
            self._print_extra_info(solution_second_leg_path2)


            this_amms = {
                key1: solution_first_leg_path1,
                key2: solution_second_leg_path1,
                key3: solution_first_leg_path2,
                key4: solution_second_leg_path2

            }


        # Save the final amms solution to a suitable format.
        for amm_name, amm_data in this_amms.items():
            solution.update(
                {amm_name:
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

        return {order_num: this_order}

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
