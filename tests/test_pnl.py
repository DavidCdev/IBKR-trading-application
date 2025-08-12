from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from threading import Timer

class PnlApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def pnl(self, reqId, dailyPnL, unrealizedPnL, realizedPnL):
        print(f"Daily P&L: {dailyPnL}, Unrealized P&L: {unrealizedPnL}, Realized P&L: {realizedPnL}")
        self.cancelPnL(reqId)  # Cancel if no longer needed

def main():
    app = PnlApp()
    app.connect("127.0.0.1", 7496, 0)
    app.reqPnL(1, "YourAccountId", "")  # Subscribe to account P&L
    app.run()

if __name__ == "__main__":
    main()
