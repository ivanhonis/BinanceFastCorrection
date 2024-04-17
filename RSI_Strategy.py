# Binance Fast Correction Strategy
import random
import requests
from collections import deque
import backtrader as bt
import pickle
from datetime import datetime

import numpy as np


class CollectData:

    def __init__(self, lengt, live_run, init_price=69250.0):

        # az záróár az elején van azaz [0] az aktuális záró, [1] az időben egyel előtte
        self.open_history = deque([init_price] * lengt, maxlen=lengt)
        self.high_history = deque([init_price] * lengt, maxlen=lengt)
        self.low_history = deque([init_price] * lengt, maxlen=lengt)
        self.close_history = deque([init_price] * lengt, maxlen=lengt)
        self.rsi_history = deque([50.0] * lengt, maxlen=lengt)
        self.rsi_over_sold = deque([50.0] * lengt, maxlen=lengt)
        self.rsi_over_bought = deque([50.0] * lengt, maxlen=lengt)

        # záróár
        self.open = 0
        self.high = 0
        self.low = 0
        self.close = 0

        self.decision = deque([0] * lengt, maxlen=lengt)
        self.meta = {}
        self.live_run = live_run

    def add_data(self, data, last_rsi, over_sold, over_bought):
        if self.live_run or True:

            self.open_history.appendleft(float(data.open[0]))
            self.high_history.appendleft(float(data.high[0]))
            self.low_history.appendleft(float(data.low[0]))
            self.close_history.appendleft(float(data.close[0]))
            self.rsi_history.appendleft(float(last_rsi))
            self.rsi_over_sold.appendleft(float(over_sold))
            self.rsi_over_bought.appendleft(float(over_bought))

            self.open = float(data.open[0])  # utolsó érték azaz piaci érték
            self.high = float(data.high[0])
            self.low = float(data.low[0])
            self.close = float(data.close[0])

            self.decision.append(0)

    def add_meta(self, field, value):
        if self.live_run:
            self.meta[field] = str(value)

    def save(self):
        if self.live_run:
            save_data_form = {
                'open': self.open_history,
                'high': self.high_history,
                'low': self.low_history,
                'close': self.close_history,
                'rsi': self.rsi_history,
                'rsi_over_sold': self.rsi_over_sold,
                'rsi_over_bought': self.rsi_over_bought,
                'decision': self.decision,
                'meta': self.meta}
            with open('data_transfer_for_process.pickle', 'wb') as handle:
                pickle.dump(save_data_form, handle, protocol=pickle.HIGHEST_PROTOCOL)


