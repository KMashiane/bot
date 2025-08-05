import pandas as pd
from binance.client import Client
from binance.enums import *
import talib # For moving average calculation

# --- Step 1: Set up Binance API Client ---
api_key = ''
api_secret = ''
client = Client(api_key, api_secret)

# --- Step 2: Fetch Historical Candlestick Data ---
def get_historical_klines(symbol, interval, start_str):
    """
    Fetches historical candlestick data from the Binance API.
    
    Args:
        symbol (str): The trading pair (e.g., 'POLUSDT').
        interval (str): The candlestick time frame (e.g., '1h' for 1 hour).
        start_str (str): The start date for the data (e.g., '1 Jan, 2024').

    Returns:
        pd.DataFrame: A DataFrame with the candlestick data.
    """
    print(f"Fetching historical data for {symbol} from {start_str}...")
    klines = client.get_historical_klines(symbol, interval, start_str)
    
    df = pd.DataFrame(klines, columns=['open_time', 'Open', 'High', 'Low', 'Close', 'Volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = pd.to_numeric(df[col])
    
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('open_time', inplace=True)
    
    print("Data fetched successfully.")
    return df

# --- Step 3: Define the Candlestick Pattern Logic with Filters ---

def check_engulfing_pattern(df, index):
    """
    Checks for a bullish or bearish engulfing pattern with trend and volume confirmation.
    
    Args:
        df (pd.DataFrame): The candlestick data.
        index (int): The index of the current candle to check.

    Returns:
        str: 'bullish' if a valid bullish signal is found, 'bearish' for a bearish signal,
             otherwise returns None.
    """
    if index < 20: 
        return None
        
    current_candle = df.iloc[index]
    previous_candle = df.iloc[index - 1]

    # Check basic engulfing criteria for both types
    previous_is_bearish = previous_candle['Close'] < previous_candle['Open']
    current_is_bullish = current_candle['Close'] > current_candle['Open']
    
    previous_is_bullish = previous_candle['Close'] > previous_candle['Open']
    current_is_bearish = current_candle['Close'] < current_candle['Open']
    
    body_size_p2 = abs(current_candle['Close'] - current_candle['Open'])
    body_size_p1 = abs(previous_candle['Close'] - previous_candle['Open'])
    p2_body_larger = body_size_p2 > body_size_p1

    # Check for Volume Confirmation
    volume_period = 10
    avg_volume = df['Volume'].iloc[index - volume_period:index].mean()
    is_volume_confirmed = current_candle['Volume'] > avg_volume

    # Check for Trend Confirmation (using a simple moving average)
    ma_period = 20
    sma = talib.SMA(df['Close'], timeperiod=ma_period)
    is_in_uptrend = current_candle['Close'] > sma.iloc[index]
    is_in_downtrend = current_candle['Close'] < sma.iloc[index]

    # Bullish Engulfing Pattern
    # P1 is bearish, P2 is bullish, P2's body engulfs P1, P2 body is larger, volume is confirmed, and is in a downtrend.
    bullish_engulfs = (current_candle['Close'] > previous_candle['Open']) and \
                      (current_candle['Open'] < previous_candle['Close'])
                      
    is_bullish_pattern = previous_is_bearish and current_is_bullish and bullish_engulfs and p2_body_larger and is_volume_confirmed and is_in_downtrend
    
    if is_bullish_pattern:
        return 'bullish'

    # Bearish Engulfing Pattern
    # P1 is bullish, P2 is bearish, P2's body engulfs P1, P2 body is larger, volume is confirmed, and is in an uptrend.
    bearish_engulfs = (current_candle['Close'] < previous_candle['Open']) and \
                      (current_candle['Open'] > previous_candle['Close'])
    
    is_bearish_pattern = previous_is_bullish and current_is_bearish and bearish_engulfs and p2_body_larger and is_volume_confirmed and is_in_uptrend
    
    if is_bearish_pattern:
        return 'bearish'
        
    return None

# --- Step 4: Integrate a Trading Strategy for both Long and Short Positions ---

def simulated_trading_logic(df, initial_capital, risk_per_trade_pct, profit_target_pct):
    """
    Simulates a trading strategy for both long and short positions with risk management.
    
    Args:
        df (pd.DataFrame): The candlestick data.
        initial_capital (float): The starting capital.
        risk_per_trade_pct (float): The percentage of capital to risk per trade (e.g., 0.01 for 1%).
        profit_target_pct (float): The percentage profit at which to exit a trade.
    """
    capital = initial_capital
    position_open = False
    position_type = None # 'long' or 'short'
    
    print(f"Starting simulation with an initial capital of ${capital:.2f}")

    for i in range(1, len(df)):
        current_candle = df.iloc[i]
        
        if position_open:
            if position_type == 'long':
                # Check take-profit for a long position
                if current_candle['High'] >= take_profit_price:
                    capital += position_size * profit_target_pct
                    position_open = False
                    print(f"Time {df.index[i]}: LONG TAKE-PROFIT HIT! New capital: ${capital:.2f}")
                
                # Check stop-loss for a long position
                elif current_candle['Low'] <= stop_loss_price:
                    capital -= (entry_price - stop_loss_price) / entry_price * position_size
                    position_open = False
                    print(f"Time {df.index[i]}: LONG STOP-LOSS HIT! New capital: ${capital:.2f}")
            
            elif position_type == 'short':
                # Check take-profit for a short position
                if current_candle['Low'] <= take_profit_price:
                    capital += (entry_price - take_profit_price) / entry_price * position_size
                    position_open = False
                    print(f"Time {df.index[i]}: SHORT TAKE-PROFIT HIT! New capital: ${capital:.2f}")
                
                # Check stop-loss for a short position
                elif current_candle['High'] >= stop_loss_price:
                    capital -= (stop_loss_price - entry_price) / entry_price * position_size
                    position_open = False
                    print(f"Time {df.index[i]}: SHORT STOP-LOSS HIT! New capital: ${capital:.2f}")
        
        else: # No position is open
            signal = check_engulfing_pattern(df, i)
            
            if signal == 'bullish':
                print(f"Time {df.index[i]}: Valid BULLISH engulfing pattern detected!")
                entry_price = current_candle['Close']
                
                # Stop-loss placement for long position
                previous_candle = df.iloc[i-1]
                stop_loss_price = min(current_candle['Low'], previous_candle['Low'])
                
                # Position Sizing
                risk_amount = capital * risk_per_trade_pct
                stop_loss_distance = entry_price - stop_loss_price
                
                if stop_loss_distance > 0:
                    position_size = risk_amount / stop_loss_distance
                    take_profit_price = entry_price * (1 + profit_target_pct)
                    position_open = True
                    position_type = 'long'
                    print(f"Time {df.index[i]}: Opening LONG position. Entry: ${entry_price:.4f}, Stop-Loss: ${stop_loss_price:.4f}, Take-Profit: ${take_profit_price:.4f}")
            
            elif signal == 'bearish':
                print(f"Time {df.index[i]}: Valid BEARISH engulfing pattern detected!")
                entry_price = current_candle['Close']
                
                # Stop-loss placement for short position
                previous_candle = df.iloc[i-1]
                stop_loss_price = max(current_candle['High'], previous_candle['High'])
                
                # Position Sizing
                risk_amount = capital * risk_per_trade_pct
                stop_loss_distance = stop_loss_price - entry_price
                
                if stop_loss_distance > 0:
                    position_size = risk_amount / stop_loss_distance
                    take_profit_price = entry_price * (1 - profit_target_pct)
                    position_open = True
                    position_type = 'short'
                    print(f"Time {df.index[i]}: Opening SHORT position. Entry: ${entry_price:.4f}, Stop-Loss: ${stop_loss_price:.4f}, Take-Profit: ${take_profit_price:.4f}")

    if position_open:
        print(f"Simulation ended with an open {position_type} position. For a real bot, this would be closed.")
        # Logic for closing the final position could be added here
    
    print(f"\nSimulation finished. Final capital: ${capital:.2f}")

# --- Step 5: Run the Simulation with Real Data ---
if __name__ == "__main__":
    historical_data = get_historical_klines("POLUSDT", Client.KLINE_INTERVAL_1HOUR, "30 day ago UTC")
    
    if not historical_data.empty:
        initial_capital = 1000
        risk_per_trade_pct = 0.01 
        profit_target_pct = 0.02 
        
        simulated_trading_logic(historical_data, initial_capital, risk_per_trade_pct, profit_target_pct)
    else:
        print("Failed to fetch historical data. Please check the symbol and API settings.")

