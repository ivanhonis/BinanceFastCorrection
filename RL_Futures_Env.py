import datetime
# import sys
import copy
import sys
import time
import random
import gymnasium as gym
# import matplotlib
# import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gymnasium.spaces.discrete import Discrete
from gymnasium.spaces.box import Box
# from gymnasium.utils import seeding
# from stable_baselines3.common.logger import Logger, KVWriter, CSVOutputFormat
import math
import torch as th
from prettytable import PrettyTable


class Collector:
    def __init__(self, initial_size, initial_value):
        self.initial_size = initial_size
        self.initial_value = initial_value
        self.data = [initial_value] * initial_size

    def add(self, value):
        # print("collector add:", value)
        self.data.append(value)

    def reset(self):
        self.data = [self.initial_value] * self.initial_size

    def get(self, numpy=False):
        if numpy:
            return np.array(self.data)
        else:
            return self.data

    def sum(self):
        return sum(self.data)

    def save_np(self, fname):
        np.save(fname, np.array(self.data))
        return

    def get_last(self, size=10, numpy=False, precision=6):
        if numpy:
            return np.array(self.data[-size:]).round(precision)
        else:
            return self.data[-size:]

    def describe(self):
        arr = np.array(self.data)

        # Calculate statistics
        stats = {
            'count': len(arr),
            'mean': np.mean(arr),
            'std': np.std(arr, ddof=1),  # Use sample standard deviation
            'min': np.min(arr),
            '25%': np.percentile(arr, 25),
            '50%': np.percentile(arr, 50),  # This is the median
            '75%': np.percentile(arr, 75),
            'max': np.max(arr)
        }

        return stats


class DataCollector:
    def __init__(self, initial_size=10, initial_value=0.0, initial_cash=100_000.0, initial_date=datetime.datetime.now()):
        self.reward = Collector(initial_size, initial_value)
        self.portfolio_value = Collector(initial_size, initial_cash)
        self.position = Collector(initial_size, initial_value)
        self.trade_steps = Collector(initial_size, initial_value)
        self.open_position = Collector(initial_size, initial_value)
        self.last_trade_net_profit = Collector(initial_size, initial_value)
        self.last_trade_gross_profit = Collector(initial_size, initial_value)
        self.last_trade_fee = Collector(initial_size, initial_value)
        self.action = Collector(initial_size, initial_value)
        self.real_action = Collector(initial_size, initial_value)
        self.current_date = Collector(initial_size, initial_date)
        self.market_price = Collector(initial_size, initial_date)
        self.state = Collector(0, [])

    def reset(self):
        self.reward.reset()
        self.portfolio_value.reset()
        self.position.reset()
        self.trade_steps.reset()
        self.open_position.reset()
        self.last_trade_net_profit.reset()
        self.last_trade_gross_profit.reset()
        self.last_trade_fee.reset()
        self.real_action.reset()
        self.current_date.reset()
        self.market_price.reset()
        self.state.reset()
        self.action.reset()


class SingleFuturesEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, df,  worker_id=0, start_step_count=0, lock=object, predict_mode=False):

        self.df = df
        self.df_rows = self.df.shape[0]
        self.worker_id = worker_id
        self.start_step_count = start_step_count
        self.lock = lock
        self.predict_mode = predict_mode

        # különböző workerek különböző abalkokkal dolgoznak
        window_management_types = ["growing", "slideing", "slideing-overlay"]
        self.window_type = window_management_types[worker_id % 3]
        # self.window_type = "slideing-overlay"
        # self.window_type = "slideing"

        print(f"Start worket: {self.worker_id +1}, window manager: {self.window_type}")

        if self.window_type == "growing":
            self.window_size = int(self.df_rows / 10)
        elif self.window_type == "slideing":
            self.window_size = int(self.df_rows / 5)
        elif self.window_type == "slideing-overlay":
            self.window_size = int(self.df_rows / 5)
        else:
            print("Error: window_type")
            self.window_size = int(self.df_rows / 1)

        # const
        self.total_timesteps = 0
        self.memory_size = 10
        self.fee_percent = 0.065
        self.initial_cash = 100_000.0
        self.asset_precision_decimal = 4
        self.data_precision_decimal = 6

        self.action_space = Discrete(4)  # 0 hold, 1 long, 2 short, 3 close (lond and close)
        extra_inline_features = 3
        self.features_space = (self.df.shape[1] - 1 + extra_inline_features) * self.memory_size  # -1 for date time
        # self.features_space = (self.df.shape[1] - 1 + extra_inline_features)   # -1 for date time
        self.observation_space = Box(low=0, high=3_000_000, shape=(self.features_space, ))

        # self.observation_space = Dict({
        #     '2d_array': Box(low=0, high=3_000_000, shape=(self.features_space, self.memory_size), dtype=np.float32),  # 2D array (10x10)
        # })

        self.window_size = int(self.df_rows / 10)
        # self.window_size = 3000
        #
        self.take_profit_reward_limit_percent = 4.0  # %
        self.stop_loss_panelty_limit_percent = -1.75  # %
        self.position_funding_panelty_percent = 0.0  # % / step
        self.position_funding_panelty = 0.0
        self.good_hold_reward_percent = 7   # %

        rp_lot = 0
        self.price_list_base = {
            "repeat_long": {
                "reinforcement": "panelty",
                "type": "fix",
                "value": rp_lot,
                "base": None,
                "count": 0,
                "amount": 0,
            },
            "repeat_short": {
                "reinforcement": "panelty",
                "type": "fix",
                "value": rp_lot,
                "base": None,
                "count": 0,
                "amount": 0,
            },
            "turn_over": {
                "reinforcement": "panelty",
                "type": "fix",
                "value": rp_lot,
                "base": None,
                "count": 0,
                "amount": 0,
            },
            "close_empty": {
                "reinforcement": "panelty",
                "type": "fix",
                "value": rp_lot,
                "base": None,
                "count": 0,
                "amount": 0,
            },
            "hold_position": {
                "reinforcement": "reward",
                "type": "fix",
                "value": rp_lot,
                "base": None,
                "count": 0,
                "amount": 0,
            },
            "close_trade": {
                "reinforcement": "panelty",
                "type": "fix",
                "value": 0,
                "base": None,
                "count": 0,
                "amount": 0,
            },
            "stop_loss": {
                "reinforcement": "panelty",
                "type": "percent",
                "value": 0,
                "base": "trade_value",
                "count": 0,
                "amount": 0,
            },
            "take_profit": {
                "reinforcement": "reward",
                "type": "percent",
                "value": 0,
                "base": "trade_value",
                "count": 0,
                "amount": 0,
            },
        }

        # reset adja a kezdő értéket
        # self.fee_total = None
        self.position_enter_qty = None
        self.cash = None
        self.market_price = None
        self.position_enter_price = None
        self.step_count = None
        self.data = None
        self.current_date = None
        self.terminal = None
        self.truncated = None
        self.trades_count = None
        self.last_trade_gross_profit = None
        self.last_trade_fee = None
        self.last_trade_steps = None
        # self.closed_trades_profit = None
        self.step_reward = None
        self.position = None  # 1 long, -1 short, 0 None
        self.real_action = None
        self.trade_steps = None
        self.r_ticket = None
        self.price_list = None

        # erre azért van szükség, mert a tréning elején a reset 2x hívódik meg
        # egyszer, hogy megkapja a kezdő értékeket, és egyszer már a PPO hívja meg a observationért
        # ezt azért csináltam így, hogy a kezdő értékek csak 1 helyen legyenek megadva
        # így kerülöm el, hogy az init és reset eltérő értékekkel indít
        # az end_window ez alól kivétel
        self.end_window = -self.window_size

        self.collect = DataCollector()
        self.set_init_values()
        # self.reset(options={'from': 'init'})
        # self.reset()

    def add_rticket(self, ticket):
        self.r_ticket.append(ticket)

    def calculate_rtickets(self, last_trade_profit, portfolio_value):
        ret_reward = 0
        for t in self.r_ticket:
            ticket = self.price_list[t]
            t_amount = 0
            if ticket["type"] == "fix":
                t_amount = float(ticket["value"])
            elif ticket["type"] == "percent":
                if ticket["base"] == "trade_value":
                    if last_trade_profit == 0:
                        print("calculate_reward Error (trade_value = 0)", t)
                    else:
                        t_amount = last_trade_profit * float(ticket["value"]) / 100
                elif ticket["base"] == "portfolio_value":
                    if portfolio_value == 0:
                        print("calculate_reward Error (tradportfolio_valuee_value = 0)", t)
                    else:
                        t_amount = portfolio_value * float(ticket["value"]) / 100
                else:
                    print("calculate_reward Error (base)", t)
            else:
                print("calculate_reward Error (type)", t)

            self.price_list[t]["count"] += 1

            if ticket["reinforcement"] == "panelty":
                self.price_list[t]["amount"] -= t_amount
                ret_reward -= t_amount
            elif ticket["reinforcement"] == "reward":
                self.price_list[t]["amount"] += t_amount
                ret_reward += t_amount
        self.r_ticket = []
        return ret_reward

    def qprint(self, *args, table_indent=25):
        table = PrettyTable()
        table.header = False
        table.align = "l"
        for arg in args:
            table.add_row([arg])
        table_str = table.get_string()
        indented_table = "\n".join((" " * table_indent) + line for line in table_str.splitlines())
        if self.predict_mode:
            pass
        else:
            with self.lock:
                print(indented_table)

    def seed(self, seed):
        print("Set seed.")
        random.seed(seed)
        np.random.seed(seed)
        th.manual_seed(seed)

        # Ha CUDA-t használsz
        th.cuda.manual_seed(seed)
        th.cuda.manual_seed_all(seed)
        pass

    def dround(self, value):
        factor = 10 ** self.asset_precision_decimal
        return math.floor(value * factor) / factor

    def long(self):
        self.position = 1
        self.position_enter_price = self.market_price
        self.position_enter_qty = self.dround(self.cash / self.market_price)
        self.trade_steps = 1
        self.real_action = 1

    def short(self):
        self.position = -1
        self.position_enter_price = self.market_price
        self.position_enter_qty = self.dround(self.cash / self.market_price)
        self.trade_steps = 1
        self.real_action = 3

    def close_all(self):
        fee = 0
        profit = 0
        if self.position == 1:  # close long
            profit = (self.market_price - self.position_enter_price) * self.position_enter_qty
            fee = (self.position_enter_qty * self.market_price) * (self.fee_percent / 100)
            self.real_action = 2

        elif self.position == -1:  # close short
            profit = (self.position_enter_price - self.market_price) * self.position_enter_qty
            fee = (self.position_enter_qty * self.market_price) * (self.fee_percent / 100)
            self.real_action = 4

        # self.fee_total += fee
        # self.fee_total = round(self.fee_total, 2)

        self.last_trade_gross_profit = profit
        self.last_trade_fee = fee
        # self.closed_trades_profit += self.last_trade_profit
        self.cash += (profit - fee)
        self.cash = round(self.cash, 2)

        # Reinforcement stop loss; take profit, fun
        enter_value = self.position_enter_price * self.position_enter_qty
        trade_profit_percent = (profit / enter_value) * 100
        if trade_profit_percent > self.take_profit_reward_limit_percent:
            self.add_rticket("take_profit")
        elif trade_profit_percent < self.stop_loss_panelty_limit_percent:
            self.add_rticket("stop_loss")
        self.position_funding_panelty = enter_value * ((self.position_funding_panelty_percent / 100) * self.trade_steps)

        self.position = 0
        self.trades_count += 1
        self.position_enter_qty = 0
        self.position_enter_price = 0
        self.last_trade_steps = self.trade_steps
        self.trade_steps = 0

    def convert_2d(self, data_dict, data_precision_decimal=6):
        result_df = pd.DataFrame()

        for key, value in data_dict.items():
            if isinstance(value, pd.DataFrame):
                result_df = pd.concat([result_df, value], axis=1)
            elif isinstance(value, list):
                result_df[key] = np.array(value)
            elif isinstance(value, np.ndarray) and value.ndim == 1:
                result_df[key] = value
            else:
                # Hibakezelés: ha nem megfelelő típusú adatot kapunk
                raise ValueError(f"A dictionary {key} kulcshoz tartozó értéke nem DataFrame vagy 1D numpy array", type(value))

        ret = result_df.to_numpy(dtype=np.float64).flatten().round(data_precision_decimal).tolist()
        # ret = np.reshape(ret,(self.features_space, self.memory_size))
        ret = result_df.values.flatten().tolist()
        return ret

    # @staticmethod
    # def covert_1d(d: dict):
    #     flat_list = []
    #
    #     for value in d.values():
    #         if isinstance(value, list):
    #             flat_list.extend(value)
    #         elif isinstance(value, pd.Series) or isinstance(value, pd.DataFrame):
    #             flat_list.extend(value.values.flatten())
    #         else:
    #             flat_list.append(value)
    #
    #     return np.array(flat_list, dtype=np.float64)

    def get_open_position_value(self):
        if self.position == 1:
            ret = (self.market_price - self.position_enter_price) * self.position_enter_qty
        elif self.position == -1:
            ret = (self.position_enter_price - self.market_price) * self.position_enter_qty
        else:
            ret = 0.0
        return round(ret, 2)

    # def create_state_1d(self):
    #     state_dict = {
    #         "position": self.position,
    #         "trade_steps": self.trade_steps,
    #         "data": self.data.drop(["date"]),
    #         "potfolio_value": self.get_portfolio_value() / self.initial_cash,
    #         "open_position_value": self.get_open_position_value() / self.initial_cash,
    #     }
    #     return self.covert_1d(state_dict)

    def create_state_2d(self):
        idf = self.df[self.step_count-self.memory_size:self.step_count].copy()
        idf = idf.drop(columns=['date'])
        state_dict = {
            "data": idf.round(self.data_precision_decimal),
            "position": self.collect.position.get_last(numpy=True, precision=self.data_precision_decimal),
            "trade_steps": self.collect.trade_steps.get_last(numpy=True, precision=self.data_precision_decimal),
            # "potfolio_value": np.round(self.collect.portfolio_value.get_last(numpy=True, precision=self.data_precision_decimal) / self.initial_cash, self.data_precision_decimal),
            "open_position_value": np.round(self.collect.open_position.get_last(numpy=True, precision=self.data_precision_decimal) / self.initial_cash, self.data_precision_decimal),
        }

        # return {'2d_array': self.convert_2d(state_dict, self.data_precision_decimal)}
        return self.convert_2d(state_dict, self.data_precision_decimal)

    def get_portfolio_value(self):
        ret = 0.0
        if self.position == 0:
            ret = self.cash
        elif self.position == 1:
            ret = self.cash + ((self.market_price - self.position_enter_price) * self.position_enter_qty)
        elif self.position == -1:
            ret = self.cash + ((self.position_enter_price - self.market_price) * self.position_enter_qty)
        return round(ret, 2)

    def step(self, action):

        # print(self.step_count, self.end_window, action)

        self.step_count += 1
        self.total_timesteps += 1

        self.real_action = 0

        self.terminal = self.step_count >= min(self.end_window, self.df_rows - 1)
        self.truncated = self.terminal

        # print(self.step_count, self.end_window, self.total_timesteps, self.df_rows, self.terminal)

        if self.step_count == self.df_rows - 1 - (self.memory_size * 2):
            self.render()


            # if self.predict_mode:
            # df = pd.DataFrame()
            # df["real_action"] = self.collect.real_action.get(numpy=True)[10:]
            # df["last_trade_gross_profit"] = self.collect.last_trade_gross_profit.get(numpy=True)[10:]
            # df["current_date"] = self.collect.current_date.get()[10:]
            # df["market_price"] = self.collect.market_price.get()[10:]
            # df["action"] = self.collect.action.get()[10:]
            # df.to_hdf("RL_Futures/learn_train.hdf5", key='df', mode='w')
            # self.collect.state.save_np("RL_Futures/states")

            # np.save('RL_Futures/real_action_memory.npy', self.collect.real_action.get(numpy=True))
            # np.save('RL_Futures/last_trade_gross_profit_memory.npy', self.collect.last_trade_gross_profit.get(numpy=True))
            # np.save('RL_Futures/current_date_memory.npy', self.collect.current_date.get(numpy=True))

        if not self.terminal:

            if self.position != 0:
                self.trade_steps += 1

            self.last_trade_gross_profit = 0
            self.last_trade_fee = 0

            self.data = self.df.loc[self.step_count, :]
            self.current_date = self.data["date"]
            # row = self.df.values[self.step_count]
            self.market_price = self.data["close"]

            if action == 0:  # hold/
                if self.position == 1:
                    self.add_rticket("hold_position")
                elif self.position == 0:
                    self.add_rticket("hold_position")
                elif self.position == -1:
                    self.add_rticket("hold_position")
            if action == 1:  # long
                if self.position == 1:
                    self.add_rticket("repeat_long")
                elif self.position == 0:
                    self.long()
                elif self.position == -1:
                    self.add_rticket("turn_over")
            elif action == 2:  # short
                if self.position == 1:
                    self.add_rticket("turn_over")
                elif self.position == 0:
                    self.short()
                elif self.position == -1:
                    self.add_rticket("repeat_short")
            elif action == 3:  # close
                if self.position == 1:
                    self.close_all()
                    self.add_rticket("close_trade")
                elif self.position == 0:
                    self.add_rticket("close_empty")
                elif self.position == -1:
                    self.close_all()
                    self.add_rticket("close_trade")

            # reward calculator
            self.step_reward = self.calc_step_reward()

            # memory
            self.collect.position.add(self.position)
            self.collect.trade_steps.add(self.trade_steps)
            self.collect.portfolio_value.add(self.get_portfolio_value())
            self.collect.open_position.add(self.get_open_position_value())
            self.collect.last_trade_net_profit.add(self.last_trade_gross_profit - self.last_trade_fee)
            self.collect.last_trade_gross_profit.add(self.last_trade_gross_profit)
            self.collect.last_trade_fee.add(self.last_trade_fee)
            self.collect.real_action.add(self.real_action)
            self.collect.current_date.add(self.current_date)
            self.collect.reward.add(self.step_reward)
            self.collect.market_price.add(self.market_price)
            self.collect.state.add(self.create_state_2d())
            self.collect.action.add(action)
            self.position_funding_panelty = 0.0

            # print(self.collect.portfolio_value.get_last())

            #
            # print(action, self.real_action, self.step_count, self.market_price, self.current_date, np.sum(self.create_state_2d()))
            # sys.exit(0)

        return (self.create_state_2d(), self.collect.reward.sum(), self.terminal, self.truncated,
                {
                    "date": pd.to_datetime(self.current_date),
                    "real_action": self.real_action,
                    "action": action,
                    "step_count": self.step_count,
                    "end_window": self.end_window,
                    "portfolio_value": self.get_portfolio_value(),
                    "last_trade_gross_profit": self.last_trade_gross_profit,
                    "last_trade_fee": self.last_trade_fee,
                    "last_trade_net_profit": self.last_trade_gross_profit - self.last_trade_fee,
                    "market_price": self.market_price,
                })

    def calc_step_reward(self):
        # rtickets_value = self.calculate_rtickets(self.last_trade_gross_profit - self.last_trade_fee, self.get_portfolio_value())
        # return self.last_trade_gross_profit - self.last_trade_fee + rtickets_value

        good_hold_reward = 0
        if self.real_action in [2, 4]:
            good_hold_reward = (self.last_trade_gross_profit * (self.good_hold_reward_percent / 100)) * self.last_trade_steps
            self.last_trade_steps = 0
        return self.last_trade_gross_profit - self.last_trade_fee + good_hold_reward
        # return rtickets_value

    def set_init_values(self):
        self.real_action = 0
        self.trade_steps = 0
        self.last_trade_steps = 0
        self.position_enter_qty = 0
        self.position_enter_price = 0
        self.cash = self.initial_cash
        self.market_price = 0
        # if self.predict_mode:
        #     self.step_count = self.memory_size+1
        # else:

        self.terminal = False
        self.truncated = False
        self.trades_count = 0
        self.step_reward = 0.0
        self.position = 0  # 1 long, -1 short, 0 None
        self.r_ticket = []
        self.last_trade_gross_profit = 0.0
        self.last_trade_fee = 0.0
        self.position_funding_panelty = 0.0
        self.price_list = copy.deepcopy(self.price_list_base)


    def reset(self, seed=None, options=None):

        # if options is None:
            # print("options: None")
        # else:
            # print("options:", options)

        self.set_init_values()

        if self.predict_mode:
            self.end_window = self.df_rows - 1
        else:
            if self.window_type == "growing":
                if self.step_count is None:
                    self.step_count = self.memory_size
                    self.end_window = self.window_size
                elif self.end_window == self.df_rows - 1:
                    self.step_count = self.memory_size
                    self.end_window = self.window_size
                else:
                    self.step_count = self.memory_size
                    self.end_window += self.window_size
                    self.end_window = min(self.end_window, self.df_rows - 1)
            elif self.window_type == "slideing":
                if self.step_count is None:
                    self.step_count = self.memory_size
                    self.end_window = self.window_size
                elif self.end_window == self.df_rows - 1:
                    self.step_count = self.memory_size
                    self.end_window = self.window_size
                else:
                    self.end_window += self.window_size
                    self.end_window = min(self.end_window, self.df_rows - 1)
            elif self.window_type == "slideing-overlay":
                if self.step_count is None:
                    self.step_count = self.memory_size
                    self.end_window = self.window_size
                elif self.end_window == self.df_rows - 1:
                    self.step_count = self.memory_size
                    self.end_window = self.window_size
                else:
                    self.step_count -= int(self.window_size / 2)
                    self.end_window = self.step_count + self.window_size
                    self.end_window = min(self.end_window, self.df_rows - 1)

            # self.render()

        self.collect.reset()
        self.data = self.df.loc[self.step_count, :]
        return self.create_state_2d(), {}

    def render(self, mode='human'):
        rtickets = "\n".join([f"  {key}: {value['count']} / {value['amount']:,.2f}" for key, value in self.price_list.items()])
        gross_profit = self.collect.last_trade_gross_profit.sum()
        total_fee = self.collect.last_trade_fee.sum()
        net_profit = gross_profit - total_fee

        count_1 = np.count_nonzero(self.collect.real_action.get(numpy=True) == 1)
        count_2 = np.count_nonzero(self.collect.real_action.get(numpy=True) == 2)
        count_3 = np.count_nonzero(self.collect.real_action.get(numpy=True) == 3)
        count_4 = np.count_nonzero(self.collect.real_action.get(numpy=True) == 4)

        # print(self.collect.last_trade_net_profit.describe())
        # print('- ' * 50)

        self.qprint(f"Render: {self.worker_id} {self.window_type}",
                    f"               Datetime: {datetime.datetime.now().strftime('%Y.%m.%d %H:%M:%S')}",
                    f"                 Reward: {self.collect.reward.sum():,.2f}",
                    f"        Portfolio value: {self.get_portfolio_value():,.2f}",
                    f"     Total gross profit: {gross_profit:,.2f}",
                    f"              Total fee: {total_fee:,.2f}",
                    f"             Net profit: {net_profit:,.2f}",
                    f"          Closed trades: {self.trades_count} / {int(self.df_rows / (self.trades_count + 0.01))} min",
                    f"AVG net profit / trades: {net_profit / (self.trades_count + 0.01):,.2f}",
                    f"             Step count: {self.step_count}",
                    f"             End window: {self.end_window}",
                    f"       Num of open long: {count_1}",
                    f"      Num of close long: {count_3}",
                    f"      Num of open short: {count_2}",
                    f"     Num of close short: {count_4}",
                    f"RTickets: ",
                    rtickets,
                    )
        return self.create_state_2d()

