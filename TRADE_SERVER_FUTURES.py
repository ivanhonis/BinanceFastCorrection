# Regular
import datetime
import sys
import requests
import pickle
import time
import os
import random
import itertools
import json
from prettytable import PrettyTable
# from tqdm.auto import tqdm
import datetime as dt
from types import SimpleNamespace
import asyncio
import cProfile
# binance
from binance.client import Client

# Backtrader
import backtrader as bt
from bt_binance_futures import BinanceStore
import backtrader.analyzers as btanalyzers
# from bt_tools import yahoo_download, df_check, binance_download

# Pandas and friends
import pandas as pd
import numpy as np


# Data transfer
import os

# Own
# from RSI_Strategy import RSIStrategy
# from RSI_Strategy_dev import RSIStrategy
# from RSI_Strategy_dev2 import RSIStrategy
# from RSI_Strategy_dev3 import RSIStrategy, XSizer
from EMA_Shift_Multi_Strategy import EmaShiftMultiStrategy
from EMA_Shift_Multi_Strategy import ESMSizer
from bt_tools import Logger

logger = Logger()
log = logger.log

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


def print_object(obj):
    all_properties = dir(obj)

    for prop in all_properties:
        if callable(getattr(obj, prop)):
            print(f"Method: {prop}")
        else:
            print(f"Attribute: {prop}")


def get_public_ip():
    try:
        response = requests.get('https://api.ipify.org')
        if response.status_code == 200:
            return response.text
        else:
            return "Could not obtain IP address"
    except Exception as e:
        log(f"Error obtaining public IP address: {e}", level=10)
        return None


def get_futures_ticker(client, base, quote="USDT"):
    return float(client.futures_symbol_ticker(symbol=base+quote)['price'])


def get_futures_positions(client, is_print=False):
    ret_position = {}
    ret_price = {}

    account_info = client.futures_account()
    positions = account_info['positions']
    open_positions = [position for position in positions if float(position['positionAmt']) != 0.0]

    table = PrettyTable()
    table.title = "Open Perpetual Futures Positions"
    table.field_names = ["Symbol", "Position", "Entry Price", "USDT_Enter_Value", "USDT_Market_Value", "Unrealized PnL (USDT)"]
    table.align["Symbol"] = "c"
    table.align["Position"] = "r"
    table.align["Entry Price"] = "r"
    table.align["USDT_Enter_Value"] = "r"
    table.align["USDT_Market_Value"] = "r"
    table.align["Unrealized PnL (USDT)"] = "r"
    # {'symbol': 'ETHUSDT',
    # 'initialMargin': '22.97904000',
    # 'maintMargin': '0.09191616',
    # 'unrealizedProfit': '-0.12708000',
    # 'positionInitialMargin': '22.97904000',
    #  'openOrderInitialMargin': '0',
    #  'leverage': '1',
    #  'isolated': False,
    #  'entryPrice': '3851.02',
    #  'breakEvenPrice': '3852.752959',
    #  'maxNotional': '1.2E9',
    #  'positionSide': 'BOTH',
    #  'positionAmt': '0.006',
    #  'notional': '22.97904000',
    #  'isolatedWallet': '0',
    #  'updateTime': 1717691333502,
    #  'bidNotional': '0',
    #  'askNotional': '0'},

    total_unrealized_pnl = 0.0
    market_value = 0
    for position in open_positions:
        symbol = position['symbol']
        position_amt = float(position['positionAmt'])
        entry_price = float(position['entryPrice'])
        unrealized_pnl = round(float(position['unrealizedProfit']), 4)
        total_unrealized_pnl += unrealized_pnl
        USDT_Enter_Value = round((float(position['entryPrice']) * position_amt), 4)
        USDT_Value = round((float(position['entryPrice']) * position_amt) + unrealized_pnl, 4)

        market_value += abs(USDT_Value)
        market_value = round(market_value, 4)

        ret_position[symbol] = position_amt
        ret_price[symbol] = entry_price

        table.add_row([symbol,
                       position_amt,
                       entry_price,
                       USDT_Enter_Value,
                       USDT_Value,
                       unrealized_pnl,
                       ])

    table.add_row([
        "TOTAL:",
        "",
        "",
        "",
        market_value,
        round(total_unrealized_pnl, 4),
        ])

    if is_print:
        log("\n",table, level=10)
    return ret_position, ret_price, market_value


