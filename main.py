from PyQt5.QtWidgets import QApplication
from main_window import MainWindow
import sys

# Uygulama versiyon bilgisi
__version__ = "0.1.1-dev"


def main():
    # Versiyon bilgisini konsola yaz
    print(f"TangentialCAM {__version__} başlatılıyor...")

    app = QApplication(sys.argv)
    win = MainWindow()

    # Pencere başlığına versiyon bilgisini ekle
    base_title = win.windowTitle() or "Tangential Knife CAM"
    win.setWindowTitle(f"{base_title} - v{__version__}")

    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
