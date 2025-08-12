from ib_async import *
import pandas as pd
import time


def get_complete_option_chain_sync(symbol, num_strikes=10):
    """동기 방식으로 옵션 체인 가져오기"""

    # 연결
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=2)

    # 주식 정보
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)

    # 옵션 매개변수 가져오기
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)

    option_data = []

    for chain in chains[:1]:  # 첫 번째 체인만
        expiry = chain.expirations[0]  # 첫 번째 만료일

        # 행사가격 중 중간 부근 선택
        strikes = sorted(chain.strikes)
        mid_idx = len(strikes) // 2
        selected_strikes = strikes[mid_idx - num_strikes // 2:mid_idx + num_strikes // 2]

        print(f"Processing {len(selected_strikes)} strikes for {expiry}")

        for strike in selected_strikes:
            # 콜 옵션
            call = Option(symbol, expiry, strike, 'C', 'SMART')
            call_data = get_option_details(ib, call, 'CALL')
            if call_data:
                option_data.append(call_data)

            # 풋 옵션  
            put = Option(symbol, expiry, strike, 'P', 'SMART')
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
        ticker = ib.reqMktData(option, '104,105,106,100,101', False, False)
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
            'open_interest': getattr(ticker, 'openInterest', None),
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
print(calls_df[['strike', 'bid', 'ask', 'volume', 'delta', 'gamma', 'theta', 'vega', 'iv']].to_string(index=False))

print("\n=== PUT OPTIONS ===")
print(puts_df[['strike', 'bid', 'ask', 'volume', 'delta', 'gamma', 'theta', 'vega', 'iv']].to_string(index=False))