from ib_async import IB, ExecutionFilter, util

# Connect to TWS or IB Gateway
ib = IB()
ib.connect('127.0.0.1', 7499, clientId=2)

# Create a time filter in IB's required format
# Format: 'YYYYMMDD-HH:MM:SS'
start_time = '20250801-00:00:00'  # June 1, 2024 start
# end_time = '20240610-23:59:59'    # June 10, 2024 end

# Note: IB API does not support filtering to end_time directly.
# You can only filter ON or SINCE a given start time.

# Create ExecutionFilter with a starting time
filter = ExecutionFilter(time=start_time)

# Request executions filtered by time
executions = ib.reqExecutions(filter)

# Output results
for trade in executions:
    exec_time = trade.execution.time  # UTC datetime
    print(f"{trade.contract.symbol} | {trade.execution.side} | Qty: {trade.execution.shares} | Price: {trade.execution.price} | Time: {exec_time}")

ib.disconnect()