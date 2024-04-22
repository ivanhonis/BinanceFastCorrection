# Regular
# import sys
import requests
import os
import random
import itertools
import json
from tqdm.auto import tqdm
import datetime as dt
# import keyboard

# Backtrader
import backtrader as bt
import backtrader.analyzers as btanalyzers

# Pandas
import pandas as pd
import numpy as np

# process
from multiprocessing import Process

# matplotlib
# import matplotlib.pyplot as plt

# Own
# from RSI_Strategy import RSIStrategy
# from RSI_Strategy_dev import RSIStrategy
# from RSI_Strategy_dev2 import RSIStrategy
from RSI_Strategy_dev3 import RSIStrategy

pd.set_option('display.precision', 8)


def get_binance_bars(symbol, interval, start_time, end_time):
    url = "https://api.binance.com/api/v3/klines"

    start_time = str(int(start_time.timestamp() * 1000))
    end_time = str(int(end_time.timestamp() * 1000))
    limit = '1000'

    req_params = {"symbol": symbol, 'interval': interval, 'startTime': start_time, 'endTime': end_time, 'limit': limit}

    df = pd.DataFrame(json.loads(requests.get(url, params=req_params).text))

    if len(df.index) == 0:
        return None

    df = df.iloc[:, 0:6]
    df.columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']

    df.open = df.open.astype("float")
    df.high = df.high.astype("float")
    df.low = df.low.astype("float")
    df.close = df.close.astype("float")
    df.volume = df.volume.astype("float")

    df['adj_close'] = df['close']

    df.index = [dt.datetime.fromtimestamp(x / 1000.0) for x in df.datetime]

    return df


def binance_download(symbol, length, back_shift, refresh=False):
    file_name = "binance_data/" + symbol + "_" + str(length)

    if refresh and os.path.exists(file_name):
        os.remove(file_name)

    if os.path.exists(file_name):
        # Load the data from the CSV file
        df = pd.read_hdf(file_name, "df")
        print("Loaded data from existing file.")
    else:
        pbar = tqdm(total=100)
        df_list = []
        now = dt.datetime.now() - dt.timedelta(minutes=back_shift)
        last_datetime = now - dt.timedelta(minutes=length)
        # last_datetime = dt.datetime(2019, 1, 1)
        while True:
            # for it in tqdm(range(15)):
            new_df = get_binance_bars(symbol, '1m', last_datetime, now)
            if new_df is None:
                break
            df_list.append(new_df)
            pbar.update(1)
            last_datetime = max(new_df.index) + dt.timedelta(0, 1)

        df = pd.concat(df_list)
        df.to_hdf(file_name, key='df', mode='w')

    return df


def process_combination(df,
                        rsi_period,
                        std_period,
                        dev_min,
                        dev_max,
                        c,
                        plot=False):
    coin_target = 'FDUSD'  # the base ticker in which calculations will be performed
    symbol = 'BTC' + coin_target

    cerebro = bt.Cerebro()

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    cerebro.addstrategy(RSIStrategy,
                        rsi_period=rsi_period,
                        std_period=std_period,
                        dev_min=dev_min,
                        dev_max=dev_max,
                        c=c, )

    start_cash = 10000.0
    cerebro.broker.setcash(start_cash)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=100)
    # cerebro.addsizer(bt.sizers.AllInSizer)

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    cerebro.addanalyzer(bt.analyzers.SQN, _name="sqn")
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="annualreturn")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.1)
    cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    result = cerebro.run()

    time_period_day = df.index[-1] - df.index[0]
    time_period_day = time_period_day.days
    p365 = round((cerebro.broker.getvalue() - start_cash) / time_period_day * 365, 0)
    drawdown = round(result[0].analyzers.getbyname('drawdown').get_analysis().max.moneydown, 2)
    transactions = len(result[0].analyzers.trans.get_analysis())
    sharperatio = result[0].analyzers.sharpe.get_analysis()['sharperatio']
    annualreturn = result[0].analyzers.getbyname('annualreturn').get_analysis()
    sqn = round(result[0].analyzers.getbyname('sqn').get_analysis()['sqn'], 2)
    nom_pnl = round((cerebro.broker.getvalue() - start_cash), 3)

    if plot:
        cerebro.plot()

    return result, p365, transactions, drawdown, sharperatio, annualreturn, sqn ,nom_pnl


