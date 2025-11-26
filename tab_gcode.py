from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QFileDialog


class GCodeTab(QWidget):
    """Tab 3: G-kodu önizleme (şimdilik sadece metin gösteriyor)."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel("Henüz G-kodu üretilmedi.")
        layout.addWidget(self.label)

        # G-kodunu gösteren metin alanı
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit, 1)

        # G-kodu diske kaydetme butonu
        self.btn_save = QPushButton("Kaydet...")
        self.btn_save.clicked.connect(self.on_save_clicked)
        layout.addWidget(self.btn_save)

    def set_gcode_text(self, text: str):
        if not text:
            self.label.setText("Henüz G-kodu üretilmedi.")
            self.text_edit.clear()
        else:
            self.label.setText("G-kodu:")
            self.text_edit.setPlainText(text)


    def on_save_clicked(self):
        """Mevcut G-kodunu dosyaya kaydet."""
        text = self.text_edit.toPlainText()
        if not text.strip():
            # Kaydedilecek bir şey yok
            return
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "G-kodu kaydet",
            "",
            "G-code Files (*.nc *.tap *.gcode);;Tüm Dosyalar (*)",
        )
        if not fname:
            return
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            # Çok detaylı hata mesajı göstermiyoruz; istersen MessageBox eklenebilir.
            print("G-kodu kaydedilirken hata:", e)
