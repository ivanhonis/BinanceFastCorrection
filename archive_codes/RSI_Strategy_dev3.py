# Binance Fast Correction Strategy
import random
import sys

import requests
# from collections import deque
import backtrader as bt
import pickle
from datetime import datetime
from types import SimpleNamespace
import json

import numpy as np
import ta as ta
import pandas as pd
from joblib import dump, load
from binance import Client, ThreadedWebsocketManager
import pprint

class CollectData:

    def __init__(self, length, live_run, init_price=69250.0):
        self.length = length

        # az záróár az elején van azaz [0] az aktuális záró, [1] az időben egyel előtte
        self.open_history = np.full(length, init_price, dtype=np.float64)
        self.high_history = np.full(length, init_price, dtype=np.float64)
        self.low_history = np.full(length, init_price, dtype=np.float64)
        self.close_history = np.full(length, init_price, dtype=np.float64)
        self.rsi_history = np.full(length, init_price, dtype=np.float64)
        self.rsi_over_sold = np.full(length, 50, dtype=np.float64)
        self.rsi_over_bought = np.full(length, 50, dtype=np.float64)

        # záróár
        self.open = 0
        self.high = 0
        self.low = 0
        self.close = 0

        self.decision = np.full(length, 0, dtype=np.int8)
        self.meta = {}
        self.live_run = live_run

    def add_left(self, array, data):
        array[1:] = array[0:self.length - 1]
        array[0] = data

    def add_data(self, data, last_rsi, over_sold, over_bought):
        if self.live_run or True:

            self.add_left(self.open_history, float(data.open[0]))
            self.add_left(self.high_history, float(data.high[0]))
            self.add_left(self.low_history, float(data.low[0]))
            self.add_left(self.close_history, float(data.close[0]))
            self.add_left(self.rsi_history, float(last_rsi))
            self.add_left(self.rsi_over_sold, float(over_sold))
            self.add_left(self.rsi_over_bought, float(over_bought))

            self.open = float(data.open[0])
            self.high = float(data.high[0])
            self.low = float(data.low[0])
            self.close = float(data.close[0])

            self.add_left(self.decision, float(0))

    def add_meta(self, field, value):
        if self.live_run:
            self.meta[field] = str(value)

    def save(self):
        if self.live_run:
            save_data_form = {
                'open': self.open_history,
                'high': self.high_history,
                'low': self.low_history,
                'close': self.close_history,
                'rsi': self.rsi_history,
                'rsi_over_sold': self.rsi_over_sold,
                'rsi_over_bought': self.rsi_over_bought,
                'decision': self.decision,
                'meta': self.meta}
            with open('../data_transfer_for_process.pickle', 'wb') as handle:
                pickle.dump(save_data_form, handle, protocol=pickle.HIGHEST_PROTOCOL)


class XSizer(bt.Sizer):

    def __init__(self):
        self.a = 1
        # self.start_cash = start_cash
        # self.force_num_of_symbols = force_num_of_symbols
        # self.max_percent = max_percent
        # self.symbols = symbols
        # self.num_of_symbols = len(self.symbols)
        #
        # self.symbols_position = {}
        # for sy in self.symbols:
        #     self.symbols_position[sy] = 0.0

    # def _getsizing(self, comminfo, cash, data, isbuy):
    #     max_value = self.broker.get_value() * (self.max_percent / 100)
    #     if self.force_num_of_symbols is None:
    #         one_symbol_max_value = max_value / self.num_of_symbols
    #     else:
    #         one_symbol_max_value = max_value / self.force_num_of_symbols
    #
    #     self.symbols_position = {key: 0 for key in self.symbols_position}
    #     for data, position in self.broker.positions.items():
    #         self.symbols_position[data._name] = position.size
    #         # symbol = data._name
    #         # size = position.size
    #         # print(f'Symbol: {symbol}, Position Size: {size}')
    #
    #     # position = self.broker.getposition(data)
    #     qty = (one_symbol_max_value / data.close[0]) - self.symbols_position[data._name]
    #     size = round(qty, 8)
    #
    #     print(self.strategy.symbol_profit)
    #     return size

    def _getsizing(self, comminfo, cash, data, isbuy):

        # print(comminfo, cash, data, isbuy)
        max_value = self.start_cash * (self.max_percent / 100)
        if self.force_num_of_symbols is None:
            one_symbol_max_value = max_value / self.num_of_symbols
        else:
            one_symbol_max_value = max_value / self.force_num_of_symbols

        self.symbols_position = {key: 0 for key in self.symbols_position}
        for idata, position in self.broker.positions.items():
            self.symbols_position[idata._name] = position.size
            # symbol = data._name
            # size = position.size
            # print(f'Symbol: {symbol}, Position Size: {size}')

        # position = self.broker.getposition(data)
        qty = ((one_symbol_max_value + self.strategy.symbol_profit[data._name]) / data.close[0]) - self.symbols_position[data._name]
        size = round(qty, 8)

        if isbuy:
            ib = "BUY"
        else:
            ib = "SELL"

        # print(ib, "Cash:", cash,
        #       "Profit:", self.strategy.symbol_profit,
        #       "Position:", self.symbols_position,
        #       data._name, size,
        #       size * data.close[0])
        return size


