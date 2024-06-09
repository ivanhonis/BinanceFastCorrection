# Regular
# import sys
import time

import requests
import os
import json
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

# process
from multiprocessing import Process, Manager
from types import SimpleNamespace

from numba import jit

# import yfinance_cache as yf_cache
import yfinance as yf

# matplotlib
# import matplotlib.pyplot as plt

# Own

# from RSI_Strategy_dev3 import RSIStrategy
from archive_codes.EMA_Shift_Strategy import EmaShiftStrategy

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

def get_binance_futures_bars(symbol, interval, start_time, end_time):
    url = "https://fapi.binance.com/fapi/v1/continuousKlines"

    start_time = str(int(start_time.timestamp() * 1000))
    end_time = str(int(end_time.timestamp() * 1000))
    limit = '1000'

    # https://binance-docs.github.io/apidocs/futures/en/#continuous-contract-kline-candlestick-data

    req_params = {"pair": symbol,
                  'interval': interval,
                  'startTime': start_time,
                  'endTime': end_time,
                  'limit': limit,
                  'contractType': "PERPETUAL"}

    # print(json.loads(requests.get(url, params=req_params).text))
    df = pd.DataFrame(json.loads(requests.get(url, params=req_params).text))

    if len(df.index) == 0:
        return None

    df = df.iloc[:, 0:6]
    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']

    df.open = df.open.astype("float64")
    df.high = df.high.astype("float64")
    df.low = df.low.astype("float64")
    df.close = df.close.astype("float64")
    df.volume = df.volume.astype("float64")

    df['adj_close'] = df['close']

    df.index = [dt.datetime.fromtimestamp(x / 1000.0) for x in df.datetime]

    return df


def yahoo_download(symbol, from_dt, back_shift, refresh=False, interval='1h'):
    return yf.download(symbol, start=from_dt, interval=interval, auto_adjust=True)


def df_check(df, del_duplicates=False):
    print(df.T)
    print("Data qualtiy check: ------------------------------")

    print("Datetime:  first - last")
    print("datetime: ", df.index[0], "-", df.index[-1])
    print("close:    ", df.close[0], "-", df.close[-1])

    duplicates = df.index.duplicated()
    if duplicates.any():
        print("Duplicates")
        duplicated_indices = df.index[duplicates]

        if not duplicated_indices.empty:
            duplicated_rows = df.loc[duplicated_indices]
            print(duplicated_rows)

    else:
        print("No duplicates.")

    full_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq='H')
    missing_hours = full_range.difference(df.index)
    if not missing_hours.empty:
        # print("Hiányzó órák az adatokban:")
        # print(missing_hours)

        print("Missing rows.")
        for missing in missing_hours:
            before = df[df.index < missing].iloc[-1]
            after = df[df.index > missing].iloc[0]
            print(f"Before missing data: ({before.name}): {before.to_dict()}")
            print(f"After missing data:  ({after.name}): {after.to_dict()}")

    else:
        print("No missing row.")

    if del_duplicates:
        print("Delete duplicated datas.")
        duplicate_mask = df[['open', 'high', 'low', 'close']].eq(df[['open', 'high', 'low', 'close']].shift())
        print(df[duplicate_mask.all(axis=1)])

        # Drop duplicate rows
        print(df.shape)
        df = df[~(duplicate_mask.all(axis=1))]
        print(df.shape)
        print("------------------------------------------")
    return df


