import datetime
import time
import os
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
# import sys
import pandas as pd
import pandas_ta as ta
import numpy as np
import random
from tqdm import tqdm

# import matplotlib
# import matplotlib.pyplot as plt
# import datetime
from stable_baselines3 import PPO
# from stable_baselines3.common.env_checker import check_env
# from stable_baselines3 import PPO, DDPG, A2C, TD3
# from stable_baselines3 import DDPG
# from stable_baselines3 import A2C
# from stable_baselines3 import SAC
# from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize, SubprocVecEnv
from stable_baselines3.common.vec_env import VecNormalize, SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.callbacks import BaseCallback, CallbackList
from stable_baselines3.common.utils import set_random_seed
# from stable_baselines3.common.policies import MlpPolicy
import torch as th
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from binance.client import Client

from RL_Futures_Env import SingleFuturesEnv
from RL_Futures_Visualization import RLVisualizer
# import torch
import datetime as dt
# import multiprocessing
import multiprocessing as mp
from scipy import stats
mp.set_start_method('spawn', force=True)

rl_path = "RL_Futures/"
np.set_printoptions(precision=2, suppress=True)
seed_value = 42
log_dir = "tensorboard_logs/"

# 1. Általános random seed beállítása
random.seed(seed_value)
np.random.seed(seed_value)
th.manual_seed(seed_value)

# Ha CUDA-t használsz
th.cuda.manual_seed(seed_value)
th.cuda.manual_seed_all(seed_value)


class TensorboardCallback(BaseCallback):
    """
    Egyedi callback a TensorBoard-hoz, amely további értékeket naplóz.
    """
    def __init__(self, verbose=0):
        super(TensorboardCallback, self).__init__(verbose)

    def _on_step(self) -> bool:
        # Egyedi értékek naplózása

        # custom_env = self.training_env.envs[0]

        # portfolio_value = self.training_env.get_attr('portfolio_value', 0)[0]
        portfolio_value = self.training_env.env_method('get_portfolio_value', indices=0)[0]  # Az első környezet

        # Elérjük a custom_env attribútumát: last_action
        # portfolio_value = custom_env.get_portfolio_value()

        # Naplózzuk az utolsó akciót a TensorBoard-ba
        if portfolio_value is not None:
            self.logger.record('custom_metric/portfolio_value', portfolio_value)

        return True



class TimeEstimatorCallback(BaseCallback):
    def __init__(self, total_timesteps, verbose=1):
        super(TimeEstimatorCallback, self).__init__(verbose)
        self.total_timesteps = total_timesteps
        self.start_time = None
        self.elapsed_time = time.time()
        self.estimated_remaining_time = None

    def _on_training_start(self):
        self.start_time = time.time()  # Start timer at the beginning of training

    def _on_step(self) -> bool:
        self.elapsed_time = time.time() - self.start_time
        current_timesteps = self.model.num_timesteps
        fps = current_timesteps / self.elapsed_time if self.elapsed_time > 0 else float('inf')
        remaining_timesteps = self.total_timesteps - current_timesteps
        self.estimated_remaining_time = remaining_timesteps / fps if fps > 0 else float('inf')
        return True

    def _on_rollout_end(self):
        if self.verbose > 0:
            remaining_time = datetime.timedelta(seconds=self.estimated_remaining_time)
            estimated_end_time = datetime.datetime.now() + remaining_time
            print(f"Estimated remaining time: {estimated_end_time}")
        return



