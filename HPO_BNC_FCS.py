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

# matplotlib
# import matplotlib.pyplot as plt

# Own
from Fast_Correction_Strategy import FastCorrectionStrategy


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


def binance_download(symbol, length):
    file_name = "binance_data/" + symbol + "_" + str(length)

    if os.path.exists(file_name):
        # Load the data from the CSV file
        df = pd.read_hdf(file_name, "df")
        print("Loaded data from existing file.")
    else:
        pbar = tqdm(total=100)
        df_list = []
        now = dt.datetime.now()
        last_datetime = now - dt.timedelta(minutes=length)
        # last_datetime = dt.datetime(2019, 1, 1)
        while True:
            # for it in tqdm(range(15)):
            new_df = get_binance_bars(symbol, '1m', last_datetime, dt.datetime.now())
            if new_df is None:
                break
            df_list.append(new_df)
            pbar.update(1)
            last_datetime = max(new_df.index) + dt.timedelta(0, 1)

        df = pd.concat(df_list)
        df.to_hdf(file_name, key='df', mode='w')

    return df


def process_combination(df,
                        dropeed_time_frame=25,
                        dropped_down=70,
                        pt_pip=50,
                        sl_pip=50,
                        plot=False):

    coin_target = 'FDUSD'  # the base ticker in which calculations will be performed
    symbol = 'BTC' + coin_target

    cerebro = bt.Cerebro()

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    cerebro.addstrategy(FastCorrectionStrategy,
                        dropeed_time_frame=dropeed_time_frame,
                        dropped_down=dropped_down,
                        pt_pip=pt_pip,
                        sl_pip=sl_pip)

    start_cash = 10000.0
    cerebro.broker.setcash(start_cash)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=100)
    # cerebro.addsizer(bt.sizers.AllInSizer)

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.1)
    cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    result = cerebro.run()

    time_period_day = df.index[-1] - df.index[0]
    time_period_day = time_period_day.days
    p365 = round((cerebro.broker.getvalue() - start_cash) / time_period_day * 365, 0)
    # print("Ending balance:", round(cerebro.broker.getvalue(),0),
    #       # "Sharpe", result[0].analyzers.sharpe.get_analysis(),
    #       "   Number of Trades:", len(result[0].analyzers.trans.get_analysis()),
    #       "      365:", p365)
    drawdown = result[0].analyzers.getbyname('drawdown').get_analysis().max.drawdown
    transactions = len(result[0].analyzers.trans.get_analysis())
    sharperatio = result[0].analyzers.sharpe.get_analysis()

    if plot:
        cerebro.plot()

    return result, p365, transactions, drawdown, sharperatio


if __name__ == "__main__":

    df = binance_download("BTCFDUSD", 60 * 24 * 365)  # in minute from now()

    print(df.T)

    comb_dropeed_time_frame = range(3, 30, 2)  # [3, 6, 9, 12, 15, 18, 21]
    comb_dropped_down = range(5, 300, 3)  # [110, 120, 140, 16]
    comb_pt_pip = range(5, 150, 5)  # [30, 40, 50]
    comb_sl_pip = range(5, 150, 5)  # [30, 40, 50, 60]

    # comb_minimum_steps = [100]
    # comb_dropeed_time_frame = [15]
    # comb_dropped_down = [110]
    # comb_pt_pip = [30]
    # comb_sl_pip = [40]

    possible_settings = [comb_dropeed_time_frame, comb_dropped_down,
                         comb_pt_pip, comb_sl_pip]
    all_combinations = list(itertools.product(*possible_settings))
    all_res = []

    selected_combinations = random.sample(all_combinations, min(500, len(all_combinations)))
    p365 = 0

    for c in selected_combinations:
        (res, act_p365,
         num_of_trades,
         drawdown,
         sharperatio) = process_combination(df,
                                            dropeed_time_frame=c[0],
                                            dropped_down=c[1],
                                            pt_pip=c[2],
                                            sl_pip=c[3],
                                            plot=False)
        all_res.append(res)

        if act_p365 > p365:
            # csak az előzőnél jobbat írja ki
            p365 = act_p365

            with open('HPO_results.txt', 'a') as file:
                print("Settings:",
                      '   DROPPER_TIME_FRAM:', c[0],
                      '   DROPPED_DOWN:', c[1],
                      '   PT_PIP:', c[2],
                      '   SL_PIP:', c[3],
                      '   P365:', act_p365,
                      '   Num Of Trades:', num_of_trades,
                      '   drawdown', drawdown,
                      '   sharperatio', sharperatio,
                      file=file)

            print("Settings:",
                  '   DROPPER_TIME_FRAM:', c[0],
                  '   DROPPED_DOWN:', c[1],
                  '   PT_PIP:', c[2],
                  '   SL_PIP:', c[3],
                  '   P365:', act_p365,
                  '   Num Of Trades:', num_of_trades,
                  '   drawdown', drawdown,
                  '   sharperatio', sharperatio)

