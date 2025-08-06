import sys

from ui.main_gui import Ui_MainWindow
from PySide6.QtWidgets import QApplication, QMainWindow


class TradingMonitoAPP(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = TradingMonitoAPP()
    main_window.show()
    sys.exit(app.exec())

