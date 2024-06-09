import yfinance as yf
import pandas as pd
import os
from binance.client import Client


def yahoo_download(symbol, from_dt, back_shift, refresh=False, interval='1h'):
    return yf.download(symbol, start=from_dt, interval=interval, auto_adjust=True)


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