def binance_download(symbol, from_dt, cutoff_dt=None, refresh=False, futures=False, interval='1h'):
    print("binance_download2->", from_dt.strftime("%Y-%m-%d %H:%M:%S"), symbol)

    file_name = "binance_data/" + symbol + "_" + from_dt.strftime("%Y-%m-%d_%H-%M-%S")
    if refresh and os.path.exists(file_name):
        os.remove(file_name)

    if os.path.exists(file_name):
        print("Loaded data from existing file.")
        df = pd.read_hdf(file_name, "df")
    else:
        print("Download from Binance.")

        from_dt = from_dt.strftime("%Y-%m-%d %H:%M:%S")
        api_key = 'YOUR_API_KEY'
        api_secret = 'YOUR_API_SECRET'
        client = Client(api_key, api_secret)
        # adatok letöltéséhez kell a client objektum, de nem kell belépni
        if interval == '1h':
            klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1HOUR, from_dt)
        else:
            print("írd meg különböző időintervallumra is :)")

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                                           'taker_buy_quote_asset_volume', 'ignore'])

        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df[['datetime', 'timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df.set_index('datetime', inplace=True)

        df.open = df.open.astype("float64")
        df.high = df.high.astype("float64")
        df.low = df.low.astype("float64")
        df.close = df.close.astype("float64")
        df.volume = df.volume.astype("float64")
        df['adj_close'] = df['close']
        df.to_hdf(file_name, key='df', mode='w')

    if cutoff_dt:
        print("cut off")
        cutoff_dt = pd.Timestamp(cutoff_dt.strftime("%Y-%m-%d %H:%M:%S"), unit='ms')
        df = df[df.index <= cutoff_dt]

    return df


def cerebro_process(df, conf_obj, plot=False):
    cerebro = bt.Cerebro()

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    cerebro.addstrategy(EmaShiftStrategy, config=conf_obj)

    start_cash = 100000.0
    cerebro.broker.setcash(start_cash)
    cerebro.broker.setcommission(commission=0.00075)
    # cerebro.broker.setcommission(commission=0.0)
    # cerebro.addsizer(bt.sizers.PercentSizer, percents=70)
    # cerebro.addsizer(bt.sizers.AllInSizer)

    # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    # cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
    cerebro.addanalyzer(bt.analyzers.VWR, _name="vwr")
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="annualreturn")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.02)
    cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.PyFolio, _name='pyfolio')

    cerebro_result = cerebro.run()

    time_period_day = df.index[-1] - df.index[0]
    time_period_day = time_period_day.total_seconds() / 60 / (60 * 24)

    data_res = {}
    # data_res["time_period_day"] = time_period_day
    # data_res["p365"] = round((cerebro.broker.getvalue() - start_cash) / time_period_day * 365, 0)
    # data_res["nom_pnl_closed_trades"] = round((cerebro.broker.get_value()), 3)
    data_res["nom_pnl_closed_trades"] = cerebro_result[0].free_cash - cerebro_result[0].initial_cash
    data_res["drawdown"] = round(cerebro_result[0].analyzers.getbyname('drawdown').get_analysis().max.moneydown, 2)
    data_res["trades"] = len(cerebro_result[0].analyzers.trans.get_analysis()) // 2
    data_res["sharperatio"] = cerebro_result[0].analyzers.sharpe.get_analysis()['sharperatio']
    data_res["vwr"] = cerebro_result[0].analyzers.vwr.get_analysis()['vwr']
    data_res["annualreturn"] = cerebro_result[0].analyzers.getbyname('annualreturn').get_analysis()
    data_res["sqn"] = round(cerebro_result[0].analyzers.getbyname('sqn').get_analysis()['sqn'], 2)
    # data_res["trade_analyzer"] = cerebro_result[0].analyzers.getbyname('trade_analyzer').get_analysis()
    # data_res["returns"] = cerebro_result[0].analyzers.getbyname('returns').get_analysis()
    # returns, positions, transactions, gross_lev = cerebro_result[0].analyzers.getbyname('pyfolio').get_pf_items()
    # data_res["pyfolio_returns"] = returns
    # data_res["pyfolio_positions"] = positions
    # data_res["pyfolio_transactions"] = transactions
    # data_res["pyfolio_gross_lev"] = gross_lev

    # ----------------------------------------
    # meter
    # ----------------------------------------

    calmar_ratio = data_res["nom_pnl_closed_trades"] / data_res["drawdown"]

    # RARMD -> Risk-Adjusted Return with Maximum Drawdown
    rarmd = data_res["sharperatio"] / data_res["drawdown"]

    data_res["meter"] = rarmd

    if plot:
        cerebro.plot()

    return cerebro_result, data_res


def print_data_result(conf, res_dict):
    print(conf)
    print(res_dict)
    print('')

    with open('../HPO_results.txt', 'a') as file:
        print(conf, file=file)
        print(res_dict, file=file)


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

    possible_settings = []
    settings_name = []

    for k in settings:
        possible_settings.append(settings[k])
        settings_name.append(k)

    # all_combinations = np.array(tuple(itertools.product(*possible_settings)), dtype=np.int8)
    # all_combinations = numba_product(*possible_settings)
    # print(f"All combinations: {len(all_combinations)}")
    # time.sleep(50)
    # np.random.seed(42)
    # numba_shuffle(all_combinations)
    # print(f"Number total combination: {len(all_combinations)}")
    # splited_combinations = np.array_split(all_combinations, max_worker)
    # del all_combinations
    return possible_settings, settings_name


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


