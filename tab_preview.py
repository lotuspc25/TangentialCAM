from knife_visual import compute_path_tangent_angle_deg, estimate_visual_length, draw_knife_gl_3d, draw_knife_2d_matplotlib
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QComboBox
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

from gcode_generator import generate_gcode_flat


class PreviewTab(QWidget):
    """Tab 2: XY Bıçak Yolu önizlemesi."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.path_data = None

        # Ham yol (döndürmeden önceki)
        self.base_x = None
        self.base_y = None

        # Görünüm döndürme açısı (sadece ekranda)
        self.view_angle_deg = 0.0

        layout = QVBoxLayout()
        self.setLayout(layout)

        # --- Grafik ---
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas, 1)

        # --- Alt kısım: bilgi + döndürme butonları ---
        bottom = QHBoxLayout()
        self.label_info = QLabel("Henüz yol üretilmedi.")
        bottom.addWidget(self.label_info)

        # Bıçak yönü seçimi (2D G-kodu için)
        self.combo_knife = QComboBox()
        self.combo_knife.addItem("Bıçak: 0° (standart)")
        self.combo_knife.addItem("Bıçak: +90°")
        self.combo_knife.addItem("Bıçak: -90°")
        self.combo_knife.addItem("Bıçak: +180°")
        self.combo_knife.addItem("Bıçak: -180°")
        bottom.addWidget(self.combo_knife)

        bottom.addStretch(1)

        self.btn_rot_ccw = QPushButton("↺ 90°")
        self.btn_rot_cw = QPushButton("↻ 90°")
        bottom.addWidget(self.btn_rot_ccw)
        bottom.addWidget(self.btn_rot_cw)

        # Z takibi OLMAYAN G-kodu üretme butonu
        self.btn_make_gcode_flat = QPushButton("G-kodu oluştur")
        self.btn_make_gcode_flat.clicked.connect(self.on_generate_gcode_flat)
        bottom.addWidget(self.btn_make_gcode_flat)

        layout.addLayout(bottom)

        # Zoom
        self.canvas.mpl_connect("scroll_event", self.on_scroll)

        # Pan
        self.is_panning = False
        self.pan_start = None
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)

        # Döndürme butonları
        self.btn_rot_ccw.clicked.connect(lambda: self.rotate_view(-90.0))
        self.btn_rot_cw.clicked.connect(lambda: self.rotate_view(+90.0))

    # ------------------------------------------------------------------ public API

    def set_path_data(self, path_data):
        """MainWindow burayı çağırıyor."""
        self.path_data = path_data
        self.view_angle_deg = 0.0  # yeni yol geldiğinde açıyı sıfırla
        self._update_plot_from_pathdata()

    # ------------------------------------------------------------------ G-kodu üret (Z takipsiz)

    def on_generate_gcode_flat(self):
        """Yol Önizleme'den, Z takibi OLMAYAN G-kodu üret."""
        path_data = self.main_window.get_path_data()
        if path_data is None or getattr(path_data, "xy", None) is None:
            QMessageBox.warning(self, "Uyarı", "Önce Yol Üret panelinden yol üretin.")
            return

        # Bıçak yönü offset seçimi
        idx = self.combo_knife.currentIndex()
        if idx == 0:
            knife_offset = 0.0
        elif idx == 1:
            knife_offset = 90.0
        elif idx == 2:
            knife_offset = -90.0
        elif idx == 3:
            knife_offset = 180.0
        else:
            knife_offset = -180.0

        origin_mode = self.main_window.get_origin_mode()
        gcode = generate_gcode_flat(path_data, knife_offset_deg=knife_offset, origin_mode=origin_mode)
        self.main_window.set_gcode_text(gcode)


    # ------------------------------------------------------------------ iç mantık

    def _update_plot_from_pathdata(self):
        """path_data.xy'den base_x/base_y üret ve çiz."""
        self.ax.clear()
        self.base_x = None
        self.base_y = None

        if (
            self.path_data is None
            or not hasattr(self.path_data, "xy")
            or self.path_data.xy is None
        ):
            self._reset_axes()
            self.label_info.setText("Henüz yol üretilmedi.")
            self.canvas.draw()
            return

        xy = np.asarray(self.path_data.xy, dtype=float)
        if xy.ndim != 2 or xy.shape[1] < 2 or xy.shape[0] == 0:
            self._reset_axes()
            self.label_info.setText("Yol verisi geçersiz.")
            self.canvas.draw()
            return

        self.base_x = xy[:, 0]
        self.base_y = xy[:, 1]

        self._redraw_from_base()

    def _redraw_from_base(self):
        """base_x/base_y ve view_angle_deg'e göre grafiği baştan çiz."""
        self.ax.clear()
        if self.base_x is None or self.base_y is None:
            self._reset_axes()
            self.canvas.draw()
            return

        # Döndürülmüş koordinatları hesapla
        x_draw, y_draw = self._get_rotated_coords()

        # Çizim
        self.ax.plot(x_draw, y_draw, "-")
        self.ax.plot([x_draw[0]], [y_draw[0]], "ro")  # başlangıç

        self.ax.set_aspect("equal", adjustable="box")
        self.ax.set_title("XY Bıçak Yolu")
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Y (mm)")
        self.ax.grid(True)

        # Limitler
        x_min, x_max = float(x_draw.min()), float(x_draw.max())
        y_min, y_max = float(y_draw.min()), float(y_draw.max())

        dx = (x_max - x_min) * 0.05 + 1.0
        dy = (y_max - y_min) * 0.05 + 1.0

        self.ax.set_xlim(x_min - dx, x_max + dx)
        self.ax.set_ylim(y_min - dy, y_max + dy)

        self.label_info.setText(
            f"Nokta sayısı: {len(x_draw)} | "
            f"X: {x_min:.2f}..{x_max:.2f} | "
            f"Y: {y_min:.2f}..{y_max:.2f} | "
            f"Açı: {self.view_angle_deg:.0f}°"
        )

        self.canvas.draw()

    def _get_rotated_coords(self):
        """view_angle_deg'e göre base_x/base_y'i döndür."""
        if self.base_x is None or self.base_y is None:
            return None, None

        if self.view_angle_deg % 360 == 0:
            return self.base_x, self.base_y

        theta = np.deg2rad(self.view_angle_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)

        x = self.base_x * cos_t - self.base_y * sin_t
        y = self.base_x * sin_t + self.base_y * cos_t
        return x, y

    def _reset_axes(self):
        self.ax.set_title("XY Bıçak Yolu")
        self.ax.set_xlabel("X (mm)")
        self.ax.set_ylabel("Y (mm)")
        self.ax.grid(True)
        self.ax.set_xlim(0, 400)
        self.ax.set_ylim(0, 800)

    # ------------------------------------------------------------------ Zoom

    def on_scroll(self, event):
        # Yol yoksa zoom yapma
        if self.base_x is None or self.base_y is None:
            return

        xdata, ydata = event.xdata, event.ydata
        if xdata is None or ydata is None:
            return

        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        zoom = 1.2
        if event.button == "up":
            scale_factor = 1 / zoom
        elif event.button == "down":
            scale_factor = zoom
        else:
            return

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

        self.ax.set_xlim(
            [xdata - new_width * (1 - relx), xdata + new_width * relx]
        )
        self.ax.set_ylim(
            [ydata - new_height * (1 - rely), ydata + new_height * rely]
        )

        self.canvas.draw_idle()

    # ------------------------------------------------------------------ Pan (sol tık)

    def on_mouse_press(self, event):
        if event.button == 1:  # sol tık
            self.is_panning = True
            self.pan_start = (event.xdata, event.ydata)

    def on_mouse_release(self, event):
        self.is_panning = False
        self.pan_start = None

    def on_mouse_move(self, event):
        if not self.is_panning or self.pan_start is None:
            return
        if event.xdata is None or event.ydata is None:
            return

        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        x0, y0 = self.pan_start
        dx = x0 - event.xdata
        dy = y0 - event.ydata

        self.ax.set_xlim(cur_xlim[0] + dx, cur_xlim[1] + dx)
        self.ax.set_ylim(cur_ylim[0] + dy, cur_ylim[1] + dy)

        self.pan_start = (event.xdata, event.ydata)
        self.canvas.draw_idle()

    # ------------------------------------------------------------------ Görünümü döndür

    def rotate_view(self, delta_deg):
        """Sadece ekrandaki görünümü döndür (G-kodu değişmez)."""
        if self.base_x is None or self.base_y is None:
            return
        self.view_angle_deg = (self.view_angle_deg + delta_deg) % 360
        self._redraw_from_base()
