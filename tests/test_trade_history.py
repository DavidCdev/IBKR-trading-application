from ib_async import *
from collections import defaultdict, deque
from datetime import datetime, date
import csv
import os

ib = IB()
ib.connect('127.0.0.1', 7498, clientId=2)


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


def export_trades_to_csv(trades, filename='option_trades.csv'):
    """Export all option trades to CSV file"""
    if not trades:
        print(f"No trades to export to {filename}")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'execId', 'time', 'side', 'qty', 'price', 'symbol', 'expiry', 
            'strike', 'right', 'multiplier', 'acctNumber', 'exchange', 
            'shares', 'permId', 'clientId', 'orderId', 'liquidation', 
            'cumQty', 'avgPrice', 'orderRef', 'evRule', 'evMultiplier', 
            'modelCode', 'lastLiquidity', 'pendingPriceRevision'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for trade in trades:
            contract = trade.contract
            exec = trade.execution
            
            writer.writerow({
                'execId': exec.execId,
                'time': exec.time.strftime('%Y-%m-%d %H:%M:%S') if exec.time else '',
                'side': exec.side,
                'qty': exec.shares,
                'price': exec.price,
                'symbol': contract.symbol,
                'expiry': contract.lastTradeDateOrContractMonth,
                'strike': contract.strike,
                'right': contract.right,
                'multiplier': contract.multiplier or 100,
                'acctNumber': exec.acctNumber,
                'exchange': exec.exchange,
                'shares': exec.shares,
                'permId': exec.permId,
                'clientId': exec.clientId,
                'orderId': exec.orderId,
                'liquidation': exec.liquidation,
                'cumQty': exec.cumQty,
                'avgPrice': exec.avgPrice,
                'orderRef': exec.orderRef,
                'evRule': exec.evRule,
                'evMultiplier': exec.evMultiplier,
                'modelCode': exec.modelCode,
                'lastLiquidity': exec.lastLiquidity,
                'pendingPriceRevision': exec.pendingPriceRevision
            })
    
    print(f"Exported {len(trades)} trades to {filename}")