class RSIStrategy(bt.Strategy):

    def __init__(self,
                 rsi_period,
                 std_period,
                 dev_min,
                 dev_max,
                 c,
                 coin_target="BTCFDUSD",
                 show_log=False,
                 live_run=False):

        self.rsi_period = rsi_period
        self.std_period = std_period
        self.dev_max = dev_max
        self.dev_min = dev_min
        self.c = c

        self.vrsi = bt.ind.RSI(self.data, period=self.rsi_period)
        # self.co = bt.ind.CrossOver(vrsi, over_sold)
        # self.cu = bt.ind.CrossOver(vrsi, over_bought)

        self.show_log = show_log
        self.live_run = live_run

        self.MINIMUM_STEPS = max(std_period, rsi_period) + 1
        self.coin_target = coin_target
        self.steps_count = 0
        self.last_buy_order = None
        self.total_pnl = 0.0

        self.cd = CollectData(120, live_run, self.get_price(self.coin_target))

    @staticmethod
    def get_price(symbol):
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url)
        data = response.json()
        price = data['price']
        return float(price)

    @staticmethod
    def print_object(obj):
        all_properties = dir(obj)

        for prop in all_properties:
            if callable(getattr(obj, prop)):
                print(f"Method: {prop}")
            else:
                print(f"Attribute: {prop}")

    def log(self, text, text2="", text3=""):
        if self.show_log:
            print(text, text2, text3)

    def start(self):
        # This method is called once before the preloaded data is processed
        print("Starting strategy")

    def position_value(self):
        if self.live_run:
            return ((self.broker.get_asset_balance('BTC')[0] *
                    self.data.close[0]) +
                    self.broker.get_asset_balance('FDUSD')[0])
        else:
            return self.broker.getvalue()

    @staticmethod
    def exponential_scale(value, min_old, max_old, min_new, max_new, c=1):
        # Normalize the original value
        normalized_value = (value - min_old) / (max_old - min_old)

        # Apply the exponential function (using natural base e)
        exp_value = np.exp(c * normalized_value) - 1

        # Scale the exp value to the range [0, e-1], then to the desired range
        scaled_value = min_new + (exp_value / (np.e - 1)) * (max_new - min_new)

        return min(max(scaled_value, min_new), max_new)

    def get_positon_text(self):
        if self.live_run:
            position = self.getposition(self.data)
            return (f"{self.steps_count} Position: {self.data._name}: {position.size} "
                    f"AVG price:{round(position.price, 4)}  "
                    f"Balance: {round(self.broker.getvalue(), 2)}  "
                    f"Cash: {round(self.broker.getcash(), 2)}  "
                    f"BTC: {self.broker.get_asset_balance('BTC')}  "
                    f"FDUSD: {self.broker.get_asset_balance('FDUSD')}  "
                    f"VALUE: {round(self.position_value(), 2)}  "
                    )
        else:
            position = self.getposition(self.data)
            return (f"{self.steps_count} Position: {self.data._name}: {position.size} "
                    f"AVG price:{round(position.price, 4)}  "
                    f"Balance: {round(self.broker.getvalue(), 2)}  "
                    f"Cash: {round(self.broker.getcash(), 2)}  "
                    # f"BTC: {self.broker.get_asset_balance('BTC')}  "
                    # f"FDUSD: {self.broker.get_asset_balance('FDUSD')}  "
                    f"VALUE: {round(self.position_value(), 2)}  "
                    )

    def is_live_data(self):

        status = self.datas[0]._state  # 0 - Live data, 1 - History data, 2 - None
        if status in [0, 1]:
            if status:
                return False
            else:
                return True

    def next(self):
        self.steps_count += 1
        # print(self.steps_count, self.datas[0].datetime.datetime(0))

        std = np.std(np.array(self.cd.close_history)[:self.std_period])
        dev_distance = self.exponential_scale(std, 2, 250, self.dev_min, self.dev_max, c=self.c)
        over_sold = 50 - dev_distance
        over_bought = 50 + dev_distance
        self.cd.add_meta('line2', f"STD: {std}  RSI over sold: {round(over_sold, 2)}  RSI over bought: {round(over_bought)}")

        self.cd.add_data(self.data, self.vrsi[0], over_sold=over_sold, over_bought=over_bought)


        # for data in self.datas:

        # if self.live_run:
        #     status = data._state  # 0 - Live data, 1 - History data, 2 - None
        #     if status in [0, 1]:
        #         if status:
        #             state_hol = "History data"
        #         else:
        #             state_hol = "Live data"
        #
        #             print(self.get_positon_text())

        # print(
        #     f"{self.steps_count}#  "
        #     f"{bt.num2date(data.datetime[0])} "
        #     f"/ {data._name} "
        #     f"minperiod[{data._minperiod}] - "
        #     f"Open: {data.open[0]}, "
        #     f"High: {data.high[0]}, "
        #     f"Low: {data.low[0]}, "
        #     f"Close: {data.close[0]}, "
        #     f"Volume: {data.volume[0]} -"
        #     f" {state_hol}")
        if not self.live_run or self.is_live_data():
            if self.steps_count >= self.MINIMUM_STEPS:

                std = np.std(np.array(self.cd.close_history)[:self.std_period])
                dev_distance = self.exponential_scale(std, 2, 250, self.dev_min, self.dev_max, c=self.c)
                over_sold = 50 - dev_distance
                over_bought = 50 + dev_distance
                self.cd.add_meta('line2', f"STD: {std}  RSI over sold: {round(over_sold,2)}  RSI over bought: {round(over_bought)}")

                # self.co = bt.ind.CrossOver(self.vrsi, over_sold)
                # self.cu = bt.ind.CrossOver(self.vrsi, over_bought)

                # print(self.vrsi[0], self.vrsi[1])
                # print(self.data.close[-1], self.data.close[-2])

                # print(over_sold, over_bought)
                #
                #
                # print("self.position", self.position)
                if not self.position:

                    # print("if", self.vrsi[0], over_sold, self.vrsi[-1])

                    if self.vrsi[0] < over_sold <= self.vrsi[-1]:
                        if self.live_run:
                            size = round((self.broker.getvalue() * .9) / self.data.close[0], 4)
                            self.last_buy_order = self.buy(data=self.datas[0], exectype=bt.Order.Market, size=size)
                            # print("buy")
                        else:
                            self.buy()
                        self.cd.decision[-1] = 1  # 1= BUY
                else:
                    # print("else,", self.vrsi[0], over_sold, self.vrsi[-1])
                    if self.vrsi[0] > over_bought >= self.vrsi[-1]:
                        # self.sell(size=self.last_buy_order.size)
                        self.close()
                        # print("close")
                        self.cd.decision[-1] = 2  # 2= Close Stop Loss

        self.cd.add_meta('line1', self.get_positon_text())
        self.cd.save()

    def stop(self):
        # Close all positions at the end of the strategy
        for data in self.datas:
            # Check if we have an open position for this data
            if self.getposition(data).size != 0:
                # If so, issue an order to close it
                # print(f"Closing position in {data._name}")
                self.close(data)

    def notify_data(self, data, status, *args, **kwargs):
        return
        # if status == data.LIVE:
        #     if not self.close_prices_history_first_fill:
        #         self.log("First fill of close_prices_history")
        #         for i in range(self.DROPPER_TIME_FRAM):
        #             print("i", i, self.data[i])
        #             # self.close_prices_history.append(data.close[i])
        #             # print(self.close_prices_history)
        #         self.close_prices_history_first_fill = True

    def notify_order(self, order):
        """Changing the status of the order"""
        order_data_name = order.data._name  # Name of ticker from order
        self.log(
            f'Order number {order.ref} {order.info["order_number"]} {order.getstatusname()} {"Buy" if order.isbuy() else "Sell"} {order_data_name} {order.size} @ {order.price}')
        if order.status == bt.Order.Completed:  # If the order is fully executed
            if order.isbuy():  # The order to buy
                self.log(
                    f'Buy {order_data_name} Price: {order.executed.price:.2f}, Value {order.executed.value:.2f} {self.coin_target}, Commission {order.executed.comm:.10f} {self.coin_target}')
            else:  # The order to sell
                self.log(
                    f'Sell {order_data_name} Price: {order.executed.price:.2f}, Value {order.executed.value:.2f} {self.coin_target}, Commission {order.executed.comm:.10f} {self.coin_target}')
                if self.live_run:
                    pnl = round((order.executed.price - self.last_buy_order.price) * self.last_buy_order.size, 6)
                    self.total_pnl += pnl
                    text = f"Total PNL: {round(self.total_pnl, 6)} Last trade PNL: {pnl}"
                    self.log(text)
                    self.cd.add_meta('line3', text)
            # self.orders[order_data_name] = None  # Reset the order to enter the position

    def notify_trade(self, trade):
        """Changing the position status"""
        if trade.isclosed:  # If the position is closed
            self.log(f'Profit on a closed position {trade.getdataname()} Total={trade.pnl:.2f}, No commission={trade.pnlcomm:.2f}')


# test
if __name__ == "__main__":

    def exponential_scale(value, min_old, max_old, min_new, max_new, c=1):
        # Normalize the original value
        normalized_value = (value - min_old) / (max_old - min_old)

        # Apply the exponential function (using natural base e)
        exp_value = np.exp(c * normalized_value) - 1

        # Scale the exp value to the range [0, e-1], then to the desired range
        scaled_value = min_new + (exp_value / (np.e - 1)) * (max_new - min_new)

        return min(max(scaled_value, min_new), max_new)

    for i in range(5, 300):
        print(exponential_scale(i, 0,600,0,40))

