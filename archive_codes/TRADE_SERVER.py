# Regular
import requests
import json
from tqdm.auto import tqdm
import datetime as dt
from types import SimpleNamespace

# binance
from binance.client import Client

# Backtrader
import backtrader as bt
from backtrader_binance import BinanceStore
import backtrader.analyzers as btanalyzers

# Pandas and friends
import pandas as pd

# Data transfer
import os

# Own
# from RSI_Strategy import RSIStrategy
# from RSI_Strategy_dev import RSIStrategy
# from RSI_Strategy_dev2 import RSIStrategy
from archive_codes.RSI_Strategy_dev3 import RSIStrategy


def get_api_key():
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


def run_live_trade():

    api_key, secure_key = get_api_key()
    base = "ETH"
    quote = "BTC"

    cerebro = bt.Cerebro()

    store = BinanceStore(
        api_key=api_key,
        api_secret=secure_key,
        coin_target=quote,
        testnet=False,
        # tld="us",  # for US customers => to use the 'Binance.us' url
    )  # Binance Storage

    client = Client(api_key, secure_key)
    quote_balance = client.get_asset_balance(asset=quote)['free']
    print(f"Balance: {quote} {quote_balance}")

    broker = store.getbroker()

    print(f"Cerebro cash: {broker.getcash()}")
    cerebro.setbroker(broker)

    from_date = dt.datetime.utcnow() - dt.timedelta(minutes=60 * 2)  # we take data for the last 1 hour
    data = store.getdata(timeframe=bt.TimeFrame.Minutes, compression=1, dataname=base+quote, start_date=from_date, LiveBars=True)

    cerebro.adddata(data)

    # [['rsi_period', 23], ['std_period', 19], ['stop_percent', 5], ['take_percent', 5], ['std_multipler_up', 41], ['std_multipler_down', 11],
    # ['rsi_period', 20], ['std_period', 28], ['stop_percent', 11], ['take_percent', 31], ['std_multipler_up', 35], ['std_multipler_down', 26]
    # [['rsi_period', 12], ['std_period', 3], ['stop_percent', 5], ['take_percent', 5], ['std_multipler_up', 23], ['std_multipler_down', 89]
# [['rsi_period', 24], ['stop_percent', 5], ['take_percent', 7], ['std_multipler_up', 11], ['std_multipler_down', 14]
#     ['rsi_period', 16], ['stop_percent', 17], ['take_percent', 35], ['std_multipler_up', 15], ['std_multipler_down', 16]


    config = []
    config.append(['base', base])
    config.append(['quote', quote])
    config.append(['rsi_period', 14])
    # config.append(['std_period', 3])
    config.append(['stop_percent', 17])
    config.append(['take_percent', 30])
    config.append(['std_multipler_up', 30])
    config.append(['std_multipler_down', 45])
    config.append(["plot", False])
    config.append(["show_log", True])
    config.append(["live_run", True])

    kwargs = dict(config)
    config_obj = SimpleNamespace(**kwargs)

    cerebro.addstrategy(RSIStrategy, config=config_obj, is_load_config=False)
    cerebro.broker.setcommission(commission=0.075)

    cerebro.addsizer(bt.sizers.PercentSizer, percents=80)
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

    run_live_trade()

