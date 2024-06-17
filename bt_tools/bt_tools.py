import os
from pathlib import Path
import json
import requests
from typing import Callable, Tuple
import time
from datetime import datetime, timedelta
import threading
import pandas as pd
from prettytable import PrettyTable

from binance.client import Client
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class TaskScheduler:
    def __init__(self, tasks: Tuple[Tuple[datetime, Callable]], set_life_signal=object):
        self.tasks = tasks
        self.scheduler_thread = threading.Thread(target=self.run, daemon=True)
        self.logger = Logger()
        self.log = self.logger.log
        self.set_life_signal = set_life_signal

    def calculate_next_delay(self):
        now = datetime.now()
        future_tasks = [task for task in self.tasks if task[0] > now]
        if not future_tasks:
            return None, None
        next_task = min(future_tasks, key=lambda task: task[0])
        return (next_task[0] - now).total_seconds(), next_task[1]

    def run(self):
        while True:
            self.set_life_signal(key="TaskScheduler",
                                 cclass="EmaShiftMultiStrategy",
                                 method="run",
                                 msg1="",
                                 msg2="",
                                 msg3=""
                                 )
            delay, next_method = self.calculate_next_delay()
            if delay is None:
                break  # No future tasks
            time.sleep(delay)
            next_method()
            self.update_next_time()

    def update_next_time(self):
        now = datetime.now()
        for task in self.tasks:
            if task[0] <= now:
                # Move the datetime to the next day if it's a daily schedule; adjust as needed
                task[0] = task[0] + timedelta(days=1)

    def start(self):
        self.log(f"Task scheduler started.", level=10)
        self.scheduler_thread.start()


class GoogleDriveConnect:
    def __init__(self, scopes=None):
        if scopes is None:
            scopes = ['https://www.googleapis.com/auth/drive.file']
        self.folder_id = "1XAdfXaTAdOkE3sFAFDDbW8ctiTDfmyax"
        self.scopes = scopes
        self.creds = None
        self.service = None
        self.logger = Logger()
        self.log = self.logger.log
        self.root_dit = ""
        self.get_project_root()
        # self.service_account_file = self.root_dit + r'/tokens/thematic-answer-426211-f7-e010f5445c30.json'
        self.service_account_file = r'tokens/thematic-answer-426211-f7-e010f5445c30.json'

    def authenticate(self):
        self.creds = Credentials.from_service_account_file(
            self.service_account_file,
            scopes=self.scopes
        )
        self.service = build('drive', 'v3', credentials=self.creds)

    def get_project_root(self):
        self.root_dit = f'{Path(__file__).parent.parent}'
        print()

    def upload_file(self, file_name):
        self.authenticate()
        file_name = self.root_dit + file_name
        if self.service is None:
            self.log("GoogleDriveConnect -> Service not initialized. Call authenticate() first.")
        file_metadata = {
            'name': os.path.basename(file_name),
            'parents': [self.folder_id]
        }
        media = MediaFileUpload(file_name, resumable=True)
        try:
            self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            # self.log(f'File ID: {file.get("id")}')
        except Exception as e:
            self.log(f'GoogleDriveConnect -> An error occurred: {e}')

    def list_files_in_folder(self):
        query = f"'{self.folder_id}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageSize=100
        ).execute()

        files = results.get('files', [])
        if not files:
            self.log('No files found.')
        else:
            self.log('Files:')
            for file in files:
                self.log(f"Name: {file.get('name')}, ID: {file.get('id')}")

    def delete_file_in_folder(self, file_name):
        self.authenticate()
        query = f"'{self.folder_id}' in parents and name='{file_name}' and trashed=false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)'
        ).execute()

        files = results.get('files', [])
        if not files:
            self.log(f'File "{file_name}" not found in folder "{self.folder_id}".', 10)
        else:
            for file in files:
                self.service.files().delete(fileId=file.get('id')).execute()
                # print(f'File "{file.get("name")}" with ID "{file.get("id")}" deleted from folder "{folder_id}".')


