from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QDoubleSpinBox, QSpinBox, QPushButton,
    QProgressBar, QTextEdit, QMessageBox, QCheckBox
)
from PyQt5.QtCore import QCoreApplication
from stl_loader import make_transform_matrix
from path_generator import generate_path


class PathTab(QWidget):
    """Tab 2: Yol üretimi (G-kod yok, sadece geometri)."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Ayarlar grubu ---
        param_group = QGroupBox("Yol Ayarları")
        pg_layout = QHBoxLayout()
        param_group.setLayout(pg_layout)

        # MIN_AREA
        self.spin_min_area = QDoubleSpinBox()
        self.spin_min_area.setRange(0.0, 1.0)
        self.spin_min_area.setDecimals(6)
        self.spin_min_area.setValue(0.0001)

        # STEP_DECIMATE
        self.spin_step_dec = QSpinBox()
        self.spin_step_dec.setRange(1, 1000)
        self.spin_step_dec.setValue(1)

        # Depth
        self.spin_depth = QDoubleSpinBox()
        self.spin_depth.setRange(0.0, 50.0)
        self.spin_depth.setDecimals(3)
        self.spin_depth.setValue(1.0)

        # Makine 90 derece
        self.chk_rotate = QCheckBox("Makineye göre 90° döndür (X400/Y800)")
        self.chk_rotate.setChecked(True)

        def row(lbl, widget):
            box = QHBoxLayout()
            box.addWidget(QLabel(lbl))
            box.addWidget(widget)
            pg_layout.addLayout(box)

        row("Min Alan (mm²):", self.spin_min_area)
        row("Nokta Seyreltme:", self.spin_step_dec)
        row("Yüzeyden derinlik (mm):", self.spin_depth)
        pg_layout.addWidget(self.chk_rotate)

        layout.addWidget(param_group)

        # --- Progress + buton ---
        top = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        btn_run = QPushButton("Yol Üret")
        btn_run.clicked.connect(self.on_run)

        top.addWidget(self.progress, 1)
        top.addWidget(btn_run)
        layout.addLayout(top)

        # --- Log kutusu ---
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(200)
        layout.addWidget(self.log_edit, 1)

    # ------------ Logic ------------

    def log(self, text):
        self.log_edit.append(text)
        self.log_edit.ensureCursorVisible()

    def _progress_cb(self, pct, msg):
        self.progress.setValue(pct)
        self.progress.setFormat(f"{pct}% - {msg}")
        QCoreApplication.processEvents()

    def on_run(self):
        mesh = self.main_window.get_mesh()
        if mesh is None:
            QMessageBox.warning(self, "Uyarı", "Önce Model sekmesinde STL yükleyin.")
            return

        t = self.main_window.get_transform_params()
        M = make_transform_matrix(
            t["rot_x"], t["rot_y"], t["rot_z"], t["scale"]
        )

        min_area = self.spin_min_area.value()
        step_dec = self.spin_step_dec.value()
        depth = self.spin_depth.value()
        rotate_90 = self.chk_rotate.isChecked()

        self.log("Yol üretimi başladı...")
        self.progress.setValue(0)

        try:
            path_data = generate_path(
                mesh,
                transform_matrix=M,
                min_area=min_area,
                step_decimate=step_dec,
                rotate_90_for_machine=rotate_90,
                depth_from_top=depth,
                progress_callback=self._progress_cb,
            )
        except Exception as e:
            self.log(f"Hata: {e}")
            QMessageBox.critical(self, "Hata", str(e))
            return

        self.log(
            f"Yol üretildi. Nokta sayısı: {len(path_data.xy)} "
            f"X aralığı: {path_data.xy[:,0].min():.2f}..{path_data.xy[:,0].max():.2f} "
            f"Y aralığı: {path_data.xy[:,1].min():.2f}..{path_data.xy[:,1].max():.2f}"
        )

        self.main_window.set_path_data(path_data)
        self.progress.setValue(100)
        self.progress.setFormat("Tamamlandı")
