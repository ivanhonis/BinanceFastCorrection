# Regular
import datetime
# import sys
#
# import pickle
# import time
# import os
# import random
# import itertools

# from prettytable import PrettyTable
# from tqdm.auto import tqdm
# import datetime as dt
from types import SimpleNamespace
# import asyncio
import cProfile
# binance
from binance.client import Client

# Backtrader
import backtrader as bt
from bt_binance_futures import BinanceStore
import backtrader.analyzers as btanalyzers

# Pandas and friends
# import pandas as pd
# import numpy as np


# Data transfer
# import os

# Own
# from RSI_Strategy import RSIStrategy
# from RSI_Strategy_dev import RSIStrategy
# from RSI_Strategy_dev2 import RSIStrategy
# from RSI_Strategy_dev3 import RSIStrategy, XSizer
from EMA_Shift_Multi_Strategy import EmaShiftMultiStrategy
from EMA_Shift_Multi_Strategy import ESMSizer
from bt_tools import get_public_ip, get_api_key, get_asset_balance, get_futures_positions, Logger
logger = Logger()
log = logger.log


def run_live_trade():
    api_key, secure_key = get_api_key()
    client = Client(api_key, secure_key)

    USDT_asset, BNB_asset, other_asset = get_asset_balance(client, asset="USDT", is_print=True)
    start_position, start_price, market_value = get_futures_positions(client, is_print=True)

    log("Warnings:", level=10)
    if BNB_asset < 50:
        log("Not enough BNB for commission:", BNB_asset, level=10)
    log("", level=10)

    quote = "USDT"

    cerebro = bt.Cerebro(quicknotify=True)

    store = BinanceStore(
        api_key=api_key,
        api_secret=secure_key,
        coin_target=quote,
        testnet=False,
        # tld="us",  # for US customers => to use the 'Binance.us' url
    )  # Binance Storage

    broker = store.getbroker()
    cerebro.setbroker(broker)

    cc_base = [["plot", False],
               ["show_log", False],
               ["worker_no", 0],
               ]

    cc = {}

    base = "BNB"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1],
              ['ema_fast_long', 30],
              ['ema_slow_long', 476],
              ['ema_fast_long_down_shift', 97],
              ['is_stop_loss_long', 1],
              ['stop_loss_percent_long', 30],
              ['is_short', 0],
              ['ema_fast_short', 31],
              ['ema_slow_short', 462],
              ['ema_fast_short_up_shift', 101],
              ['is_stop_loss_short', 0],
              ['stop_loss_percent_short', 64],
              ['is_trailer_short', 0],
              ['trailer_short_enter_percent', 10],
              ['trailer_short_offset', 212]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "ETH"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1],
              ['ema_fast_long', 19],
              ['ema_slow_long', 421],
              ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1],
              ['stop_loss_percent_long', 38],
              ['is_short', 0],
              ['ema_fast_short', 33],
              ['ema_slow_short', 561],
              ['ema_fast_short_up_shift', 97],
              ['is_stop_loss_short', 1],
              ['stop_loss_percent_short', 59],
              ['is_trailer_short', 0],
              ['trailer_short_enter_percent', 31],
              ['trailer_short_offset', 100]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "BTC"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1],
              ['ema_fast_long', 38],
              ['ema_slow_long', 426],
              ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1],
              ['stop_loss_percent_long', 15],
              ['is_short', 0],
              ['ema_fast_short', 35],
              ['ema_slow_short', 478],
              ['ema_fast_short_up_shift', 103],
              ['is_stop_loss_short', 0],
              ['stop_loss_percent_short', 53],
              ['is_trailer_short', 0],
              ['trailer_short_enter_percent', 40],
              ['trailer_short_offset', 311]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "AVAX"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1],
              ['ema_fast_long', 33],
              ['ema_slow_long', 476],
              ['ema_fast_long_down_shift', 93],
              ['is_stop_loss_long', 1],
              ['stop_loss_percent_long', 59],
              ['is_short', 1],
              ['ema_fast_short', 22],
              ['ema_slow_short', 574],
              ['ema_fast_short_up_shift', 98],
              ['is_stop_loss_short', 1],
              ['stop_loss_percent_short', 32],
              ['is_trailer_short', 1],
              ['trailer_short_enter_percent', 248],
              ['trailer_short_offset', 22]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    from_dt = datetime.datetime.utcnow() - datetime.timedelta(hours=700)
    comression = 60

    # from_dt = datetime.datetime.utcnow() - datetime.timedelta(minutes=700)
    # comression = 1

    df_dict = {}
    for k in cc:
        c = cc[k]
        log(f"Download: {c.base + c.quote} -  {from_dt}", level=10)

        df_dict[k] = store.getdata(dataname=c.base + c.quote, timeframe=bt.TimeFrame.Minutes, compression=comression, start_date=from_dt,  LiveBars=True)
        cerebro.adddata(df_dict[k], name=k)

    cerebro.addstrategy(EmaShiftMultiStrategy,
                        config=cc,
                        start_position=start_position,
                        start_price=start_price,
                        is_live_run=True,
                        )
    cerebro.broker.setcommission(commission=0.075)

    # cerebro.addsizer(bt.sizers.PercentSizer, percents=42)
    # cerebro.addsizer(bt.sizers.AllInSizer)
    cerebro.addsizer(ESMSizer, symbols=list(df_dict.keys()), max_percent=70, start_cash=USDT_asset + market_value, is_live_run=True)

    # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.2)
    # cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    # cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    log("Cerebro RUN", level=10)

    result = cerebro.run()
    return result


if __name__ == "__main__":
    log(f"TRADE_SERVER_FUTURES VERSION: 1.0.25", level=10)
    log("Public IP (for Binance api)", get_public_ip(), level=10)
    # cProfile.run('run_live_trade()')
    run_live_trade()
