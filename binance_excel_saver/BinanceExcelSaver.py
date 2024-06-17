import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from datetime import datetime


class BinanceExcelSaver:
    """
    A class to save Binance execution report, account update data, and generic dictionary data to different sheets in an Excel file with specified columns and data types.
    """
    # Define a dictionary to map short keys to their full meanings for execution reports
    binance_execution_key_mapping = {
        's': 'symbol',
        'T': 'event_time',
        'S': 'side',
        'o': 'order_type',
        'X': 'order_status',
        'l': 'last_executed_quantity',
        'L': 'last_executed_price',
        'n': 'commission_amount',
        'N': 'commission_asset'
    }

    # Define a dictionary to map short keys to their full meanings for account updates
    binance_account_key_mapping = {
        'T': 'transaction_time',
        'E': 'event_time',
        'a': 'account_update'
    }

    # Define the desired column order for execution reports
    desired_execution_columns = [
        'symbol', 'event_time', 'side', 'order_type', 'order_status',
        'last_executed_quantity', 'last_executed_price', 'last_executed_value',
        'commission_amount', 'commission_asset'
    ]

    # Define the desired column order for account updates
    desired_account_columns = [
        'transaction_time', 'event_time', 'asset', 'wallet_balance', 'cross_wallet_balance', 'balance_change', 'm'
    ]

    @staticmethod
    def convert_data_types(data, context):
        """
        Convert data types for numeric fields based on the context (execution or account).
        """
        if context == 'execution':
            conversions = {
                'event_time': lambda x: datetime.utcfromtimestamp(x / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'last_executed_quantity': float,
                'last_executed_price': float,
                'commission_amount': float
            }
        elif context == 'account':
            conversions = {
                'transaction_time': lambda x: datetime.utcfromtimestamp(x / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'event_time': lambda x: datetime.utcfromtimestamp(x / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'wallet_balance': float,
                'cross_wallet_balance': float,
                'balance_change': float
            }
        return {k: conversions.get(k, lambda v: v)(v) for k, v in data.items()}

    @classmethod
    def save_execution_report(cls, data, filename='data_transfer/ESM_settlement.xlsx'):
        """
        Save specific fields from execution report data to the 'trade_report' sheet in an Excel file.

        Parameters:
        data (dict): The data to be saved.
        filename (str): The name of the Excel file.
        """
        # Extract and map only the required fields
        filtered_data = {cls.binance_execution_key_mapping.get(k, k): v for k, v in data.items() if k in cls.binance_execution_key_mapping}

        # Convert data types for numeric fields
        filtered_data = cls.convert_data_types(filtered_data, 'execution')

        # Add the last_executed_value field
        if 'last_executed_quantity' in filtered_data and 'last_executed_price' in filtered_data:
            filtered_data['last_executed_value'] = (
                    filtered_data['last_executed_quantity'] * filtered_data['last_executed_price']
            )

        # Convert the dictionary to a DataFrame
        new_df = pd.DataFrame([filtered_data])

        # Set the column order
        new_df = new_df[cls.desired_execution_columns]

        cls.append_to_excel(new_df, filename, sheet_name='trade_report')

    @classmethod
    def save_account_update(cls, data, filename='data_transfer/ESM_settlement.xlsx'):
        """
        Save specific fields from account update data to the 'account_report' sheet in an Excel file.

        Parameters:
        data (dict): The data to be saved.
        filename (str): The name of the Excel file.
        """
        # Extract account update details
        account_update = data.get('a', {})
        balance_updates = account_update.get('B', [])

        rows = []
        for balance in balance_updates:
            # Prepare a row for each balance update
            row = {
                'transaction_time': data.get('T', None),
                'event_time': data.get('E', None),
                'asset': balance.get('a', ''),
                'wallet_balance': balance.get('wb', '0'),
                'cross_wallet_balance': balance.get('cw', '0'),
                'balance_change': balance.get('bc', '0'),
                'm': account_update.get('m', '')
            }
            # Convert data types for numeric fields
            row = cls.convert_data_types(row, 'account')
            rows.append(row)

        # Convert the rows to a DataFrame
        new_df = pd.DataFrame(rows)

        # Set the column order
        new_df = new_df[cls.desired_account_columns]

        cls.append_to_excel(new_df, filename, sheet_name='account_report')

    @staticmethod
    def append_to_excel(df, filename, sheet_name):
        """
        Append a DataFrame to an existing Excel sheet or create a new one if it doesn't exist.

        Parameters:
        df (DataFrame): The DataFrame to be appended.
        filename (str): The name of the Excel file.
        sheet_name (str): The name of the sheet to append to.
        """
        if os.path.exists(filename):
            book = load_workbook(filename)
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
                writer.workbook = book
                writer.worksheets = {ws.title: ws for ws in book.worksheets}
                if sheet_name in writer.sheets:
                    startrow = writer.sheets[sheet_name].max_row
                    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=False), start=startrow):
                        for c_idx, value in enumerate(row, 1):
                            writer.sheets[sheet_name].cell(row=r_idx + 1, column=c_idx, value=value)
                else:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                BinanceExcelSaver.auto_adjust_column_width(writer.sheets[sheet_name])
        else:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                BinanceExcelSaver.auto_adjust_column_width(writer.sheets[sheet_name])

    @classmethod
    def save_info_sheet(cls, data, filename='data_transfer/ESM_settlement.xlsx'):
        """
        Save dictionary data to the 'info' sheet in an Excel file, with each key-value pair in adjacent columns.
        If the value is a datetime in milliseconds, convert it to a human-readable format.

        Parameters:
        data (dict): The dictionary data to be saved.
        filename (str): The name of the Excel file.
        """
        # Convert datetime values to human-readable format
        info_data = {
            key: datetime.utcfromtimestamp(value / 1000).strftime('%Y-%m-%d %H:%M:%S') if isinstance(value, (int, float)) and key.endswith('time') else value
            for key, value in data.items()
        }

        # Convert to DataFrame with two columns: 'Key' and 'Value'
        info_df = pd.DataFrame([info_data])

        cls.append_info_to_excel(info_df, filename, sheet_name='info')

    @staticmethod
    def append_info_to_excel(df, filename, sheet_name):
        """
        Append info DataFrame to an existing Excel sheet or create a new one if it doesn't exist.

        Parameters:
        df (DataFrame): The DataFrame to be appended.
        filename (str): The name of the Excel file.
        sheet_name (str): The name of the sheet to append to.
        """
        if os.path.exists(filename):
            book = load_workbook(filename)
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
                writer.workbook = book
                writer.worksheets = {ws.title: ws for ws in book.worksheets}
                if sheet_name in writer.sheets:
                    startrow = writer.sheets[sheet_name].max_row
                    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=startrow):
                        for c_idx, value in enumerate(row, 1):
                            writer.sheets[sheet_name].cell(row=r_idx + 1, column=c_idx, value=value)
                else:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                BinanceExcelSaver.auto_adjust_column_width(writer.sheets[sheet_name])
        else:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                BinanceExcelSaver.auto_adjust_column_width(writer.sheets[sheet_name])

    @staticmethod
    def auto_adjust_column_width(sheet):
        """
        Adjust column width to fit the contents.

        Parameters:
        sheet (Worksheet): The worksheet to adjust column widths for.
        """
        for column in sheet.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = (max_length + 2)
            sheet.column_dimensions[column_letter].width = adjusted_width

    @classmethod
    def save_balance_data(cls, data, filename='data_transfer/ESM_settlement.xlsx'):
        balance_header = ['timestamp', 'asset', 'balance', 'crossWalletBalance', 'availableBalance', 'crossUnPnl', 'USDT_Value']

        # Current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Convert the data into a format suitable for DataFrame with timestamp
        rows = []
        for row in data:
            rows.append([timestamp] + [item[0] for item in row])

        balance_df = pd.DataFrame(rows, columns=balance_header)

        columns_to_convert = ['balance',
                              'crossWalletBalance',
                              'availableBalance',
                              'crossUnPnl',
                              'USDT_Value'
                              ]

        balance_df[columns_to_convert] = balance_df[columns_to_convert].astype(float)

        # Calculate the total USDT_Value
        # total_usdt_value = balance_df['USDT_Value'].astype(float).abs().sum()
        #
        # # Append a summary row
        # summary_row = pd.DataFrame([[timestamp, 'TOTAL', None, None, None, None, total_usdt_value]], columns=balance_header)
        # balance_df = pd.concat([balance_df, summary_row], ignore_index=True)

        # Create or overwrite the "Balance" sheet
        if os.path.exists(filename):
            book = load_workbook(filename)
            if "Balance" in book.sheetnames:
                del book["Balance"]
            book.save(filename)

        with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
            balance_df.to_excel(writer, sheet_name='Balance', index=False)
            BinanceExcelSaver.auto_adjust_column_width(writer.sheets['Balance'])

    @classmethod
    def save_positions_data(cls, data, filename='data_transfer/ESM_settlement.xlsx'):
        positions_header = [
            'timestamp', 'Symbol', 'Position', 'Entry Price', 'USDT_Enter_Value',
            'USDT_Market_Value', 'Unrealized PnL (USDT)'
        ]

        # Current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Convert the data into a format suitable for DataFrame with timestamp
        rows = []
        for row in data:
            rows.append([timestamp] + [item[0] for item in row])

        positions_df = pd.DataFrame(rows, columns=positions_header)

        columns_to_convert = ['Position',
                              'Entry Price',
                              'USDT_Enter_Value',
                              'USDT_Market_Value',
                              'Unrealized PnL (USDT)'
                              ]

        positions_df[columns_to_convert] = positions_df[columns_to_convert].astype(float)

        # # Calculate the totals for USDT_Enter_Value, USDT_Market_Value, Unrealized PnL (USDT)
        # total_usdt_enter_value = positions_df['USDT_Enter_Value'].sum()
        # total_usdt_market_value = positions_df['USDT_Market_Value'].sum()
        # total_unrealized_pnl = positions_df['Unrealized PnL (USDT)'].sum()
        #
        # # Append a summary row
        # summary_row = pd.DataFrame(
        #     [[timestamp, 'TOTAL', '', '', total_usdt_enter_value, total_usdt_market_value, total_unrealized_pnl]],
        #     columns=positions_header
        # )
        # positions_df = pd.concat([positions_df, summary_row], ignore_index=True)

        # Create or overwrite the "Positions" sheet
        if os.path.exists(filename):
            book = load_workbook(filename)
            if "Positions" in book.sheetnames:
                del book["Positions"]
            book.save(filename)

        with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
            positions_df.to_excel(writer, sheet_name='Positions', index=False)
            BinanceExcelSaver.auto_adjust_column_width(writer.sheets['Positions'])

