# -*- encoding: utf-8 -*-
# apis/uniswapv2.py
# This class implements an api for trading tokens on AMMs reserves
# governed by constant product, such as Uniswap V2 (and its forks).

from decimal import Decimal
from src.util.arithmetics import div, to_decimal

class ConstantProductAmmApi(object):

    def __init__(self, order, amms):

        # Order data
        self.buy_amount = to_decimal(order['buy_amount'])
        self.sell_amount = to_decimal(order['sell_amount'])
        self.is_sell_order = bool(order['is_sell_order'])
        self.allow_partial_fill = bool(order['allow_partial_fill'])

        # Reserves data
        self.buy_token_reserve = to_decimal(amms['buy_reserve'])
        self.sell_token_reserve = to_decimal(amms['sell_reserve'])


    ###############################
    #     Private methods         #
    ###############################

    def _calculate_limit_price(self) -> Decimal:
        """Calculate the limit price of a given order."""
        return div(self.sell_amount, self.buy_amount)

    def _calculate_exec_sell_amount(self) -> Decimal:
        """"
            Implement a constant-product the retrieval of tokens B from selling an amount 
            t of tokens A in an AB pool, where a and b are the initial token reserves:
                 δ    ≤    (b − a * b) / (a + t)    =    (b * t) / (a + t)
        """
        return div((self.buy_token_reserve * self.sell_amount), \
                                    (self.sell_token_reserve + self.sell_amount))
    
    def _calculate_exec_buy_amount(self) -> Decimal: 
        raise NotImplementedError

    def _can_fill_order(self, exec_amount, limit_amount) -> bool:
        """Verify whether the order checks the limit price constraint."""
        if self.allow_partial_fill:
            return exec_amount <= limit_amount
        else:
            return exec_amount == limit_amount


    ###############################
    #      Static methods         #
    ###############################

    @staticmethod
    def _calculate_token_price(token_balance, pair_token_balance) -> Decimal:
        """Return the current (market) price for a token in the pool."""
        return div(pair_token_balance, token_balance)
   
    @staticmethod
    def _calculate_surplus(exec_amount, amount) -> Decimal:
        """
            Calculate the surplus of an executed order. This is similar to:
            exec_buy_amount - exec_sell_amount / limit_price
        """
        return to_decimal(exec_amount) - to_decimal(amount)

    @staticmethod
    def _calculate_exchange_rate(sell_reserve, buy_reserve):
        """Calculate the exchange rate between a pair of tokens."""
        return div(buy_reserve, sell_reserve)


    ###############################
    #     Public methods          #
    ###############################

    def trade_sell_order(self) -> dict:
        """
            Get sell limit order data for a list of reserves.

            In this trade, the order will add "sell_token" to the reserve at the value
            of "sell_amount" and retrieve "buy_token" at a calculated "exec_buy_amount".
            This will reflect the inverse in the amm: the reserve will receive token A 
            at the amount "amm_exec_buy_amount" (which matches the order's exec_sell_amount),
            and lose token C at "amm_exec_sell_amount" (orders' calculated exec_buy_amount).
        """
        
        # Calculate order execution data
        amm_exec_buy_amount = int(self.sell_amount)
        amm_exec_sell_amount = int(self._calculate_exec_sell_amount())

        # Check limit price for exec_sell_ammount
        can_fill = self._can_fill_order(amm_exec_buy_amount, self.sell_amount)

        # Calculate surplus for this sell order
        surplus = int(self._calculate_surplus(amm_exec_sell_amount, self.buy_amount))

        # Get some extra data on the reserve
        prior_sell_token_reserve = int(self.sell_token_reserve)
        prior_buy_token_reserve = int(self.buy_token_reserve)
        updated_sell_token_reserve = int(self.sell_token_reserve + amm_exec_buy_amount)
        updated_buy_token_reserve = int(self.buy_token_reserve - amm_exec_sell_amount)
        exchange_rate = float(self._calculate_exchange_rate(prior_sell_token_reserve, \
                                                        prior_buy_token_reserve))

        # Return order execution simulation results
        return({
            'exchange_rate': exchange_rate,
            'surplus': surplus,
            'amm_exec_sell_amount': amm_exec_buy_amount,
            'amm_exec_buy_amount': amm_exec_sell_amount,
            'updated_sell_token_reserve': updated_sell_token_reserve,
            'updated_buy_token_reserve': updated_buy_token_reserve,
            'prior_sell_token_reserve': prior_sell_token_reserve,
            'prior_buy_token_reserve': prior_buy_token_reserve,
            'can_fill': can_fill
        })


    def trade_buy_order(self) -> dict:
        """Get buy limit order data for a list of reserves."""
        raise NotImplementedError


    def solve(self) -> dict:
        """Entry point for this class."""
        if self.is_sell_order:
            return self.trade_sell_order()
        else:
            return self.trade_buy_order()
