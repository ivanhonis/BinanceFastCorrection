# Regular
# import sys
import time

import requests
import os
from copy import deepcopy
import random
import math
import itertools
import json
from tqdm.auto import tqdm
import datetime as dt
# import keyboard

# Backtrader
import backtrader as bt
import backtrader.analyzers as btanalyzers

# Binance
from binance.client import Client

# Pandas
import pandas as pd
import numpy as np
from joblib import dump, load

# process
from multiprocessing import Process, Manager
from types import SimpleNamespace

from numba import jit

from bt_tools import df_check, binance_download

# matplotlib
# import matplotlib.pyplot as plt

# Own

# from RSI_Strategy_dev3 import RSIStrategy
from EMA_Shift_Multi_Strategy import EmaShiftMultiStrategy
from EMA_Shift_Multi_Strategy import ESMSizer

# from strategy_levi import BreakoutStrategy, NamedPandasData, FixedCashSizer, AccountValueObserver
# from data_utils import download_tickers, get_tickers_from_wiki

pd.set_option('display.precision', 8)


class DeterministicRND:
    def __init__(self, min_value=1, max_value=10000, seed=0):
        self.min_value = min_value
        self.max_value = max_value
        self.range_size = max_value - min_value + 1
        self.seed = seed

    def _hash(self, x):
        # A simple hash function for demonstration purposes
        return (x * 1664525 + 1013904223) % self.range_size

    def generate(self, index):
        if index < 0 or index >= self.range_size:
            raise IndexError("Index out of bounds")

        hashed_value = self._hash(index + self.seed)
        return (hashed_value + self.min_value) % self.range_size + self.min_value

# def get_binance_futures_bars(symbol, interval, start_time, end_time):
#     url = "https://fapi.binance.com/fapi/v1/continuousKlines"
#
#     start_time = str(int(start_time.timestamp() * 1000))
#     end_time = str(int(end_time.timestamp() * 1000))
#     limit = '1000'
#
#     # https://binance-docs.github.io/apidocs/futures/en/#continuous-contract-kline-candlestick-data
#
#     req_params = {"pair": symbol,
#                   'interval': interval,
#                   'startTime': start_time,
#                   'endTime': end_time,
#                   'limit': limit,
#                   'contractType': "PERPETUAL"}
#
#     # print(json.loads(requests.get(url, params=req_params).text))
#     df = pd.DataFrame(json.loads(requests.get(url, params=req_params).text))
#
#     if len(df.index) == 0:
#         return None
#
#     df = df.iloc[:, 0:6]
#     df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
#
#     df.open = df.open.astype("float64")
#     df.high = df.high.astype("float64")
#     df.low = df.low.astype("float64")
#     df.close = df.close.astype("float64")
#     df.volume = df.volume.astype("float64")
#
#     df['adj_close'] = df['close']
#
#     df.index = [dt.datetime.fromtimestamp(x / 1000.0) for x in df.datetime]
#
#     return df


