import random
import sys
import time
import os
import json

import requests
import backtrader as bt
from backtrader.utils import date2num, num2date
import pickle
from datetime import datetime
from types import SimpleNamespace
import threading

import pandas as pd
import numpy as np
import math
import pprint
from binance.helpers import round_step_size
from binance import Client
from bt_tools import Logger, TaskScheduler, GoogleDriveConnect, get_asset_balance, get_futures_positions
from binance_excel_saver import BinanceExcelSaver
from candlestick_chart import CandlestickChart


class CollectData:

    def __init__(self, length, is_live_run,
                 init_price=69250.0,
                 worker_no=0,
                 symbol="",
                 total_data_len=100000,
                 set_life_signal=object):

        self.symbol = symbol
        self.length = length
        self.worker_no = worker_no

        self.open_history = np.full(length, init_price, dtype=np.float64)
        self.high_history = np.full(length, init_price, dtype=np.float64)
        self.low_history = np.full(length, init_price, dtype=np.float64)
        self.close_history = np.full(length, init_price, dtype=np.float64)

        self.ema_fast_long_data_history = np.full(length, init_price, dtype=np.float64)
        self.ema_fast_long_down_shift_data_history = np.full(length, init_price, dtype=np.float64)
        self.ema_slow_long_data_history = np.full(length, init_price, dtype=np.float64)

        self.ema_fast_short_data_history = np.full(length, init_price, dtype=np.float64)
        self.ema_fast_short_up_shift_data_history = np.full(length, init_price, dtype=np.float64)
        self.ema_slow_short_data_history = np.full(length, init_price, dtype=np.float64)

        # ennek nem elég a length ennek a teljes futást rögzíteni kell
        # TODO: megkapja a DF.sahapét
        self.portfolio_value = np.full(total_data_len, 0.0, dtype=np.float64)

        self.long_signal = np.full(length, 0, dtype=np.int8)
        self.short_signal = np.full(length, 0, dtype=np.int8)

        # záróár
        self.open = 0
        self.high = 0
        self.low = 0
        self.close = 0

        self.decision = np.full(length, 0, dtype=np.int8)
        self.meta = {}
        self.is_live_run = is_live_run

        self.logger = Logger()
        self.log = self.logger.log
        if self.is_live_run:
            self.set_life_signal = set_life_signal

    @staticmethod
    def s_round(value):
        decimal = 8
        return round(value, decimal)

    def add_que(self, array, data):
        # array = np.append(array, data)
        # if len(array) > self.length:
        #     array = array[1:-1]
        alen = len(array)
        array[1:] = array[0:alen - 1]
        array[0] = self.s_round(data)

    def add_signal(self, long_signal, short_signal):
        long_signal = int(long_signal)
        short_signal = int(short_signal)

        self.add_que(self.long_signal, long_signal)
        self.add_que(self.short_signal, short_signal)
        if self.is_live_run:
            self.set_life_signal(key="CollectData_1" + str(self.symbol),
                                 cclass="CollectData",
                                 method="add_signal",
                                 msg1=str(self.symbol),
                                 msg2="",
                                 msg3=""
                                 )

    def add_data(self, data,
                 ema_fast_long_data,
                 ema_fast_long_down_shift_data,
                 ema_slow_long_data,
                 ema_fast_short_data,
                 ema_fast_short_up_shift_data,
                 ema_slow_short_data,
                 portfolio_value
                 ):

        self.add_que(self.open_history, float(data.open[0]))
        self.add_que(self.high_history, float(data.high[0]))
        self.add_que(self.low_history, float(data.low[0]))
        self.add_que(self.close_history, round(float(data.close[0]), 8))

        self.add_que(self.ema_fast_long_data_history, float(ema_fast_long_data))
        self.add_que(self.ema_fast_long_down_shift_data_history, float(ema_fast_long_down_shift_data))
        self.add_que(self.ema_slow_long_data_history, float(ema_slow_long_data))

        self.add_que(self.ema_fast_short_data_history, float(ema_fast_short_data))
        self.add_que(self.ema_fast_short_up_shift_data_history, float(ema_fast_short_up_shift_data))
        self.add_que(self.ema_slow_short_data_history, float(ema_slow_short_data))

        self.add_que(self.portfolio_value, float(portfolio_value))

        self.open = float(data.open[0])
        self.high = float(data.high[0])
        self.low = float(data.low[0])
        self.close = round(float(data.close[0]), 1)

        self.add_que(self.decision, int(0))
        # if self.is_live_run:
        #     self.set_life_signal(key="CollectData_2" + str(self.symbol),
        #                          cclass="CollectData",
        #                          method="add_data",
        #                          msg1=str(self.symbol),
        #                          msg2="",
        #                          msg3=""
        #                          )

    def add_meta(self, field, value):
        if self.is_live_run:
            self.meta[field] = str(value)

    # def get_save_meta(self):
    #     return self.meta

    def get_save_data(self):
        save_data = {
            'symbol': self.symbol,
            'open_history': tuple(self.open_history),
            'high_history': tuple(self.high_history),
            'low_history': tuple(self.low_history),
            'close_history': tuple(self.close_history),

            'ema_fast_long_data_history': tuple(self.ema_fast_long_data_history),
            'ema_fast_long_down_shift_data_history': tuple(self.ema_fast_long_down_shift_data_history),
            'ema_slow_long_data_history': tuple(self.ema_slow_long_data_history),

            'ema_fast_short_data_history': tuple(self.ema_fast_short_data_history),
            'ema_fast_short_up_shift_data_history': tuple(self.ema_fast_short_up_shift_data_history),
            'ema_slow_short_data_history': tuple(self.ema_slow_short_data_history),

            'decision': tuple(self.decision),
            'meta': self.meta
        }
        return save_data
            # with open('data_transfer_for_process.pickle', 'wb') as handle:
            #     pickle.dump(save_data_form, handle, protocol=pickle.HIGHEST_PROTOCOL)


