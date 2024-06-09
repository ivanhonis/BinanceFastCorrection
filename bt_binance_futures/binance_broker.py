import datetime as dt
import time

from collections import defaultdict, deque
from math import copysign

from backtrader.broker import BrokerBase
from backtrader.order import Order, OrderBase
from backtrader.position import Position
from binance.enums import *
from binance_excel_saver import BinanceExcelSaver


class BinanceOrder(OrderBase):
    def __init__(self, owner, data, exectype, binance_order):
        self.owner = owner
        self.data = data
        self.exectype = exectype
        self.ordtype = self.Buy if binance_order['side'] == SIDE_BUY else self.Sell

        # {'orderId': 8389765685775627292,
        # 'symbol': 'ETHUSDT',
        # 'status': 'FILLED',
        # 'clientOrderId':
        # 'uWnRpZNpmYMSDbhebXuV1H',
        # 'price': '0.00',
        # 'avgPrice': '3825.01000',
        #  'origQty': '0.600',
        #  'executedQty': '0.600',
        #  'cumQuote': '2295.00600',
        #  'timeInForce': 'GTC',
        #  'type': 'MARKET',
        #  'reduceOnly': False,
        #  'closePosition': False,
        #  'side': 'BUY',
        #  'positionSide': 'BOTH',
        #  'stopPrice': '0.00',
        #  'workingType': 'CONTRACT_PRICE',
        #  'priceProtect': False,
        #  'origType': 'MARKET',
        #  'priceMatch': 'NONE',
        #  'selfTradePreventionMode': 'NONE',
        #  'goodTillDate': 0,
        #  'time': 1716924050235,
        #  'updateTime': 1716924050235}

        # Market order price is zero
        if self.exectype == Order.Market:
            self.size = float(binance_order['executedQty'])
            self.price = float(binance_order['avgPrice'])
            # self.price = sum(float(fill['price']) for fill in binance_order['fills']) / len(binance_order['fills'])  # Average price
        else:
            self.size = float(binance_order['origQty'])
            self.price = float(binance_order['price'])
        self.binance_order = binance_order

        super(BinanceOrder, self).__init__()
        self.accept()


