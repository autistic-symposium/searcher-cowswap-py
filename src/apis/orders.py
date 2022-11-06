# -*- encoding: utf-8 -*-
# apis/orders.py
# This class implements an api to parse order instances.


from src.util.os import open_json, log_error
from src.util.strings import to_decimal_str, pprint

class OrdersApi(object):

    def __init__(self, input_file):
        
        self.__orders = None
        self.__amms = None

        # initialization
        self._parse_order_instance(input_file)


    ###########################
    #     Access methods      #
    ###########################
    @property
    def orders(self) -> dict:
        """Access to full order data."""
        return self.__orders

    @property
    def orders_data(self) -> dict:
        """Pretty print full orders data."""
        return pprint(self.__orders)

    @property
    def amms_data(self) -> dict:
        """Pretty print full amms data."""
        return pprint(self.__amms)


    ###############################
    #     Private methods         #
    ###############################

    def _parse_order_instance(self, input_file) -> None:
        """Parse an input instance of orders to a suitable format."""

        order_instance = open_json(input_file)

        try:
            self.__orders = order_instance['orders']        
            self.__amms = order_instance['amms']
        
        except KeyError as e:
            log_error(f'Could not load order instance(no amms or orders key): {e}')


    ###############################
    #     Static methods          #
    ###############################

    @staticmethod
    def parse_order_for_spread_trade(order, order_num) -> dict:
        """Parse input order into a suitable format for spread strategy."""

        try: 
            return {
                    'allow_partial_fill': order['allow_partial_fill'],
                    'is_sell_order': order['is_sell_order'],
                    'buy_amount': to_decimal_str(order['buy_amount']),
                    'sell_amount': to_decimal_str(order['sell_amount']),
                    'buy_token': order['buy_token'],
                    'sell_token': order['sell_token'],
                    'order_num': order_num
                }

        except KeyError as e:
            log_error(f'Input order data is ill-formatted: {e}')


    ###############################
    #     Public methods          #
    ###############################

    def parse_amms_for_spread_trade(self, order) -> dict:
        """Parse a list of pools into a suitable format for spread strategy."""

        # Check whether input order is valid and tokens are not zero.
        try:
            buy_token = order['buy_token']
            sell_token = order['sell_token']
        except KeyError as e:
            log_error(f'Order has no data for buy/sell token: {e}')
            return

        if buy_token == 0 or sell_token == 0:
            log_error('Order invalid: either sell or buy token is zero.')
            return
        
        # Parse amms in terms of number of trading legs and pools.
        trade_path = sell_token + buy_token
        this_amms = {}

        for pool, pool_data in self.__amms.items():

            try:

                pool_data = pool_data['reserves']

                # Parse data for one-leg trades.
                if pool == trade_path:

                    trade_type = 'one_leg_trade'

                    data = {
                        'buy_token': buy_token,
                        'sell_token': sell_token,
                        'sell_reserve': to_decimal_str(pool_data[sell_token]),
                        'buy_reserve': to_decimal_str(pool_data[buy_token])
                    }

                    this_amms[trade_type] = data

                # Parse data for two-leg trades.
                else:
                    # For orders with more than one-leg, reserve names
                    # are represented by 3 letters (e.g. AB1).
                    if len(pool) == 3:
                        trade_type = 'two_legs_trade'
                        
                        if trade_type not in this_amms.keys():
                            this_amms[trade_type] = {}

                        # First leg
                        if pool[0] == sell_token:
                            this_buy_token = pool[1:]
                            if this_buy_token not in this_amms[trade_type].keys():
                                this_amms[trade_type][this_buy_token] = {}

                            data = {
                                    'sell_token': sell_token,
                                    'buy_token': this_buy_token,
                                    'sell_reserve': to_decimal_str(pool_data[sell_token]),
                                    'buy_reserve': to_decimal_str(pool_data[this_buy_token])
                            }
                            this_amms[trade_type][this_buy_token]['first_leg'] = data
                
                        # Second leg
                        elif pool[-1] == buy_token:
                            this_sell_token = pool[:-1]
                            if this_sell_token not in this_amms[trade_type].keys():
                                this_amms[trade_type][this_buy_token] = {}

                            data = {
                                    'sell_token': this_sell_token,
                                    'buy_token': buy_token,
                                    'sell_reserve': to_decimal_str(pool_data[this_sell_token]), 
                                    'buy_reserve': to_decimal_str(pool_data[buy_token])
                                }
                            this_amms[trade_type][this_sell_token]['second_leg'] = data
                        
                        else:
                            log_error(f'Could not extract order data for {pool}.')
                
                    else:
                        log_error(f'COWSOL has no strategy for 3-legs trade or higher (yet)')

            
            except KeyError as e:
                log_error(f'Input data is ill-formatted: {e}')
                continue

        return this_amms