def hpo_worker(worker_no, max_worker, df, arrays, total_combinations, settings_name, shared_dict, base, quote):
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
        config.append(["live_run", False])
        config.append(["worker_no", worker_no])

        kwargs = dict(config)
        config_obj = SimpleNamespace(**kwargs)

        cerebro_res, data_res = cerebro_process(df, config_obj)

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

    # asset_type = "stock"
    # base = "MSFT"
    # quote = ""
    # from_dt = dt.datetime.now() - dt.timedelta(days=729)

    asset_type = "crypto"
    base = "ETH"
    quote = "USDT"
    # from_dt = dt.datetime(year=2017, month=8, day=17, hour=0, minute=0)
    # cutoff_dt = dt.datetime(year=2022, month=1, day=1, hour=0, minute=0)
    from_dt = dt.datetime(year=2022, month=1, day=1, hour=0, minute=0)
    cutoff_dt = None

    if run_type == "HPO":
        processors_use = 14
        arrays, settings_name = parmeter_combinations(processors_use)
        total_combinations = 1
        for a in arrays:
            total_combinations *= len(a)

        print(f"Total combinations: {total_combinations}, combinations / processor: {int(total_combinations /processors_use)}")

        # while True:
        start_time = time.time()
        if asset_type == "crypto":
            df = binance_download(base + quote,
                                  from_dt=from_dt,
                                  cutoff_dt=cutoff_dt,
                                  refresh=True,
                                  futures=False,
                                  interval='1h')  # in minute from now()

            df = df_check(df, del_duplicates=False)

            # !!!!!!!!
            # A Binance-nél volt el leállás '2023-03-24 11:00:00' ez a lállás 1 óráig tartott,
            # de a tw nél ez két adat hiányát ereményezte azért , hogy a tw vel azonos legyen egy adatoto kitörlök
            try:
                date_to_delete = '2023-03-24 12:00:00'
                date_to_delete = pd.to_datetime(date_to_delete)
                df = df.drop(date_to_delete)
            except:
                pass
            # !!!!!!!!

        elif asset_type == "stock":
            df = yahoo_download(base + quote, from_dt, back_shift=0, refresh=True, interval="1h")
            print(df)

            # MINIMUM_CANDLES = 4000
            # ticker_datas, length = download_tickers(TICKERS, END_DATE, MINIMUM_CANDLES, cache=False, interval="1h")
            # START_DATE = ticker_datas[0][1].iloc[-length].name
            # for ticker, ticker_data in tqdm(ticker_datas):
            #     df = NamedPandasData(dataname=ticker_data.iloc[-length:].copy(deep=True), timeframe=bt.TimeFrame.Days, ticker=ticker)

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
                'df': df,
                'arrays': arrays,
                'total_combinations': total_combinations,
                'settings_name': settings_name,
                'shared_dict': shared_dict,
                'base': base,
                'quote': quote,
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

        end_time = time.time()
        print(f"Execution time: {end_time - start_time} seconds")

    elif run_type == "SET":
        df = binance_download(base + quote, 60 * 6, 60 * 24 * 0, refresh=True)  # in minute from now()
        # df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0, refresh=False)  # in minute from now()
        # df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0)  # in minute from now()
        # print(df.T)
        print(df.index[0], "-", df.index[-1])
        print(df.close[0:10], "-", df.close[-10:])

        # [['rsi_period', 17], ['std_period', 4], ['std_multipler', 51], ['plot', False], ['coin_target', 'BTCFDUSD'], ['show_log', False], ['live_run', False]]
        # {'time_period_day': 0.24930555555555556, 'p365': 71933.0, 'drawdown': 7.9, 'transactions': 4, 'sharperatio': None, 'annualreturn': OrderedDict([(2024, 0.004913237485099531)]), 'sqn': 7.76, 'nom_pnl': 49.132}

        config = []
        config.append(['base', base])
        config.append(['quote', quote])
        config.append(['rsi_period', 3])
        config.append(['std_period', 21])
        config.append(['std_multipler_up', 12])
        config.append(['std_multipler_down', 13])
        config.append(["plot", False])
        config.append(["show_log", False])
        config.append(["live_run", False])

        kwargs = dict(config)
        config_obj = SimpleNamespace(**kwargs)

        cerebro_res, data_res = cerebro_process(df, config_obj, plot=True)
        print_data_result(config, data_res)
