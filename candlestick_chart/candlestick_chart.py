import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import datetime
from types import SimpleNamespace


class CandlestickChart:
    def __init__(self):

        self.df = None
        self.symbol = ""

        self.open_prices = None
        self.high_prices = None
        self.low_prices = None
        self.close_prices = None

        self.dates = None
        self.moving_averages = {}
        self.config = ""

    def add_config(self, config):
        self.config = config

    def get_config(self, config=""):
        cc = self.config

        l1 = f"is_long  {cc.is_long}, ema_fast_long  {cc.ema_fast_long}, ema_slow_long  {cc.ema_slow_long}, long_down_shift {cc.ema_fast_long_down_shift}"
        l2 = f"is_stop_loss_long {cc.is_stop_loss_long}, stop_loss_percent_long {cc.stop_loss_percent_long}"
        l3 = f"is_short {cc.is_short}, ema_fast_short {cc.ema_fast_short}, ema_slow_short {cc.ema_slow_short}, short_up_shift  {cc.ema_fast_short_up_shift}"
        l4 = f"is_stop_loss_short {cc.is_stop_loss_short}, stop_loss_percent_short {cc.stop_loss_percent_short}"
        l5 = f"is_trailer_short   {cc.is_trailer_short}, trailer_short_enter_percent {cc.trailer_short_enter_percent}, trailer_short_offset {cc.trailer_short_offset}"

        return l1, l2, l3, l4, l5

    def add(self, df, symbol):

        self.df = df
        self.symbol = symbol

        self.open_prices = self.df.open_history
        self.high_prices = self.df.high_history
        self.low_prices = self.df.low_history
        self.close_prices = self.df.close_history

        self.dates = pd.date_range('2024-01-01', periods=len(self.df['close_history']))
        self.moving_averages = {
            'ema_fast_long_data_history': {
                'values': self.df.ema_fast_long_data_history,
                'color': 'green',
                'linestyle': 'solid',
                'linewidth': '1'
            }, 'ema_fast_long_down_shift_data_history': {
                'values': self.df.ema_fast_long_down_shift_data_history,
                'color': 'green',
                'linestyle': 'dashed',
                'linewidth': '1'
            }, 'ema_slow_long_data_history': {
                'values': self.df.ema_slow_long_data_history,
                'color': 'green',
                'linestyle': 'solid',
                'linewidth': '3'
            }, 'ema_fast_short_data_history': {
                'values': self.df.ema_fast_short_data_history,
                'color': 'red',
                'linestyle': 'solid',
                'linewidth': '1'
            }, 'ema_fast_short_up_shift_data_history': {
                'values': self.df.ema_fast_short_up_shift_data_history,
                'color': 'red',
                'linestyle': 'dashed',
                'linewidth': '1'
            }, 'ema_slow_short_data_history': {
                'values': self.df.ema_slow_short_data_history,
                'color': 'red',
                'linestyle': 'solid',
                'linewidth': '3'
            }
        }

    def plot_candlestick(self, ax, width=0.5):
        def plot_single_candlestick(date, open_price, close_price, high_price, low_price):
            color = '#80ff80' if close_price >= open_price else '#ff8080'
            ax.plot([date, date], [low_price, high_price], color=color, linewidth=0.6)
            ax.add_patch(Rectangle((date - width / 2, min(open_price, close_price)),
                                   width, abs(close_price - open_price),
                                   edgecolor=color, facecolor=color))

        width = 0.8 * (mdates.date2num(self.dates[1]) - mdates.date2num(self.dates[0]))
        for i, date in enumerate(self.dates):
            plot_single_candlestick(mdates.date2num(date), self.open_prices[i], self.close_prices[i], self.high_prices[i], self.low_prices[i])

    def plot(self, filename):
        fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(12, 16), sharex=True)

        # Set background colors
        ax1.set_facecolor('#f0fff6')  # Light green
        ax2.set_facecolor('#fff0f6')  # Light red

        # Plot candlesticks
        self.plot_candlestick(ax1)
        self.plot_candlestick(ax2)

        # Plot moving averages
        for name, ma in self.moving_averages.items():
            if name in ['ema_fast_long_data_history', 'ema_fast_long_down_shift_data_history', 'ema_slow_long_data_history']:
                ax1.plot(self.dates, ma['values'],
                         label=name,
                         color=ma['color'],
                         linestyle=ma['linestyle'],
                         linewidth=ma['linewidth']
                         )
            if name in ['ema_fast_short_data_history', 'ema_fast_short_up_shift_data_history', 'ema_slow_short_data_history']:
                ax2.plot(self.dates, ma['values'],
                         label=name,
                         color=ma['color'],
                         linestyle=ma['linestyle'],
                         linewidth=ma['linewidth']
                         )

        # Formatting the chart
        ax1.set_title(f'{self.symbol} - ESM LONG')
        ax2.set_title(f'{self.symbol} - ESM SHORT')
        ax1.set_ylabel('Price')
        ax2.set_ylabel('Price')
        # ax1.set_xlabel('Time')
        # ax2.set_xlabel('Time')
        ax1.grid(True)
        ax2.grid(True)
        # ax1.legend(['ema_fast', 'ema_fast_shift', 'ema_slow'])
        # ax2.legend(['ema_fast', 'ema_fast_shift', 'ema_slow'])
        ax1.legend()
        ax2.legend()
        # fig.autofmt_xdate()
        ax1.xaxis.set_visible(False)
        ax2.xaxis.set_visible(False)

        l1, l2, l3, l4, l5 = self.get_config()

        fig.text(0.125, 0.085 + 0.004, l1, ha='left', fontsize=15, color='#333333')
        fig.text(0.125, 0.070 + 0.004, l2, ha='left', fontsize=15, color='#333333')
        fig.text(0.125, 0.055 + 0.004, l3, ha='left', fontsize=15, color='#333333')
        fig.text(0.125, 0.040 + 0.004, l4, ha='left', fontsize=15, color='#333333')
        fig.text(0.125, 0.025 + 0.004, l5, ha='left', fontsize=15, color='#333333')
        fig.text(0.125, 0.010, f"Tokyo, {datetime.datetime.now().strftime('%B %d, %Y %I:%M:%S %p')}", ha='left', fontsize=16, color='#333333')

        # Save the chart to a file
        plt.savefig(filename)
        plt.close()