# Example usage:
# uploader = GoogleDriveUploader(service_account_file=SERVICE_ACCOUNT_FILE)
# uploader.authenticate()
# uploader.upload_file('path/to/your/file.txt', folder_id='your-folder-id')
# uploader.delete_file('file.txt', folder_id='your-folder-id')


class LifeSignal:
    def __init__(self):
        self.life_sinals = {}
        self.logger = Logger()
        self.log = self.logger.log
        self.log(f"Life Signal Monitor started.", level=10)

    def save_life_signals(self):

        self.delete_file()
        self.set_life_signal(key="LifeSignal1",
                             cclass="LifeSignal",
                             method="life_data_loop",
                             msg1="",
                             msg2="",
                             msg3=""
                             )
        self.print_to_file()

    @staticmethod
    def delete_file():
        file_path = "data_transfer/life_signals.txt"
        try:
            os.remove(file_path)
        except:
            pass

    def print_to_file(self, file_path="data_transfer/life_signals.txt"):

        table = PrettyTable()
        table.title = "Life Status Signals"
        table.field_names = ["Datetime",
                             "Class",
                             "Method",
                             "Message 1",
                             "Message 2",
                             "Message 3"]

        table.align["Datetime"] = "l"
        table.align["Class"] = "l"
        table.align["Method"] = "l"
        table.align["Message 1"] = "l"
        table.align["Message 2"] = "l"
        table.align["Message 3"] = "l"

        for k in self.life_sinals:
            item = self.life_sinals[k]

            table.add_row([item[0],
                           item[1],
                           item[2],
                           item[3],
                           item[4],
                           item[5]
                           ])

        try:
            with open(file_path, 'a') as file:
                file.write(table.get_string())
        except Exception as e:
            self.log(f"An error occurred: {e}", level=10)

    def set_life_signal(self, key, cclass="", method="", msg1="", msg2="", msg3=""):
        self.life_sinals[key] = [datetime.now().strftime('%Y.%m.%d_%H:%M:%S'),
                                 str(cclass),
                                 str(method),
                                 str(msg1),
                                 str(msg2),
                                 str(msg3)]


class Logger:
    def __init__(self, log_level=6, log_file='ESMLog.txt'):
        self.log_level = log_level
        self.log_file = log_file

    def log(self, *texts, level=1, output_mode='screen'):
        if level >= self.log_level:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            message = f"{timestamp} ->   {' '.join(map(str, texts))}"
            if output_mode == 'screen':
                print(message)
            elif output_mode == 'text':
                with open(self.log_file, 'a') as file:
                    file.write(message + '\n')


# def yahoo_download(symbol, from_dt, back_shift, refresh=False, interval='1h'):
#     return yf.download(symbol, start=from_dt, interval=interval, auto_adjust=True)


