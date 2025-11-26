from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
)

from tab_model import ModelTab
from tab_preview import PreviewTab
from tab_preview3d import Preview3DTab
from stl_loader import make_transform_matrix, apply_transform

# Opsiyonel G-kod sekmesi
try:
    from tab_gcode import GCodeTab
    HAS_GCODE_TAB = True
except ImportError:
    GCodeTab = None
    HAS_GCODE_TAB = False


class MainWindow(QMainWindow):
    """Sekmeler arası veri akışını yöneten ana pencere."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Tangential Knife CAM")

        # Dahili durum
        self._mesh = None          # Trimesh veya None
        self._path_data = None     # Yol verisi (en az .xy içeren)

        # G54 parça orjini modu (Model sekmesinden seçilecek)
        # Olası değerler: bottom_left, bottom_right, top_left, top_right, center
        self.origin_mode = "bottom_left"

        # Model döndürme / ölçek parametreleri
        self.last_rot_x = 0.0
        self.last_rot_y = 0.0
        self.last_rot_z = 0.0
        self.last_scale = 1.0

        # Merkez widget / layout
        central = QWidget(self)
        self.setCentralWidget(central)

        layout = QVBoxLayout()
        central.setLayout(layout)

        # Sekme kontrolü
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Sekme nesneleri
        self.model_tab = ModelTab(self)
        self.preview_tab = PreviewTab(self)
        self.preview3d_tab = Preview3DTab(self)

        if HAS_GCODE_TAB:
            self.gcode_tab = GCodeTab(self)
        else:
            self.gcode_tab = None

        # Sekmeleri ekle
        self.tabs.addTab(self.model_tab, "Model")
        self.tabs.addTab(self.preview_tab, "Yol Önizleme")
        if HAS_GCODE_TAB:
            self.tabs.addTab(self.gcode_tab, "G-kodu Önizleme")
        self.tabs.addTab(self.preview3d_tab, "3D Önizleme")

    # ------------------------------------------------------------------
    #  ModelTab <-> PathTab için ARAYÜZ
    # ------------------------------------------------------------------

    # ---- Mesh erişimi ----
    def set_mesh(self, mesh):
        """ModelTab STL yüklediğinde çağrılır."""
        self._mesh = mesh

        # 3D önizleme sekmesine dönüştürülmüş mesh'i gönder
        self._update_preview3d_mesh()

    def get_mesh(self):
        """Yol üretim kodu mesh'e ihtiyaç duyduğunda buradan alır."""
        return self._mesh

    # ---- Dönüş / ölçek parametreleri ----
    def set_transform_params(self, rot_x, rot_y, rot_z, scale):
        """Model sekmesi STL'i döndürdüğünde / ölçeklediğinde çağrılır."""
        self.last_rot_x = float(rot_x)
        self.last_rot_y = float(rot_y)
        self.last_rot_z = float(rot_z)
        self.last_scale = float(scale)
        self._update_preview3d_mesh()

    def get_transform_params(self):
        """Yol Üret sekmesi mesh'i aynı açı/ölçekte işlemek için kullanır."""
        return {
            "rot_x": self.last_rot_x,
            "rot_y": self.last_rot_y,
            "rot_z": self.last_rot_z,
            "scale": self.last_scale,
        }

    def _update_preview3d_mesh(self):
        """3D önizleme sekmesinde, yol ile aynı transform uygulanmış mesh'i çizer."""
        if self.preview3d_tab is None or self._mesh is None:
            return

        try:
            M = make_transform_matrix(
                self.last_rot_x, self.last_rot_y, self.last_rot_z, self.last_scale
            )
            t_mesh = apply_transform(self._mesh, M)
        except Exception:
            # Mesh ya da matris hatası durumunda sessizce geç
            return

        self.preview3d_tab.set_mesh(t_mesh)

    # ---- Yol / path verisi ----
    def set_path_data(self, path_data):
        """
        Yol Üret sekmesi hesapladığı yolu buraya verir.
        path_data:
           - tab_path içinde oluşturulan nesne,
             en azından .xy alanı (Nx2 koordinatlar) bulunmalı.
        """
        self._path_data = path_data

        # 2D Yol Önizleme sekmesine gönder
        if self.preview_tab is not None:
            self.preview_tab.set_path_data(path_data)

        # 3D Önizleme sekmesine TAM path_data'yı ver
        # (XY + Z varsa Z'yi de okuyup çizecek)
        if self.preview3d_tab is not None:
            self.preview3d_tab.set_path_data(path_data)

        # G-kodu sekmesi varsa oraya da gönder
        if (
            self.gcode_tab is not None
            and hasattr(self.gcode_tab, "set_path_data")
        ):
            self.gcode_tab.set_path_data(path_data)

        # Yol üretildikten sonra otomatik olarak 2D Yol Önizleme'ye geç
        if self.preview_tab is not None:
            self.tabs.setCurrentWidget(self.preview_tab)

    def get_path_data(self):
        """Yol / path verisini diğer sekmelerden okumak için."""
        return self._path_data

    def set_gcode_text(self, text: str):
        """Herhangi bir sekmeden üretilen G-kodunu G-kodu sekmesine gönder."""
        if self.gcode_tab is not None:
            # G-kodu sekmesinde metni güncelle
            if hasattr(self.gcode_tab, "set_gcode_text"):
                self.gcode_tab.set_gcode_text(text)
            # Ve sekmeyi öne getir
            self.tabs.setCurrentWidget(self.gcode_tab)

    def set_origin_mode(self, mode: str):
        """Model sekmesinden seçilen G54 parça orjini modunu kaydeder."""
        self.origin_mode = str(mode)

    def get_origin_mode(self) -> str:
        """G-kodu üretimi sırasında kullanılan G54 parça orjini modu."""
        return getattr(self, "origin_mode", "bottom_left")