def get_asset_balance(client, asset, is_print=False):
    data = client.futures_account_balance()

    # [{'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'FDUSD', 'balance': '0.00000000', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000',
    #   'availableBalance': '0.00000000', 'maxWithdrawAmount': '0.00000000', 'marginAvailable': True, 'updateTime': 0},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'BTC', 'balance': '0.00000000', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000', 'availableBalance': '0.00000000',
    #   'maxWithdrawAmount': '0.00000000', 'marginAvailable': True, 'updateTime': 0},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'XRP', 'balance': '0.00000000', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000', 'availableBalance': '0.00000000',
    #   'maxWithdrawAmount': '0.00000000', 'marginAvailable': True, 'updateTime': 0},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'TUSD', 'balance': '0.00000000', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000',
    #   'availableBalance': '0.00000000', 'maxWithdrawAmount': '0.00000000', 'marginAvailable': True, 'updateTime': 0},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'BNB', 'balance': '0.02737372', 'crossWalletBalance': '0.02737372', 'crossUnPnl': '0.00000000', 'availableBalance': '0.02737372',
    #   'maxWithdrawAmount': '0.02737372', 'marginAvailable': True, 'updateTime': 1717691356266},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'ETH', 'balance': '0.00000000', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000', 'availableBalance': '0.00000000',
    #   'maxWithdrawAmount': '0.00000000', 'marginAvailable': True, 'updateTime': 0},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'USDT', 'balance': '201.28918176', 'crossWalletBalance': '201.28918176', 'crossUnPnl': '-0.01494000',
    #   'availableBalance': '157.16860176', 'maxWithdrawAmount': '157.16860176', 'marginAvailable': True, 'updateTime': 1717610762294},
    #  {'accountAlias': 'SgSgXqmYoCoCuXfW', 'asset': 'USDC', 'balance': '0.00000000', 'crossWalletBalance': '0.00000000', 'crossUnPnl': '0.00000000',
    #   'availableBalance': '0.00000000', 'maxWithdrawAmount': '0.00000000', 'marginAvailable': True, 'updateTime': 0}]

    table = PrettyTable()
    table.title = "Futures Account Balance"
    table.field_names = ["asset", "balance", "crossWalletBalance", "availableBalance", "crossUnPnl", "USDT_Value"]
    table.align["asset"] = "c"
    table.align["balance"] = "r"
    table.align["crossWalletBalance"] = "r"
    table.align["availableBalance"] = "r"
    table.align["crossUnPnl"] = "r"
    table.align["USDT_Value"] = "r"

    ret_asset = 0.0
    ret_BNB = 0.0
    ret_other = {}
    for item in data:
        if float(item['crossWalletBalance']) != 0 or float(item['balance']) != 0:
            if item['asset'] == "USDT":
                USDT_Value = item['availableBalance']
            else:
                USDT_Value = get_futures_ticker(client, item['asset']) * float(item['availableBalance'])

            table.add_row([item['asset'],
                           item['balance'],
                           item['crossWalletBalance'],
                           item['availableBalance'],
                           item['crossUnPnl'],
                           USDT_Value
                           ])
            if item['asset'] == asset:
                ret_asset = float(item['availableBalance'])
            if item['asset'] == "BNB":
                ret_BNB = float(item['availableBalance'])
            else:
                ret_other[item['asset']] = float(item['availableBalance'])

    if is_print:
        log("\n", table, level=10)
    return ret_asset, ret_BNB, ret_other


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
    log("Public IP (for Binance api)", get_public_ip())
    cProfile.run('run_live_trade()')
    # run_live_trade()
