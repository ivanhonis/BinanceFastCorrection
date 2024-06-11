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
from tqdm.auto import tqdm
import datetime as dt

# multiprc & thr
from multiprocessing import Process
import threading

# Backtrader
import backtrader as bt
from backtrader_binance import BinanceStore
import backtrader.analyzers as btanalyzers

# Pandas and friends
import pandas as pd
import numpy as np

# matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib as mpl
import seaborn as sns

# Data transfer
import ftplib
import os
import paramiko


class Monitor:

    def __init__(self, external_server=False):
        self.external_server = external_server
        self.data = {}
        self.symbols = {}

        # 'open_history': tuple(self.open_history),
        # 'high_history': tuple(self.high_history),
        # 'low_history': tuple(self.low_history),
        # 'close_history': tuple(self.close_history),
        #
        # 'ema_fast_long_data_history': tuple(self.ema_fast_long_data_history),
        # 'ema_fast_long_down_shift_data_history': tuple(self.ema_fast_long_down_shift_data_history),
        # 'ema_slow_long_data_history': tuple(self.ema_slow_long_data_history),
        #
        # 'ema_fast_short_data_history': tuple(self.ema_fast_short_data_history),
        # 'ema_fast_short_up_shift_data_history': tuple(self.ema_fast_short_up_shift_data_history),
        # 'ema_slow_short_data_history': tuple(self.ema_slow_short_data_history),

        self.open_history = {}
        self.high_history = {}
        self.low_history = {}
        self.close_history = {}

        self.ema_fast_long_data_history = {}
        self.ema_fast_long_down_shift_data_history = {}
        self.ema_slow_long_data_history = {}

        self.ema_fast_short_data_history = {}
        self.ema_fast_short_up_shift_data_history = {}
        self.ema_slow_short_data_history = {}

        self.decision = {}
        self.meta = {}

        self.p = {}
        for i in range(6):
            self.p[i] = {}

        self.anim_speed = 1000 * 10

        self.last_plotted_close = {}
        for i in range(6):
            self.last_plotted_close[i] = np.array([0]*700)

        self.xaxis = np.array([])
        self.zoom_xaxis = np.array([])
        self.zoom = 300

        self.time_period = 0
        self.is_load_data_run = True

    def start_threads(self):
        thread1 = threading.Thread(target=self.load_data)
        # thread2 = threading.Thread(target=self.start_create_chart_thread)

        thread1.start()
        # thread2.start()
        self.start_create_chart_thread()

        thread1.join()
        # thread2.join()

    @staticmethod
    def download_file_sftp():
        hostname = "202.182.111.65"
        port = 22
        username = "root"
        password = "b$8JeBFfhL5F.9JR"
        remote_filepath = "data_transfer/data_transfer_for_process.pickle"
        local_filepath = "data_transfer/data_transfer_for_process.pickle"
        max_attempts = 4

        # Initialize the SSH client
        client = paramiko.SSHClient()
        # Add server's SSH key automatically if missing
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        attempt = 0
        while attempt < max_attempts:
            try:
                # Connect to the server
                client.connect(hostname, port=port, username=username, password=password)
                # Start SFTP session
                sftp = client.open_sftp()
                # Download file
                sftp.get(remote_filepath, local_filepath)
                # Close SFTP session
                sftp.close()
                break  # Exit the loop if download was successful
            except (paramiko.SSHException, paramiko.sftp_lib.SFTPError) as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(5)  # Wait for 5 seconds before retrying
                attempt += 1
            finally:
                # Ensure the client is closed properly
                client.close()

        if attempt == max_attempts:
            print("Failed to download the file after maximum attempts.")

    @staticmethod
    def pickle_loader(filename, attempts=3, delay=3):
        for attempt in range(attempts):
            try:
                with open(filename, 'rb') as handle:
                    data = pickle.load(handle)
                return data
            except IOError as e:
                time.sleep(delay)
            except Exception as e:
                return None
        return None

    def load_data(self):
        print("data readin threat start")
        while self.is_load_data_run:
            if self.external_server:
                self.download_file_sftp()
            self.data = self.pickle_loader('data_transfer/data_transfer_for_process.pickle')

            # print(self.data)
            # time.sleep(15)
            # continue

            data_no = {"ETHUSDT": 0,
                       "BTCUSDT": 1,
                       "AVAXUSDT": 2,
                       "BNBUSDT": 3,
                       }

            for dk in self.data:
                x = data_no[self.data[dk]['symbol']]
                if dk != "meta":
                    d = self.data[dk]

                    # 'open_history': tuple(self.open_history),
                    # 'high_history': tuple(self.high_history),
                    # 'low_history': tuple(self.low_history),
                    # 'close_history': tuple(self.close_history),
                    #
                    # 'ema_fast_long_data_history': tuple(self.ema_fast_long_data_history),
                    # 'ema_fast_long_down_shift_data_history': tuple(self.ema_fast_long_down_shift_data_history),
                    # 'ema_slow_long_data_history': tuple(self.ema_slow_long_data_history),
                    #
                    # 'ema_fast_short_data_history': tuple(self.ema_fast_short_data_history),
                    # 'ema_fast_short_up_shift_data_history': tuple(self.ema_fast_short_up_shift_data_history),
                    # 'ema_slow_short_data_history': tuple(self.ema_slow_short_data_history),

                    self.symbols[x] = d['symbol']
                    self.open_history[x] = np.array(d['open_history'], dtype=float)[::-1]
                    self.high_history[x] = np.array(d['high_history'], dtype=float)[::-1]
                    self.low_history[x] = np.array(d['low_history'], dtype=float)[::-1]
                    self.close_history[x] = np.array(d['close_history'], dtype=float)[::-1]
                    self.ema_fast_long_data_history[x] = np.array(d['ema_fast_long_data_history'], dtype=float)[::-1]
                    self.ema_fast_long_down_shift_data_history[x] = np.array(d['ema_fast_long_down_shift_data_history'], dtype=float)[::-1]
                    self.ema_slow_long_data_history[x] = np.array(d['ema_slow_long_data_history'], dtype=float)[::-1]
                    self.ema_fast_short_data_history[x] = np.array(d['ema_fast_short_data_history'], dtype=float)[::-1]
                    self.ema_fast_short_up_shift_data_history[x] = np.array(d['ema_fast_short_up_shift_data_history'], dtype=float)[::-1]
                    self.ema_slow_short_data_history[x] = np.array(d['ema_slow_short_data_history'], dtype=float)[::-1]
                    self.decision[x] = np.array(d['decision'], dtype=int)[::-1]
                    self.time_period = len(self.close_history[x])
                self.meta[x] = self.data[dk]['meta']

                # for xk in self.meta[x]:
                #     if len(str(self.meta[x][xk])) > 200:
                #         self.meta[x][xk] = str(self.meta[x][xk])[:200]
                #         self.meta[x][str(xk)+"1"] = str(self.meta[x][xk])[200:]

            for i in range(5*60):
                time.sleep(1)
                if not self.is_load_data_run:
                    break
        print("Stop Monitor load data.")
        sys.exit(0)

    def on_close(self, event):
        plt.close('all')
        self.is_load_data_run = False

    def start_create_chart_thread(self):
        print('start_create_chart_thread')
        sns.set_theme(style="whitegrid", font_scale=.6)
        time.sleep(15)

        ani = [[], [], [], [], [], [], [], [], [], [], [], []]
        wm_geometry = ['+0+0',
                       '+1920+0',
                       '+0+1030',
                       '+1920+1030']

        for sid in range(4):
            rows = 4
            # sid = 1

            # self.xaxis = np.arange(0, self.time_period)
            # self.xaxis = self.xaxis.reshape((-1, 1))

            self.xaxis = np.array(range(self.time_period))
            self.zoom_xaxis = np.array(range(self.zoom))

            self.p[sid]['fig'], self.p[sid]['ax'] = plt.subplots(rows, 1,
                                                                 gridspec_kw={'height_ratios': [20, 50, 15, 20]},
                                                                 figsize=(8.5, 4),
                                                                 num=sid + 1)

            self.p[sid]['fig'].canvas.mpl_connect('close_event', self.on_close)

            self.p[sid]['ax11'] = self.p[sid]['fig'].add_subplot(rows, 1, 1)
            self.p[sid]['ax12'] = self.p[sid]['fig'].add_subplot(rows, 1, 2)
            self.p[sid]['ax13'] = self.p[sid]['fig'].add_subplot(rows, 1, 3)
            self.p[sid]['ax14'] = self.p[sid]['fig'].add_subplot(rows, 1, 4)

            plt.autoscale(False)
            for axx in self.p[sid]['ax']:
                axx.set_xticks([])
                axx.set_yticks([])
                axx.get_yaxis().set_visible(False)
                axx.xaxis.set_major_formatter(plt.NullFormatter())
                axx.spines['bottom'].set_visible(False)

            plt.subplots_adjust(left=0.06, right=1, top=1, bottom=0, hspace=-0.01, wspace=0.01)
            ani[sid] = animation.FuncAnimation(self.p[sid]['fig'], self.animate_plot,
                                          interval=self.anim_speed,
                                          fargs=(sid,),
                                          cache_frame_data=False)
            self.p[sid]['fig'].canvas.manager.window.wm_geometry(wm_geometry[sid])
            # plt.tight_layout(pad=0.2, h_pad=0.2, w_pad=0.2)
        plt.show()

    def animate_plot(self, i, sid):
        # print(np.equal(self.low_history[sid], self.high_history[sid]))
        if np.all(np.equal(self.low_history[sid], self.high_history[sid])):
            return

        if not np.all(self.last_plotted_close[sid] == self.close_history[sid]):
            fig = plt.gcf()
            size = fig.get_size_inches() * fig.dpi  # size in pixels
            if size[0] < 1910:
                fsize = 7.85
            else:
                fsize = 10.5

            self.p[sid]['fig'].canvas.manager.set_window_title("Monitor - Binance ESM    " + self.symbols[sid])

            # TEXT
            self.p[sid]['ax14'].clear()
            self.p[sid]['ax14'].grid(color='#666666', linestyle='', linewidth=0)
            self.p[sid]['ax14'].get_yaxis().set_ticks([])
            self.p[sid]['ax14'].xaxis.set_major_formatter(plt.NullFormatter())
            self.p[sid]['ax14'].set_facecolor('#e5e5e5')

            self.meta['0'] = "Local time:" + str(datetime.datetime.now().strftime("%Y. %m. %d. %H:%M:%S"))

            for i, key in enumerate(self.meta[sid]):
                # print(i, key, self.meta[key])
                self.p[sid]['ax14'].text(0.009, 0.12 * (i - 1) + 0.2, self.meta[sid][key], style='normal', fontsize=fsize, color="#000000")

            # chart
            self.p[sid]['ax11'].clear()
            self.p[sid]['ax11'].margins(x=0)
            self.p[sid]['ax11'].xaxis.set_major_formatter(plt.NullFormatter())
            self.p[sid]['ylim_min'] = min(self.low_history[sid])
            self.p[sid]['ylim_max'] = max(self.high_history[sid])

            self.p[sid]['ax11'].set_ylim([self.p[sid]['ylim_min'], self.p[sid]['ylim_max']])
            self.p[sid]['ax11'].ticklabel_format(axis='y', style='sci', useOffset=False)
            self.p[sid]['ax11'].xaxis.set_ticks(np.arange(0, self.time_period, 5000))
            self.p[sid]['ax11'].set_facecolor('#ffffff')

            color = np.array([''] * self.time_period)
            color_mask_up = np.where(self.close_history[sid] >= self.open_history[sid])[0]
            color_mask_down = np.where(self.close_history[sid] < self.open_history[sid])[0]
            color[color_mask_up] = "green"
            color[color_mask_down] = "red"

            self.p[sid]['ax11'].bar(self.xaxis, bottom=self.open_history[sid],
                                    height=(self.close_history[sid] - self.open_history[sid]),
                                    width=1,
                                    color=color,
                                    align='edge',
                                    edgecolor='none')

            self.p[sid]['ax11'].bar(self.xaxis + .45, bottom=self.low_history[sid],
                                    height=(self.high_history[sid] - self.low_history[sid]),
                                    width=0.1,
                                    color=color,
                                    align='edge',
                                    edgecolor='none')

            # BUY
            mark_array = np.array([np.nan] * abs(self.time_period))
            buy_mask = np.where(self.decision[sid] == 1)[0]
            mark_array[buy_mask] = self.low_history[sid][buy_mask]
            self.p[sid]['ax11'].plot(self.xaxis + .5, mark_array, color="blue",
                                     marker=(3, 0, 0),
                                     markersize=10,
                                     linestyle='None')

            # SELL
            mark_array = np.array([np.nan] * abs(self.time_period))
            buy_mask = np.where(self.decision[sid] == -1)[0]
            mark_array[buy_mask] = self.low_history[sid][buy_mask]
            self.p[sid]['ax11'].plot(self.xaxis + .5, mark_array, color="orange",
                                     marker=(3, 0, 180),
                                     markersize=10,
                                     linestyle='None')

            # CLOSE
            mark_array = np.array([np.nan] * abs(self.time_period))
            buy_mask = np.where(self.decision[sid] == 2)[0]
            mark_array[buy_mask] = self.low_history[sid][buy_mask]
            self.p[sid]['ax11'].plot(self.xaxis + .5, mark_array, color="green",
                                     marker=(3, 0, 180),
                                     markersize=10,
                                     linestyle='None')

            self.last_plotted_close[sid] = self.close_history[sid]

            # # self.p[sid]['ax11'].plot(self.xaxis, self.d[sid]['ma_history'], 'y-', alpha=0.9, linewidth=1, )
            # # self.p[sid]['ax11'].plot(self.xaxis, self.d[sid]['ma_history'], 'g-', alpha=0.9, linewidth=2, )
            # # self.p[sid]['ax11'].plot(self.xaxis, self.d[sid]['ma_history'], 'r-', alpha=0.9, linewidth=2, )
            # # self.p[sid]['ax11'].plot(self.xaxis, self.d[sid]['ma_history_fast'], 'c--', alpha=0.9, linewidth=1, )
            #
            # # nma = np.array([np.nan] * abs(self.time_period))
            # # ma = self.moving_average(self.d[sid]['best_bid_price_history'], 4000)
            # # self.p[sid]['ax11'].plot(self.xaxis, ma, 'r-', alpha=0.6, linewidth=1, )
            # #
            # # detect = 2000
            # #
            # # for count in range(len(self.d[sid]['best_bid_price_history'])):
            # #     if count < detect:
            # #         pass
            # #     else:
            # #         grad = ma[count] - (np.sum(ma[count-detect:count]) / detect)
            # #         if np.mean(ma[-300:-200]) > np.mean(ma[-200:-100]) < np.mean(ma[-100:]):
            # #             nma[count] = ma[count]
            # # if np.mean(ma[count-2000:count-1]) < ma[count] - 2.5:
            # #     nma[count] = self.d[sid]['best_bid_price_history'][count]
            # #
            # # self.p[sid]['ax11'].plot(self.xaxis, nma, 'b-', alpha=0.99, linewidth=1, )
            #
            # self.plot_decision_set(sid, 'ax11', zoom=False)
            #
            # # ZOOM
            #
            self.p[sid]['ax12'].clear()
            self.p[sid]['ax12'].margins(x=0)
            self.p[sid]['ax12'].xaxis.set_major_formatter(plt.NullFormatter())
            self.p[sid]['ax12'].set_facecolor('#e6fff2')

            ylim_min1 = min([min(self.ema_fast_long_data_history[sid][-self.zoom:]),
                            min(self.ema_slow_long_data_history[sid][-self.zoom:]),
                            min(self.low_history[sid][-self.zoom:]),
                            min(self.high_history[sid][-self.zoom:]),
                            min(self.ema_fast_long_down_shift_data_history[sid][-self.zoom:])])

            ylim_max1 = max([max(self.ema_fast_long_data_history[sid][-self.zoom:]),
                            max(self.ema_slow_long_data_history[sid][-self.zoom:]),
                            max(self.low_history[sid][-self.zoom:]),
                            max(self.high_history[sid][-self.zoom:]),
                            max(self.ema_fast_long_down_shift_data_history[sid][-self.zoom:])])

            self.p[sid]['ax12'].set_ylim([ylim_min1, ylim_max1])
            self.p[sid]['ax12'].ticklabel_format(axis='y', style='sci', useOffset=False)

            self.p[sid]['ax12'].bar(self.zoom_xaxis, bottom=self.open_history[sid][-self.zoom:],
                                    height=(self.close_history[sid][-self.zoom:] - self.open_history[sid][-self.zoom:]),
                                    width=1,
                                    color=color,
                                    align='edge',
                                    edgecolor='none')

            self.p[sid]['ax12'].bar(self.zoom_xaxis + .45, bottom=self.low_history[sid][-self.zoom:],
                                    height=(self.high_history[sid][-self.zoom:] - self.low_history[sid][-self.zoom:][-self.zoom:]),
                                    width=0.1,
                                    color=color,
                                    align='edge',
                                    edgecolor='none')
            #
            self.p[sid]['ax12'].plot(self.zoom_xaxis, self.ema_fast_long_data_history[sid][-self.zoom:], 'g-', alpha=0.8, linewidth=1)
            self.p[sid]['ax12'].plot(self.zoom_xaxis, self.ema_slow_long_data_history[sid][-self.zoom:], 'g-', alpha=0.8, linewidth=2)
            self.p[sid]['ax12'].plot(self.zoom_xaxis, self.ema_fast_long_down_shift_data_history[sid][-self.zoom:], 'g--', alpha=0.8, linewidth=1)

            self.p[sid]['ax13'].clear()
            self.p[sid]['ax13'].margins(x=0)
            self.p[sid]['ax13'].xaxis.set_major_formatter(plt.NullFormatter())
            self.p[sid]['ax13'].set_facecolor('#ffe6e6')

            ylim_min = min([min(self.ema_fast_short_data_history[sid][-self.zoom:]),
                            min(self.ema_fast_short_data_history[sid][-self.zoom:]),
                            min(self.low_history[sid][-self.zoom:]),
                            min(self.high_history[sid][-self.zoom:]),
                            min(self.ema_fast_short_up_shift_data_history[sid][-self.zoom:])])

            ylim_max = max([max(self.ema_fast_short_data_history[sid][-self.zoom:]),
                            max(self.ema_fast_short_data_history[sid][-self.zoom:]),
                            max(self.low_history[sid][-self.zoom:]),
                            max(self.high_history[sid][-self.zoom:]),
                            max(self.ema_fast_short_up_shift_data_history[sid][-self.zoom:])])

            self.p[sid]['ax13'].set_ylim([ylim_min, ylim_max])
            self.p[sid]['ax13'].ticklabel_format(axis='y', style='sci', useOffset=False)

            self.p[sid]['ax13'].bar(self.zoom_xaxis, bottom=self.open_history[sid][-self.zoom:],
                                    height=(self.close_history[sid][-self.zoom:] - self.open_history[sid][-self.zoom:]),
                                    width=1,
                                    color=color,
                                    align='edge',
                                    edgecolor='none')

            self.p[sid]['ax13'].bar(self.zoom_xaxis + .45, bottom=self.low_history[sid][-self.zoom:],
                                    height=(self.high_history[sid][-self.zoom:] - self.low_history[sid][-self.zoom:][-self.zoom:]),
                                    width=0.1,
                                    color=color,
                                    align='edge',
                                    edgecolor='none')

            self.p[sid]['ax13'].plot(self.zoom_xaxis, self.ema_fast_short_data_history[sid][-self.zoom:], 'r-', alpha=0.8, linewidth=1)
            self.p[sid]['ax13'].plot(self.ema_fast_short_data_history[sid][-self.zoom:], 'r-', alpha=0.8, linewidth=2)
            self.p[sid]['ax13'].plot(self.zoom_xaxis, self.ema_fast_short_up_shift_data_history[sid][-self.zoom:], 'r--', alpha=0.8, linewidth=1)


            #
            if not self.is_load_data_run:
                sys.exit(0)
            # self.p[sid]['ax12'].plot(self.xaxis, self.d[sid]['best_bid_price_history'][self.zoom_part:], 'r-', alpha=0.6, linewidth=1, )
            #
            # mid_price = (self.d[sid]['best_bid_price_history'][self.zoom_part:] + self.d[sid]['best_ask_price_history'][self.zoom_part:]) / 2
            # self.p[sid]['ax12'].plot(self.xaxis_zoom, mid_price, 'k-', alpha=0.8, linewidth=2, )
            #
            # # self.p[sid]['ax12'].plot(self.xaxis_zoom, self.d[sid]['best_ask_price_history_us'][self.zoom_part:], 'b--', alpha=0.6, linewidth=1)
            # # self.p[sid]['ax12'].plot(self.xaxis_zoom, self.d[sid]['best_bid_price_history_us'][self.zoom_part:], 'r--', alpha=0.6, linewidth=1, )
            #
            # # self.p[sid]['ax12'].plot(self.xaxis_zoom, self.moving_average(self.d[sid]['best_bid_price_history'][self.zoom_part:], 750), 'r-', alpha=0.6, linewidth=1, )
            # upper = self.d[sid]['ma_history_fast'][self.zoom_part:] + (self.d[sid]['std_history'][self.zoom_part:] * 2)
            # lower = self.d[sid]['ma_history_fast'][self.zoom_part:] - (self.d[sid]['std_history'][self.zoom_part:] * 2)
            # self.p[sid]['ax12'].plot(self.xaxis_zoom, self.d[sid]['ma_history_fast'][self.zoom_part:], 'y-', alpha=0.8, linewidth=1, )
            # self.p[sid]['ax12'].plot(self.xaxis_zoom, upper, 'g--', alpha=0.8, linewidth=2, )
            # self.p[sid]['ax12'].plot(self.xaxis_zoom, lower, 'r--', alpha=0.8, linewidth=2, )
            # # self.p[sid]['ax12'].plot(self.xaxis_zoom, self.d[sid]['ma_history_fast'][self.zoom_part:], 'c--', alpha=0.8, linewidth=1, )
            #
            # self.plot_decision_set(sid, 'ax12', zoom=True)
            #
            # # self.plot_traded_price(sid,
            # #                        axis='ax12',
            # #                        zoom=True,
            # #                        color='k',
            # #                        markersize=1,
            # #                        marker=4,
            # #                        shift=0)
            #
            # # self.p[sid]['ax15'].clear()
            # # self.p[sid]['ax15'].margins(x=0)
            # # self.p[sid]['ax15'].xaxis.set_major_formatter(plt.NullFormatter())
            # # # self.p[sid]['ax15'].set_ylim(900, 1100)
            # # self.p[sid]['ax15'].get_yaxis().set_ticks([])
            # # self.p[sid]['ax15'].xaxis.set_ticks(np.arange(0, self.time_period, 500))
            # # self.p[sid]['ax15'].set_facecolor('#efefef')
            # #
            # # amount = self.d[sid]['riport0'].split("Deposit:", 1)
            # # amount = int(amount[1][1:6])
            # # bline = np.array([amount] * abs(self.zoom_part2))
            # # self.p[sid]['ax15'].plot(self.xaxis_zoom2, bline, 'r--', linewidth=1, alpha=0.4)
            # #
            # # if np.max(self.d[sid]['silent_history'][self.zoom_part2:]) != 0:
            # #     self.p[sid]['ax15'].plot(self.xaxis_zoom2, self.d[sid]['silent_history'][self.zoom_part2:], 'g-', linewidth=1, alpha=0.4)
            # #
            # # sec_text = '25 min'
            # # # pos_val = (np.max(self.d[sid]['value_history'][self.zoom_part:]) + np.min(self.d[sid]['value_history'][self.zoom_part:])) / 2
            # # pos_val = np.min(self.d[sid]['silent_history'][self.zoom_part2:])
            # # for st in range(12):
            # #     self.p[sid]['ax15'].text(st * 500 + 150, pos_val, sec_text, style='normal', fontsize=8, color="#adadad")
            # # self.p[sid]['ax15'].plot(self.xaxis_zoom2, self.d[sid]['value_history'][self.zoom_part2:], 'y-', linewidth=1)
            # #
            # # price_arr = self.d[sid]['position_price_arr'][self.d[sid]['position_price_arr'] != 0]
            # # qty_arr = self.d[sid]['position_qty_arr'][self.d[sid]['position_qty_arr'] != 0]
            # #
            # # if len(price_arr) > 0:
            # #     min_pos = np.min(price_arr)
            # #     max_pos = np.max(price_arr)
            # #     avg_price = np.sum(price_arr * qty_arr) / np.sum(qty_arr)
            # #
            # # else:
            # #     min_pos = 0
            # #     max_pos = 0
            # #     avg_price = 0
            # #
            # # pos_price_arr = np.array([min_pos] * self.time_period)
            # # pos_qty_arr = np.array([0.0] * self.time_period)
            # # xi = 0
            # # for px, p in enumerate(price_arr):
            # #     for xj in range(int(20000 / len(price_arr))):
            # #         pos_price_arr[xi] = p
            # #         pos_qty_arr[xi] = round(qty_arr[px] * 1100, 0)
            # #         xi += 1
            # #
            # # pos_qty_arr = pos_qty_arr + min_pos
            # #
            # # self.p[sid]['ax15'].clear()
            # # self.p[sid]['ax15'].margins(x=0)
            # # self.p[sid]['ax15'].xaxis.set_major_formatter(plt.NullFormatter())
            # # try:
            # #     ylmaxp = np.max(self.d[sid]['profit_history'][self.d[sid]['profit_history'] > 0]) + 5
            # #     ylminp = np.min(self.d[sid]['profit_history'][self.d[sid]['profit_history'] > 0]) - 5
            # #
            # #     ylmaxs = np.max(self.d[sid]['silent_investor_history'][self.d[sid]['silent_investor_history'] > 0]) + 5
            # #     ylmins = np.min(self.d[sid]['silent_investor_history'][self.d[sid]['silent_investor_history'] > 0]) - 5
            # #
            # #     ylmin = np.min([ylminp, ylmins])
            # #     ylmax = np.max([ylmaxs, ylmaxp])
            # #
            # # except:
            # #
            # #     ylmin = 10000
            # #     ylmax = 60000
            # #
            # # self.p[sid]['ax15'].set_ylim(ylmin, ylmax)
            # # self.p[sid]['ax15'].ticklabel_format(axis='y', style='sci', useOffset=False)
            # #
            # # # self.p[sid]['ax16'].get_yaxis().set_ticks([])
            # # # self.p[sid]['ax15'].xaxis.set_ticks(np.arange(0, self.time_period, 500))
            # #
            # # # amount = self.d[sid]['riport0'].split("Deposit:", 1)
            # # # amount = int(amount[1][1:6])
            # # # bline = np.array([22425.79] * abs(self.time_period))
            # # # self.p[sid]['ax16'].plot(self.xaxis, bline, 'r--', linewidth=1, alpha=0.4)
            # # self.p[sid]['ax15'].set_facecolor('#efefef')
            # # # self.p[sid]['ax15'].plot(self.xaxis_zoom, self.d[sid]['profit_history'][self.zoom_part:], 'g-', linewidth=1, alpha=1.0)
            # # # self.p[sid]['ax15'].plot(self.xaxis_zoom, self.d[sid]['silent_investor_history'][self.zoom_part:], 'b-', linewidth=1, alpha=1.0)
            # #
            # # # except:
            # # #     pass

    # def visualization(self):
    #     while True:
    #         plt.cla()
    #         x = range(len(self.close))
    #         plt.plot(x, self.close, c="gray", zorder=1)
    #         # # x0, y0 = zip(*peaks_and_valleys[0])
    #         # # x1, y1 = zip(*peaks_and_valleys[1])
    #         # # plt.scatter(x0, y0, c="red", zorder=2)
    #         # # plt.scatter(x1, y1, c="blue", zorder=3)
    #         # # plt.plot(x, [y_breakout] * len_df, c="yellow", zorder=1)
    #         # # plt.plot(x, [y_stoploss_level] * len_df, c="red", zorder=1)
    #         # # plt.plot(x, [y_takeprofit_level] * len_df, c="green", zorder=1)
    #         plt.pause(1)


if __name__ == "__main__":
    m = Monitor(external_server=True)
    m.start_threads()