if __name__ == "__main__":
    # Example usage
    np.random.seed(42)
    num_days = 150
    dates = pd.date_range('2024-01-01', periods=num_days)
    initial_price = 100
    daily_volatility = 0.02

    # Generate realistic stock prices
    daily_returns = np.random.normal(0, daily_volatility, num_days)
    prices = initial_price * np.exp(np.cumsum(daily_returns))
    open_prices = np.roll(prices, 1)
    open_prices[0] = initial_price
    high_prices = open_prices + np.random.uniform(0.5, 3.0, num_days)
    low_prices = open_prices - np.random.uniform(0.5, 3.0, num_days)
    close_prices = prices

    df = pd.DataFrame({
        'open_history': open_prices,
        'high_history': high_prices,
        'low_history': low_prices,
        'close_history': close_prices
    })

    df['ema_fast_long_data_history'] = df['close_history'].rolling(window=30).mean()
    df['ema_fast_long_down_shift_data_history'] = df['ema_fast_long_data_history'] * 0.98
    df['ema_slow_long_data_history'] = df['close_history'].rolling(window=15).mean()

    df['ema_fast_short_data_history'] = df['close_history'].rolling(window=30).mean()
    df['ema_fast_short_up_shift_data_history'] = df['ema_fast_short_data_history'] * 1.02
    df['ema_slow_short_data_history'] = df['close_history'].rolling(window=15).mean()


    df = df.tail(15)
    df.index = range(0, 15)
    symbol = "ETHUSDT"
    chart = CandlestickChart()
    chart.add(df, symbol + " PERPETUAL")

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

    kwargs = dict(config)
    cc = SimpleNamespace(**kwargs)

    chart.add_config(cc)
    chart.get_config()
    filename = symbol + '_zoom.png'
    chart.plot(filename)
