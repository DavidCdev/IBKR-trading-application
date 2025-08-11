from ib_async import *

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2)

# Get account summary
account = ib.managedAccounts()[0]
all_info = ib.accountValues(account)
summary = ib.accountSummary(account)
for item in summary:
    print(f"{item.tag}: {item.value}")

# print(f"All info: {all_info}")
for item in all_info:
    print(f"{item.tag}: {item.value}")
ib.disconnect()