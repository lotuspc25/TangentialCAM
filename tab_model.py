from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLineEdit, QLabel, QFileDialog, QComboBox
)
from gl_viewer import GLViewer
from stl_loader import load_stl
from settings import load_settings, save_settings
from tab_path import PathTab   # Yol üret paneli olarak kullanacağız


class ModelTab(QWidget):
    """Tab 1: STL yükleme + 3D önizleme + Yol Üret paneli + renk ayarları."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.mesh = None

        # Döndürme değerleri
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0

        # Ayarları .ini'den oku
        self.settings = load_settings()

        # Renk presetleri
        self.bg_presets = [
            ("Koyu Gri", "#444444"),
            ("Açık Gri", "#E5E5E5"),
            ("Açık Sarı", "#FFFFE6"),
            ("Beyaz", "#FFFFFF"),
        ]
        self.mesh_presets = [
            ("Pembe", "#D07090"),
            ("Mavi", "#0000FF"),
            ("Koyu Mavi", "#000080"),
            ("Kırmızı", "#FF0000"),
            ("Yeşil", "#00AA00"),
            ("Siyah", "#000000"),
            ("Gri", "#666666"),
        ]

        self._build_ui()
        self._apply_initial_colors()

    # --------- Yardımcı: renk dönüşümleri ---------

    @staticmethod
    def _hex_to_rgb_f(hex_str):
        s = hex_str.strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) != 6:
            return 1.0, 1.0, 1.0
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return r, g, b

    # --------- UI ---------

    def _build_ui(self):
        # Dış layout: üstte model görünümü, altta yol üret paneli
        outer_layout = QVBoxLayout()
        self.setLayout(outer_layout)

        # Üst satır: 3D viewer + sağ panel
        top_layout = QHBoxLayout()
        outer_layout.addLayout(top_layout, 1)

        # Sol: OpenGL viewer
        self.viewer = GLViewer(self)
        top_layout.addWidget(self.viewer, 3)

        # Sağ: kontrol paneli
        right_panel = QVBoxLayout()
        top_layout.addLayout(right_panel, 1)

        # --- Dosya grubu ---
        file_group = QGroupBox("STL Dosyası")
        fg_layout = QVBoxLayout()
        file_group.setLayout(fg_layout)

        self.edit_path = QLineEdit()
        self.edit_path.setReadOnly(True)
        btn_browse = QPushButton("Gözat...")
        btn_browse.clicked.connect(self.on_browse)

        fg_layout.addWidget(self.edit_path)
        fg_layout.addWidget(btn_browse)

        right_panel.addWidget(file_group)

        # --- Dönüşüm butonları grubu ---
        tr_group = QGroupBox("Model Döndürme (90° adımlar)")
        tr_layout = QVBoxLayout()
        tr_group.setLayout(tr_layout)

        # X ekseni
        row_x = QHBoxLayout()
        row_x.addWidget(QLabel("Rot X:"))
        btn_x_minus = QPushButton("-90°")
        btn_x_plus = QPushButton("+90°")
        btn_x_minus.clicked.connect(lambda: self._rotate("x", -90.0))
        btn_x_plus.clicked.connect(lambda: self._rotate("x", +90.0))
        row_x.addWidget(btn_x_minus)
        row_x.addWidget(btn_x_plus)
        tr_layout.addLayout(row_x)

        # Y ekseni
        row_y = QHBoxLayout()
        row_y.addWidget(QLabel("Rot Y:"))
        btn_y_minus = QPushButton("-90°")
        btn_y_plus = QPushButton("+90°")
        btn_y_minus.clicked.connect(lambda: self._rotate("y", -90.0))
        btn_y_plus.clicked.connect(lambda: self._rotate("y", +90.0))
        row_y.addWidget(btn_y_minus)
        row_y.addWidget(btn_y_plus)
        tr_layout.addLayout(row_y)

        # Z ekseni
        row_z = QHBoxLayout()
        row_z.addWidget(QLabel("Rot Z:"))
        btn_z_minus = QPushButton("-90°")
        btn_z_plus = QPushButton("+90°")
        btn_z_minus.clicked.connect(lambda: self._rotate("z", -90.0))
        btn_z_plus.clicked.connect(lambda: self._rotate("z", +90.0))
        row_z.addWidget(btn_z_minus)
        row_z.addWidget(btn_z_plus)
        tr_layout.addLayout(row_z)

        right_panel.addWidget(tr_group)
        # --- Parça orjini (G54) grubu ---
        origin_group = QGroupBox("Parça Orjini (G54)")
        og_layout = QVBoxLayout()
        origin_group.setLayout(og_layout)

        self.combo_origin = QComboBox()
        self.combo_origin.addItem("Sol Alt (minX, minY)")
        self.combo_origin.addItem("Sol Üst (minX, maxY)")
        self.combo_origin.addItem("Sağ Alt (maxX, minY)")
        self.combo_origin.addItem("Sağ Üst (maxX, maxY)")
        self.combo_origin.addItem("Merkez")
        og_layout.addWidget(self.combo_origin)

        # Seçim değişince ana pencereye bildir (G54 modu)
        self.combo_origin.currentIndexChanged.connect(self._on_origin_changed)

        right_panel.addWidget(origin_group)


        # --- Görünüm grubu (renk seçimleri) ---
        view_group = QGroupBox("Görünüm")
        vg_layout = QVBoxLayout()
        view_group.setLayout(vg_layout)

        # Zemin rengi
        row_bg = QHBoxLayout()
        row_bg.addWidget(QLabel("Zemin:"))
        self.combo_bg = QComboBox()
        for name, hexc in self.bg_presets:
            self.combo_bg.addItem(name, hexc)
        self.combo_bg.currentIndexChanged.connect(self.on_bg_changed)
        row_bg.addWidget(self.combo_bg)
        vg_layout.addLayout(row_bg)

        # STL rengi
        row_mesh = QHBoxLayout()
        row_mesh.addWidget(QLabel("STL:"))
        self.combo_mesh = QComboBox()
        for name, hexc in self.mesh_presets:
            self.combo_mesh.addItem(name, hexc)
        self.combo_mesh.currentIndexChanged.connect(self.on_mesh_changed)
        row_mesh.addWidget(self.combo_mesh)
        vg_layout.addLayout(row_mesh)

        right_panel.addWidget(view_group)

        # --- Bilgi etiketi ---
        self.label_info = QLabel("Mesh bilgisi yok.")
        right_panel.addWidget(self.label_info)

        right_panel.addStretch(1)

        # ==== ALTTA: YOL ÜRET PANELİ (eski 2. tab) ====
        self.path_panel = PathTab(self.main_window)
        # Panel yüksekliğini sınırlayalım ki altta kocaman boşluk kalmasın
        self.path_panel.setMaximumHeight(160)   # istersen 220 / 300 yapabilirsin
        outer_layout.addWidget(self.path_panel)   # full width alt kısım


    def _apply_initial_colors(self):
        """INI'den gelen renkleri viewer ve combobox'lara uygula."""
        bg_hex = self.settings.get("bg_color", "#FFFFE6")
        mesh_hex = self.settings.get("mesh_color", "#0000FF")

        # Combobox indexlerini ayarla
        def set_combo_from_hex(combo, presets, target_hex):
            target_hex = target_hex.upper()
            idx = 0
            for i, (_, hx) in enumerate(presets):
                if hx.upper() == target_hex:
                    idx = i
                    break
            combo.setCurrentIndex(idx)

        set_combo_from_hex(self.combo_bg, self.bg_presets, bg_hex)
        set_combo_from_hex(self.combo_mesh, self.mesh_presets, mesh_hex)

        # Viewer renklerini uygula
        br, bg, bb = self._hex_to_rgb_f(bg_hex)
        mr, mg, mb = self._hex_to_rgb_f(mesh_hex)
        self.viewer.set_bg_color(br, bg, bb)
        self.viewer.set_mesh_color(mr, mg, mb)

    # ------------ Event / Logic ------------

    def on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "STL dosyası seç",
            "",
            "STL Files (*.stl);;All Files (*.*)",
        )
        if not path:
            return
        self.edit_path.setText(path)
        self.load_mesh(path)

    def load_mesh(self, path):
        try:
            mesh = load_stl(path)
        except Exception as e:
            self.label_info.setText(f"Hata: {e}")
            return

        self.mesh = mesh
        self.main_window.set_mesh(mesh)

        verts = mesh.vertices
        faces = mesh.faces
        self.viewer.set_mesh(verts, faces)

        vmin = verts.min(axis=0)
        vmax = verts.max(axis=0)
        size = vmax - vmin

        info = (
            f"Vertex sayısı: {len(verts)}\n"
            f"Face sayısı: {len(faces)}\n"
            f"Boyutlar (X,Y,Z): "
            f"{size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f}"
        )
        self.label_info.setText(info)

        # Dönüşümleri sıfırla
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.rot_z = 0.0
        self._apply_transform()

    def _rotate(self, axis, delta_deg):
        if axis == "x":
            self.rot_x += delta_deg
        elif axis == "y":
            self.rot_y += delta_deg
        elif axis == "z":
            self.rot_z += delta_deg
        self._apply_transform()

    def _apply_transform(self):
        """Butonlarla güncellenen açıları viewer ve MainWindow'a yansıt."""
        self.viewer.set_user_transform(self.rot_x, self.rot_y, self.rot_z, 1.0)
        self.viewer.reset_view()
        self.main_window.set_transform_params(self.rot_x, self.rot_y, self.rot_z, 1.0)

    # ----- Renk combobox callback'leri -----

    def on_bg_changed(self, index):
        if index < 0:
            return
        hex_color = self.combo_bg.itemData(index)
        r, g, b = self._hex_to_rgb_f(hex_color)
        self.viewer.set_bg_color(r, g, b)
        self.settings["bg_color"] = hex_color
        save_settings(self.settings)

    def on_mesh_changed(self, index):
        if index < 0:
            return
        hex_color = self.combo_mesh.itemData(index)
        r, g, b = self._hex_to_rgb_f(hex_color)
        self.viewer.set_mesh_color(r, g, b)
        self.settings["mesh_color"] = hex_color
        save_settings(self.settings)

    def _on_origin_changed(self, index: int):
        """G54 parça orjini seçimi değişince MainWindow'a bildir."""
        mode = "bottom_left"
        if index == 0:
            mode = "bottom_left"
        elif index == 1:
            mode = "top_left"
        elif index == 2:
            mode = "bottom_right"
        elif index == 3:
            mode = "top_right"
        elif index == 4:
            mode = "center"
        # Ana pencereye gönder
        if hasattr(self.main_window, "set_origin_mode"):
            self.main_window.set_origin_mode(mode)
