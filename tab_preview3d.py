from knife_visual import compute_path_tangent_angle_deg, estimate_visual_length, draw_knife_gl_3d, draw_knife_2d_matplotlib
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QOpenGLWidget, QLabel, QPushButton, QComboBox, QMessageBox
from PyQt5.QtCore import Qt, QPoint

from OpenGL.GL import (
    glClearColor, glEnable, glClear, glViewport,
    glMatrixMode, glLoadIdentity, glTranslatef, glRotatef,
    glBegin, glEnd, glVertex3f, glColor3f, glLineWidth,
    glPointSize, glRasterPos3f,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST, GL_PROJECTION, GL_MODELVIEW,
    GL_LINES, GL_LINE_STRIP, GL_POINTS,
)
from OpenGL.GLU import gluPerspective
from OpenGL.GLUT import glutInit, glutBitmapCharacter, GLUT_BITMAP_HELVETICA_18

import numpy as np

from gcode_generator import generate_gcode_3d


class Path3DViewer(QOpenGLWidget):
    """
    STL + bıçak yolunun 3D önizlemesi.

    - Sol tuş basılı, sürükle  -> kamerayı döndür (orbit)
    - Mouse wheel              -> zoom
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # GLUT metin fonksiyonları için bir kez init
        try:
            glutInit()
        except Exception:
            # Aynı process içinde birden fazla çağrı sorun çıkarabiliyor;
            # hata alsak bile kritik değil.
            pass

        # Kamera parametreleri
        self.distance = 1200.0
        self.rot_x = 30.0
        self.rot_y = -45.0

        # Mouse takibi
        self.last_pos = QPoint()

        # Çizilecek veriler
        self.mesh = None          # Trimesh
        self.path_points = None   # (N,3) numpy array

    # ---------- DIŞ ARAYÜZ ----------

    def set_mesh(self, mesh):
        """Model sekmesi STL yüklediğinde çağrılır."""
        self.mesh = mesh
        self.update()

    def set_path_data(self, path_data):
        """
        Yol verisini alır.

        path_data:
          - PathData nesnesi (xy, z, angles) veya
          - dict: {"xy": ..., "z": ...} gibi.

        Z dizisi yoksa 0 kabul edilir.
        """
        if path_data is None:
            self.path_points = None
            self.update()
            return

        xy = None
        z = None

        # dict ise
        if isinstance(path_data, dict):
            if "xy" in path_data:
                xy = np.asarray(path_data["xy"], dtype=float)
            if "z" in path_data:
                z = np.asarray(path_data["z"], dtype=float)
            if "xyz" in path_data:
                arr = np.asarray(path_data["xyz"], dtype=float)
                if arr.ndim == 2 and arr.shape[1] >= 3 and len(arr) > 0:
                    self.path_points = arr[:, :3]
                    self.update()
                    return
        else:
            # PathData benzeri bir nesne ise attribute üzerinden al.
            # Öncelikle, STL ile çakışan geometri XY'si varsa onu tercih ediyoruz.
            if hasattr(path_data, "xy_geom"):
                xy = np.asarray(path_data.xy_geom, dtype=float)
            elif hasattr(path_data, "xy"):
                xy = np.asarray(path_data.xy, dtype=float)

            if hasattr(path_data, "z"):
                z = np.asarray(path_data.z, dtype=float)

            if hasattr(path_data, "xyz"):
                arr = np.asarray(path_data.xyz, dtype=float)
                if arr.ndim == 2 and arr.shape[1] >= 3 and len(arr) > 0:
                    self.path_points = arr[:, :3]
                    self.update()
                    return

        if xy is None or xy.ndim != 2 or xy.shape[1] < 2 or len(xy) == 0:
            self.path_points = None
            self.update()
            return

        n = len(xy)
        if z is None or len(z) != n:
            z = np.zeros(n, dtype=float)

        # Mesh koordinat sistemi: X,Y düzlem, Z yükseklik.
        # Yol noktalarını da aynı sisteme yerleştiriyoruz.
        self.path_points = np.column_stack((xy[:, 0], xy[:, 1], z))
        self.update()

    # ---------- OPENGL CALLBACK'LERİ ----------

    def initializeGL(self):
        # Açık sarı arka plan
        glClearColor(0.98, 0.97, 0.90, 1.0)
        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / max(1, h)
        gluPerspective(45.0, aspect, 0.1, 5000.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Kamerayı Z ekseni boyunca geriye taşı
        glTranslatef(0.0, 0.0, -self.distance)

        # Orbit rotasyonları
        glRotatef(self.rot_x, 1.0, 0.0, 0.0)
        glRotatef(self.rot_y, 0.0, 1.0, 0.0)

        # Hafif yukarıdan bakmak için küçük ekstra rotasyon istenirse buraya eklenebilir.

        # Çizimler
        self._draw_grid()
        self._draw_axes()

        if self.mesh is not None:
            self._draw_mesh()

        if self.path_points is not None:
            self._draw_path()

    # ---------- ÇİZİM FONKSİYONLARI ----------

    def _draw_grid(self):
        """
        400 x 800 mm XY çalışma alanı, 50 mm grid.
        XY düzleminde, Z=0 seviyesinde.
        """
        size_x = 400.0
        size_y = 800.0
        step = 50.0

        glColor3f(0.8, 0.8, 0.8)
        glLineWidth(1.0)
        glBegin(GL_LINES)

        # Y doğrultusunda paralel çizgiler (X değişiyor)
        y = 0.0
        while y <= size_y + 1e-6:
            glVertex3f(0.0, y, 0.0)
            glVertex3f(size_x, y, 0.0)
            y += step

        # X doğrultusunda paralel çizgiler (Y değişiyor)
        x = 0.0
        while x <= size_x + 1e-6:
            glVertex3f(x, 0.0, 0.0)
            glVertex3f(x, size_y, 0.0)
            x += step

        glEnd()

    def _draw_axes(self, length: float = 120.0):
        glLineWidth(3.0)
        glBegin(GL_LINES)

        # X ekseni (kırmızı)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(length, 0.0, 0.0)

        # Y ekseni (yeşil)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.0, length, 0.0)

        # Z ekseni (mavi)
        glColor3f(0.0, 0.2, 0.8)
        glVertex3f(0.0, 0.0, 0.0)
        glVertex3f(0.0, 0.0, length)

        glEnd()
        glLineWidth(1.0)

        # Eksen isimleri
        self._draw_text3d(length + 10, 0, 0, "X")
        self._draw_text3d(0, length + 10, 0, "Y")
        self._draw_text3d(0, 0, length + 10, "Z")

    def _draw_mesh(self):
        """
        Trimesh üçgenlerini çiz.
        """
        # Mesh rengi: koyu mavi
        glColor3f(0.0, 0.0, 0.8)
        glBegin(GL_LINES)
        # Çok detaylı doldurma yapmak yerine sadece kenarları kaba şekilde çiziyoruz
        # performans ve sadelik için.
        try:
            faces = self.mesh.faces
            vertices = self.mesh.vertices
        except Exception:
            glEnd()
            return

        n_faces = len(faces)
        for i, f in enumerate(faces):
            if i % 5000 == 0 and n_faces > 0:
                # İleride buraya istenirse progress hesabı eklenebilir
                pass

            v0 = vertices[f[0]]
            v1 = vertices[f[1]]
            v2 = vertices[f[2]]

            glVertex3f(v0[0], v0[1], v0[2])
            glVertex3f(v1[0], v1[1], v1[2])

            glVertex3f(v1[0], v1[1], v1[2])
            glVertex3f(v2[0], v2[1], v2[2])

            glVertex3f(v2[0], v2[1], v2[2])
            glVertex3f(v0[0], v0[1], v0[2])

        glEnd()

    def _draw_path(self):
        """
        Kırmızı çizgi olarak bıçak yolunu çizer.
        Z değerlerini PathData.z'den kullanır.
        """
        pts = self.path_points
        if pts is None or len(pts) == 0:
            return

        # Yol çizgisi
        glColor3f(1.0, 0.2, 0.0)
        glLineWidth(2.0)
        glBegin(GL_LINE_STRIP)
        for x, y, z in pts:
            # Yüzeyle üst üste binmemesi için Z'yi azıcık yukarı kaydırıyoruz
            glVertex3f(x, y, z + 0.1)
        glEnd()

        # Başlangıç noktasını küçük bir nokta ile işaretleyelim
        glPointSize(6.0)
        glBegin(GL_POINTS)
        x0, y0, z0 = pts[0]
        glVertex3f(x0, y0, z0 + 0.2)
        glEnd()
        glPointSize(1.0)

    def _draw_text3d(self, x, y, z, text: str):
        """
        Basit 3D metin çizimi (eksen isimleri için).
        """
        glColor3f(0.0, 0.0, 0.0)
        glRasterPos3f(x, y, z)
        for ch in text:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

    # ---------- MOUSE ETKİLEŞİMİ ----------

    def mousePressEvent(self, event):
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()

        if event.buttons() & Qt.LeftButton:
            # Orbit
            self.rot_x += dy * 0.5
            self.rot_y += dx * 0.5

        self.last_pos = event.pos()
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        # Zoom: tekerlek ileri -> yakınlaş, geri -> uzaklaş
        if delta > 0:
            self.distance *= 0.9
        else:
            self.distance *= 1.1

        # Aşırıya kaçmasın
        self.distance = max(50.0, min(5000.0, self.distance))
        self.update()


class Preview3DTab(QWidget):
    """
    3D Önizleme sekmesi:
      - Path3DViewer (Z derinlikli yolu gösterir)
      - Alt kısımda: bıçak yönü seçimi + G-kodu oluştur (Z'li) butonu
    """

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Üstte 3D viewer
        self.viewer = Path3DViewer(self)
        layout.addWidget(self.viewer, 1)

        # Altta kontrol çubuğu
        bottom = QHBoxLayout()
        layout.addLayout(bottom)

        self.combo_knife = QComboBox()
        self.combo_knife.addItem("Bıçak: 0° (standart)")
        self.combo_knife.addItem("Bıçak: +90°")
        self.combo_knife.addItem("Bıçak: -90°")
        self.combo_knife.addItem("Bıçak: +180°")
        self.combo_knife.addItem("Bıçak: -180°")
        bottom.addWidget(self.combo_knife)

        bottom.addStretch(1)

        self.btn_make_gcode_3d = QPushButton("G-kodu oluştur (Z'li)")
        self.btn_make_gcode_3d.clicked.connect(self.on_generate_gcode_3d)
        bottom.addWidget(self.btn_make_gcode_3d)

    def set_mesh(self, mesh):
        self.viewer.set_mesh(mesh)

    def set_path_data(self, path_data):
        self.viewer.set_path_data(path_data)

    # ------------------------------------------------------------------ G-kodu üret (Z'li + bıçak yönü)

    def on_generate_gcode_3d(self):
        """3D önizlemedeki Z derinlikli yoldan, bıçak yönüne göre G-kodu üret."""
        path_data = self.main_window.get_path_data()
        if path_data is None or getattr(path_data, "xy", None) is None:
            QMessageBox.warning(self, "Uyarı", "Önce Yol Üret panelinden yol üretin.")
            return

        idx = self.combo_knife.currentIndex()
        # 0: 0°, 1: +90°, 2: -90°, 3: +180°, 4: -180°
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
        gcode = generate_gcode_3d(
            path_data,
            knife_offset_deg=knife_offset,
            origin_mode=origin_mode,
        )
        self.main_window.set_gcode_text(gcode)
