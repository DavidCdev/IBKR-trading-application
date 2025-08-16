from PyQt6 import QtWidgets, uic
import sys

app = QtWidgets.QApplication(sys.argv)
window = uic.loadUi("main.ui")  # Replace with your .ui file path
window.show()
sys.exit(app.exec_())
