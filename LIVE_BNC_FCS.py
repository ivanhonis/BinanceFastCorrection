# Regular
import sys
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
from backtrader_binance import BinanceStore
import backtrader.analyzers as btanalyzers

# Pandas
import pandas as pd

# matplotlib
import matplotlib.pyplot as plt

# Own
from Fast_Correction_Strategy import FastCorrectionStrategy


def get_api_key():
    # api_acces_key.json file is:
    #
    # {
    #     "api_key": "xxxxx",
    #     "secure_key": "yyyyy"
    # }

    json_file_path = 'api_acces_key.json'
    with open(json_file_path, 'r') as file:
        keys = json.load(file)

    api_key = keys['api_key']
    secure_key = keys['secure_key']

    return api_key, secure_key


def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org')
        if response.status_code == 200:
            return response.text
        else:
            return "Could not obtain IP address"
    except Exception as e:
        print(f"Error obtaining public IP address: {e}")
        return None


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


def process_combination(dropeed_time_frame=7,
                        dropped_down=5,
                        pt_pip=120,
                        sl_pip=105):

    api_key, secure_key = get_api_key()
    print(api_key)
    print(secure_key)

    coin_target = 'FDUSD'  # the base ticker in which calculations will be performed
    symbol = 'BTC' + coin_target

    cerebro = bt.Cerebro()

    store = BinanceStore(
        api_key=api_key,
        api_secret=secure_key,
        coin_target=coin_target,
        testnet=False,
        # tld="us",  # for US customers => to use the 'Binance.us' url
    )  # Binance Storage
    broker = store.getbroker()
    cerebro.setbroker(broker)

    from_date = dt.datetime.utcnow() - dt.timedelta(minutes=60)  # we take data for the last 1 hour
    data = store.getdata(timeframe=bt.TimeFrame.Minutes, compression=1, dataname=symbol, start_date=from_date, LiveBars=True)

    cerebro.adddata(data)

    # a HPO 10000 dolláros kezdőportfolióval dolgozik
    # ezért ezt a paramétert hozzá kell állítani az aktuális cash-hez
    cash = cerebro.broker.getcash()
    pt_pip = pt_pip / 10000 * cash
    sl_pip = sl_pip / 10000 * cash

    cerebro.addstrategy(FastCorrectionStrategy,
                        dropeed_time_frame=dropeed_time_frame,
                        dropped_down=dropped_down,
                        pt_pip=pt_pip,
                        sl_pip=sl_pip)

    cerebro.addsizer(bt.sizers.PercentSizer, percents=100)
    # cerebro.addsizer(bt.sizers.AllInSizer)

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.1)
    cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    result = cerebro.run()
    cerebro.plot()
    return result


if __name__ == "__main__":
    print("Public IP (for Binance api)", get_public_ip())

    # df = binance_download("BTCFDUSD", 60 * 24 * 365)  # in minute from now()
    #
    # print(df.T)

    process_combination(dropeed_time_frame=7,
                        dropped_down=5,
                        pt_pip=120,
                        sl_pip=105)
