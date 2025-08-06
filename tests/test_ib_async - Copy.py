from ib_async import *


import logging

ib = IB()
ib.connect("127.0.0.1", 7497, clientId=1)

ib.positions()

account_metrics = [
    v
    for v in ib.accountValues()
    if v.tag == "NetLiquidationByCurrency" and v.currency == "BASE"
]

print(account_metrics)