# def fetch_binance_data(symbol, interval, start_str, end_str=None):
#     klines = client.futures_historical_klines(symbol=symbol, interval=interval, start_str=start_str, end_str=end_str)
#     data = pd.DataFrame(klines, columns=[
#         'date', 'open', 'high', 'low', 'close', 'volume',
#         'close_time', 'quote_asset_volume', 'number_of_trades',
#         'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
#     ])
#     # data.set_index('date', inplace=True)
#     data = data[['date', 'open', 'high', 'low', 'close', 'volume',
#                  'quote_asset_volume',
#                  'number_of_trades',
#                  'taker_buy_base_asset_volume',
#                  'taker_buy_quote_asset_volume']].astype(np.float64)
#     # data['volume'] = data['volume'].astype(np.int64)
#     data['date'] = pd.to_datetime(data['date'], unit='ms')
#     # data['Volume'] = data['Volume'].astype(np.float32)
#     data["date"] = data.date.apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
#     # data['tic'] = symbol
#     data = data.dropna()
#     data = data.reset_index(drop=True)
#     data = data.sort_values(by=["date"]).reset_index(drop=True)
#     return data

# def make_env(rank, seed=0, lock=object):
#     def _init():
#         env = SingleFuturesEnv(df, worker_id=rank, lock=lock)
#         env.seed(seed + rank)
#         env.action_space.seed(seed + rank)
#         env.observation_space.seed(seed + rank)
#         return env
#     return _init


def make_env(df, rank, seed=0, lock=object):
    def _init():
        env = SingleFuturesEnv(df, worker_id=rank, lock=lock)
        env.seed(seed_value)
        env.action_space.seed(seed + rank)
        env.observation_space.seed(seed + rank)
        return env
    return _init


def df_split(df, start, end, target_date_col="date"):
    data = df[(df[target_date_col] >= start) & (df[target_date_col] < end)]
    # data = data.sort_values([target_date_col, "tic"], ignore_index=True)
    data.index = data[target_date_col].factorize()[0]
    return data

