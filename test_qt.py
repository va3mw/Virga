import sys
print("Starting Qt test...")
from PySide6.QtWidgets import QApplication, QLabel
print("PySide6 imported OK")
app = QApplication(sys.argv)
print("QApplication created")
label = QLabel("Virga Qt test — if you see this, Qt works!")
label.setWindowTitle("Virga Qt Test")
label.resize(400, 100)
label.show()
print("Window shown, entering event loop...")
code = app.exec()
print(f"Event loop exited with code {code}")
