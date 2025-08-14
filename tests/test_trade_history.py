from ib_async import *
from collections import defaultdict, deque
from datetime import datetime, date

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)


def get_today_option_executions(symbol='SPY'):
    executions = ib.reqExecutions()
    today = date.today()
    trades = []

    for trade in executions:
        exec_date = trade.execution.time.astimezone().date()
        contract = trade.contract

        if (
            exec_date == today and
            contract.secType == 'OPT' and
            contract.symbol == symbol and
            contract.right in ['C', 'P']
        ):
            trades.append(trade)

    return trades


def match_trades_and_calculate_pnl(trades):
    open_positions = defaultdict(deque)  # {contract key: deque of fills}
    closed_trades = []

    for trade in trades:
        contract = trade.contract
        exec = trade.execution
        side = exec.side.upper()  # BOT or SLD
        quantity = exec.shares
        price = exec.price
        time = exec.time
        multiplier = int(contract.multiplier) if contract.multiplier else 100
        key = (contract.symbol, contract.lastTradeDateOrContractMonth,
               contract.strike, contract.right)

        position = {
            'time': time,
            'side': side,
            'qty': quantity,
            'price': price,
            'contract': contract
        }

        if side == 'BOT':
            open_positions[key].append(position)
        elif side == 'SLD':
            # Try to find matching buy(s)
            remaining_qty = quantity
            while remaining_qty > 0 and open_positions[key]:
                buy_trade = open_positions[key][0]
                match_qty = min(remaining_qty, buy_trade['qty'])

                pnl = (price - buy_trade['price']) * match_qty * multiplier

                closed_trades.append({
                    'buy_time': buy_trade['time'],
                    'sell_time': time,
                    'contract': contract,
                    'buy_price': buy_trade['price'],
                    'sell_price': price,
                    'qty': match_qty,
                    'pnl': pnl
                })

                # Adjust unmatched quantities
                buy_trade['qty'] -= match_qty
                remaining_qty -= match_qty

                if buy_trade['qty'] == 0:
                    open_positions[key].popleft()
        # You can repeat the same if you short first and buy-to-cover later.
        # For simplicity, we’re only handling BOT then SLD
    return closed_trades


def print_closed_pnl(closed_trades):
    print(f"{'Symbol':<10} {'Strike':<7} {'Right':<5} {'Qty':<5} {'Buy@$':<8} {'Sell@$':<8} {'P&L':<10}")
    print("=" * 60)
    total_pnl = 0
    for t in closed_trades:
        c = t['contract']
        pnl = t['pnl']
        total_pnl += pnl
        print(f"{c.symbol:<10} {c.strike:<7.2f} {c.right:<5} {t['qty']:<5} {t['buy_price']:<8.2f} {t['sell_price']:<8.2f} {pnl:<10.2f}")
    print("=" * 60)
    print(f"Total Realized P&L: {total_pnl:.2f}")


if __name__ == "__main__":
    all_trades = get_today_option_executions('SPY')
    closed = match_trades_and_calculate_pnl(all_trades)
    print_closed_pnl(closed)

    ib.disconnect()