def df_check(df, del_duplicates=False):
    print("Data qualtiy check:")
    print("                    first         -    last")
    print("   datetime: ", df.index[0], "-", df.index[-1])
    print("   close:    ", df.close.iloc[0], "              -", df.close.iloc[0])

    duplicates = df.index.duplicated()
    if duplicates.any():
        print("   Duplicates:")
        duplicated_indices = df.index[duplicates]

        if not duplicated_indices.empty:
            duplicated_rows = df.loc[duplicated_indices]
            print('   ',duplicated_rows)

    else:
        print("   No duplicates.")

    full_range = pd.date_range(start=df.index.min(), end=df.index.max(), freq='h')
    missing_hours = full_range.difference(df.index)
    if not missing_hours.empty:
        print("   Missing rows:")
        for missing in missing_hours:
            before = df[df.index < missing].iloc[-1]
            after = df[df.index > missing].iloc[0]
            print(f"   Before missing data: ({before.name}): {before.to_dict()}")
            print(f"   After missing data:  ({after.name}): {after.to_dict()}")

    else:
        print("   No missing row.")

    if del_duplicates:
        print("   Delete duplicated datas.")
        duplicate_mask = df[['open', 'high', 'low', 'close']].eq(df[['open', 'high', 'low', 'close']].shift())
        print(df[duplicate_mask.all(axis=1)])

        # Drop duplicate rows
        print(df.shape)
        df = df[~(duplicate_mask.all(axis=1))]
        print(df.shape)
    return df


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

        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
                                           'taker_buy_quote_asset_volume', 'ignore'])

        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df[['datetime', 'timestamp', 'open', 'high', 'low', 'close', 'volume']]
        df.set_index('datetime', inplace=True)

        df.open = df.open.astype("float64")
        df.high = df.high.astype("float64")
        df.low = df.low.astype("float64")
        df.close = df.close.astype("float64")
        df.volume = df.volume.astype("float64")
        df['adj_close'] = df['close']
        df.to_hdf(file_name, key='df', mode='w')

    if cutoff_dt:
        print("   Cut off from:", cutoff_dt)
        cutoff_dt = pd.Timestamp(cutoff_dt.strftime("%Y-%m-%d %H:%M:%S"), unit='ms')
        df = df[df.index <= cutoff_dt]

    return df


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


def get_futures_positions(client, is_print=False, is_return_array=False):
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
    ret_array = []
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

        ret_array.append([
            [symbol],
            [position_amt],
            [entry_price],
            [USDT_Enter_Value],
            [USDT_Value],
            [unrealized_pnl]
        ])

    table.add_row([
        "TOTAL:",
        "",
        "",
        "",
        market_value,
        round(total_unrealized_pnl, 4),
        ])

    ret_array.append([
        ["TOTAL:"],
        [None],
        [None],
        [None],
        [market_value],
        [round(total_unrealized_pnl, 4)]
    ])

    if is_print:
        log("\n",table, level=10)
    if is_return_array:
        return ret_array
    else:
        return ret_position, ret_price, market_value


def get_asset_balance(client, asset, is_print=False, is_return_array=False):
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
    ret_array = []
    total_crossUnPnl = 0.0
    total_USDT_Value = 0.0
    for item in data:
        if float(item['crossWalletBalance']) != 0 or float(item['balance']) != 0:
            if item['asset'] == "USDT":
                USDT_Value = round(float(item['availableBalance']) ,4)
            else:
                USDT_Value = round(get_futures_ticker(client, item['asset']) * float(item['availableBalance']), 4)

            table.add_row([item['asset'],
                           item['balance'],
                           item['crossWalletBalance'],
                           item['availableBalance'],
                           item['crossUnPnl'],
                           USDT_Value
                           ])
            total_crossUnPnl += float(item['crossUnPnl'])
            total_USDT_Value += USDT_Value

            ret_array.append([
                [item['asset']],
                [item['balance']],
                [item['crossWalletBalance']],
                [item['availableBalance']],
                [item['crossUnPnl']],
                [USDT_Value]
            ])
            if item['asset'] == asset:
                ret_asset = float(item['availableBalance'])
            if item['asset'] == "BNB":
                ret_BNB = float(item['availableBalance'])
            else:
                ret_other[item['asset']] = float(item['availableBalance'])

    table.add_row([
        "TOTAL:",
        "",
        "",
        "",
        round(total_crossUnPnl, 4),
        round(total_USDT_Value, 4)
    ])

    ret_array.append([
        ["Total:"],
        [None],
        [None],
        [None],
        [round(total_crossUnPnl, 4)],
        [round(total_USDT_Value, 4)]
    ])

    if is_print:
        log("\n", table.get_string(), level=10)
    if is_return_array:
        return ret_array
    else:
        return ret_asset, ret_BNB, ret_other



if __name__ == "__main__":

    gdc = GoogleDriveConnect()
    # gdc.list_files_in_folder()
    gdc.delete_file_in_folder("ESM_settlement.xlsx")
    gdc.upload_file(r'\data_transfer\data.xlsx')