class RSIStrategy(bt.Strategy):

    def __init__(self, config, is_load_config=False):
        self.c = config
        self.is_load_config = is_load_config
        self.config_time_stamp = 0
        self.stop_price = 0
        self.take_price = 0
        self.symbol = self.c.base + self.c.quote
        self.do_trade = True

        # self.vrsi = bt.ind.RSI(self.data, period=self.c.rsi_period)
        # self.co = bt.ind.CrossOver(vrsi, over_sold)
        # self.cu = bt.ind.CrossOver(vrsi, over_bought)

        # self.min_steps = max(self.c.std_period, self.c.rsi_period) + 1
        # self.min_steps = self.c.ema_slow + 1

        self.steps_count = 0
        self.last_buy_order = None
        self.total_pnl = 0.00000000

        self.cd = CollectData(length=120,
                              live_run=self.c.live_run,
                              init_price=self.get_price(self.symbol))

        # print("ITT")
        # api_key, api_secret = self.get_api_key()
        # self.binance_socket = ThreadedWebsocketManager(api_key, api_secret, testnet=False)
        # self.binance_socket.daemon = True
        # self.binance_socket.start()
        #
        # self.binance_socket.start_futures_user_socket(self._handle_user_socket_message)

        self.start_cash = self.broker.getcash()
        print("Start cash", self.broker.getcash())


    def get_api_key(self):
        # api_acces_key.json file is:
        #
        # {
        #     "api_key": "xxxxx",
        #     "secure_key": "yyyyy"
        # }

        json_file_path = '../api_acces_key.json'
        with open(json_file_path, 'r') as file:
            keys = json.load(file)

        api_key = keys['api_key']
        secure_key = keys['secure_key']

        return api_key, secure_key


    def _handle_user_socket_message(self, msg):
        """https://binance-docs.github.io/apidocs/spot/en/#payload-order-update"""
        print(msg)
        return
        # # {'e': 'executionReport', 'E': 1707120960762, 's': 'ETHUSDT', 'c': 'oVoRofmTTXJCqnGNuvcuEu', 'S': 'BUY', 'o': 'MARKET', 'f': 'GTC', 'q': '0.00220000', 'p': '0.00000000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '', 'x': 'NEW', 'X': 'NEW', 'r': 'NONE', 'i': 15859894465, 'l': '0.00000000', 'z': '0.00000000', 'L': '0.00000000', 'n': '0', 'N': None, 'T': 1707120960761, 't': -1, 'I': 33028455024, 'w': True, 'm': False, 'M': False, 'O': 1707120960761, 'Z': '0.00000000', 'Y': '0.00000000', 'Q': '0.00000000', 'W': 1707120960761, 'V': 'EXPIRE_MAKER'}
        #
        # # {'e': 'executionReport', 'E': 1707120960762, 's': 'ETHUSDT', 'c': 'oVoRofmTTXJCqnGNuvcuEu', 'S': 'BUY', 'o': 'MARKET', 'f': 'GTC', 'q': '0.00220000', 'p': '0.00000000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '',
        # # 'x': 'TRADE', 'X': 'FILLED', 'r': 'NONE', 'i': 15859894465, 'l': '0.00220000', 'z': '0.00220000', 'L': '2319.53000000', 'n': '0.00000220', 'N': 'ETH', 'T': 1707120960761, 't': 1297224255, 'I': 33028455025, 'w': False,
        # # 'm': False, 'M': True, 'O': 1707120960761, 'Z': '5.10296600', 'Y': '5.10296600', 'Q': '0.00000000', 'W': 1707120960761, 'V': 'EXPIRE_MAKER'}
        # if msg['e'] == 'executionReport':
        #     if msg['s'] in self._store.symbols:
        #         for o in self.open_orders:
        #             if o.binance_order['orderId'] == msg['i']:
        #                 if msg['X'] in [ORDER_STATUS_FILLED, ORDER_STATUS_PARTIALLY_FILLED]:
        #                     _dt = dt.datetime.fromtimestamp(int(msg['T']) / 1000)
        #                     executed_size = float(msg['l'])
        #                     executed_price = float(msg['L'])
        #                     executed_value = float(msg['Z'])
        #                     executed_comm = float(msg['n'])
        #                     # print(_dt, executed_size, executed_price)
        #                     self._execute_order(o, _dt, executed_size, executed_price, executed_value, executed_comm)
        #                 self._set_order_status(o, msg['X'])
        #
        #                 if o.status not in [Order.Accepted, Order.Partial]:
        #                     self.open_orders.remove(o)
        #                 self.notify(o)
        # elif msg['e'] == 'error':
        #     raise msg

    @staticmethod
    def get_price(symbol):
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url)
        data = response.json()
        price = data['price']
        return float(price)

    @staticmethod
    def print_object(obj):
        all_properties = dir(obj)

        for prop in all_properties:
            if callable(getattr(obj, prop)):
                print(f"Method: {prop}")
            else:
                print(f"Attribute: {prop}")

    def log(self, text, text2="", text3=""):
        # if self.c.show_log:
        print(text, text2, text3)

    def start(self):
        # This method is called once before the preloaded data is processed
        # print("Starting strategy")
        print("start")
        return

    def position_value(self):
        if self.c.live_run:
            return ((self.broker.get_asset_balance(self.c.base)[0] *
                    self.data.close[0]) +
                    self.broker.get_asset_balance(self.c.quote)[0])
        else:
            return self.broker.getvalue()

    @staticmethod
    def exponential_scale(value, min_old, max_old, min_new, max_new, c=1):
        # Normalize the original value
        normalized_value = (value - min_old) / (max_old - min_old)

        # Apply the exponential function (using natural base e)
        exp_value = np.exp(c * normalized_value) - 1

        # Scale the exp value to the range [0, e-1], then to the desired range
        scaled_value = min_new + (exp_value / (np.e - 1)) * (max_new - min_new)

        return min(max(scaled_value, min_new), max_new)

    def get_positon_text(self):
        if self.c.live_run:
            position = self.getposition(self.data)
            return (f"{self.steps_count} Position: {self.data._name}: {position.size} "
                    f"AVG price:{round(position.price, 4)}  "
                    f"Balance: {round(self.broker.getvalue(), 2)}  "
                    f"Cash: {round(self.broker.getcash(), 2)}  "
                    f"{self.c.base}: {self.broker.get_asset_balance(self.c.base)}  "
                    f"{self.c.quote}: {self.broker.get_asset_balance(self.c.quote)}  "
                    f"VALUE: {round(self.position_value(), 2)}  "
                    )
        else:
            position = self.getposition(self.data)
            return (f"{self.steps_count} Position: {self.data._name}: {position.size} "
                    f"AVG price:{round(position.price, 4)}  "
                    f"Balance: {round(self.broker.getvalue(), 2)}  "
                    f"Cash: {round(self.broker.getcash(), 2)}  "
                    # f"BTC: {self.broker.get_asset_balance('BTC')}  "
                    # f"FDUSD: {self.broker.get_asset_balance('FDUSD')}  "
                    f"VALUE: {round(self.position_value(), 2)}  "
                    )

    def is_live_data(self):

        status = self.datas[0]._state  # 0 - Live data, 1 - History data, 2 - None
        if status == 1:
            return False
        elif status == 0:
            return True
        else:
            print("ERROR, Live or History?")
            return False

    @staticmethod
    def dfloor(num, decimals=4):
        factor = 10 ** decimals
        return np.floor(num * factor) / factor

    def s_close(self):
        self.close()
        self.cd.decision[0] = 2  # 2= Close Stop Loss
        self.cd.add_meta('line1', self.get_positon_text())

    def s_buy(self):
        # if self.c.live_run:
        #     size = self.dfloor((self.broker.getvalue() * .8) / self.data.close[0], 4)
        #     self.last_buy_order = self.buy(data=self.datas[0], exectype=bt.Order.Market, size=size)
        #     self.cd.add_meta('line1', self.get_positon_text())
        # else:
        #     self.buy()

        self.last_buy_order = self.buy()

        self.stop_price = self.data.close[0] * (1 - ((self.c.stop_percent / 10) / 100))
        self.take_price = self.data.close[0] * (1 + ((self.c.take_percent / 10) / 100))
        self.cd.decision[0] = 1  # 1= BUY

    def load_config(self):
        if self.is_load_config:
            config = load('../config.joblib')
            kwargs = dict(config)
            config_obj = SimpleNamespace(**kwargs)

            if self.config_time_stamp != config_obj.time_stamp:
                self.c = config_obj
                self.c.live_run = True
                self.c.show_log = True
                self.min_steps = self.c.rsi_period + 1
                print(self.c)
                self.config_time_stamp = config_obj.time_stamp

    def data_manager(self, who):
        print("data_manager", who)

    def prenext(self):
        self.data_manager("prenext")

    def next(self):
        self.data_manager("next")
        if self.is_live_data():
            self.steps_count += 1


        for d in self.datas:
            print(d._name, d.num2date(), d.close[0], self.getposition(d).size)
            # if self.is_live_data():
            #     print(self.broker.get_asset_balance("USDT"))

            if self.do_trade and self.is_live_data() and d._name == "ETHUSDT":
                print("SHORT ETHUSDT")
                self.broker.set_leverage(d._name, 1)
                order = self.sell(data=d),
                # self.print_object(order)
                self.do_trade = False

            # if self.do_trade and self.is_live_data() and d._name == "AVAXUSDT":
            #     print("LONG AVAXUSDT  Cash:", self.broker.getcash())
            #     print("LONG AVAXUSDT  Cash:", self.broker.getcash(refresh=True))
            #     sz = (self.broker.getcash() * .9) / d.close[0]
            #     print("LONG AVAXUSDT  size:", sz)
            #
            #     order = self.buy(data=d, size=sz),
            #     # self.print_object(order)
            #     self.do_trade = False

            if self.steps_count == 5 and d._name == "ETHUSDT":
                self.close(d)

            if self.steps_count == 5 and d._name == "AVAXUSDT":
                self.close(d)

    def stop(self):

        return
        # # Close all positions at the end of the strategy
        # for data in self.datas:
        #     # Check if we have an open position for this data
        #     if self.getposition(data).size != 0:
        #         # If so, issue an order to close it
        #         # print(f"Closing position in {data._name}")
        #         self.close(data)

    def notify_data(self, data, status, *args, **kwargs):
        print("notify_data")
        return
        # if status == data.LIVE:
        #     if not self.close_prices_history_first_fill:
        #         self.log("First fill of close_prices_history")
        #         for i in range(self.DROPPER_TIME_FRAM):
        #             print("i", i, self.data[i])
        #             # self.close_prices_history.append(data.close[i])
        #             # print(self.close_prices_history)
        #         self.close_prices_history_first_fill = True

    def notify_order(self, order):
        # self.print_object(order)
        # self.print_object(order)
        # print(self.getposition)
        if order.status == bt.Order.Completed:
            print("Notify order: Completed")

            for data, position in self.broker.positions.items():
                # self.symbols_position[data._name] = position.size
                symbol = data
                size = position.size
                print(f'  Position: symbol: {symbol}, size: {size}')

        # """Changing the status of the order"""
        # order_data_name = order.data._name  # Name of ticker from order
        # self.log(
        #     f'Order number {order.ref} {order.info["order_number"]} {order.getstatusname()}
        #     {"Buy" if order.isbuy() else "Sell"} {order_data_name} {order.size:.10f} @ {order.price:.10f}')
        if order.status == bt.Order.Completed:  # If the order is fully executed
            print(f'  {"Buy" if order.isbuy() else "Sell"} '
                  f'{order.data._name} Size: {order.executed.size:.10f}, Price: {order.executed.price:.10f}, '
                  f'Value {order.executed.value:.10f}, Commission {order.executed.comm:.10f}')

    def notify_trade(self, trade):
        print("notify_trade")
        print(trade)

    def notify_cashvalue(self, cash, value):
        print("notify_cash value", cash, value, "Profit Net profit (incluse fee):", value - self.start_cash)

        # print(self.broker.getcash(), self.broker.getvalue())

        # if self.is_live_data():
        #     for idata, position in self.broker.positions.items():
        #         print("position", idata, position.size)

    def notify_fund(self, cash, value, fundvalue, shares):
        # print("notify_fund", cash, value, fundvalue, shares)
        return

    def notify_store(self, msg, *args, **kwargs):
        print("notify_store", msg)

        # if trade.justopened:
        #     print(f'   Open    {trade.getdataname()} {self.data.num2date(trade.data.datetime[0])} {trade.price} {trade.size} {trade.status_names[trade.status]}')

        # """Changing the position status"""
        # if trade.isjust:  # If the position is closed
        #     self.log(f'Profit on a closed position {trade.getdataname()} Total={trade.pnl:.10f}, No commission={trade.pnlcomm:.10f}')


# test
if __name__ == "__main__":

    def exponential_scale(value, min_old, max_old, min_new, max_new, c=1):
        # Normalize the original value
        normalized_value = (value - min_old) / (max_old - min_old)

        # Apply the exponential function (using natural base e)
        exp_value = np.exp(c * normalized_value) - 1

        # Scale the exp value to the range [0, e-1], then to the desired range
        scaled_value = min_new + (exp_value / (np.e - 1)) * (max_new - min_new)

        return min(max(scaled_value, min_new), max_new)

    for i in range(5, 300):
        print(exponential_scale(i, 0,600,0,40))

