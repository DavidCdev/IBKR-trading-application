from ib_async import *
import pandas as pd
import time


def get_complete_option_chain_sync(option_symbol, num_strikes=10):

    # 연결
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=2)
    strike = 636.0
    option_symbol = 'SPY'
    stock = Stock(option_symbol, 'SMART', 'USD')
    stock_qualified = ib.qualifyContracts(stock)
    print(f"Stock qualified: {stock_qualified}")
    stock_qualified = stock_qualified[0]
    # 옵션 매개변수 가져오기
    chains = ib.reqSecDefOptParams(stock_qualified.symbol, '', stock_qualified.secType, stock_qualified.conId)
    chain = chains[0]
    option_data = []
    expirations = sorted(chain.expirations)[:3]  # Get first 3 expirations
    expiry = expirations[0]

    call = Option(option_symbol, expiry, strike, 'C', 'SMART')
    call_data = get_option_details(ib, call, 'CALL')
    if call_data:
        option_data.append(call_data)

    # 풋 옵션
    put = Option(option_symbol, expiry, strike, 'P', 'SMART')
    put_data = get_option_details(ib, put, 'PUT')
    if put_data:
        option_data.append(put_data)

    time.sleep(0.1)  # API 제한 방지

    ib.disconnect()
    return option_data


def get_option_details(ib, option, option_type):
    """개별 옵션의 상세 정보 가져오기"""
    try:
        ib.qualifyContracts(option)

        # 시장 데이터 요청
        ticker = ib.reqMktData(option, '', False, False)
        ib.sleep(1)  # 데이터 대기

        # Greeks 요청
        ticker = ib.reqMktData(option, '100,101,104,106', False, False)
        ib.sleep(1)
        data = {
            'type': option_type,
            'symbol': option.symbol,
            'expiry': option.lastTradeDateOrContractMonth,
            'strike': option.strike,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'last': ticker.last,
            'volume': ticker.volume,
            'Call_Open_Interest': getattr(ticker, 'callOpenInterest', 0),
            'Put_Open_Interest': getattr(ticker, 'putOpenInterest', 0),
            'delta': getattr(ticker.modelGreeks, 'delta', None) if ticker.modelGreeks else None,
            'gamma': getattr(ticker.modelGreeks, 'gamma', None) if ticker.modelGreeks else None,
            'theta': getattr(ticker.modelGreeks, 'theta', None) if ticker.modelGreeks else None,
            'vega': getattr(ticker.modelGreeks, 'vega', None) if ticker.modelGreeks else None,
            'iv': getattr(ticker.modelGreeks, 'impliedVol',
                          None) * 100 if ticker.modelGreeks and ticker.modelGreeks.impliedVol else None
        }

        ib.cancelMktData(option)
        return data

    except Exception as e:
        print(f"Error getting data for {option}: {e}")
        return None


# 실행
option_data = get_complete_option_chain_sync('SPY', num_strikes=10)

# DataFrame으로 변환 및 출력
df = pd.DataFrame(option_data)
calls_df = df[df['type'] == 'CALL'].sort_values('strike')
puts_df = df[df['type'] == 'PUT'].sort_values('strike')

print("\n=== CALL OPTIONS ===")
print(calls_df[['strike', 'bid', 'ask', 'volume', 'delta', 'gamma', 'theta', 'vega', 'iv', 'Call_Open_Interest', 'Put_Open_Interest']].to_string(index=False))

print("\n=== PUT OPTIONS ===")
print(puts_df[['strike', 'bid', 'ask', 'volume', 'delta', 'gamma', 'theta', 'vega', 'iv', 'Call_Open_Interest', 'Put_Open_Interest']].to_string(index=False))