class OnePositionSizer(bt.Sizer):

    def __init__(self, symbols, percent=80, start_cash=100000, is_live_run=False):
        self.percent = percent / 100
        self.start_cash = start_cash
        self.is_live_run = is_live_run

        self.logger = Logger()
        self.log = self.logger.log

        self.min_qty = {}
        self.max_qty = {}
        self.step_size = {}
        self.min_notional = {}
        self.symbol_info = {}

        self.symbols = symbols
        self.num_of_symbols = len(self.symbols)
        self.set_life_signal = object

    def has_open_position(self):
        # Check if there is any open position across all assets
        for idata, position in self.broker.positions.items():
            # for position in self.broker.positions:
            if position.size != 0:
                return True
        return False

    def is_valid_quantity(self, symbol, qty):
        if not (self.min_qty[symbol] <= abs(qty) <= self.max_qty[symbol]):
            return False
        return True

    def round_to_step(self, symbol, qty):
        return round(qty / self.step_size[symbol]) * self.step_size[symbol]

    def round_down_to_step(self, symbol, qty):
        round_down = (qty // self.step_size[symbol]) * self.step_size[symbol]
        return round_step_size(round_down, self.step_size[symbol])

    def start(self):
        if self.is_live_run:
            for symbol in self.symbols:
                self.log(f"Get market info: {symbol}", level=10)
                self.symbol_info[symbol] = self.broker.futures_symbol_info(symbol)
                filter_params = [f for f in self.symbol_info[symbol]['filters'] if f.get('filterType') == 'MARKET_LOT_SIZE'][0]
                self.min_qty[symbol] = float(filter_params.get('minQty', 0))
                self.max_qty[symbol] = float(filter_params.get('maxQty', float('inf')))
                self.step_size[symbol] = float(filter_params.get('stepSize', 1))
                filter_params = [f for f in self.symbol_info[symbol]['filters'] if f.get('filterType') == 'MIN_NOTIONAL'][0]
                self.min_notional[symbol] = float(filter_params.get('notional', 0))

    def _getsizing(self, comminfo, cash, data, isbuy):
        symbol = data._name

        # if self.has_open_position():
        #     return 0

        if self.is_live_run:
            # size = (cash * self.percent) / data.close[0]
            size = self.start_cash / data.close[0]
            size = self.round_to_step(symbol, size)

            if size == 0:
                self.log(f"Sizer: Trade failed {symbol} Size 0")
                print(f"Sizer: Trade failed {symbol} Size 0")
                size = 0
            elif not self.is_valid_quantity(symbol, size):
                self.log(f"Sizer: Trade failed {symbol} invalid size (min, max, stepsize)")
                size = None
            elif self.min_notional[symbol] > (abs(size) * data.close[0]):
                self.log(f"Sizer: Trade failed {symbol} min_notional")
                size = None

        else:
            size = int((cash * self.percent) / 4) // data.close[0]

        return size

    def set(self, strategy, broker):
        self.strategy = strategy
        self.broker = broker
        if self.is_live_run:
            self.set_life_signal = self.broker.set_life_signal
        self.start()


class ESMSizer(bt.Sizer):

    def __init__(self, symbols, max_percent=70, start_cash=100000, force_num_of_symbols=None, is_live_run=False):
        self.is_live_run = is_live_run
        self.start_cash = start_cash
        self.force_num_of_symbols = force_num_of_symbols
        self.max_percent = max_percent
        self.symbols = symbols
        self.num_of_symbols = len(self.symbols)

        self.min_qty = {}
        self.max_qty = {}
        self.step_size = {}
        self.symbol_info = {}

        self.symbols_position = {}
        self.symbol_info = {}
        self.min_notional = {}

        for sy in self.symbols:
            self.symbols_position[sy] = 0.0

        self.logger = Logger()
        self.log = self.logger.log
        if self.is_live_run:
            self.set_life_signal = object

    def start(self):
        if self.is_live_run:
            for symbol in self.symbols:
                self.log(f"Get market info: {symbol}", level=10)
                if self.is_live_run:
                    self.symbol_info[symbol] = self.broker.futures_symbol_info(symbol)
                else:
                    self.symbol_info[symbol] = self.get_symbol_info(symbol)
                filter_params = [f for f in self.symbol_info[symbol]['filters'] if f.get('filterType') == 'MARKET_LOT_SIZE'][0]
                self.min_qty[symbol] = float(filter_params.get('minQty', 0))
                self.max_qty[symbol] = float(filter_params.get('maxQty', float('inf')))
                self.step_size[symbol] = float(filter_params.get('stepSize', 1))
                filter_params = [f for f in self.symbol_info[symbol]['filters'] if f.get('filterType') == 'MIN_NOTIONAL'][0]
                self.min_notional[symbol] = float(filter_params.get('notional', 0))

    def get_symbol_info(self, ssymbol):
        # print(self.binance.get_symbol_info(symbol))
        exchange_info = self.strategy.bclient.futures_exchange_info()
        symbol_info = next((symbol for symbol in exchange_info['symbols'] if symbol['symbol'] == ssymbol), None)
        # print(symbol_info)
        return symbol_info

    def is_valid_quantity(self, symbol, qty):
        # print("")
        # print(f"{self.min_qty[symbol]} <= {abs(qty)} <= {self.max_qty[symbol]})")
        if not (self.min_qty[symbol] <= abs(qty) <= self.max_qty[symbol]):
            return False
        # print(f"({abs(qty)} - {self.min_qty[symbol]}) % {self.step_size[symbol]}) != 0")
        # if ((abs(qty) - self.min_qty[symbol]) % self.step_size[symbol]) != 0:
        #     return False
        # print("Retrurn True")
        return True

    def round_to_step(self, symbol, qty):
        return round(qty / self.step_size[symbol]) * self.step_size[symbol]

    def round_down_to_step(self, symbol, qty):
        round_down = (qty // self.step_size[symbol]) * self.step_size[symbol]
        return round_step_size(round_down, self.step_size[symbol])

        #_getsizing
    def _getsizing(self, comminfo, cash, data, isbuy):
        self.log("_getsizing:", level=1)
        symbol = data._name

        if self.is_live_run:

            # ha van befejezetlen order akkor nem enged rányitni.

            save_pos = 0
            for idata, position in self.broker.positions.items():
                if symbol == idata:
                    save_pos = position.size

            try_count_order = 0
            order_detected = False
            order_run_over = False
            while try_count_order < 10:
                order_detected = False
                for order in self.broker.open_orders:
                    if order.data._name == symbol:
                        order_detected = True
                        order_run_over = True
                        self.log(f'Still open order symbol: {order.data._name} '
                                 f'Open Order: ID={order.ref}, Status={order.getstatusname()}, '
                                 f'Size={order.size}, Price={order.price}', level=1)
                        break

                if order_detected:
                    time.sleep(.35)
                    try_count_order += 1
                    continue
                else:
                    break

            if order_detected:
                self.log("Order is still aliven (x 10 try)", level=1)
                return None

            if order_run_over:
                self.log(f"Order filled. Check Position. saved pos {save_pos}", level=1)
                try_count_pos = 0
                position_changed = False
                sy_pos = 0
                while try_count_pos < 5:
                    for idata, position in self.broker.positions.items():
                        if idata == symbol:
                            sy_pos = position.size
                            if position.size == save_pos:
                                print(f'Still in position.', position.size )
                                position_changed = False
                                break
                            else:
                                print('Position settled.')
                                position_changed = True
                                try_count_pos = 100
                                break
                    time.sleep(.35)
                    try_count_pos += 1

                if not position_changed and sy_pos != 0:
                    return None

        max_value = self.start_cash * (self.max_percent / 100)
        if self.force_num_of_symbols is None:
            one_symbol_max_value = max_value / self.num_of_symbols
        else:
            one_symbol_max_value = max_value / self.force_num_of_symbols

        self.symbols_position = {key: 0 for key in self.symbols_position}
        for idata, position in self.broker.positions.items():
            if self.is_live_run:
                self.symbols_position[idata] = position.size
            else:
                self.symbols_position[idata._name] = position.size
        # print(self.symbols_position)

        max_long_position = (one_symbol_max_value + self.strategy.symbol_profit[symbol]) / data.close[0]
        max_short_position = -max_long_position
        # ennyi db ilyen eszetel lehet + és - irányba is

        if isbuy:
            qty = max_long_position - self.symbols_position[symbol]
            qty = 0 if qty < 0 else qty
        else:
            qty = max_short_position - self.symbols_position[symbol]
            qty = 0 if qty > 0 else qty

            # x	x	            buy	          sell
            # x	x	           max long	    max short
            # x	x	            2	            -2
            #
            # position	0   	2	            -2
            # position	-1	    3	            -1
            # position	1	    1	            -3
            # position	2,5	    -0,5	        -4,5
            # position	-2,5	4,5	            0,5


            # ha shorba vagyok és longolni akarok akkor átfordul
            # pozíció -1 short és longolni akkor akkor enged a maxi long ig kötni

        # position = self.broker.getposition(data)
        # print(f"{data._name} {one_symbol_max_value} {data.close[0]}")
        # qty = ((one_symbol_max_value + self.strategy.symbol_profit[data._name]) / data.close[0]) - self.symbols_position[data._name]
        ori_size = round(qty, 8)
        if self.is_live_run:
            size = self.round_down_to_step(symbol, ori_size)

            self.log(f"symbol                  {symbol}", level=1)
            self.log(f"side                    {'Buy' if isbuy else 'Sell'}", level=1)
            self.log(f"size                    {size}", level=1)
            self.log(f"qty                     {qty}", level=1)
            self.log(f"ori_size                {ori_size}", level=1)
            self.log(f"max_long_position       {max_long_position}", level=1)
            self.log(f"max_short_position      {max_short_position}", level=1)
            self.log(f"stepsize                {self.step_size[symbol]}", level=1)
            self.log(f"self.start_cash         {self.start_cash}", level=1)
            self.log(f"max_value               {max_value} {round(max_value / self.start_cash * 100, 2)}", level=1)
            self.log(f"one_symbol_max_value    {one_symbol_max_value}", level=1)
            self.log(f"symbol_profit           {self.strategy.symbol_profit[symbol]}", level=1)
            self.log(f"symbols_position        {self.symbols_position[symbol]}", level=1)

            if size == 0:
                print(f"Sizer: Trade failed {symbol} Size 0")
                size = None
            elif not self.is_valid_quantity(symbol, size):
                print(f"Sizer: Trade failed {symbol} invalid size (min, max, stepsize)")
                size = None
            elif self.min_notional[symbol] > (abs(size) * data.close[0]):
                print(f"Sizer: Trade failed {symbol} min_notional")
                size = None
        else:
            size = ori_size

        self.log(f"return size             {size}", level=1)
        self.log("", level=1)

        # if isbuy:
        #     ib = "BUY"
        # else:
        #     ib = "SELL"
        #
        # print(ib, "Cash:", cash,
        #       "Profit:", self.strategy.symbol_profit,
        #       "Position:", self.symbols_position,
        #       data._name,
        #       "return size: ", size,
        #       "price: ", data.close[0],
        #       "values: ", size * data.close[0],
        #       )

        if self.is_live_run:
            self.set_life_signal(key="ESMSizer_1" + str(symbol),
                                 cclass="ESMSizer",
                                 method="_getsizing",
                                 msg1=str(symbol),
                                 msg2=str(ori_size),
                                 msg3=str(size)
                                 )

        return size

    def set(self, strategy, broker):
        self.strategy = strategy
        self.broker = broker
        if self.is_live_run:
            self.set_life_signal = self.broker.set_life_signal
        self.start()


class EmaShiftMultiStrategy(bt.Strategy):

    def __init__(self, config, start_position={}, start_price={}, is_live_run=False, total_data_len=100000):

        self.all_symbols = []
        self.cc = config
        self.start_position = start_position
        self.start_price = start_price
        self.is_live_run = is_live_run

        self.closed_trade_count = 0

        self.logger = Logger()
        self.log = self.logger.log
        if self.is_live_run:
            self.set_life_signal = self.broker.set_life_signal

        api_key, secure_key = self.get_api_key()
        self.bclient = Client(api_key, secure_key, requests_params={'timeout': (10, 20)})

        self.dt_array = []
        for x in self.cc.keys():
            self.dt_array.append(0)

        # self.c.is_long = 1
        # self.c.ema_fast_long = 27
        # self.c.ema_slow_long = 408
        # self.c.ema_fast_long_down_shift = 98
        # self.c.is_stop_loss_long = 1
        # self.c.stop_loss_percent_long = 20
        #
        # self.c.is_short = 1
        # self.c.ema_fast_short = 19
        # self.c.ema_slow_short = 494
        # self.c.ema_fast_short_up_shift = 95
        # self.c.is_stop_loss_short = 1
        # self.c.stop_loss_percent_short = 20
        # self.c.is_trailer_short = 1
        # self.c.trailer_short_enter_percent = 20
        # self.c.trailer_short_offset = 10

        # Global variables  - ezek symboltól függetlenül mindenkinél ugyan az
        self.initial_cash = 100000
        self.free_cash = self.initial_cash
        # self.lot_percent = 70.0  # 70 = 70%
        self.total_pnlcomm = 0.0

        # self.comission_percen = 0.075  # 0.075 = 0.075 %
        self.paid_comission = 0.0

        self.steps_count = 0
        # self.closed_trade_count = 1
        self.end_close = False  # futás végén lezárja a poziiciiót

        # Symboltól függő változók
        v_start = [
            ['long_stop_price', 0],
            ['short_stop_price', 1000000000000.0],

            ["trailer_long_activation_price", 0.0],
            ["trailer_long_active", False],
            ["trailer_long_highest_price", 0.0],
            ["trailer_long_stop_price", 0.0],

            ["trailer_short_activation_price", 0.0],
            ["trailer_short_active", False],
            ["trailer_short_lowest_price", 1000000000000.0],
            ["trailer_short_stop_price", 0.0],

            ["last_long_order", None],
            ["last_short_order", None],
            ["last_long_qty", 0.0],
            ["last_long_price", 0.0],
            ["last_short_qty", 0.0],
            ["last_short_price", 0.0],
            ["trade_steps", 0],
            ["dn_steps_count", 0],
            ["in_position", False],
        ]

        kwargs = dict(v_start)
        # v_start_obj = SimpleNamespace(**kwargs)

        self.in_position = False
        self.position_slots = 4
        self.v = {}
        self.cd = {}
        self.symbol_profit = {}

        self.start_market_prices = {}
        for d in self.datas:
            dn = d._name
            self.start_market_prices[dn] = self.get_price(self.cc[dn].base + self.cc[dn].quote)
            self.symbol_profit[dn] = 0.0
            self.v[dn] = SimpleNamespace(**kwargs)
            self.cd[dn] = CollectData(length=700,
                                      is_live_run=self.is_live_run,
                                      init_price=self.start_market_prices[dn],
                                      worker_no=self.cc[dn].worker_no,
                                      symbol=dn,
                                      total_data_len=total_data_len + 10,
                                      set_life_signal=self.set_life_signal if self.is_live_run else None
                                      )

        if self.is_live_run:
            self.chart = CandlestickChart()
            self.leverage = 1
            for data in self.datas:
                dn = data._name
                self.log(f"Get symbol leverage: {dn} {self.leverage}")
                self.broker.set_leverage(dn, self.leverage)

            self.binance_excel_saver = BinanceExcelSaver

            self.gdc = GoogleDriveConnect()
            now = datetime.now()
            self.tasks = []
            for i in range(0, 24):
                # for j in [5]:
                for j in range(1, 59, 3):
                    self.tasks.append(
                        [datetime(now.year, now.month, now.day, hour=i, minute=j), self.scheduled_life_signals]
                    )
                self.tasks.append(
                    [datetime(now.year, now.month, now.day, hour=i, minute=2), self.scheduled_account_info]
                )

            # self.tasks.append(
            #     [datetime(now.year, now.month, now.day, hour=now.hour, minute=now.minute + 1), self.scheduled_life_signals]
            # )
            # self.tasks.append(
            #     [datetime(now.year, now.month, now.day, hour=now.hour, minute=now.minute + 2), self.scheduled_account_info]
            # )

            # self.scheduler = TaskScheduler(self.tasks, set_life_signal=self.set_life_signal)
            # self.scheduler.start()

    def scheduled_life_signals(self):
        self.broker.save_life_signals()
        try:
            self.gdc.delete_file_in_folder(file_name='life_signals.txt')
            self.gdc.upload_file(file_name='/data_transfer/life_signals.txt')
        except:
            pass

    def scheduled_account_info(self):
        self.save_collected_data()

        ret_array_balance = get_asset_balance(self.bclient, asset="USDC", is_print=False, is_return_array=True)
        ret_array_position = get_futures_positions(self.bclient, is_print=False, is_return_array=True)

        self.binance_excel_saver.save_balance_data(ret_array_balance)
        self.binance_excel_saver.save_positions_data(ret_array_position)

        self.gdc.delete_file_in_folder(file_name='ESM_settlement.xlsx')
        self.gdc.upload_file(file_name='/data_transfer/ESM_settlement.xlsx')

        for cd_key in self.cd:
            fn0, fn1 = self.create_chart(cd_key, self.cc[cd_key])


            try:
                self.gdc.delete_file_in_folder(file_name=fn0)
                self.gdc.upload_file(file_name='/data_transfer/' + fn0)

                self.gdc.delete_file_in_folder(file_name=fn1)
                self.gdc.upload_file(file_name='/data_transfer/' + fn1)
            except:
                pass

    def create_chart(self, dn, c):
        df = pd.DataFrame({
            'open_history': self.cd[dn].open_history[::-1],
            'high_history': self.cd[dn].high_history[::-1],
            'low_history': self.cd[dn].low_history[::-1],
            'close_history': self.cd[dn].close_history[::-1],
            'ema_fast_long_data_history': self.cd[dn].ema_fast_long_data_history[::-1],
            'ema_fast_long_down_shift_data_history': self.cd[dn].ema_fast_long_down_shift_data_history[::-1],
            'ema_slow_long_data_history': self.cd[dn].ema_slow_long_data_history[::-1],
            'ema_fast_short_data_history': self.cd[dn].ema_fast_short_data_history[::-1],
            'ema_fast_short_up_shift_data_history': self.cd[dn].ema_fast_short_up_shift_data_history[::-1],
            'ema_slow_short_data_history': self.cd[dn].ema_slow_short_data_history[::-1],
        })

        df0 = df.tail(500)
        df0.index = range(0, 500)
        self.chart.add(df0, dn + " PERPETUAL")
        self.chart.add_config(c)
        filename0 = "!" + dn + '.png'
        self.chart.plot("data_transfer/" + filename0)

        df1 = df.tail(24)
        df1.index = range(0, 24)
        self.chart.add(df1, dn + " PERPETUAL ZOOM")
        self.chart.add_config(c)
        filename1 = "!" + dn + '_zoom.png'
        self.chart.plot("data_transfer/" + filename1)
        return filename0, filename1


    @staticmethod
    def get_api_key():
        # api_acces_key.json file is:
        #
        # {
        #     "api_key": "xxxxx",
        #     "secure_key": "yyyyy"
        # }

        json_file_path = 'tokens/api_acces_key.json'
        with open(json_file_path, 'r') as file:
            keys = json.load(file)

        api_key = keys['api_key']
        secure_key = keys['secure_key']

        return api_key, secure_key

    # def start_data_threads(self):
    #     if self.is_live_run:
    #         thread1 = threading.Thread(target=self.save_data_loop)
    #         thread1.start()
    #         # thread1.join()

    def save_collected_data(self):
        save_dict = {}
        for cd_key in self.cd:
            save_dict[cd_key] = self.cd[cd_key].get_save_data()
        self.save_dict(save_dict)

    def save_dict(self, ddict, file_path='data_transfer/data_transfer_for_process.pickle'):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            with open(file_path, 'wb') as file:
                pickle.dump(ddict, file)
        except Exception as e:
            self.log(f"An error occurred while saving the dictionary: {e}", level=1)

    def get_price(self, symbol):
        if self.is_live_run:
            return float(self.broker.futures_symbol_ticker(symbol))
        else:
            self.bclient.futures_symbol_ticker(symbol=symbol)

    def print_object(self, obj):
        all_properties = dir(obj)

        for prop in all_properties:
            if callable(getattr(obj, prop)):
                self.log(f"Method: {prop}", level=10)
            else:
                self.log(f"Attribute: {prop}", level=10)

    def in_position_count(self):
        ret = 0
        for dn in self.all_symbols:
            if self.v[dn].in_position:
                ret += 1
        return ret

    def start(self):
        self.all_symbols = []
        for data in self.datas:
            self.all_symbols.append(data._name)

        if self.is_live_run:
            # beállítom a kezdő portfolió értékeket
            for data in self.datas:
                dn = data._name
                self.cd[dn].add_meta("cc", self.cc[dn])
                if dn in self.start_position:
                    self.broker.update_position(data, self.start_position[dn], self.start_price[dn])
            return

    def position_value(self):
        if self.is_live_run:
            if self.is_live_data():
                ret_value = self.broker.getvalue(refresh=True)
                return ret_value
            else:
                ret_value = self.broker.getvalue(refresh=False)
                return ret_value
        else:
            # print(self.broker.getcash())
            # print(self.broker.getvalue())
            ret_value = self.broker.getcash()
            for data, position in self.broker.positions.items():
                # print(data._name, position.size, position.size * data.close[0])
                ret_value += position.size * data.low[0]
            # return self.broker.getvalue()
            return ret_value

    # @staticmethod
    # def exponential_scale(value, min_old, max_old, min_new, max_new, c=1):
    #     # Normalize the original value
    #     normalized_value = (value - min_old) / (max_old - min_old)
    #
    #     # Apply the exponential function (using natural base e)
    #     exp_value = np.exp(c * normalized_value) - 1
    #
    #     # Scale the exp value to the range [0, e-1], then to the desired range
    #     scaled_value = min_new + (exp_value / (np.e - 1)) * (max_new - min_new)
    #
    #     return min(max(scaled_value, min_new), max_new)

    def get_positon_text(self):
        if self.is_live_run:
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

    # def is_live_data(self):
    #
    #     status = self.datas[0]._state  # 0 - Live data, 1 - History data, 2 - None
    #     if status in [0, 1]:
    #         if status:
    #             return False
    #         else:
    #             return True
    #
    # @staticmethod
    # def dfloor(num, decimals=4):
    #     factor = 10 ** decimals
    #     return np.floor(num * factor) / factor

    @staticmethod
    def round_down(number, decimals=2):
        factor = 10 ** decimals
        return math.floor(number * factor) / factor

    def rsrc(self, data):
        return self.round_down(data.close[0], 8)

    def s_close(self, data, stype):
        dn = data._name
        c = self.cc[dn]

        if not self.v[dn].in_position:
            return

        self.log("", level=1)
        self.log(datetime.now(), num2date(data.datetime[0]), "Close", dn, level=1)
        self.log("-" * 80, level=1)

        # for order in self.broker.open_orders:
        #     if order.data._name == dn:
        #         print(f'Open Order symbol: {order.data._name} Open Order: ID={order.ref}, Status={order.getstatusname()}, Size={order.size}, Price={order.price}')
        #         return None

        # CLOSE PROTOCOL ---------------------------

    #     profit = 0.0
    #     if strategy.position_size < 0.0
    #         comission_short = math.round((last_short_qty * last_short_price) * (comission_percen / 100), 4)
    #         comission_short_stop = math.round((last_short_qty * rsrc) * (comission_percen / 100), 4)
    #         profit := math.round(last_short_qty * (last_short_price - rsrc), 2) - comission_short - comission_short_stop
    #     else if strategy.position_size > 0.0
    #        comission_long = math.round((last_long_qty * last_long_price) * (comission_percen / 100), 4)
    #        comission_long_stop = math.round((last_long_qty * rsrc) * (comission_percen / 100), 4)
    #        profit := math.round(last_long_qty * (rsrc - last_long_price), 2) - comission_long - comission_long_stop
    #
    #     free_cash := free_cash + profit
    #     trailer_short_active := false
    #     long_stop_price := 0.0
    #     short_stop_price := 1000000000000.0

        # rsrc = self.rsrc(data)
        #
        # profit = 0.0
        # pstr = ""
        # if self.getposition(data).size < 0:
        #     comission_short = round((self.v[dn].last_short_qty * self.v[dn].last_short_price) * (self.comission_percen / 100), 16)
        #     comission_short_stop = round((self.v[dn].last_short_qty * rsrc) * (self.comission_percen / 100), 16)
        #     profit = round(self.v[dn].last_short_qty * (self.v[dn].last_short_price - rsrc), 2) - comission_short - comission_short_stop
        #     self.paid_comission = self.paid_comission + comission_short + comission_short_stop
        #     self.free_cash = self.free_cash + profit
        #     pstr = (f"close, {dn},{data.datetime.datetime(0) + dt.timedelta(hours=1)}, {rsrc}, {self.v[dn].last_short_qty}, profit: {profit} cash:{self.free_cash} "
        #             f"total_comisson: {self.paid_comission} {stype} {self.broker.get_cash()}")
        # elif self.getposition(data).size > 0:
        #     comission_long = round((self.v[dn].last_long_qty * self.v[dn].last_long_price) * (self.comission_percen / 100), 16)
        #     comission_long_stop = round((self.v[dn].last_long_qty * rsrc) * (self.comission_percen / 100), 16)
        #     profit = round(self.v[dn].last_long_qty * (rsrc - self.v[dn].last_long_price), 2) - comission_long - comission_long_stop
        #     self.paid_comission = self.paid_comission + comission_long + comission_long_stop
        #     self.free_cash = self.free_cash + profit
        #     pstr = (f"close, {dn},{data.datetime.datetime(0) + dt.timedelta(hours=1)}, {rsrc}, {self.v[dn].last_long_qty}, profit: {profit} cash:{self.free_cash} "
        #             f"total_comisson: {self.paid_comission} {stype} {self.broker.get_cash()}")
        # else:
        #     print("Close nem lehet position size 0 esetén !!!!!!!", stype , "-" * 80)

        self.v[dn].long_stop_price = 0.0
        self.v[dn].long_take_price = 0.0

        self.v[dn].short_stop_price = 1000000000000.0
        self.v[dn].short_take_price = 1000000000000.0

        self.v[dn].trailer_long_active = False
        self.v[dn].trailer_long_activation_price = 0.0
        self.v[dn].trailer_long_highest_price = 0.0
        self.v[dn].trailer_long_stop_price = 0.0

        self.v[dn].trailer_short_active = False
        self.v[dn].trailer_short_activation_price = 0.0
        self.v[dn].trailer_short_lowest_price = 1000000000000.0
        self.v[dn].trailer_short_stop_price = 0.0

        x_close = self.close(data)
        print("CLOSE", dn, stype)
        print(x_close)
        print("-" * 80)

        self.cd[dn].decision[0] = 2  # 2= Close Stop Loss
        self.in_position = False
        self.v[dn].in_position = False
        self.v[dn].trade_steps = 0

        # self.cd[dn].add_meta('line1', self.get_positon_text())

        # if c.worker_no == 0:
        #     # print(self.closed_trade_count, self.v[dn].popen)
        #     print(self.closed_trade_count, pstr)
        #     self.closed_trade_count += 1

    def s_buy(self, data):
        dn = data._name
        c = self.cc[dn]

        if self.v[dn].in_position or self.in_position_count() >= self.position_slots:
            return

        self.log("", level=1)
        self.log(datetime.now(), num2date(data.datetime[0]), "s_buy", dn, level=1)
        self.log("-" * 80, level=1)

        rsrc = self.rsrc(data)
        # self.v[dn].last_long_qty = round((self.free_cash * (self.lot_percent / 100)) / rsrc, 2)
        # # print(dn, self.v[dn].last_long_qty )
        # self.v[dn].last_long_price = rsrc

        # Stop loss price set
        self.v[dn].long_stop_price = rsrc * (1 - (c.stop_loss_percent_long / 1000))
        # self.v[dn].long_take_price = rsrc * (1 + (c.take_percent_long / 1000))

        # Trailer sets
        self.v[dn].trailer_long_activation_price = rsrc * (1 + (c.trailer_long_enter_percent / 1000))
        self.v[dn].trailer_long_active = False
        self.v[dn].trailer_long_highest_price = 0.0

        # print("BUY SIZE:",self.v[dn].last_long_qty)
        # self.v[dn].last_long_order = self.buy(data, size=self.v[dn].last_long_qty)
        self.v[dn].last_long_order = self.buy(data)
        print("BUY", dn)
        print(self.v[dn].last_long_order)
        print("-" * 80)
        if self.v[dn].last_long_order:
            self.v[dn].trade_steps = 0
            self.cd[dn].decision[0] = 1  # 1= BUY
            self.in_position = True
            self.v[dn].in_position = True

        # self.v[dn].popen = (f"long , {dn},{self.data.datetime.datetime(0) + dt.timedelta(hours=1)}, {data.close[0] * self.v[dn].last_long_qty}, "
        #                     f"broker cash: {self.broker.get_cash()}")

    def s_sell(self, data):
        dn = data._name
        c = self.cc[dn]

        if self.v[dn].in_position or self.in_position_count() >= self.position_slots:
            return

        self.log("", level=1)
        self.log(datetime.now(), num2date(data.datetime[0]), "s_sell", dn, level=1)
        self.log("-" * 80, level=1)

        rsrc = self.rsrc(data)
        # self.v[dn].last_short_qty = round((self.free_cash * (self.lot_percent / 100)) / rsrc, 2)
        # # print(dn, self.v[dn].last_short_qty)
        # self.v[dn].last_short_price = rsrc

        # Stop Loss price set
        self.v[dn].short_stop_price = rsrc * (1 + (c.stop_loss_percent_short / 1000))
        # self.v[dn].short_take_price = rsrc * (1 - (c.take_percent_short / 1000))

        # Trailer sets
        self.v[dn].trailer_short_activation_price = rsrc * (1 - (c.trailer_short_enter_percent / 1000))
        self.v[dn].trailer_short_active = False
        self.v[dn].trailer_short_lowest_price = 1000000000000.0

        # self.v[dn].last_short_order = self.sell(data, size=self.v[dn].last_short_qty)
        self.v[dn].last_short_order = self.sell(data)
        print("SELL", dn)
        print(self.v[dn].last_short_order)
        print("-" * 80)

        if self.v[dn].last_short_order:
            self.v[dn].trade_steps = 0

            self.cd[dn].decision[0] = -1  # -1= sell
            self.in_position = True
            self.v[dn].in_position = True


        # self.v[dn].popen = (f"short, {dn},{self.data.datetime.datetime(0) + dt.timedelta(hours=1)}, {data.close[0] * self.v[dn].last_short_qty}, "
        #                     f"broker cash: {self.broker.get_cash()}")

        # print(self.v[dn].popen)

    # def load_config(self):
    #     if self.is_load_config:
    #         config = load('config.joblib')
    #         kwargs = dict(config)
    #         config_obj = SimpleNamespace(**kwargs)
    #
    #         if self.config_time_stamp != config_obj.time_stamp:
    #             self.c = config_obj
    #             self.c.live_run = True
    #             self.c.show_log = True
    #             self.min_steps = self.c.rsi_period + 1
    #             print(self.c)
    #             self.config_time_stamp = config_obj.time_stamp

    def pine_ema(self, src, length, last_ssum):

        # print("pine_ema", src, length, last_ssum)

        alpha = round(2 / (length + 1), 8)
        if self.steps_count == 0:
            ssum = round(src, 8)
        else:
            ssum = round(alpha * src + (1 - alpha) * last_ssum, 8)
        return ssum

    def is_live_data(self):

        if self.is_live_run:
            status = self.datas[0]._state  # 0 - Live data, 1 - History data, 2 - None
            if status == 1:
                return False
            elif status == 0:
                return True
            else:
                print("ERROR, Live or History?")
                return False
        else:
            return True

    def data_manager(self, data):

        dn = data._name
        c = self.cc[dn]

        # print(c)

        # if dn == "ETHUSDT":
        #     print(dn, num2date(data.datetime[0]), data.close[0], self.is_live_data())
        #     return
        # else:
        #     return

        rsrc = self.rsrc(data)
        # print(dn, data.close[0], rsrc)
        if self.steps_count == 0:
            ema_fast_long_data = rsrc
            ema_fast_long_down_shift_data = round(ema_fast_long_data * (c.ema_fast_long_down_shift / 100), 8)
            ema_slow_long_data = rsrc
            ema_fast_short_data = rsrc
            ema_fast_short_up_shift_data = round(ema_fast_short_data * (c.ema_fast_short_up_shift / 100), 8)
            ema_slow_short_data = rsrc

        else:
            ema_fast_long_data = self.pine_ema(rsrc, c.ema_fast_long, self.cd[dn].ema_fast_long_data_history[0])
            ema_fast_long_down_shift_data = ema_fast_long_data * (c.ema_fast_long_down_shift / 100)
            ema_slow_long_data = self.pine_ema(rsrc, c.ema_slow_long, self.cd[dn].ema_slow_long_data_history[0])
            ema_fast_short_data = self.pine_ema(rsrc, c.ema_fast_short, self.cd[dn].ema_fast_short_data_history[0])
            ema_fast_short_up_shift_data = ema_fast_short_data * (c.ema_fast_short_up_shift / 100)
            ema_slow_short_data = self.pine_ema(rsrc, c.ema_slow_short, self.cd[dn].ema_slow_short_data_history[0])

        # if 0 == 0:
        #     print(f"{data.datetime.datetime(0)}; "
        #           f"{data.open[0]}; "
        #           f"{data.high[0]}; "
        #           f"{data.low[0]}; "
        #           f"{rsrc}; "
        #           f"{ema_fast_long_data}; "
        #           f"{ema_fast_long_down_shift_data}; "
        #           f"{ema_slow_long_data}"
        #           f"{ema_fast_short_data}; "
        #           f"{ema_fast_short_up_shift_data}; "
        #           f"{ema_slow_short_data}"
        #           )

        portfolio_value = self.position_value()

        self.cd[dn].add_data(data,
                             ema_fast_long_data=ema_fast_long_data,
                             ema_fast_long_down_shift_data=ema_fast_long_down_shift_data,
                             ema_slow_long_data=ema_slow_long_data,
                             ema_fast_short_data=ema_fast_short_data,
                             ema_fast_short_up_shift_data=ema_fast_short_up_shift_data,
                             ema_slow_short_data=ema_slow_short_data,
                             portfolio_value=portfolio_value,
                             )

        # for data in self.datas:
        #     print("Data manager v steps count", data._name, self.v[data._name].dn_steps_count)

        if data._name == self.datas[len(self.datas) - 1]._name:
            self.steps_count += 1


        # if self.c.worker_no == 0:
        #     print(self.cd.ema_fast_long_data_history)
        #     print(self.cd.ema_slow_long_data_history)
        #
        # if self.steps_count > 500:
        #     sys.exit(0)

        return

    def prenext(self):
        # print("prenext")
        for data in self.datas:
            self.data_manager(data)

    def select_diff_datetime(self, dt_array):

        ret = []

        for x, dtx in enumerate(dt_array):
            if self.dt_array[x] != dtx:
                ret.append(x)
        self.dt_array = dt_array
        return ret

    def next(self):
        dt_array = []
        for data in self.datas:
            dt_array.append(data.datetime[0])
        arrived_data = self.select_diff_datetime(dt_array)

        for ad in arrived_data:
            data = self.datas[ad]
            dn = data._name

            if self.v[dn].in_position:
                self.v[dn].trade_steps += 1
            else:
                self.v[dn].trade_steps = 0

            self.v[dn].dn_steps_count += 1
            # print(dn, data.close[0])
            #
            # if self.is_live_run:
            #     self.set_life_signal(key="Strategy_next1_" + str(dn),
            #                          cclass="EmaShiftMultiStrategy",
            #                          method="next",
            #                          msg1=str(dn),
            #                          msg2=str(str(data.close[0])),
            #                          msg3=""
            #                          )

            self.log(f"Market data recieved: {num2date(data.datetime[0])} {dn}, {data.close[0]}", level=5)
            c = self.cc[dn]
            # if ad == 0:
            #     print("next", dn, num2date(data.datetime[0]), data.close[0])

            self.data_manager(data)

            # if self.c.worker_no == 0:
            # if 1 == 1:
            #     print("-" * 80)
            #     print(dn)
            #     print(self.cd[dn].ema_fast_long_down_shift_data_history[0])
            #     print(self.cd[dn].ema_fast_long_down_shift_data_history[1])
            #     print(self.cd[dn].ema_slow_long_data_history[0])
            #     print(self.cd[dn].ema_slow_long_data_history[1])

            if self.steps_count < 2:
                continue
            # elif self.is_live_run and self.steps_count == 699:
            #     if dn == list(self.cd.keys())[0]:
            #         self.save_collected_data()
            #         self.scheduled_account_info()

            long_signal = (round(self.cd[dn].ema_fast_long_down_shift_data_history[0], 8) > round(self.cd[dn].ema_slow_long_data_history[0], 8)and
                           round(self.cd[dn].ema_fast_long_down_shift_data_history[1], 8) <= round(self.cd[dn].ema_slow_long_data_history[1], 8))
            # long_close = (round(self.cd[dn].ema_fast_long_down_shift_data_history[0], 8) < round(self.cd[dn].ema_slow_long_data_history[0], 8) and
            #           round(self.cd[dn].ema_fast_long_down_shift_data_history[1], 8) >= round(self.cd[dn].ema_slow_long_data_history[1], 8))

            short_signal = (round(self.cd[dn].ema_fast_short_up_shift_data_history[0], 8) < round(self.cd[dn].ema_slow_short_data_history[0], 8) and
                            round(self.cd[dn].ema_fast_short_up_shift_data_history[1], 8) >= round(self.cd[dn].ema_slow_short_data_history[1], 8))
            # short_close = (round(self.cd[dn].ema_fast_short_up_shift_data_history[0], 8) > round(self.cd[dn].ema_slow_short_data_history[0], 8) and
            #                round(self.cd[dn].ema_fast_short_up_shift_data_history[1], 8) <= round(self.cd[dn].ema_slow_short_data_history[1], 8))

            # if self.is_live_run:
                # self.set_life_signal(key="Strategy_next2_" + str(dn) + "long_signal",
                #                      cclass="EmaShiftMultiStrategy",
                #                      method="next",
                #                      msg1=str(dn),
                #                      msg2=str("long_signal"),
                #                      msg3=str(long_signal)
                #                      )

                # self.set_life_signal(key="Strategy_next2_" + str(dn) + "long_close",
                #                      cclass="EmaShiftMultiStrategy",
                #                      method="next",
                #                      msg1=str(dn),
                #                      msg2=str("long_close"),
                #                      msg3=str(long_close)
                #                      )

                # self.set_life_signal(key="Strategy_next2_" + str(dn) + "short_signal",
                #                      cclass="EmaShiftMultiStrategy",
                #                      method="next",
                #                      msg1=str(dn),
                #                      msg2=str("short_signal"),
                #                      msg3=str(short_signal)
                #                      )

                # self.set_life_signal(key="Strategy_next2_" + str(dn) + "short_close",
                #                      cclass="EmaShiftMultiStrategy",
                #                      method="next",
                #                      msg1=str(dn),
                #                      msg2=str("short_close"),
                #                      msg3=str(short_close)
                #                      )

            # long_signal = True if np.random.randint(0, 3) == 0 else False
            # long_close = True if np.random.randint(0, 3) == 0 else False
            # short_signal = True if np.random.randint(0, 3) == 0 else False
            # short_close = True if np.random.randint(0, 3) == 0 else False
            #
            # long_close = False if long_signal else long_close
            # short_close = False if short_signal else short_close

            self.cd[dn].add_signal(long_signal, short_signal)

            # Strategy trade
            rsrc = self.rsrc(data)
            # continue
            if not self.is_live_data():
                continue

            # print("position:")
            # for idata, position in self.broker.positions.items():
            #     # for position in self.broker.positions:
            #     print(idata._name, position.size)

            # ax = round(self.cd[dn].ema_fast_long_down_shift_data_history[0], 8)
            # bx = round(self.cd[dn].ema_slow_long_data_history[0], 8)
            # cx = round(self.cd[dn].ema_fast_long_down_shift_data_history[1], 8)
            # dx = round(self.cd[dn].ema_slow_long_data_history[1], 8)
            #
            # print(datetime.utcnow(), self.steps_count, dn, rsrc, ax, bx, cx, dx)
            # if long_signal or short_signal:
            #     print(self.steps_count, dn, long_signal, short_signal)

            # if dn == "BNBUSDT":
            #     continue

            # TRADE -------------------------------------------------------------------------------
            # print("steps", self.steps_count, dn)
            # print(self.v[dn].trade_steps, c.max_trade_steps)
            if (self.v[dn].trade_steps > c.max_trade_steps and not self.v[dn].trailer_long_active
                    and not self.v[dn].trailer_short_active):
                print(self.v[dn].trade_steps, c.max_trade_steps)
                self.s_close(data, "close max_trade_steps")

            # if self.steps_count == 701 and dn == "ETHUSDT":
            #     self.s_buy(data)
            #
            # if self.steps_count == 703 and dn == "ETHUSDT":
            #     self.s_close(data, "stop")
            #
            # if self.steps_count == 704 and dn == "ETHUSDT":
            #     self.s_sell(data)
            #
            # if self.steps_count == 706 and dn == "ETHUSDT":
            #     self.s_close(data, "stop")
            #
            # continue

            if c.is_long == 1:
                # if long_signal and self.getposition(data).size == 0.0:
                if long_signal:
                    self.log(f"{dn} Strategy: long_signal ", level=3)
                    #
                    # if self.getposition(data).size < 0:
                    #     # Turn over Short to Long
                    #     self.log(f"{dn} Strategy: Short->Long ", level=3)
                    #     self.s_close(data, "Short->Long")
                    #     if self.is_live_run:
                    #         time.sleep(10)
                    self.s_buy(data)

                elif rsrc < self.v[dn].long_stop_price and c.is_stop_loss_long == 1 and self.getposition(data).size > 0.0:
                    self.log(f"{dn} Strategy: is_stop_loss_long ", level=3)
                    self.s_close(data, "Long_SLoss")

                elif c.is_trailer_long == 1 and self.v[dn].trailer_long_active and rsrc < self.v[dn].trailer_long_stop_price and self.getposition(data).size > 0:
                    self.s_close(data, "close trailer_long_active")

                # elif long_close and self.getposition(data).size > 0:
                #     self.log(f"{dn} Strategy: Long_Close ", level=3)

                # elif self.getposition(data).size > 0.0 and rsrc > self.v[dn].long_take_price:
                #     self.log(f"{dn} Strategy: Long_Close ", level=3)
                #     self.s_close(data, "Long_Close")

                # if c.worker_no == 1:
                #     print(rsrc, c.is_trailer_long, self.v[dn].trailer_long_active, self.v[dn].trailer_long_activation_price, self.v[dn].trailer_long_stop_price)

                if c.is_trailer_long == 1 and self.getposition(data).size > 0.0 and rsrc > self.v[dn].trailer_long_activation_price and not self.v[dn].trailer_long_active:
                    self.v[dn].trailer_long_active = True

                if c.is_trailer_long == 1 and self.v[dn].trailer_long_active:

                    self.v[dn].trailer_long_highest_price = max(self.v[dn].trailer_long_highest_price, rsrc)
                    self.v[dn].trailer_long_stop_price = self.v[dn].trailer_long_highest_price * (1 - (c.trailer_long_offset / 1000))

            if c.is_short == 1:
                # if short_signal and self.getposition(data).size == 0.0:
                if short_signal:
                    self.log(f"{dn} Strategy: short_signal ", level=3)

                    # if self.getposition(data).size > 0.0:
                    #     # Turn over Long to Short
                    #     self.log(f"{dn} Strategy: Long->Short ")
                    #     self.s_close(data, "Long->Short")
                    #     if self.is_live_run:
                    #         time.sleep(10)
                    self.s_sell(data)

                elif rsrc > self.v[dn].short_stop_price and c.is_stop_loss_short == 1 and self.getposition(data).size < 0.0:
                    self.log(f"{dn} Strategy: is_stop_loss_short ", level=3)

                    self.s_close(data, "Short_SLoss")

                elif c.is_trailer_short == 1 and self.v[dn].trailer_short_active and rsrc > self.v[dn].trailer_short_stop_price and self.getposition(data).size < 0:
                    self.s_close(data,"close trailer_short_active")

                # elif self.getposition(data).size < 0.0 and rsrc < self.v[dn].short_take_price:
                #     self.log(f"{dn} Strategy: short_close ", level=3)
                #
                #     self.s_close(data, "Short_Close")

                if c.is_trailer_short == 1 and self.getposition(data).size < 0.0 and rsrc < self.v[dn].trailer_short_activation_price and not self.v[dn].trailer_short_active:
                    self.v[dn].trailer_short_active = True

                if c.is_trailer_short == 1 and self.v[dn].trailer_short_active:

                    self.v[dn].trailer_short_lowest_price = min(self.v[dn].trailer_short_lowest_price, rsrc)
                    self.v[dn].trailer_short_stop_price = self.v[dn].trailer_short_lowest_price * (1 + (c.trailer_short_offset / 1000))

            # self.cd.add_meta('linet', "Server time:" + str(datetime.now().strftime("%Y. %m. %d. %H:%M:%S")))
        # self.cd.save()

    def stop(self):
        if not self.end_close:
            return
        else:
            for data in self.datas:
                if self.getposition(data).size != 0:
                    self.s_close(data, "Strategy Stop Close")

    def notify_data(self, data, status, *args, **kwargs):
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
        # print(order.data._name, order.executed.size, order.params.size)
        return
        # if self.c.worker_no == 0:
        #     if order.status in [order.Completed, order.Canceled, order.Rejected]:
        #         if self.last_buy_order and self.last_buy_order.ref == order.ref:
        #             print(f'Last BUY Order ID: {order.ref}')
        #         if self.last_sell_order and self.last_sell_order.ref == order.ref:
        #             print(f'Last SELL Order ID: {order.ref}')
        # """Changing the status of the order"""
        # order_data_name = order.data._name  # Name of ticker from order
        # # self.log(
        # #     f'Order number {order.ref} {order.info["order_number"]} {order.getstatusname()} {"Buy" if order.isbuy() else "Sell"} {order_data_name} {order.size:.10f} @ {order.price:.10f}')
        # if order.status == bt.Order.Completed:  # If the order is fully executed
        #     if order.isbuy():  # The order to buy
        #         self.log(
        #             f'Buy {order_data_name} Price: {order.executed.price:.10f}, Value {order.executed.value:.10f} {self.symbol}, Commission {order.executed.comm:.10f}')
        #     else:  # The order to sell
        #         self.log(
        #             f'Sell {order_data_name} Price: {order.executed.price:.10f}, Value {order.executed.value:.10f} {self.symbol}, Commission {order.executed.comm:.10f}')
        #         if self.c.live_run:
        #             pnl = order.executed.value - self.last_buy_order.executed.value
        #             self.total_pnl += pnl
        #             text = f"Total PNL: {self.total_pnl:.10f} Last trade PNL: {pnl:.10f}"
        #             self.log(text)
        #             self.cd.add_meta('line3', text)

            # self.orders[order_data_name] = None  # Reset the order to enter the position

    def notify_trade(self, trade):
        # return
        if not self.is_live_run:
            if trade.isclosed:
                self.symbol_profit[trade.getdataname()] += trade.pnlcomm
                self.total_pnlcomm += trade.pnlcomm
                self.paid_comission += (trade.pnlcomm - trade.pnl)
                # print("close", trade.getdataname())

            c = self.cc[trade.getdataname()]
            if c.show_log or True:
                if trade.isclosed:  # If the position is closed
                    self.log(f'{self.closed_trade_count} Closed  {trade.getdataname()} {self.data.num2date(trade.data.datetime[0])} {trade.data.close[0]} PNL={trade.pnlcomm:.10f}, Commission{trade.pnlcomm - trade.pnl:.10f} {trade.status_names[trade.status]}')
                    self.closed_trade_count += 1
                elif trade.justopened:
                    self.log(f'   Open    {trade.getdataname()} {self.data.num2date(trade.data.datetime[0])} {trade.price} {trade.size} {trade.status_names[trade.status]}')



# # test
# if __name__ == "__main__":
#
#     print("Rosszat inddiitottál")
