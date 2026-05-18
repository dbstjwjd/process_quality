import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase

app = QApplication(sys.argv)

id = QFontDatabase.addApplicationFont("assets/fonts/Pretendard-Regular.otf")
print("폰트 ID:", id)
print("패밀리명:", QFontDatabase.applicationFontFamilies(id))