def cerebro_process(df_dict, config_dict, plot=False, force_num_of_symbols=None):

    cerebro = bt.Cerebro()

    data = {}
    for k in df_dict:
        data[k] = bt.feeds.PandasData(dataname=df_dict[k])
        cerebro.adddata(data[k], name=k)
    del data

    cdk = tuple(df_dict.keys())[0]
    total_data_len = df_dict[cdk].shape[0]
    cerebro.addstrategy(EmaShiftMultiStrategy, config=config_dict, total_data_len=total_data_len)

    start_cash = 100000.0
    cerebro.broker.setcash(start_cash)
    cerebro.broker.setcommission(commission=0.00075)
    # cerebro.broker.setcommission(commission=0.0)
    # cerebro.addsizer(bt.sizers.PercentSizer, percents=70)
    cerebro.addsizer(ESMSizer, symbols=list(df_dict.keys()),  max_percent=70, start_cash=start_cash, force_num_of_symbols=force_num_of_symbols)

    # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    # cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
    # cerebro.addanalyzer(bt.analyzers.VWR, _name="vwr")
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="annualreturn")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.02)
    cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    # cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    # cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')

    cerebro_result = cerebro.run()

    # time_period_day = df.index[-1] - df.index[0]
    # time_period_day = time_period_day.total_seconds() / 60 / (60 * 24)

    data_res = {}
    # data_res["time_period_day"] = time_period_day
    # data_res["p365"] = round((cerebro.broker.getvalue() - start_cash) / time_period_day * 365, 0)
    data_res["nom_pnl_end"] = round((cerebro.broker.get_value() - start_cash), 3)
    data_res["nom_pnl_closed"] = round(cerebro_result[0].total_pnlcomm, 3)
    # data_res["nom_pnl_closed_trades"] = cerebro_result[0].free_cash - cerebro_result[0].initial_cash
    # data_res["drawdown"] = round(cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().max.moneydown, 2)
    data_res["trades"] = len(cerebro_result[0].analyzers.trans.get_analysis()) // 2
    data_res["sharperatio"] = cerebro_result[0].analyzers.sharpe.get_analysis()['sharperatio']
    # data_res["vwr"] = cerebro_result[0].analyzers.vwr.get_analysis()['vwr']
    data_res["annualreturn"] = cerebro_result[0].analyzers.getbyname('annualreturn').get_analysis()
    data_res["sqn"] = round(cerebro_result[0].analyzers.getbyname('sqn').get_analysis()['sqn'], 2)
    # data_res["trade_analyzer"] = cerebro_result[0].analyzers.getbyname('trade_analyzer').get_analysis()
    # data_res["returns"] = cerebro_result[0].analyzers.getbyname('returns').get_analysis()
    # returns, positions, transactions, gross_lev = cerebro_result[0].analyzers.getbyname('pyfolio').get_pf_items()
    # data_res["pyfolio_returns"] = returns
    # data_res["pyfolio_positions"] = positions
    # data_res["pyfolio_transactions"] = transactions
    # data_res["pyfolio_gross_lev"] = gross_lev
    dd_ret = {}

    cdk = tuple(cerebro_result[0].cd.keys())[0]  # mindegyiknek ugyanaz ezért elég az elsőt kiolvasni
    filtered_arr = cerebro_result[0].cd[cdk].portfolio_value[cerebro_result[0].cd[cdk].portfolio_value != 0]
    data_res["dd"] = [
                    np.min(filtered_arr),
                    np.max(filtered_arr),
                    np.std(filtered_arr),
                    cerebro_result[0].cd[cdk].portfolio_value[0],
                    ]


    #     - ``drawdown`` - drawdown value in 0.xx %
    #     - ``moneydown`` - drawdown value in monetary units
    #     - ``len`` - drawdown length
    #
    #     - ``max.drawdown`` - max drawdown value in 0.xx %
    #     - ``max.moneydown`` - max drawdown value in monetary units
    #     - ``max.len`` - max drawdown length
    #
    # print("drawdown", cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().drawdown)
    # print("moneydown", cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().moneydown)
    # print("len", cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().len)
    # print("max.drawdown", cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().max.drawdown)
    # print("max.moneydown", cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().max.moneydown)
    # print("max.len", cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().max.len)

    # ----------------------------------------
    # meter
    # ----------------------------------------
    drawdown = (start_cash - data_res["dd"][0])

    if drawdown != 0:
        calmar_ratio = data_res["nom_pnl_closed"] / drawdown
    else:
        calmar_ratio = None

    # RARMD -> Risk-Adjusted Return with Maximum Drawdown
    if data_res["sharperatio"] is None or drawdown is None:
        rarmd = -1000000000000
    else:
        if drawdown != 0:
            rarmd = (data_res["sharperatio"] / drawdown) * 1000000
        else:
            rarmd = -1000000000000

    # SHARP / CALMAR
    if data_res["sharperatio"] is None or data_res["sharperatio"] <= 0:
        spc = -1000000000000
    elif calmar_ratio:
        spc = data_res["sharperatio"] / calmar_ratio
    else:
        spc = 0

    # TARRM Transaction-adjusted Risk-Return Metric
    if data_res["sharperatio"] is None:
        tarrm = 0
    else:
        tarrm = data_res["sharperatio"] * math.log(data_res["trades"])

    data_res["meter"] = data_res["nom_pnl_closed"]
    # print(cerebro_result[0].cd["ETHUSDT"].portfolio_value)

    # filtered_arr = cerebro_result[0].cd["ETHUSDT"].portfolio_value[cerebro_result[0].cd["ETHUSDT"].portfolio_value != 0]
    # print("DD: ", np.min(filtered_arr), cerebro_result[0].cd["ETHUSDT"].portfolio_value[0])

    if plot:
        cerebro.plot()
        print("symbol_profit:", cerebro_result[0].symbol_profit)

    return cerebro_result, data_res


