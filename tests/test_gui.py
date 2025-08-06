from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
import sys

print("Starting minimal test")
app = QApplication(sys.argv)
print("Created QApplication")
window = QMainWindow()
print("Created QMainWindow")
window.setWindowTitle("Test Window")
print("Set window title")
label = QLabel("Hello World", window)
print("Created QLabel")
window.setCentralWidget(label)
print("Set central widget")
window.show()
print("Called show()")
app.exec()
print("App finished")