class BinanceBroker(BrokerBase):
    _ORDER_TYPES = {
        Order.Limit: ORDER_TYPE_LIMIT,
        Order.Market: ORDER_TYPE_MARKET,
        Order.Stop: ORDER_TYPE_STOP_LOSS,
        Order.StopLimit: ORDER_TYPE_STOP_LOSS_LIMIT,
    }

    def __init__(self, store):
        super(BinanceBroker, self).__init__()

        self.notifs = deque()
        self.positions = defaultdict(Position)

        self.startingcash = self.cash = 0  # Стартовые и текущие свободные средства по счету
        self.startingvalue = self.value = 0  # Стартовая и текущая стоимость позиций

        self.open_orders = list()

        self.log_level = 10

        self._store = store
        self._store.binance_socket.start_futures_user_socket(self._handle_user_socket_message)

        self.binance_excel_saver = BinanceExcelSaver

    def log(self, text, text2="", text3="", text4="", text5="", text6="", level=1):
        if level > self.log_level:
            print(text, text2, text3, text4, text5, text6)

    def start(self):
        self.startingcash = self.cash = self.getcash()  # Стартовые и текущие свободные средства по счету. Подписка на позиции для портфеля/биржи
        self.startingvalue = self.value = self.getvalue()  # Стартовая и текущая стоимость позиций

    def _execute_order(self, order, date, executed_size, executed_price, executed_value, executed_comm, call_by=""):
        order.execute(
            date,
            executed_size,
            executed_price,
            0, executed_value, executed_comm,
            0, 0.0, 0.0,
            0.0, 0.0,
            0, 0.0)
        pos = self.getposition(order.data, clone=False)
        pos.update(copysign(executed_size, order.size), executed_price)
        self._store.get_balance()

    def update_position(self, data, size, price):
        pos = self.getposition(data, clone=False)
        pos.update(size, price)

    def _is_order_in_open_orders(self, msg):
        if self.open_orders:
            for o in self.open_orders:
                if o.binance_order['orderId'] == msg['o']['i']:
                    return True
        return False

    def _handle_user_socket_message(self, msg):

        time.sleep(0.75)
        self.log(msg, level=1)
        if msg['e'] == 'error':
            raise msg
        elif msg['e'] == 'ACCOUNT_UPDATE':
            account_update = msg.get('a', {})
            if account_update.get('m', '') == 'FUNDING_FEE':
                self.binance_excel_saver.save_account_update(msg)
            else:
                return
        elif msg['e'] != 'ORDER_TRADE_UPDATE':
            return
        elif msg['o']['s'] not in self._store.symbols:
            return
        elif msg['o']['X'] != ORDER_STATUS_FILLED:
            return

        while not self._is_order_in_open_orders(msg):
            time.sleep(.25)

        # print("_handle_user_socket_message FILLED" * 5)
        # print(msg)
        """https://binance-docs.github.io/apidocs/spot/en/#payload-order-update"""

        # {
        #     'e': 'ACCOUNT_UPDATE', 'T': 1717804802111, 'E': 1717804802112,
        #     'a': {
        #         'B': [{
        #                   'a': 'USDT',
        #                   'wb': '201.39221840',
        #                   'cw': '201.39221840',
        #                   'bc': '0.00335157'
        #               }], 'P': [], 'm': 'FUNDING_FEE'
        #     }
        # }

        # print(msg)
        # {'e': 'executionReport', 'E': 1707120960762, 's': 'ETHUSDT', 'c': 'oVoRofmTTXJCqnGNuvcuEu', 'S': 'BUY', 'o': 'MARKET', 'f': 'GTC', 'q': '0.00220000', 'p': '0.00000000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '', 'x': 'NEW', 'X': 'NEW', 'r': 'NONE', 'i': 15859894465, 'l': '0.00000000', 'z': '0.00000000', 'L': '0.00000000', 'n': '0', 'N': None, 'T': 1707120960761, 't': -1, 'I': 33028455024, 'w': True, 'm': False, 'M': False, 'O': 1707120960761, 'Z': '0.00000000', 'Y': '0.00000000', 'Q': '0.00000000', 'W': 1707120960761, 'V': 'EXPIRE_MAKER'}

        # {'e': 'executionReport', 'E': 1707120960762, 's': 'ETHUSDT', 'c': 'oVoRofmTTXJCqnGNuvcuEu', 'S': 'BUY', 'o': 'MARKET', 'f': 'GTC', 'q': '0.00220000', 'p': '0.00000000', 'P': '0.00000000', 'F': '0.00000000', 'g': -1, 'C': '',
        # 'x': 'TRADE', 'X': 'FILLED', 'r': 'NONE', 'i': 15859894465, 'l': '0.00220000', 'z': '0.00220000', 'L': '2319.53000000', 'n': '0.00000220', 'N': 'ETH', 'T': 1707120960761, 't': 1297224255, 'I': 33028455025, 'w': False,
        # 'm': False, 'M': True, 'O': 1707120960761, 'Z': '5.10296600', 'Y': '5.10296600', 'Q': '0.00000000', 'W': 1707120960761, 'V': 'EXPIRE_MAKER'}
        # time.sleep(1)
        # print('ORDER_TRADE_UPDATE')
        # print(' self._store.symbols',  self._store.symbols)
        # print('self.open_orders', self.open_orders)

        # {'e': 'ORDER_TRADE_UPDATE', 'T': 1717875181872, 'E': 1717875181872, 'o': {
        #     's': 'AVAXUSDT', 'c': 'iSS1hvzc9e3bOcJzOULD24', 'S': 'SELL', 'o': 'MARKET',
        #     'f': 'GTC', 'q': '2', 'p': '0', 'ap': '32.4650', 'sp': '0', 'x': 'TRADE',
        #     'X': 'PARTIALLY_FILLED', 'i': 21519651154, 'l': '1', 'z': '1', 'L': '32.4650',
        #     'n': '0.00002126', 'N': 'BNB', 'T': 1717875181872, 't': 808695170, 'b': '0', 'a': '0',
        #     'm': False, 'R': False, 'wt': 'CONTRACT_PRICE',
        #     'ot': 'MARKET', 'ps': 'BOTH', 'cp': False, 'rp': '-0.01199999', 'pP': False, 'si': 0, 'ss': 0, 'V': 'NONE',
        #     'pm': 'NONE', 'gtd': 0
        # }
        # }

        # {'e': 'ORDER_TRADE_UPDATE', 'T': 1717875181872, 'E': 1717875181872, 'o': {
        #     's': 'AVAXUSDT', 'c': 'iSS1hvzc9e3bOcJzOULD24', 'S': 'SELL', 'o': 'MARKET',
        #     'f': 'GTC', 'q': '2', 'p': '0', 'ap': '32.4645', 'sp': '0', 'x': 'TRADE', 'X': 'FILLED',
        #     'i': 21519651154, 'l': '1', 'z': '2', 'L': '32.4640', 'n': '0.00002126',
        #     'N': 'BNB', 'T': 1717875181872, 't': 808695171, 'b': '0', 'a': '0', 'm': False, 'R': False,
        #     'wt': 'CONTRACT_PRICE', 'ot': 'MARKET', 'ps': 'BOTH', 'cp': False,
        #     'rp': '-0.01300000', 'pP': False, 'si': 0, 'ss': 0, 'V': 'NONE', 'pm': 'NONE', 'gtd': 0
        # }
        # }

        for o in self.open_orders:
            if o.binance_order['orderId'] == msg['o']['i']:
                if msg['o']['X'] in [ORDER_STATUS_FILLED, ORDER_STATUS_PARTIALLY_FILLED]:

                    # print("ORDER_STATUS_FILLED " * 5)
                    _dt = dt.datetime.fromtimestamp(int(msg['o']['T']) / 1000)
                    executed_size = float(msg['o']['l'])
                    executed_price = float(msg['o']['L'])
                    # executed_value = float(msg['Z'])
                    executed_value = executed_size * executed_price
                    executed_comm = float(msg['o']['n'])
                    # print(_dt, executed_size, executed_price)
                    self._execute_order(o, _dt, executed_size, executed_price, executed_value, executed_comm, call_by="_handle_user_socket_message")
                    try:
                        self.binance_excel_saver.save_execution_report(msg['o'])
                    except:
                        pass
                self._set_order_status(o, msg['o']['X'])

                if o.status not in [Order.Accepted, Order.Partial]:
                    self.open_orders.remove(o)
                self.notify(o)

    def _set_order_status(self, order, binance_order_status):
        if binance_order_status == ORDER_STATUS_CANCELED:
            order.cancel()
        # elif binance_order_status == ORDER_STATUS_NEW:
        #     order.create()
        elif binance_order_status == ORDER_STATUS_EXPIRED:
            order.expire()
        elif binance_order_status == ORDER_STATUS_FILLED:
            order.completed()
        elif binance_order_status == ORDER_STATUS_PARTIALLY_FILLED:
            order.partial()
        elif binance_order_status == ORDER_STATUS_REJECTED:
            order.reject()

    # def _submit(self, owner, data, side, exectype, size, price):
    #     type = self._ORDER_TYPES.get(exectype, ORDER_TYPE_MARKET)
    #     symbol = data._name
    #     binance_order = self._store.create_order(symbol, side, type, size, price)
    #
    #     # 1111 {'symbol': 'ETHUSDT', 'orderId': 15860400971, 'orderListId': -1, 'clientOrderId': 'EO7lLPcYNZR8cNEg8AOEPb', 'transactTime': 1707124560731, 'price': '0.00000000', 'origQty': '0.00220000', 'executedQty': '0.00220000', 'cummulativeQuoteQty': '5.10356000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'BUY', 'workingTime': 1707124560731, 'fills': [{'price': '2319.80000000', 'qty': '0.00220000', 'commission': '0.00000220', 'commissionAsset': 'ETH', 'tradeId': 1297261843}], 'selfTradePreventionMode': 'EXPIRE_MAKER'}
    #     order = BinanceOrder(owner, data, exectype, binance_order)
    #     if binance_order['status'] in [ORDER_STATUS_FILLED, ORDER_STATUS_PARTIALLY_FILLED]:
    #         avg_price =0.0
    #         comm = 0.0
    #         for f in binance_order['fills']:
    #             comm += float(f['commission'])
    #             avg_price += float(f['price'])
    #         avg_price = self._store.format_price(symbol, avg_price/len(binance_order['fills']))
    #         self._execute_order(
    #             order,
    #             dt.datetime.fromtimestamp(binance_order['transactTime'] / 1000),
    #             float(binance_order['executedQty']),
    #             float(avg_price),
    #             float(binance_order['cummulativeQuoteQty']),
    #             float(comm))
    #     self._set_order_status(order, binance_order['status'])
    #     if order.status == Order.Accepted:
    #         self.open_orders.append(order)
    #     self.notify(order)
    #     return order

    def _futures_submit(self, owner, data, side, exectype, size, price):
        type = self._ORDER_TYPES.get(exectype, ORDER_TYPE_MARKET)
        symbol = data._name
        if size is None:
            self.log("None Size ", level=1)
        self.log("_futures_submit", symbol, side, type, size, price, level=1)
        self.log("", level=1)
        binance_order = self._store.futures_create_order(symbol, side, type, size, price)

        # {
        #     "clientOrderId": "testOrder",
        #     "cumQty": "0",
        #     "cumQuote": "0",
        #     "executedQty": "0",
        #     "orderId": 22542179,
        #     "avgPrice": "0.00000",
        #     "origQty": "10",
        #     "price": "0",
        #     "reduceOnly": false,
        #     "side": "BUY",
        #     "positionSide": "SHORT",
        #     "status": "NEW",
        #     "stopPrice": "9300",        // please ignore when order type is TRAILING_STOP_MARKET
        #     "closePosition": false,   // if Close-All
        #     "symbol": "BTCUSDT",
        #     "timeInForce": "GTD",
        #     "type": "TRAILING_STOP_MARKET",
        #     "origType": "TRAILING_STOP_MARKET",
        #     "activatePrice": "9020",    // activation price, only return with TRAILING_STOP_MARKET order
        #     "priceRate": "0.3",         // callback rate, only return with TRAILING_STOP_MARKET order
        #     "updateTime": 1566818724722,
        #     "workingType": "CONTRACT_PRICE",
        #     "priceProtect": false,      // if conditional order trigger is protected
        #     "priceMatch": "NONE",              //price match mode
        #     "selfTradePreventionMode": "NONE", //self trading preventation mode
        #     "goodTillDate": 1693207680000      //order pre-set auot cancel time for TIF GTD order
        # }
        #         {'orderId': 8389765685775627292,
        #         'symbol': 'ETHUSDT',
        #         'status': 'NEW',
        #         'clientOrderId': 'uWnRpZNpmYMSDbhebXuV1H',
        #         'price': '0.00',
        #         'avgPrice': '0.00',
        #         'origQty': '0.600',
        #          executedQty': '0.000',
        #          'cumQty': '0.000',
        #          'cumQuote': '0.00000',
        #          'timeInForce': 'GTC',
        #          'type': 'MARKET',
        #          'reduceOnly': False,
        #          'closePosition': False,
        #          'side': 'BUY',
        #          'positionSide': 'BOTH',
        #          'stopPrice': '0.00',
        #          'workingType': 'CONTRACT_PRICE',
        #          'priceProtect': False,
        #          'origType': 'MARKET',
        #          'priceMatch': 'NONE',
        #          'selfTradePreventionMode': 'NONE',
        #          'goodTillDate': 0,
        #          'updateTime': 1716924050235}

        # {'orderId': 8389765685775627292,
        # 'symbol': 'ETHUSDT',
        # 'status': 'FILLED',
        # 'clientOrderId':
        # 'uWnRpZNpmYMSDbhebXuV1H',
        # 'price': '0.00',
        # 'avgPrice': '3825.01000',
        #  'origQty': '0.600',
        #  'executedQty': '0.600',
        #  'cumQuote': '2295.00600',
        #  'timeInForce': 'GTC',
        #  'type': 'MARKET',
        #  'reduceOnly': False,
        #  'closePosition': False,
        #  'side': 'BUY',
        #  'positionSide': 'BOTH',
        #  'stopPrice': '0.00',
        #  'workingType': 'CONTRACT_PRICE',
        #  'priceProtect': False,
        #  'origType': 'MARKET',
        #  'priceMatch': 'NONE',
        #  'selfTradePreventionMode': 'NONE',
        #  'goodTillDate': 0,
        #  'time': 1716924050235,
        #  'updateTime': 1716924050235}

        # 1111 {'symbol': 'ETHUSDT', 'orderId': 15860400971, 'orderListId': -1, 'clientOrderId': 'EO7lLPcYNZR8cNEg8AOEPb', 'transactTime': 1707124560731, 'price': '0.00000000', 'origQty': '0.00220000', 'executedQty': '0.00220000', 'cummulativeQuoteQty': '5.10356000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'BUY', 'workingTime': 1707124560731, 'fills': [{'price': '2319.80000000', 'qty': '0.00220000', 'commission': '0.00000220', 'commissionAsset': 'ETH', 'tradeId': 1297261843}], 'selfTradePreventionMode': 'EXPIRE_MAKER'}
        order = BinanceOrder(owner, data, exectype, binance_order)

        if binance_order['status'] in [ORDER_STATUS_FILLED, ORDER_STATUS_PARTIALLY_FILLED]:
            # avg_price =0.0
            comm = 0.0
            # for f in binance_order['fills']:
            #     comm += float(f['commission'])
            #     avg_price += float(f['price'])
            # avg_price = self._store.format_price(symbol, avg_price/len(binance_order['fills']))
            # avg_price = self._store.format_price(symbol, avg_price/len(binance_order['fills']))
            self._execute_order(
                order,
                dt.datetime.fromtimestamp(binance_order['updateTime'] / 1000),
                float(binance_order['executedQty']),
                float(binance_order['avgPrice']),
                float(binance_order['cumQuote']),
                float(comm), call_by="_futures_submit")
        self._set_order_status(order, binance_order['status'])
        if order.status == Order.Accepted:
            # print("Append open_orders")
            self.open_orders.append(order)
        self.notify(order)
        return order

    def buy(self, owner, data, size, price=None, plimit=None,
            exectype=None, valid=None, tradeid=0, oco=None,
            trailamount=None, trailpercent=None,
            **kwargs):
        self.log("Broker buy.", level=1)
        return self._futures_submit(owner, data, SIDE_BUY, exectype, size, price)

    def cancel(self, order):
        # Todo megcsinálni
        order_id = order.binance_order['orderId']
        symbol = order.binance_order['symbol']
        self._store.cancel_order(symbol=symbol, order_id=order_id)

    def format_price(self, value):
        return self._store.format_price(value)

    def get_asset_balance(self, asset):
        return self._store.get_asset_balance(asset)

    def getcash(self, refresh=False):
        if refresh:
            self._store.get_balance()
        self.cash = self._store._cash
        return self.cash

    def get_notification(self):
        if not self.notifs:
            return None

        return self.notifs.popleft()

    def getposition(self, data, clone=True):
        pos = self.positions[data._dataname]
        if clone:
            pos = pos.clone()
        return pos

    def getvalue(self, datas=None, refresh=False):
        if refresh:
            self._store.get_balance()
        self.value = self._store._value
        return self.value

    def notify(self, order):
        self.notifs.append(order)

    def set_leverage(self, symbol, leverage):
        self._store.set_leverage(symbol, leverage)

    def futures_symbol_info(self, symbol):
        return self._store.get_symbol_info(symbol)

    def sell(self, owner, data, size, price=None, plimit=None,
             exectype=None, valid=None, tradeid=0, oco=None,
             trailamount=None, trailpercent=None,
             **kwargs):
        self.log("Broker sell.", level=1)
        return self._futures_submit(owner, data, SIDE_SELL, exectype, size, price)

    def futures_symbol_ticker(self, symbol):
        return float(self._store.futures_symbol_ticker(symbol=symbol)['price'])
