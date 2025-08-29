import csv
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
import pandas as pd
from .logger import get_logger

logger = get_logger("CSV_LOGGER")

class CSVTradeLogger:
    """
    CSV Logger for trading activities and account summaries.
    Creates daily trade logs and maintains a persistent summary log.
    """
    
    def __init__(self, csv_directory: str = "csv"):
        self.csv_directory = Path(csv_directory)
        self.daily_logs_dir = self.csv_directory / "daily_logs"
        self.summary_file = self.csv_directory / "trading-summary.csv"
        
        # Ensure directories exist
        self.daily_logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize summary file if it doesn't exist
        self._initialize_summary_file()
        
        # Track current trading day
        self._current_trading_day = None
        self._daily_trade_log_file = None
        
        logger.info(f"CSV Logger initialized. Daily logs: {self.daily_logs_dir}, Summary: {self.summary_file}")
    
    def _initialize_summary_file(self):
        """Initialize the trading summary CSV file with headers if it doesn't exist."""
        if not self.summary_file.exists():
            headers = [
                'Date', 'Total Balance (CAD)', 'Daily PnL', 'Starting Balance', 
                'High water mark', 'Profitable Trades', 'Profit Amount', 
                'Loss Trades', 'Loss Amount'
            ]
            
            try:
                with open(self.summary_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                logger.info(f"Created new trading summary file: {self.summary_file}")
            except Exception as e:
                logger.error(f"Failed to create trading summary file: {e}")
    
    def _get_daily_log_filename(self, trading_date: date) -> str:
        """Generate daily log filename in the format TradingLog-YYYY-MM-DD.csv."""
        return f"TradingLog-{trading_date.strftime('%Y-%m-%d')}.csv"
    
    def _ensure_daily_log_file(self, trading_date: date):
        """Ensure the daily trade log file exists and has proper headers."""
        if self._current_trading_day != trading_date:
            self._current_trading_day = trading_date
            self._daily_trade_log_file = self.daily_logs_dir / self._get_daily_log_filename(trading_date)
            
            # Create file with headers if it doesn't exist
            if not self._daily_trade_log_file.exists():
                headers = [
                    'Timestamp', 'Trade Type', 'Right', 'ConId', 'Strike', 'Expiry',
                    'Quantity', 'Price', 'PnL', 'Outcome', 'OrderId'
                ]
                
                try:
                    with open(self._daily_trade_log_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(headers)
                    logger.info(f"Created new daily trade log: {self._daily_trade_log_file}")
                except Exception as e:
                    logger.error(f"Failed to create daily trade log file: {e}")
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """
        Log a trade execution to the daily trade log.
        
        Args:
            trade_data: Dictionary containing trade information with keys:
                - timestamp: datetime of trade execution
                - trade_type: 'BUY' or 'SELL'
                - right: 'C' for call, 'P' for put
                - con_id: Contract ID
                - strike: Strike price
                - expiry: Expiration date (YYYYMMDD format)
                - quantity: Number of contracts
                - price: Execution price
                - pnl: Profit/Loss (0 for buys)
                - outcome: 'Profit', 'Loss', or empty string
                - order_id: Order ID
        """
        try:
            # Extract trading date from timestamp
            if isinstance(trade_data['timestamp'], str):
                trading_date = datetime.fromisoformat(trade_data['timestamp']).date()
            else:
                trading_date = trade_data['timestamp'].date()
            
            # Ensure daily log file exists
            self._ensure_daily_log_file(trading_date)
            
            # Prepare row data
            row = [
                trade_data.get('timestamp', ''),
                trade_data.get('trade_type', ''),
                trade_data.get('right', ''),
                trade_data.get('con_id', ''),
                trade_data.get('strike', ''),
                trade_data.get('expiry', ''),
                trade_data.get('quantity', ''),
                trade_data.get('price', ''),
                trade_data.get('pnl', ''),
                trade_data.get('outcome', ''),
                trade_data.get('order_id', '')
            ]
            
            # Write to daily log
            with open(self._daily_trade_log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            logger.debug(f"Logged trade to daily log: {trade_data.get('trade_type')} {trade_data.get('right')} {trade_data.get('strike')}")
            
        except Exception as e:
            logger.error(f"Failed to log trade to CSV: {e}")
    
    def log_account_summary(self, account_data: Dict[str, Any], trading_date: date):
        """
        Log account summary to the trading summary CSV.
        Updates existing entry for the day or creates new one.
        
        Args:
            account_data: Dictionary containing account information
            trading_date: Date for the summary entry
        """
        try:
            # Read existing summary data
            existing_data = {}
            if self.summary_file.exists():
                try:
                    df = pd.read_csv(self.summary_file)
                    existing_data = df.set_index('Date').to_dict('index')
                except Exception as e:
                    logger.warning(f"Could not read existing summary file: {e}")
            
            # Prepare new summary row
            date_str = trading_date.strftime('%Y-%m-%d')
            logger.debug(f"Account Data: {account_data}")
            new_summary = {
                'Date': date_str,
                'Total Balance (CAD)': account_data.get('NetLiquidation', 0),
                'Daily PnL': account_data.get('DailyPnL', 0),
                'Starting Balance': account_data.get('StartingValue', 0),
                'High water mark': account_data.get('HighWaterMark', 0),
                'Profitable Trades': account_data.get('ProfitableTrades', 0),
                'Profit Amount': account_data.get('ProfitAmount', 0),
                'Loss Trades': account_data.get('LossTrades', 0),
                'Loss Amount': account_data.get('LossAmount', 0)
            }
            
            # Update existing data or add new entry
            existing_data[date_str] = new_summary
            
            # Write updated summary back to file
            df = pd.DataFrame.from_dict(existing_data, orient='index')
            df = df.reset_index(drop=True)  # Remove the index column
            df.to_csv(self.summary_file, index=False)
            
            logger.info(f"Updated trading summary for {date_str}")
            
        except Exception as e:
            logger.error(f"Failed to log account summary to CSV: {e}")
    
    def get_daily_trades(self, trading_date: date) -> List[Dict[str, Any]]:
        """
        Retrieve all trades for a specific trading day.
        
        Args:
            trading_date: Date to retrieve trades for
            
        Returns:
            List of trade dictionaries
        """
        try:
            daily_log_file = self.daily_logs_dir / self._get_daily_log_filename(trading_date)
            
            if not daily_log_file.exists():
                return []
            
            trades = []
            with open(daily_log_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trades.append(row)
            
            return trades
            
        except Exception as e:
            logger.error(f"Failed to read daily trades: {e}")
            return []
    
    def get_trading_summary(self) -> pd.DataFrame:
        """
        Retrieve the complete trading summary.
        
        Returns:
            DataFrame containing all trading summaries
        """
        try:
            if not self.summary_file.exists():
                return pd.DataFrame()
            
            return pd.read_csv(self.summary_file)
            
        except Exception as e:
            logger.error(f"Failed to read trading summary: {e}")
            return pd.DataFrame()
