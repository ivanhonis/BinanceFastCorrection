import time

from functools import wraps
from math import floor

from backtrader.dataseries import TimeFrame
from binance import Client, ThreadedWebsocketManager
from binance.enums import *
from binance.exceptions import BinanceAPIException
from requests.exceptions import ConnectTimeout, ConnectionError

from .binance_broker import BinanceBroker
from .binance_feed import BinanceData


class BinanceStore(object):
    _GRANULARITIES = {
        (TimeFrame.Minutes, 1): KLINE_INTERVAL_1MINUTE,
        (TimeFrame.Minutes, 3): KLINE_INTERVAL_3MINUTE,
        (TimeFrame.Minutes, 5): KLINE_INTERVAL_5MINUTE,
        (TimeFrame.Minutes, 15): KLINE_INTERVAL_15MINUTE,
        (TimeFrame.Minutes, 30): KLINE_INTERVAL_30MINUTE,
        (TimeFrame.Minutes, 60): KLINE_INTERVAL_1HOUR,
        (TimeFrame.Minutes, 120): KLINE_INTERVAL_2HOUR,
        (TimeFrame.Minutes, 240): KLINE_INTERVAL_4HOUR,
        (TimeFrame.Minutes, 360): KLINE_INTERVAL_6HOUR,
        (TimeFrame.Minutes, 480): KLINE_INTERVAL_8HOUR,
        (TimeFrame.Minutes, 720): KLINE_INTERVAL_12HOUR,
        (TimeFrame.Days, 1): KLINE_INTERVAL_1DAY,
        (TimeFrame.Days, 3): KLINE_INTERVAL_3DAY,
        (TimeFrame.Weeks, 1): KLINE_INTERVAL_1WEEK,
        (TimeFrame.Months, 1): KLINE_INTERVAL_1MONTH,
    }

    def __init__(self, api_key, api_secret, coin_target, testnet=False, retries=5, tld='com'):  # coin_refer, coin_target
        self.binance = Client(api_key, api_secret, testnet=testnet, tld=tld, requests_params={'timeout': (10, 20)})
        self.binance_socket = ThreadedWebsocketManager(api_key, api_secret, testnet=testnet)
        self.binance_socket.daemon = True
        self.binance_socket.start()
        # self.coin_refer = coin_refer
        self.coin_target = coin_target  # USDT
        # self.symbol = coin_refer + coin_target
        self.symbols = []  # symbols
        self.retries = retries

        self._cash = 0
        self._value = 0
        self._unpnl = 0
        self.get_balance()

        self._step_size = {}
        self._min_order = {}
        self._min_order_in_target = {}
        self._tick_size = {}

        self._broker = BinanceBroker(store=self)
        self._data = None
        self._datas = {}

        self.log_level = 10

    def _format_value(self, value, step):
        precision = step.find('1') - 1
        if precision > 0:
            return '{:0.0{}f}'.format(float(value), precision)
        return floor(int(value))
        
    def retry(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(1, self.retries + 1):
                time.sleep(60 / 1200) # API Rate Limit
                try:
                    return func(self, *args, **kwargs)
                except (BinanceAPIException, ConnectTimeout, ConnectionError) as err:
                    if isinstance(err, BinanceAPIException) and err.code == -1021:
                        # Recalculate timestamp offset between local and Binance's server
                        res = self.binance.get_server_time()
                        self.binance.timestamp_offset = res['serverTime'] - int(time.time() * 1000)
                    
                    if attempt == self.retries:
                        raise
        return wrapper

    @retry
    def cancel_open_orders(self, symbol):
        #todo megcsinálni
        orders = self.binance.get_open_orders(symbol=symbol)
        if len(orders) > 0:
            self.binance._request_api('delete', 'openOrders', signed=True, data={ 'symbol': symbol })

    @retry
    def cancel_order(self, symbol, order_id):
        #todo megcsinálni
        try:
            self.binance.cancel_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as api_err:
            if api_err.code == -2011:  # Order filled
                return
            else:
                raise api_err
        except Exception as err:
            raise err
    
    @retry
    def create_order(self, symbol, side, type, size, price):
        params = dict()
        if type in [ORDER_TYPE_LIMIT, ORDER_TYPE_STOP_LOSS_LIMIT]:
            params.update({
                'timeInForce': TIME_IN_FORCE_GTC
            })
        if type != ORDER_TYPE_MARKET:
            params.update({
                'price': self.format_price(symbol, price)
            })

        return (self.binance.create_order(
            symbol=symbol,
            side=side,
            type=type,
            quantity=self.format_quantity(symbol, size),
            **params))

    @retry
    def futures_create_order(self, symbol, side, type, size, price):
        print("futures_create_order", symbol, side, type, size, price)
        params = dict()
        if type in [ORDER_TYPE_LIMIT, ORDER_TYPE_STOP_LOSS_LIMIT]:
            params.update({
                'timeInForce': TIME_IN_FORCE_GTC
            })
        if type != ORDER_TYPE_MARKET:
            params.update({
                'price': self.format_price(symbol, price)
            })

        qqty = self.format_quantity(symbol, size)
        self.log(f"symbol={symbol}, side={side}, type={type}, quantity={qqty} {params}", level=1)
        self.log("", level=1)
        return self.binance.futures_create_order(
            symbol=symbol,
            side=side,
            type=type,
            quantity=qqty,
            **params)

    def format_price(self, symbol, price):
        return self._format_value(price, self._tick_size[symbol])
    
    def format_quantity(self, symbol, size):
        return self._format_value(size, self._step_size[symbol])

    @retry
    def get_asset_balance(self, asset):

        # balance = self.binance.get_asset_balance(asset)
        # print(balance)
        data = self.binance.futures_account_balance()

        # {'accountAlias': 'SgSgXqmYoCoCuXfW',
        #  'asset': 'USDT',
        #  'balance': '58.58942710',
        #  'crossWalletBalance': '58.58942710',
        #  'crossUnPnl': '-0.00084000',
        #  'availableBalance': '35.74490710',
        #  'maxWithdrawAmount': '35.74490710',
        #  'marginAvailable': True,
        #  'updateTime': 1717249921548}

        for item in data:
            if item['asset'] == asset:
                return (float(item['availableBalance']),
                        float(item['balance']) - float(item['availableBalance']),
                        float(item['crossUnPnl']))

        return 0.0, 0.0

    # def get_symbol_balance(self, symbol):
    #     """Get symbol balance in symbol"""
    #     balance = 0
    #     try:
    #         symbol = symbol[0:len(symbol)-len(self.coin_target)]
    #         data = self.binance.futures_account_balance()
    #
    #         for item in data:
    #             if item['asset'] == symbol:
    #                 # print("get_symbol_balance", item)
    #
    #                 balance = float(item['balance']), float(item['availableBalance'])
    #
    #         #
    #         # balance = self.binance.get_asset_balance(symbol)
    #         # balance = float(balance['free'])
    #     except Exception as e:
    #         print("Error:", e)
    #     return balance, symbol  # float(balance['locked'])

    def get_balance(self, ):
        """Balance in USDT for example - in coin target"""
        free, locked, ununl = self.get_asset_balance(self.coin_target)
        self._cash = free
        self._value = free + locked + ununl
        self._unpnl = ununl

    def getbroker(self):
        return self._broker

    def getdata(self, **kwargs):  # timeframe, compression, start_date=None, LiveBars=True
        symbol = kwargs['dataname']
        # print(symbol)
        tf = self.get_interval(kwargs['timeframe'], kwargs['compression'])
        self.symbols.append(symbol)
        self.get_filters(symbol=symbol)
        if symbol not in self._datas:
            self._datas[f"{symbol}{tf}"] = BinanceData(store=self, **kwargs)  # timeframe=timeframe, compression=compression, start_date=start_date, LiveBars=LiveBars
        return self._datas[f"{symbol}{tf}"]
        
    def get_filters(self, symbol):
        symbol_info = self.get_symbol_info(symbol)
        for f in symbol_info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                self._step_size[symbol] = f['stepSize']
                self._min_order[symbol] = f['minQty']
            elif f['filterType'] == 'PRICE_FILTER':
                self._tick_size[symbol] = f['tickSize']
            elif f['filterType'] == 'NOTIONAL':
                self._min_order_in_target[symbol] = f['minNotional']

    def get_interval(self, timeframe, compression):
        return self._GRANULARITIES.get((timeframe, compression))

    @retry
    def set_leverage(self, symbol, leverage):
        self.binance.futures_change_leverage(symbol=symbol, leverage=leverage)

    @retry
    def get_symbol_info(self, ssymbol):
        exchange_info = self.binance.futures_exchange_info()
        symbol_info = next((symbol for symbol in exchange_info['symbols'] if symbol['symbol'] == ssymbol), None)
        return symbol_info

    def stop_socket(self):
        self.binance_socket.stop()
        self.binance_socket.join(5)

    def futures_symbol_ticker(self, symbol):
        return self.binance.futures_symbol_ticker(symbol=symbol)

    def log(self, text, text2="", text3="", text4="", text5="", text6="", level=1):
        if level > self.log_level:
            print(text, text2, text3, text4, text5, text6)
