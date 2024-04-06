import sys

import requests
import os
import random
import itertools
from tqdm.auto import tqdm
import backtrader as bt
import backtrader.analyzers as btanalyzers
import json
import pandas as pd
import datetime as dt
from collections import deque
# import keyboard
import matplotlib.pyplot as plt


def get_api_key():

    json_file_path = 'api_acces_key.json'
    with open(json_file_path, 'r') as file:
        keys = json.load(file)

    api_key = keys['api_key']
    secure_key = keys['secure_key']

    return api_key, secure_key


def get_binance_bars(symbol, interval, startTime, endTime):
    url = "https://api.binance.com/api/v3/klines"

    startTime = str(int(startTime.timestamp() * 1000))
    endTime = str(int(endTime.timestamp() * 1000))
    limit = '1000'

    req_params = {"symbol": symbol, 'interval': interval, 'startTime': startTime, 'endTime': endTime, 'limit': limit}

    df = pd.DataFrame(json.loads(requests.get(url, params=req_params).text))

    if (len(df.index) == 0):
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


class FastCorrectionStrategy(bt.Strategy):

    def __init__(self, minimum_steps, dropeed_time_frame, dropped_down, pt_pip, sl_pip):
        self.MINIMUM_STEPS = minimum_steps
        self.DROPPER_TIME_FRAM = dropeed_time_frame
        self.DROPPED_DOWN = dropped_down
        self.PT_PIP = pt_pip
        self.SL_PIP = sl_pip

        # ma_fast = bt.ind.SMA(period=1000)
        # ma_slow = bt.ind.SMA(period=5000)
        self.close_prices_history = deque(maxlen=self.DROPPER_TIME_FRAM)
        # self.portfoli_value_history = deque(maxlen=25)
        self.last_buy_portfolio_value = 0
        self.steps_count = 0
        self.last_action = ""

        # self.crossover = bt.ind.CrossOver(ma_fast, ma_slow)

    def next(self):
        self.steps_count += 1
        self.close_prices_history.append(self.data.close[0])
        # print(self.broker.getvalue(), self.last_buy_portfolio_value, self.last_action, self.position)
        # self.portfoli_value_history.append(self.broker.getvalue())
        # print(self.close_prices_history[0] - self.close_prices_history[-1],
        #       self.close_prices_history[-1] - self.close_prices_history[0],
        #       self.broker.getvalue() - self.last_buy_portfoli_value)
        # portfolio_value = self.broker.getvalue()
        # print(f'Current Portfolio Value: {portfolio_value}')
        if self.steps_count > self.MINIMUM_STEPS:
            if not self.position:
                if max(self.close_prices_history) > self.close_prices_history[-1] + self.DROPPED_DOWN:
                    # if self.crossover > 0:
                    #     print("open")
                    self.last_action = "open"
                    self.buy()
                    self.last_buy_portfolio_value = self.broker.getvalue()
                    # print('self.last_buy_portfoli_value', self.last_buy_portfoli_value)
            # elif self.crossover < 0:
            elif (self.last_buy_portfolio_value - self.SL_PIP > self.broker.getvalue() or
                  self.last_buy_portfolio_value + self.PT_PIP < self.broker.getvalue()):
                # print("close")
                self.close()
                self.last_action = "close"

    def stop(self):
        # Close all positions at the end of the strategy
        for data in self.datas:
            # Check if we have an open position for this data
            if self.getposition(data).size != 0:
                # If so, issue an order to close it
                # print(f"Closing position in {data._name}")
                self.close(data)


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


def process_combination(df, minimum_steps=100,
                        dropeed_time_frame=25,
                        dropped_down=70,
                        pt_pip=50,
                        sl_pip=50,
                        plot=False):
    cerebro = bt.Cerebro()

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)

    cerebro.addstrategy(FastCorrectionStrategy,
                        minimum_steps=minimum_steps,
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

    comb_minimum_steps = [100]
    comb_dropeed_time_frame = range(3, 30, 2)  # [3, 6, 9, 12, 15, 18, 21]
    comb_dropped_down = range(5, 300, 3)  # [110, 120, 140, 16]
    comb_pt_pip = range(5, 150, 5)  # [30, 40, 50]
    comb_sl_pip = range(5, 150, 5)  # [30, 40, 50, 60]

    # comb_minimum_steps = [100]
    # comb_dropeed_time_frame = [15]
    # comb_dropped_down = [110]
    # comb_pt_pip = [30]
    # comb_sl_pip = [40]

    possible_settings = [comb_minimum_steps, comb_dropeed_time_frame, comb_dropped_down,
                         comb_pt_pip, comb_sl_pip]
    all_combinations = list(itertools.product(*possible_settings))
    all_res = []

    selected_combinations = random.sample(all_combinations, min(500, len(all_combinations)))
    p365 = 0

    for c in selected_combinations:
        (res, act_p365,
         num_of_trades,
         drawdown,
         sharperatio) = process_combination(df, minimum_steps=c[0],
                                            dropeed_time_frame=c[1],
                                            dropped_down=c[2],
                                            pt_pip=c[3],
                                            sl_pip=c[4],
                                            plot=False)
        all_res.append(res)

        if act_p365 > p365:
            p365 = act_p365
            print("Settings:   MINIMUM_STEPS:", c[0],
                  '   DROPPER_TIME_FRAM:', c[1],
                  '   DROPPED_DOWN:', c[2],
                  '   PT_PIP:', c[3],
                  '   SL_PIP:', c[4],
                  '   P365:', act_p365,
                  '   Num Of Trades:', num_of_trades,
                  '   drawdown', drawdown,
                  '   sharperatio', sharperatio)

    # print(all_res[])

    # cerebro = bt.Cerebro()
    #
    # data = bt.feeds.PandasData(dataname=df)
    # cerebro.adddata(data)
    #
    # cerebro.addstrategy(FastCorrection,
    #                     minimum_steps=100,
    #                     dropeed_time_frame=25,
    #                     dropped_down=70,
    #                     pt_pip=50,
    #                     sl_pip=50)
    # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    # start_cash = 10000.0
    # cerebro.broker.setcash(start_cash)
    #
    # cerebro.addsizer(bt.sizers.PercentSizer, percents=50)
    # cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe")
    # cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    #
    # back = cerebro.run()
    #
    # print("Ending balance", cerebro.broker.getvalue()) # Ending balance
    # print("Sharpe", back[0].analyzers.sharpe.get_analysis()) # Sharpe
    # print("Number of Trades",len(back[0].analyzers.trans.get_analysis()))# Number of Trades
    # time_period_day = df.index[-1] - df.index[0]
    # time_period_day = time_period_day.days
    # print("365", (cerebro.broker.getvalue() - start_cash) / time_period_day * 365)
    #
    # cerebro.plot()