if __name__ == "__main__":

    # Example usage for execution report:
    #
    # {'e': 'ORDER_TRADE_UPDATE', 'T': 1717873621785, 'E': 1717873621785,
    #
    #  'o': {
    #     's': 'AVAXUSDT',
    #      'c': 'YzK95WLgREO1hfLBbQyYHI',
    #      'S': 'SELL', 'o': 'MARKET', 'f': 'GTC', 'q': '1',
    #      'p': '0', 'ap': '32.5460', 'sp': '0', 'x': 'TRADE', 'X': 'FILLED',
    #     'i': 21519460598, 'l': '1', 'z': '1', 'L': '32.5460',
    #      'n': '0.00002133', 'N': 'BNB', 'T': 1717873621785,
    #      't': 808690180, 'b': '0', 'a': '0', 'm': False, 'R': False,
    #     'wt': 'CONTRACT_PRICE', 'ot': 'MARKET',
    #      'ps': 'BOTH', 'cp': False, 'rp': '0.02200000',
    #      'pP': False, 'si': 0, 'ss': 0,
    #      'V': 'NONE', 'pm': 'NONE', 'gtd': 0
    # }
    # }

    # execution_data = {
    #     'e': 'executionReport', 'E': 1707120960762, 's': 'ETHUSDT', 'c': 'oVoRofmTTXJCqnGNuvcuEu', 'S': 'BUY',
    #     'o': 'MARKET', 'f': 'GTC', 'q': '0.00220000', 'p': '0.00000000', 'P': '0.00000000', 'F': '0.00000000',
    #     'g': -1, 'C': '', 'x': 'TRADE', 'X': 'FILLED', 'r': 'NONE', 'i': 15859894465, 'l': '0.00220000',
    #     'z': '0.00220000', 'L': '2319.53000000', 'n': '0.00000220', 'N': 'ETH', 'T': 1707120960761,
    #     't': 1297224255, 'I': 33028455025, 'w': False, 'm': False, 'M': True, 'O': 1707120960761,
    #     'Z': '5.10296600', 'Y': '5.10296600', 'Q': '0.00000000', 'W': 1707120960761, 'V': 'EXPIRE_MAKER'
    # }

    # execution_data = {
    #     's': 'AVAXUSDT',
    #     'c': 'YzK95WLgREO1hfLBbQyYHI',
    #     'S': 'SELL', 'o': 'MARKET', 'f': 'GTC', 'q': '1',
    #     'p': '0', 'ap': '32.5460', 'sp': '0', 'x': 'TRADE', 'X': 'FILLED',
    #     'i': 21519460598, 'l': '1', 'z': '1', 'L': '32.5460',
    #     'n': '0.00002133', 'N': 'BNB', 'T': 1717873621785,
    #     't': 808690180, 'b': '0', 'a': '0', 'm': False, 'R': False,
    #     'wt': 'CONTRACT_PRICE', 'ot': 'MARKET',
    #     'ps': 'BOTH', 'cp': False, 'rp': '0.02200000',
    #     'pP': False, 'si': 0, 'ss': 0,
    #     'V': 'NONE', 'pm': 'NONE', 'gtd': 0
    # }
    #
    # BinanceExcelSaver.save_execution_report(execution_data, 'binance_data.xlsx')
    #
    # # Example usage for account update:
    # account_data = {
    #     'e': 'ACCOUNT_UPDATE', 'T': 1717804802111, 'E': 1717804802112,
    #     'a': {
    #         'B': [{
    #             'a': 'USDT',
    #             'wb': '201.39221840',
    #             'cw': '201.39221840',
    #             'bc': '0.00335157'
    #         }],
    #         'P': [],
    #         'm': 'FUNDING_FEE'
    #     }
    # }
    #
    # BinanceExcelSaver.save_account_update(account_data, 'binance_data.xlsx')
    #
    # # Example usage for info sheet:
    # info_data = {
    #     'start_time': 1707120960762,
    #     'end_time': 1707121960762,
    #     'description': 'Sample info data'
    # }

    data = [
        [["BTC"], [0.1], [22], [33], [44], [55]],
        [["ETH"], [0.1], [22], [33], [44], [55]],
        [["BNB"], [0.1], [22], [33], [44], [55]]
    ]
    BinanceExcelSaver.save_balance_data(data)

    data = [
        [["BTC"], [-100], [30000], [30000], [35000], [5000]],
        [["ETH"], [+200], [2000], [20000], [22000], [2000]],
        [["BNB"], [-12], [300], [15000], [18000], [3000]]
    ]

    BinanceExcelSaver.save_positions_data(data)