def export_closed_trades_to_csv(closed_trades, filename='closed_trades_pnl.csv'):
    """Export closed trades with PnL calculations to CSV file"""
    if not closed_trades:
        print(f"No closed trades to export to {filename}")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'buy_time', 'sell_time', 'symbol', 'expiry', 'strike', 'right', 
            'buy_price', 'sell_price', 'qty', 'pnl', 'pnl_per_contract',
            'buy_execId', 'sell_execId', 'buy_acctNumber', 'sell_acctNumber',
            'buy_exchange', 'sell_exchange', 'buy_shares', 'sell_shares',
            'buy_permId', 'sell_permId', 'buy_clientId', 'sell_clientId',
            'buy_orderId', 'sell_orderId', 'buy_liquidation', 'sell_liquidation',
            'buy_cumQty', 'sell_cumQty', 'buy_avgPrice', 'sell_avgPrice',
            'buy_orderRef', 'sell_orderRef', 'buy_evRule', 'sell_evRule',
            'buy_evMultiplier', 'sell_evMultiplier', 'buy_modelCode', 'sell_modelCode',
            'buy_lastLiquidity', 'sell_lastLiquidity', 'buy_pendingPriceRevision', 'sell_pendingPriceRevision'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for trade in closed_trades:
            contract = trade['contract']
            pnl_per_contract = trade['pnl'] / trade['qty'] if trade['qty'] > 0 else 0
            
            writer.writerow({
                'buy_time': trade['buy_time'].strftime('%Y-%m-%d %H:%M:%S') if trade['buy_time'] else '',
                'sell_time': trade['sell_time'].strftime('%Y-%m-%d %H:%M:%S') if trade['sell_time'] else '',
                'symbol': contract.symbol,
                'expiry': contract.lastTradeDateOrContractMonth,
                'strike': contract.strike,
                'right': contract.right,
                'buy_price': trade['buy_price'],
                'sell_price': trade['sell_price'],
                'qty': trade['qty'],
                'pnl': trade['pnl'],
                'pnl_per_contract': pnl_per_contract,
                'buy_execId': trade['buy_execId'],
                'sell_execId': trade['sell_execId'],
                'buy_acctNumber': trade['buy_acctNumber'],
                'sell_acctNumber': trade['sell_acctNumber'],
                'buy_exchange': trade['buy_exchange'],
                'sell_exchange': trade['sell_exchange'],
                'buy_shares': trade['buy_shares'],
                'sell_shares': trade['sell_shares'],
                'buy_permId': trade['buy_permId'],
                'sell_permId': trade['sell_permId'],
                'buy_clientId': trade['buy_clientId'],
                'sell_clientId': trade['sell_clientId'],
                'buy_orderId': trade['buy_orderId'],
                'sell_orderId': trade['sell_orderId'],
                'buy_liquidation': trade['buy_liquidation'],
                'sell_liquidation': trade['sell_liquidation'],
                'buy_cumQty': trade['buy_cumQty'],
                'sell_cumQty': trade['sell_cumQty'],
                'buy_avgPrice': trade['buy_avgPrice'],
                'sell_avgPrice': trade['sell_avgPrice'],
                'buy_orderRef': trade['buy_orderRef'],
                'sell_orderRef': trade['sell_orderRef'],
                'buy_evRule': trade['buy_evRule'],
                'sell_evRule': trade['sell_evRule'],
                'buy_evMultiplier': trade['buy_evMultiplier'],
                'sell_evMultiplier': trade['sell_evMultiplier'],
                'buy_modelCode': trade['buy_modelCode'],
                'sell_modelCode': trade['sell_modelCode'],
                'buy_lastLiquidity': trade['buy_lastLiquidity'],
                'sell_lastLiquidity': trade['sell_lastLiquidity'],
                'buy_pendingPriceRevision': trade['buy_pendingPriceRevision'],
                'sell_pendingPriceRevision': trade['sell_pendingPriceRevision']
            })
    
    print(f"Exported {len(closed_trades)} closed trades to {filename}")