def print_data_result(conf, res_dict):
    print(conf)
    print(res_dict)
    print('')

    # with open('HPO_results.txt', 'a') as file:
    #     print(conf, file=file)
    #     print(res_dict, file=file)


@jit(nopython=True)
def numba_product(*arrays):

    memory_gb = 127
    array_length = len(arrays)  # number of parameters
    element_size_bytes = 2  # int16 is 2 bytes
    memory_bytes = memory_gb * (2 ** 30)
    row_size_bytes = array_length * element_size_bytes
    total_rows = memory_bytes // row_size_bytes

    total = 1
    for a in arrays:
        total *= len(a)
    max_row = min(total, total_rows)

    result = np.zeros((max_row, len(arrays)), dtype=np.int16)

    for i in range(len(arrays)):
        # t = total
        n = len(arrays[i])
        total //= n
        # k = 0
        for k in range(result.shape[0]):
            for j in range(n):
                for x in range(total):
                    result[k, i] = arrays[i][j]
                    # k += 1
    return result


# for 1h
def parmeter_combinations(max_worker):
    settings = {}
    settings["is_long"] = np.random.permutation(np.arange(1, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    settings["ema_fast_long"] = np.random.permutation(np.arange(15, 40, 1, dtype=np.int16))
    settings["ema_slow_long"] = np.random.permutation(np.arange(400, 600, 1, dtype=np.int16))
    settings["ema_fast_long_down_shift"] = np.random.permutation(np.arange(90, 100, 1, dtype=np.int16))  # / 100
    settings["is_stop_loss_long"] = np.random.permutation(np.arange(0, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    settings["stop_loss_percent_long"] = np.random.permutation(np.arange(15, 66, 1, dtype=np.int16))  # / 1000

    settings["is_short"] = np.random.permutation(np.arange(0, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    settings["ema_fast_short"] = np.random.permutation(np.arange(15, 40, 1, dtype=np.int16))
    settings["ema_slow_short"] = np.random.permutation(np.arange(400, 600, 1, dtype=np.int16))
    settings["ema_fast_short_up_shift"] = np.random.permutation(np.arange(97, 115, 1, dtype=np.int16))  # / 100
    settings["is_stop_loss_short"] = np.random.permutation(np.arange(0, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    settings["stop_loss_percent_short"] = np.random.permutation(np.arange(15, 66, 1, dtype=np.int16))  # / 1000
    settings["is_trailer_short"] = np.random.permutation(np.arange(0, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    settings["trailer_short_enter_percent"] = np.random.permutation(np.arange(1, 400, 1, dtype=np.int16))  # / 1000
    settings["trailer_short_offset"] = np.random.permutation(np.arange(1, 400, 1, dtype=np.int16))  # / 1000

    # settings["is_short"] = np.random.permutation(np.arange(1, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    # settings["ema_fast_short"] = np.random.permutation(np.arange(39, 40, 1, dtype=np.int16))
    # settings["ema_slow_short"] = np.random.permutation(np.arange(598, 600, 2, dtype=np.int16))
    # settings["ema_fast_short_up_shift"] = np.random.permutation(np.arange(110, 115, 5, dtype=np.int16))  # / 100
    # settings["is_stop_loss_short"] = np.random.permutation(np.arange(1, 2, 1, dtype=np.int16))  # 0 nem 1 igen
    # settings["stop_loss_percent_short"] = np.random.permutation(np.arange(64, 66, 2, dtype=np.int16))  # / 1000

    params_array = []
    settings_name = []

    for k in settings:
        params_array.append(settings[k])
        settings_name.append(k)

    total_combinations = 1
    for a in params_array:
        total_combinations *= len(a)

    # all_combinations = np.array(tuple(itertools.product(*possible_settings)), dtype=np.int8)
    # all_combinations = numba_product(*possible_settings)
    # print(f"All combinations: {len(all_combinations)}")
    # time.sleep(50)
    # np.random.seed(42)
    # numba_shuffle(all_combinations)
    # print(f"Number total combination: {len(all_combinations)}")
    # splited_combinations = np.array_split(all_combinations, max_worker)
    # del all_combinations
    return params_array, settings_name, total_combinations


def nth_combination(arrays, n):
    indices = []
    for array in arrays:
        size = len(array)
        index = n % size
        indices.append(index)
        n //= size

    combination = [arrays[i][indices[i]] for i in range(len(arrays))]
    combination = np.array(combination, dtype=np.int64)
    return combination


def hpo_worker(worker_no, max_worker, df, arrays, total_combinations, settings_name, shared_dict, base, quote, force_num_of_symbols):
    print(f"run worker {max_worker} / {worker_no + 1}")

    slice_size = int((total_combinations - 1) / max_worker)
    # print(slice_size)
    slice_start = slice_size * worker_no
    slice_end = (slice_size * (worker_no + 1)) - 1
    # selected_slice = np.arange(slice_start, slice_end, 100)
    rnd_gen = DeterministicRND(min_value=slice_start, max_value=slice_end-1)

    # np.random.shuffle(selected_slice)

    # all_res = []
    # for i in selected_slice:
    i = 0
    while i < slice_size-2:
        rx = rnd_gen.generate(i)
        sc = nth_combination(arrays, rx)
        # print(f"Worker: {worker_no}, combination: {sc}")
        config = []
        for x, c in enumerate(sc):
            config.append([settings_name[x], c])

        config.append(['base', base])
        config.append(['quote', quote])
        config.append(["plot", False])
        config.append(["show_log", False])
        config.append(["worker_no", worker_no])

        kwargs = dict(config)

        df_dict = {base + quote: df}
        config_dict = {base + quote: SimpleNamespace(**kwargs)}
        cerebro_res, data_res = cerebro_process(df_dict,
                                                config_dict=config_dict,
                                                force_num_of_symbols=force_num_of_symbols)

        # all_res.append(data_res)

        if data_res["meter"] > shared_dict['meter']:
            # print(worker_no, "nagyobb", data_res["nom_pnl"], shared_dict['nom_pnl'])
            shared_dict['meter'] = data_res["meter"]
            shared_dict['data'] = data_res
            shared_dict['config'] = config
        # else:
            # print(worker_no, "kisebb", data_res["nom_pnl"], shared_dict['nom_pnl'])

            # print_data_result(config, data_res)
        # print(f"Eof setting")
        i += 1
    shared_dict['ready'] += 1


if __name__ == "__main__":
    # HPO Start
    run_type = 'HPO'
    # run_type = 'SET'

    if run_type == "HPO":

        # base = "MATIC"
        # base = "LINK"
        # base = "NEAR"
        # base = "ETC"
        base = "ETH"
        quote = "USDT"
        asset_type = "crypto"
        futures = True
        refresh = True
        # refresh = False
        force_num_of_symbols = None

        # from_dt = dt.datetime(year=2017, month=8, day=17, hour=0, minute=0)
        # cutoff_dt = dt.datetime(year=2022, month=1, day=1, hour=0, minute=0)
        # from_dt = dt.datetime(year=2022, month=1, day=1, hour=0, minute=0)
        # from_dt = dt.datetime(year=2023, month=1, day=1, hour=0, minute=0)
        from_dt = dt.datetime(year=2024, month=1, day=1, hour=0, minute=0)
        cutoff_dt = None
        interval = "15m"
        # interval = "1m"
        # interval = "1h"

        processors_use = 14
        arrays, settings_name, total_combinations = parmeter_combinations(processors_use)

        print(f"Total combinations: {total_combinations}, combinations / processor: {int(total_combinations /processors_use)}")

        df_dict = pd.DataFrame(None)
        if asset_type == "crypto":
            df_dict = binance_download(base + quote,
                                       from_dt=from_dt,
                                       cutoff_dt=cutoff_dt,
                                       refresh=refresh,
                                       futures=futures,
                                       interval=interval)  # in minute from now()

            df_dict = df_check(df_dict, del_duplicates=False)

            # !!!!!!!!
            # A Binance-nél volt el leállás '2023-03-24 11:00:00' ez a lállás 1 óráig tartott,
            # de a tw nél ez két adat hiányát ereményezte azért , hogy a tw vel azonos legyen egy adatoto kitörlök
            # try:
            #     date_to_delete = '2023-03-24 12:00:00'
            #     date_to_delete = pd.to_datetime(date_to_delete)
            #     df_dict = df_dict.drop(date_to_delete)
            # except:
            #     pass
            # !!!!!!!!

        # elif asset_type == "stock":
        #     df = yahoo_download(base + quote, from_dt, back_shift=0, refresh=True, interval="1h")
        #     print(df)
        #
        #     # MINIMUM_CANDLES = 4000
        #     # ticker_datas, length = download_tickers(TICKERS, END_DATE, MINIMUM_CANDLES, cache=False, interval="1h")
        #     # START_DATE = ticker_datas[0][1].iloc[-length].name
        #     # for ticker, ticker_data in tqdm(ticker_datas):
        #     #     df = NamedPandasData(dataname=ticker_data.iloc[-length:].copy(deep=True), timeframe=bt.TimeFrame.Days, ticker=ticker)

        manager = Manager()
        shared_dict = manager.dict()
        shared_dict['meter'] = -10000000000000
        shared_dict['ready'] = 1
        highest_meter = -10000000000000

        processes = [None] * processors_use

        # print("Number of combinations / processor: ", len(arrays[0]))

        for p in range(processors_use):
            processes[p] = Process(target=hpo_worker, kwargs={
                'worker_no': p,
                'max_worker': processors_use,
                'df': df_dict,
                'arrays': arrays,
                'total_combinations': total_combinations,
                'settings_name': settings_name,
                'shared_dict': shared_dict,
                'base': base,
                'quote': quote,
                'force_num_of_symbols': force_num_of_symbols,
            })
            processes[p].start()

        while shared_dict['ready'] <= processors_use:
            if highest_meter != shared_dict['meter']:
                highest_meter = shared_dict['meter']
                try:
                    print('')
                    print(shared_dict['data'])
                    print(shared_dict['config'])
                except:
                    print('')

            time.sleep(5)

        for p in range(processors_use):
            processes[p].join()

        save_dic = shared_dict['config']
        save_dic.append(["time_stamp", int(time.time())])
        # dump(save_dic, 'config.joblib')

        print(shared_dict['data'])
        print(save_dic)
        print('Ready.')

    elif run_type == "SET":

        from_dt = dt.datetime(year=2022, month=1, day=1, hour=0, minute=0)
        cutoff_dt = None
        refresh = False
        futures = True

        cc = {}

        # base = "BNB"
        # quote = "USDT"
        # config = [['base', base],
        #           ['quote', quote],
        #           ["plot", False],
        #           ["show_log", False],
        #           ["worker_no", 0],
        #           ['is_long', 1],
        #           ['ema_fast_long', 30],
        #           ['ema_slow_long', 476],
        #           ['ema_fast_long_down_shift', 97],
        #           ['is_stop_loss_long', 1],
        #           ['stop_loss_percent_long', 30],
        #           ['is_short', 0],
        #           ['ema_fast_short', 31],
        #           ['ema_slow_short', 462],
        #           ['ema_fast_short_up_shift', 101],
        #           ['is_stop_loss_short', 0],
        #           ['stop_loss_percent_short', 64],
        #           ['is_trailer_short', 0],
        #           ['trailer_short_enter_percent', 10],
        #           ['trailer_short_offset', 212]
        #           ]
        #
        # kwargs = dict(config)
        # cc[base + quote] = SimpleNamespace(**kwargs)

        # {
        #     'nom_pnl_end': 204080.098, 'nom_pnl_closed': 175130.906, 'drawdown': 54503.55, 'trades': 50, 'sharperatio': 2.172291573597915,
        #     'annualreturn': OrderedDict([(2022, 0.6818615032139941), (2023, 0.1906676959501663), (2024, 0.5184734270285465)]), 'sqn': 1.51, 'meter': 175130.906
        # }
        # [['is_long', 1], ['ema_fast_long', 29], ['ema_slow_long', 462], ['ema_fast_long_down_shift', 98], ['is_stop_loss_long', 1], ['stop_loss_percent_long', 23], ['is_short', 1],
        #  ['ema_fast_short', 34], ['ema_slow_short', 525], ['ema_fast_short_up_shift', 111], ['is_stop_loss_short', 1], ['stop_loss_percent_short', 21], ['is_trailer_short', 1],
        #  ['trailer_short_enter_percent', 210], ['trailer_short_offset', 52], ['base', 'ETH'], ['quote', 'USDT'], ['plot', False], ['show_log', False], ['worker_no', 10]]

        base = "ETH"
        quote = "USDT"
        config = [['base', base],
                  ['quote', quote],
                  ["plot", False],
                  ["show_log", False],
                  ["worker_no", 0],
                  ['is_long', 1],
                  ['ema_fast_long', 20],
                  ['ema_slow_long', 470],
                  ['ema_fast_long_down_shift', 99],
                  ['is_stop_loss_long', 1],
                  ['stop_loss_percent_long', 27],
                  ['is_short', 1],
                  ['ema_fast_short', 25],
                  ['ema_slow_short', 575],
                  ['ema_fast_short_up_shift', 107],
                  ['is_stop_loss_short', 0],
                  ['stop_loss_percent_short', 53],
                  ['is_trailer_short', 0],
                  ['trailer_short_enter_percent', 352],
                  ['trailer_short_offset', 4]
                  ]

        kwargs = dict(config)
        cc[base+quote] = SimpleNamespace(**kwargs)

        # base = "BTC"
        # quote = "USDT"
        # config = [['base', base],
        #           ['quote', quote],
        #           ["plot", False],
        #           ["show_log", False],
        #           ["worker_no", 0],
        #           ['is_long', 1],
        #           ['ema_fast_long', 38],
        #           ['ema_slow_long', 426],
        #           ['ema_fast_long_down_shift', 99],
        #           ['is_stop_loss_long', 1],
        #           ['stop_loss_percent_long', 15],
        #           ['is_short', 0],
        #           ['ema_fast_short', 35],
        #           ['ema_slow_short', 478],
        #           ['ema_fast_short_up_shift', 103],
        #           ['is_stop_loss_short', 0],
        #           ['stop_loss_percent_short', 53],
        #           ['is_trailer_short', 0],
        #           ['trailer_short_enter_percent', 40],
        #           ['trailer_short_offset', 311]
        #           ]
        #
        # kwargs = dict(config)
        # cc[base+quote] = SimpleNamespace(**kwargs)

        # base = "AVAX"
        # quote = "USDT"
        # config = [['base', base],
        #           ['quote', quote],
        #           ["plot", False],
        #           ["show_log", False],
        #           ["worker_no", 0],
        #           ['is_long', 1],
        #           ['ema_fast_long', 33],
        #           ['ema_slow_long', 476],
        #           ['ema_fast_long_down_shift', 93],
        #           ['is_stop_loss_long', 1],
        #           ['stop_loss_percent_long', 59],
        #           ['is_short', 1],
        #           ['ema_fast_short', 22],
        #           ['ema_slow_short', 574],
        #           ['ema_fast_short_up_shift', 98],
        #           ['is_stop_loss_short', 1],
        #           ['stop_loss_percent_short', 32],
        #           ['is_trailer_short', 1],
        #           ['trailer_short_enter_percent', 248],
        #           ['trailer_short_offset', 22]
        #           ]
        #
        # kwargs = dict(config)
        # cc[base + quote] = SimpleNamespace(**kwargs)

        df_dict = {}
        for k in cc:
            c = cc[k]

            df_dict[k] = binance_download(c.base + c.quote,
                                          from_dt=from_dt,
                                          cutoff_dt=cutoff_dt,
                                          refresh=refresh,
                                          futures=futures,
                                          interval='1h')  # in minute from now()

            print(df_dict[k].shape)

            df_dict[k] = df_check(df_dict[k], del_duplicates=False)

            # !!!!!!!!
            # A Binance-nél volt el leállás '2023-03-24 11:00:00' ez a lállás 1 óráig tartott,
            # de a tw nél ez két adat hiányát ereményezte azért , hogy a tw vel azonos legyen egy adatoto kitörlök
            try:
                date_to_delete = '2023-03-24 12:00:00'
                date_to_delete = pd.to_datetime(date_to_delete)
                df_dict[k] = df_dict[k].drop(date_to_delete)
            except:
                pass
            # !!!!!!!!
        print("Cerebro symbols:", list(df_dict.keys()))
        cerebro_res, data_res = cerebro_process(df_dict, cc, plot=True)
        print_data_result(cc, data_res)