def binance_download(symbol, from_dt, cutoff_dt=None, refresh=False, futures=False, interval='1h'):
    possible_interval = ['1m', '3m', '5m', '15m', '30m',
                         '1h', '2h', '4h', '6h', '8h', '12h',
                         '1d', '3d',
                         '1w',
                         '1M']

    if interval not in possible_interval:
        print("Selected intervall not exist.", interval)
        return

    print("")
    print("Binance_download->", from_dt.strftime("%Y-%m-%d %H:%M:%S"), symbol, interval)
    if futures:
        futures_text = "_futures"
    else:
        futures_text = ""

    file_name = "binance_data/" + symbol + interval + futures_text + "_" + from_dt.strftime("%Y-%m-%d_%H-%M-%S")
    if refresh and os.path.exists(file_name):
        os.remove(file_name)

    if os.path.exists(file_name):
        print("   Loaded data from existing file.")
        df = pd.read_hdf(file_name, "df")
    else:
        from_dt = from_dt.strftime("%Y-%m-%d %H:%M:%S")
        api_key = 'YOUR_API_KEY'
        api_secret = 'YOUR_API_SECRET'
        client = Client(api_key, api_secret)
        # adatok letöltéséhez kell a client objektum, de nem kell belépni

        if futures:
            klines = client.futures_historical_klines(symbol, interval, from_dt)
        else:
            klines = client.get_historical_klines(symbol, interval, from_dt)

        df = pd.DataFrame(klines, columns=[
            'date', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        # data.set_index('date', inplace=True)
        df = df[['date', 'open', 'high', 'low', 'close', 'volume',
                 'quote_asset_volume',
                 'number_of_trades',
                 'taker_buy_base_asset_volume',
                 'taker_buy_quote_asset_volume']].astype(np.float64)
        # data['volume'] = data['volume'].astype(np.int64)
        df['date'] = pd.to_datetime(df['date'], unit='ms')
        # data['Volume'] = data['Volume'].astype(np.float32)
        df["date"] = df.date.apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
        # data['tic'] = symbol
        df = df.dropna()
        df = df.reset_index(drop=True)
        df = df.sort_values(by=["date"]).reset_index(drop=True)
        df.to_hdf(file_name, key='df', mode='w')

        client.close_connection()
        del client

    if cutoff_dt:
        print("   Cut off from:", cutoff_dt)
        cutoff_dt = pd.Timestamp(cutoff_dt.strftime("%Y-%m-%d %H:%M:%S"), unit='ms')
        df = df[df.index <= cutoff_dt]

    return df


class CustomCNN(BaseFeaturesExtractor):

    def __init__(self, observation_space, features_dim=64):
        # Initialize the BaseFeaturesExtractor with the observation space
        super(CustomCNN, self).__init__(observation_space, features_dim)

        # Extract the number of input channels from the observation space
        n_input_channels = observation_space.shape[0]

        # Define a simple CNN with 1D convolution
        self.cnn = nn.Sequential(
            nn.Conv1d(in_channels=n_input_channels, out_channels=16, kernel_size=3, stride=1),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(in_channels=16, out_channels=32, kernel_size=3, stride=1),
            nn.ReLU(),
            nn.MaxPool1d(kernel_size=2),
            nn.Flatten()
        )

        # Compute the size of the output from the CNN
        with th.no_grad():
            sample_input = th.zeros((1,) + observation_space.shape)
            n_flatten = self.cnn(sample_input).shape[1]

        # Define a fully connected layer to map the CNN output to the features_dim
        self.fc = nn.Sequential(
            nn.Linear(n_flatten, features_dim),
            nn.ReLU()
        )

    def forward(self, observations: th.Tensor) -> th.Tensor:
        # Pass the observations through the CNN
        cnn_output = self.cnn(observations)
        # Pass the output of the CNN through the fully connected layer
        return self.fc(cnn_output)


if __name__ == "__main__":

    lock = mp.Lock()

    from_dt = dt.datetime(year=2024, month=9, day=8, hour=0, minute=3)
    cutoff_dt = None
    interval = "1m"
    # interval = "5m"
    # interval = "15m"
    # refresh = True
    refresh = False
    futures = True
    symbol = 'AVAXUSDT'

    df = binance_download(symbol,
                          from_dt=from_dt,
                          cutoff_dt=cutoff_dt,
                          refresh=refresh,
                          futures=futures,
                          interval=interval)  # in minute from now()

    df.drop(['open', 'quote_asset_volume', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume'], axis=1, inplace=True)

    # for lgt in range(3, 15, 7):
    #     df['EMA_'+str(lgt)] = ta.ema(df['close'], length=lgt)

    df['EMA_420'] = ta.ema(df['close'], length=420)
    df['EMA_25'] = ta.ema(df['close'], length=25) * 0.95
    df['RSI_14'] = ta.rsi(df['close'], length=14)
    df[['MACD', 'MACD_S', 'MACD_H']] = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df.drop(['MACD', 'MACD_S'], axis=1, inplace=True) # ez nem kell mert a MACD_H kifejezi a másik kettőt is
    df['ATRr_14'] = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=14)

    #statisztikai elemzés

    # Typical Price
    df['tp'] = (df['high'] + df['low'] + df['close']) /3

    window_size = 200
    df['tp_Std_Dev'] = df['tp'].rolling(window=window_size).std()

    df['Variance'] = df['tp'].rolling(window=window_size).var()
    # Átlagos Abszolút Eltérés (MAD)
    df['tp_MAD'] = df['tp'].rolling(window=window_size).apply(lambda x: np.mean(np.abs(x - np.mean(x))))

    # Tartomány
    df['tp_Range'] = df['tp'].rolling(window=window_size).apply(lambda x: np.max(x) - np.min(x))

    # Interkvartilis Terjedelem (IQR)
    df['tp_IQR'] = df['tp'].rolling(window=window_size).apply(lambda x: stats.iqr(x))

    # Autokorreláció (lag=1)
    def rolling_autocorr(x):
        if len(x) < 2:
            return np.nan
        return x.autocorr(lag=1)
    df['tp_Autocorrelation'] = df['tp'].rolling(window=window_size).apply(rolling_autocorr, raw=False)

    # Kurtózis
    df['tp_Kurtosis'] = df['tp'].rolling(window=window_size).apply(lambda x: stats.kurtosis(x), raw=False)

    # Ferdeség
    df['tp_Skewness'] = df['tp'].rolling(window=window_size).apply(lambda x: stats.skew(x), raw=False)


    # a Nan okat az elejéről levágom amit az indikátorok csinálnak
    df = df.dropna()
    df = df.reset_index(drop=True)
    df = df.sort_values(by=["date"]).reset_index(drop=True)

    # mindent ami nem date float64 re konvertálok
    cols_to_convert = df.columns.difference(['date'])
    df[cols_to_convert] = df[cols_to_convert].astype(np.float64)
    df[cols_to_convert] = df[cols_to_convert].clip(upper=300000.0)

    print("size (ori)", df.shape)

    cpos = int(df.shape[0] / 3 * 2)
    train_s = df.iloc[0]['date']
    train_e = df.iloc[cpos]['date']
    trade_s = df.iloc[cpos + 1]['date']
    trade_e = df.iloc[-1]['date']

    train = df_split(df, train_s, train_e)
    test = df_split(df, trade_s, trade_e)

    print("size (train)", train.shape)
    print("size (trade)", test.shape)

    run_mode = "train"
    # run_mode = "predict"

    load_model = False
    # load_model = True

    if run_mode == "train":
        num_cpu = 15
        total_timesteps = 6_000_000

        policy_kwargs = dict(
            net_arch=dict(pi=[64, 16, 64], vf=[64, 16, 64])
            # Two hidden layers of 64 units for both the actor (pi) and critic (vf)
        )

        # policy_kwargs = dict(
        #     features_extractor_class=CustomCNN,
        #     features_extractor_kwargs=dict(features_dim=32)
        # )

        envs_x = [make_env(df=train, rank=i, lock=lock) for i in range(num_cpu)]

        envs = SubprocVecEnv(envs_x)

        envs_norm = VecNormalize(envs, norm_obs=True, norm_reward=True)
        # envs_norm = envs

        if load_model:
            print("Load model.")
            model = PPO.load(rl_path + "RL_Futures_model_captain_0_1", env=envs_norm, tensorboard_log=log_dir)
        else:
            print("Create new model.")
            # model = PPO('MlpPolicy', envs, batch_size=512, n_steps=2048, verbose=1)

            learning_rate = 0.0002
            clip_range = 0.15
            ent_coef = 0.01
            model = PPO('MlpPolicy', envs_norm,
                        batch_size=512,
                        n_steps=2048,
                        verbose=1,
                        seed=seed_value,
                        tensorboard_log=log_dir,
                        learning_rate=learning_rate,
                        clip_range=clip_range,
                        policy_kwargs=policy_kwargs,
                        ent_coef=ent_coef,
                        )

        set_random_seed(seed_value)

        time_estimator_callback = TimeEstimatorCallback(total_timesteps=total_timesteps)
        tensorboard_callback = TensorboardCallback()

        callback_list = CallbackList([time_estimator_callback, tensorboard_callback])

        model.learn(total_timesteps=total_timesteps, callback=callback_list, tb_log_name="PPO_CartPole")
        print(datetime.datetime.now())
        model.save(rl_path + "RL_Futures_model_captain_0_1")

    elif run_mode == "predict":

        df_learn = pd.read_hdf(rl_path + "learn_train.hdf5", "df")
        df_learn = pd.DataFrame(df_learn)
        print('sum last_trade_gross_profit', np.sum(df_learn.last_trade_gross_profit))
        states_learn = np.load(rl_path + "states.npy")

        # real_action_memory = np.load(rl_path + "real_action_memorty.npy")
        # last_trade_gross_profit_memory = np.load(rl_path + 'last_trade_gross_profit_memory.npy')
        # current_date_memory = np.load(rl_path + 'current_date_memory.npy', allow_pickle=True)
        #
        # print(real_action_memory)
        # print(last_trade_gross_profit_memory)
        # print(current_date_memory)
        # print(np.sum(last_trade_gross_profit_memory))

        # dfload = True
        dfload = False

        if dfload:
            predict_df = pd.read_hdf(rl_path + "test_df", "df")
        else:
            predict_df = train.copy()

            # predict_df = test.copy()
            print(predict_df.shape)

            model = PPO.load(rl_path + "RL_Futures_model_captain_0_1")
            env_test = DummyVecEnv([lambda: SingleFuturesEnv(predict_df, lock, predict_mode=True)])
            # env_test = VecNormalize(env_test_d, norm_obs=True, norm_reward=True)

            statesx = []
            env_test.set_options({'from': 'predict'})
            state = env_test.reset()
            action, _states = model.predict(states_learn[0])
            print(action)
            print(env_test.step([action]))
            state, rewards, dones, info = env_test.step([action])

            statesx.append(state)
            # state, rewards, dones, info = env_test.step([0])

            statesx.append(state)

            predict_result = {
                "action": [],
                "date": [],
                "real_action": [],
                "step_count": [],
                "end_window": [],
                "portfolio_value": [],
                "last_trade_gross_profit": [],
                "last_trade_fee": [],
                "last_trade_net_profit": [],
                "market_price": [],
            }

            print("==============Model Prediction===========")
            print("predict_df:", predict_df.shape)
            for i in tqdm(range(predict_df.shape[0]-1-50)):

                action, _states = model.predict(states_learn[i+1])
                state, rewards, dones, info = env_test.step([action])
                statesx.append(state)

                for k in info[0]:
                    if k == "date":
                        predict_result[k].append(info[0][k])
                    elif k in predict_result.keys():
                        predict_result[k].append(float(info[0][k]))

                # real_actions.append(int(info[0]["real_action"]))
                # portfolio_value.append(int(info[0]["portfolio_value"]))
                # closed_trades_profit.append(int(info[0]["closed_trades_profit"]))
                # last_trade_profit.append(int(info[0]["last_trade_profit"]))
                # date.append(info[0]["date"])

            # real_actions.append(0)
            # portfolio_value.append(portfolio_value[-1])
            # closed_trades_profit.append(0)
            # last_trade_profit.append(0)
            # date.append(datetime.datetime.now())

            predict_df = pd.DataFrame(predict_result)
            print(predict_df)
            print('sum last_trade_gross_profit', np.sum(predict_df.last_trade_gross_profit))

            for i in range(train.shape[0]):
                # print("- " * 30)

                # print('Learn state_sum', np.sum(states_learn[i]), np.sum(statesx[i]))
                print(df_learn.action[i], predict_df.action[i], np.sum(states_learn[i]), np.sum(statesx[i]))

                # print('Learn state_sum', np.sum(states_learn[i]))
                # print(df_learn.loc[i, ['current_date', 'real_action', 'last_trade_gross_profit', 'market_price']])
                # print('')
                # print('Predict state_sum', np.sum(statesx[i]))
                # print(predict_df.loc[i, ['date', 'real_action', 'last_trade_gross_profit', 'market_price']])
                # time.sleep(1)

        #     predict_df = predict_df[10:].copy()
        #     predict_df['action'] = np.array(real_actions, dtype=int)
        #     predict_df['portfolio_value'] = np.array(portfolio_value, dtype=np.float64)
        #     predict_df['closed_trades_profit'] = np.array(closed_trades_profit, dtype=np.float64)
        #     predict_df['last_trade_profit'] = np.array(last_trade_profit, dtype=np.float64)
        #
        #     predict_df['date'] = pd.to_datetime(df['date'])
        #     predict_df.set_index('date', inplace=True)
        #
        #     predict_df.to_hdf(rl_path + "test_df", key='df', mode='w')
        #
        #     print(predict_df['portfolio_value'].describe())
        #     print(predict_df['last_trade_profit'].describe())
        #     print(predict_df['last_trade_profit'].sum())
        #
        #     # for i in range(len(last_trade_profit_memory)):
        #     #     print(last_trade_profit[i], ' - ', last_trade_profit_memory[i])
        #
        #     for i in range(len(real_actions)):
        #         print(current_date_memory[i], "/", real_actions[i], ' - ', date[i], "/", real_action_memory[i])
        #
        # visualizer = RLVisualizer(predict_df, symbol)
        # visualizer.show()