def export_open_positions_to_csv(open_positions, filename='open_positions.csv'):
    """Export open positions to CSV file"""
    if not open_positions:
        print(f"No open positions to export to {filename}")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'symbol', 'expiry', 'strike', 'right', 'total_qty', 'avg_price',
            'total_cost', 'positions_count'
        ]
        
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for key, positions in open_positions.items():
            if not positions:
                continue
                
            symbol, expiry, strike, right = key
            total_qty = sum(pos['qty'] for pos in positions)
            total_cost = sum(pos['qty'] * pos['price'] for pos in positions)
            avg_price = total_cost / total_qty if total_qty > 0 else 0
            
            writer.writerow({
                'symbol': symbol,
                'expiry': expiry,
                'strike': strike,
                'right': right,
                'total_qty': total_qty,
                'avg_price': avg_price,
                'total_cost': total_cost,
                'positions_count': len(positions)
            })
    
    print(f"Exported {len(open_positions)} open position types to {filename}")


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
        execId = exec.execId
        acctNumber = exec.acctNumber
        exchange = exec.exchange
        shares = exec.shares
        permId = exec.permId
        clientId = exec.clientId
        orderId = exec.orderId
        liquidation = exec.liquidation
        cumQty = exec.cumQty
        avgPrice = exec.avgPrice
        orderRef = exec.orderRef
        evRule = exec.evRule
        evMultiplier = exec.evMultiplier
        modelCode = exec.modelCode
        lastLiquidity = exec.lastLiquidity
        pendingPriceRevision = exec.pendingPriceRevision

        multiplier = int(contract.multiplier) if contract.multiplier else 100
        key = (contract.symbol, contract.lastTradeDateOrContractMonth,
               contract.strike, contract.right)

        position = {
            'time': time,
            'side': side,
            'qty': quantity,
            'price': price,
            'contract': contract,
            'execId': execId,
            'acctNumber': acctNumber,
            'exchange': exchange,
            'shares': shares,
            'permId': permId,
            'clientId': clientId,
            'orderId': orderId,
            'liquidation': liquidation,
            'cumQty': cumQty,
            'avgPrice': avgPrice,
            'orderRef': orderRef,
            'evRule': evRule,
            'evMultiplier': evMultiplier,
            'modelCode': modelCode,
            'lastLiquidity': lastLiquidity,
            'pendingPriceRevision': pendingPriceRevision

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
                    'pnl': pnl,
                    'buy_execId': buy_trade['execId'],
                    'sell_execId': exec.execId,
                    'buy_acctNumber': buy_trade['acctNumber'],
                    'sell_acctNumber': exec.acctNumber,
                    'buy_exchange': buy_trade['exchange'],
                    'sell_exchange': exec.exchange,
                    'buy_shares': buy_trade['shares'],
                    'sell_shares': exec.shares,
                    'buy_permId': buy_trade['permId'],
                    'sell_permId': exec.permId,
                    'buy_clientId': buy_trade['clientId'],
                    'sell_clientId': exec.clientId,
                    'buy_orderId': buy_trade['orderId'],
                    'sell_orderId': exec.orderId,
                    'buy_liquidation': buy_trade['liquidation'],
                    'sell_liquidation': exec.liquidation,
                    'buy_cumQty': buy_trade['cumQty'],
                    'sell_cumQty': exec.cumQty,
                    'buy_avgPrice': buy_trade['avgPrice'],
                    'sell_avgPrice': exec.avgPrice,
                    'buy_orderRef': buy_trade['orderRef'],
                    'sell_orderRef': exec.orderRef,
                    'buy_evRule': buy_trade['evRule'],
                    'sell_evRule': exec.evRule,
                    'buy_evMultiplier': buy_trade['evMultiplier'],
                    'sell_evMultiplier': exec.evMultiplier,
                    'buy_modelCode': buy_trade['modelCode'],
                    'sell_modelCode': exec.modelCode,
                    'buy_lastLiquidity': buy_trade['lastLiquidity'],
                    'sell_lastLiquidity': exec.lastLiquidity,
                    'buy_pendingPriceRevision': buy_trade['pendingPriceRevision'],
                    'sell_pendingPriceRevision': exec.pendingPriceRevision
                })

                # Adjust unmatched quantities
                buy_trade['qty'] -= match_qty
                remaining_qty -= match_qty

                if buy_trade['qty'] == 0:
                    open_positions[key].popleft()
        # You can repeat the same if you short first and buy-to-cover later.
        # For simplicity, we're only handling BOT then SLD

    print(f"Opening positions: {open_positions}")
    print(f"Closing positions: {closed_trades}")
    return closed_trades, open_positions

if __name__ == "__main__":
    # Create output directory if it doesn't exist
    output_dir = 'trade_exports'
    os.makedirs(output_dir, exist_ok=True)
    
    # Get all trades for today
    all_trades = get_today_option_executions('SPY')
    
    # Export raw trades to CSV
    export_trades_to_csv(all_trades, os.path.join(output_dir, 'option_trades.csv'))
    
    # Calculate PnL and get closed trades
    closed, open_pos = match_trades_and_calculate_pnl(all_trades)
    
    # Export closed trades with PnL to CSV
    export_closed_trades_to_csv(closed, os.path.join(output_dir, 'closed_trades_pnl.csv'))
    
    # Export open positions to CSV
    export_open_positions_to_csv(open_pos, os.path.join(output_dir, 'open_positions.csv'))
    
    # Print summary
    print(f"\nExport Summary:")
    print(f"Total trades: {len(all_trades)}")
    print(f"Closed trades: {len(closed)}")
    print(f"Open position types: {len(open_pos)}")
    print(f"CSV files exported to: {output_dir}/")

    ib.disconnect()