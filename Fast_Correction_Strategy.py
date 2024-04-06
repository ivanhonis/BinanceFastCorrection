# Binance Fast Correction Strategy

from collections import deque
import backtrader as bt


class FastCorrectionStrategy(bt.Strategy):

    def __init__(self, dropeed_time_frame, dropped_down, pt_pip, sl_pip, coin_target="BTCFDUSD", show_log=True):
        self.MINIMUM_STEPS = 100
        self.DROPPER_TIME_FRAM = dropeed_time_frame
        self.DROPPED_DOWN = dropped_down
        self.PT_PIP = pt_pip
        self.SL_PIP = sl_pip
        self.coin_target = coin_target
        self.total_pnl = 0
        self.show_log = show_log

        # ma_fast = bt.ind.SMA(period=1000)
        # ma_slow = bt.ind.SMA(period=5000)
        self.close_prices_history = deque(maxlen=self.DROPPER_TIME_FRAM)
        # self.portfoli_value_history = deque(maxlen=25)
        self.last_buy_portfolio_value = 0
        self.steps_count = 0
        self.last_action = ""

        # self.crossover = bt.ind.CrossOver(ma_fast, ma_slow)

    @staticmethod
    def print_object(obj):
        all_properties = dir(obj)

        for prop in all_properties:
            if callable(getattr(obj, prop)):
                print(f"Method: {prop}")
            else:
                print(f"Attribute: {prop}")

    def log(self, text):
        if self.show_log:
            print(text)

    def next(self):
        for data in self.datas:
            if not data.islive():
                state_hol = "History data"
            else:
                state_hol = "Live data"

            print('{} / {} minperiod[{}] - Open: {}, High: {}, Low: {}, Close: {}, Volume: {} - {}'.format(
                bt.num2date(data.datetime[0]),
                data._name,
                data._minperiod,  # ticker timeframe
                data.open[0],
                data.high[0],
                data.low[0],
                data.close[0],
                data.volume[0],
                state_hol,
            ))

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
            # self.orders[order_data_name] = None  # Reset the order to enter the position

    def notify_trade(self, trade):
        """Changing the position status"""
        if trade.isclosed:  # If the position is closed
            self.log(f'Profit on a closed position {trade.getdataname()} Total={trade.pnl:.2f}, No commission={trade.pnlcomm:.2f}')
