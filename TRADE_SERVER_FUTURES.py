# Regular
import datetime
import sys
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
from EMA_Shift_Multi_Strategy import ESMSizer, OnePositionSizer
from bt_tools import get_public_ip, get_api_key, get_asset_balance, get_futures_positions, Logger
logger = Logger()
log = logger.log


def run_live_trade():
    api_key, secure_key = get_api_key()
    client = Client(api_key, secure_key)

    USDT_asset, BNB_asset, other_asset = get_asset_balance(client, asset="USDC", is_print=True)
    start_position, start_price, market_value = get_futures_positions(client, is_print=True)

    log("Warnings:", level=10)
    if BNB_asset < 50:
        log("Not enough BNB for commission:", BNB_asset, level=10)
    log("", level=10)

    quote = "USDC"

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

    base = "AVAX"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1], ['ema_fast_long', 53], ['ema_slow_long', 265], ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1], ['stop_loss_percent_long', 64],
              ['is_trailer_long', 1], ['trailer_long_enter_percent', 49], ['trailer_long_offset', 47], ['is_short', 1],
              ['ema_fast_short', 39], ['ema_slow_short', 397],
              ['ema_fast_short_up_shift', 101], ['is_stop_loss_short', 1], ['stop_loss_percent_short', 48],
              ['is_trailer_short', 1], ['trailer_short_enter_percent', 38],
              ['trailer_short_offset', 85], ['max_trade_steps', 47]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "BNB"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1], ['ema_fast_long', 21], ['ema_slow_long', 227], ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1], ['stop_loss_percent_long', 57],
              ['is_trailer_long', 1], ['trailer_long_enter_percent', 78], ['trailer_long_offset', 26], ['is_short', 1],
              ['ema_fast_short', 13], ['ema_slow_short', 412],
              ['ema_fast_short_up_shift', 105], ['is_stop_loss_short', 1], ['stop_loss_percent_short', 122],
              ['is_trailer_short', 1], ['trailer_short_enter_percent', 41],
              ['trailer_short_offset', 85], ['max_trade_steps', 41]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "ETH"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1], ['ema_fast_long', 27], ['ema_slow_long', 370], ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1], ['stop_loss_percent_long', 147],
              ['is_trailer_long', 1], ['trailer_long_enter_percent', 85], ['trailer_long_offset', 94], ['is_short', 1],
              ['ema_fast_short', 40], ['ema_slow_short', 282],
              ['ema_fast_short_up_shift', 102], ['is_stop_loss_short', 1], ['stop_loss_percent_short', 19],
              ['is_trailer_short', 1], ['trailer_short_enter_percent', 12],
              ['trailer_short_offset', 89], ['max_trade_steps', 32]
              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "DOGE"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1], ['ema_fast_long', 50], ['ema_slow_long', 171], ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1], ['stop_loss_percent_long', 58], ['is_trailer_long', 1],
              ['trailer_long_enter_percent', 99], ['trailer_long_offset', 21], ['is_short', 1], ['ema_fast_short', 35],
              ['ema_slow_short', 321], ['ema_fast_short_up_shift', 103], ['is_stop_loss_short', 1],
              ['stop_loss_percent_short', 63], ['is_trailer_short', 1], ['trailer_short_enter_percent', 24],
              ['trailer_short_offset', 72], ['max_trade_steps', 38]

              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    base = "ADA"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],
              ['is_long', 1], ['ema_fast_long', 65], ['ema_slow_long', 346], ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1], ['stop_loss_percent_long', 168], ['is_trailer_long', 1],
              ['trailer_long_enter_percent', 96], ['trailer_long_offset', 87], ['is_short', 1], ['ema_fast_short', 35],
              ['ema_slow_short', 331], ['ema_fast_short_up_shift', 101], ['is_stop_loss_short', 1],
              ['stop_loss_percent_short', 138], ['is_trailer_short', 1], ['trailer_short_enter_percent', 72],
              ['trailer_short_offset', 15], ['max_trade_steps', 59]

              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)
    #
    base = "XRP"
    quote = "USDT"
    config = [['base', base],
              ['quote', quote],

              ['is_long', 1], ['ema_fast_long', 20], ['ema_slow_long', 441], ['ema_fast_long_down_shift', 99],
              ['is_stop_loss_long', 1], ['stop_loss_percent_long', 23], ['is_trailer_long', 1],
              ['trailer_long_enter_percent', 33], ['trailer_long_offset', 60], ['is_short', 1], ['ema_fast_short', 105],
              ['ema_slow_short', 366], ['ema_fast_short_up_shift', 108], ['is_stop_loss_short', 1],
              ['stop_loss_percent_short', 78], ['is_trailer_short', 1], ['trailer_short_enter_percent', 78],
              ['trailer_short_offset', 24], ['max_trade_steps', 26]

              ]

    config.extend(cc_base)
    kwargs = dict(config)
    cc[base + quote] = SimpleNamespace(**kwargs)

    # base = "SOL"
    # quote = "USDT"
    # config = [['base', base],
    #           ['quote', quote],
    #
    #           ['is_long', 1], ['ema_fast_long', 27], ['ema_slow_long', 433], ['ema_fast_long_down_shift', 99],
    #           ['is_stop_loss_long', 1], ['stop_loss_percent_long', 82], ['is_trailer_long', 1],
    #           ['trailer_long_enter_percent', 101], ['trailer_long_offset', 10], ['is_short', 1],
    #           ['ema_fast_short', 11], ['ema_slow_short', 159], ['ema_fast_short_up_shift', 103],
    #           ['is_stop_loss_short', 1], ['stop_loss_percent_short', 162], ['is_trailer_short', 1],
    #           ['trailer_short_enter_percent', 60], ['trailer_short_offset', 17], ['max_trade_steps', 35]
    #
    #           ]
    #
    # config.extend(cc_base)
    # kwargs = dict(config)
    # cc[base + quote] = SimpleNamespace(**kwargs)

    # from_dt = datetime.datetime.utcnow() - datetime.timedelta(hours=700)
    # comression = 60

    from_dt = datetime.datetime.utcnow() - datetime.timedelta(minutes=700)
    comression = 1

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
    cerebro.broker.setcommission(commission=0.00045)

    cerebro.addsizer(OnePositionSizer, symbols=list(df_dict.keys()), percent=80, start_cash=60, is_live_run=True)

    # cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    # cerebro.addanalyzer(btanalyzers.SharpeRatio, _name="sharpe", riskfreerate=0.2)
    # cerebro.addanalyzer(btanalyzers.Transactions, _name="trans")
    # cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    log("Cerebro RUN", level=10)

    result = cerebro.run()
    return result


if __name__ == "__main__":
    log(f"TRADE_SERVER_FUTURES VERSION: FAST WIN 2.0.28", level=10)
    log("Public IP (for Binance api)", get_public_ip(), level=10)
    # cProfile.run('run_live_trade()')
    run_live_trade()