def hpo_worker(worker_no, max_worker, df):
    print(f"run worker {max_worker} / {worker_no + 1}")
    # df = binance_download("BTCFDUSD", 60 * 24 * 362)  # in minute from now()

    # print(df.T)

    rsi_period = np.arange(12, 35, 1)
    std_period = np.arange(3, 35, 1)
    dev_min = np.arange(3, 4, 1)
    dev_max = np.arange(3, 4, 1)
    c = np.arange(1, 2, 1)

    possible_settings = [rsi_period, std_period, dev_min, dev_max, c]
    all_combinations = np.array(tuple(itertools.product(*possible_settings)), dtype=int)
    all_res = []

    selected_combinations = np.array_split(all_combinations, max_worker)[worker_no]
    np.random.shuffle(selected_combinations)

    p365 = -10000

    for c in selected_combinations:
        (res, act_p365,
         num_of_trades,
         drawdown,
         sharperatio,
         annualreturn,
         sqn, nom_pnl) = process_combination(df,
                                             rsi_period=int(c[0]),
                                             std_period=int(c[1]),
                                             dev_min=int(c[2]),
                                             dev_max=int(c[3]),
                                             c=int(c[4]),
                                             plot=False)

        all_res.append(res)

        if act_p365 > p365:
            # csak az előzőnél jobbat írja ki
            p365 = act_p365

            with open('HPO_results.txt', 'a') as file:
                print("Settings:",
                      '   rsi_period', c[0],
                      '   std_period', c[1],
                      '   dev_min', c[2],
                      '   dev_max', c[3],
                      '   c', c[4],
                      '   P365', act_p365,
                      '   Trades', num_of_trades,
                      '   Drawdown', drawdown,
                      '   Sharpe', sharperatio,
                      '   ann.ret.', annualreturn,
                      '   sqn', sqn,
                      '   nom_pnl', nom_pnl,
                      file=file)

            print(' rsi_period', c[0],
                  ' std_period', c[1],
                  ' dev_min', c[2],
                  ' dev_max', c[3],
                  ' c', c[4],
                  ' P365', act_p365,
                  ' Trades', num_of_trades,
                  ' Drawdown', drawdown,
                  ' Sharpe', sharperatio,
                  ' ann.ret.', annualreturn,
                  ' sqn', sqn)


if __name__ == "__main__":

    # run_type = 'HPO'
    run_type = 'SET'
    # run_type = 'GAP_TEST'

    if run_type == "HPO":
        df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 90, refresh=True)  # in minute from now()
        # df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0, refresh=False)  # in minute from now()
        # df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0)  # in minute from now()
        # print(df.T)
        print(df[["datetime", "close"]].index[1], "-", df[["datetime", "close"]].index[-1])

        processors_use = 14
        # processors_use = 6
        processes = [None] * processors_use

        for p in range(processors_use):
            processes[p] = Process(target=hpo_worker, kwargs={
                'worker_no': p,
                'max_worker': processors_use,
                'df': df,
            })
            processes[p].start()

        for p in range(processors_use):
            processes[p].join()

    elif run_type == "SET":
        df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0, refresh=True)  # in minute from now()
        # df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0, refresh=False)  # in minute from now()
        # df = binance_download("BTCFDUSD", 60 * 24 * 60, 60 * 24 * 0)  # in minute from now()
        # print(df.T)
        print(df[["datetime", "close"]].index[1], "-", df[["datetime", "close"]].index[-1])
        # rsi_period 15  std_period 23  dev_min 7  dev_max 27  c 1
        # rsi_period 28  std_period 5  dev_min 59  dev_max 3  c 1
        (res, act_p365, num_of_trades, drawdown,
         sharperatio, annualreturn, sqn, nom_pnl) = process_combination(df, rsi_period=28,
                                                                        std_period=5,
                                                                        dev_min=59,
                                                                        dev_max=3,
                                                                        c=1,
                                                                        plot=True)
        print("Settings:",
              '   P365:', act_p365,
              '   Num Of Trades:', num_of_trades,
              '   drawdown', drawdown,
              '   sharperatio', sharperatio,
              '   annual return', annualreturn,
              '   sqn', sqn)

    elif run_type == "GAP_TEST":
        print("GAP TEST")

        sum_pnl = 0
        rnd_time_period = random.randint(8,16)
        for i in range(5):
            df = binance_download("BTCFDUSD", 60 * 24 * rnd_time_period, 60 * 24 * (i * rnd_time_period * 2), refresh=True)

            print(df[["datetime", "close"]].index[1], "-", df[["datetime", "close"]].index[-1])

            # rsi_period 15  std_period 23  dev_min 7  dev_max 27  c 1
            # rsi_period 28  std_period 5  dev_min 59  dev_max 3  c 1
            # rsi_period 17  std_period 10  dev_min 3  dev_max 3  c 1
            # rsi_period 20  std_period 33  dev_min 3  dev_max 3  c 1

            (res, act_p365, num_of_trades, drawdown,
             sharperatio, annualreturn, sqn, nom_pln) = process_combination(df, rsi_period=15,
                                                                            std_period=29,
                                                                            dev_min=3,
                                                                            dev_max=3,
                                                                            c=1,
                                                                            plot=False)
            sum_pnl += nom_pln
            print("")
            print(i + 1,
                  '   nom_pnl:', nom_pln,
                  '   sum_pnl:', sum_pnl,
                  '   Num Of Trades:', num_of_trades,
                  '   drawdown', drawdown,
                  '   sharperatio', sharperatio,
                  '   annual return', annualreturn,
                  '   sqn', sqn)
