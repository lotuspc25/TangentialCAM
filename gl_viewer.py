from tool_arrow import draw_tool_arrow
from knife_visual import compute_path_tangent_angle_deg, estimate_visual_length, draw_knife_gl_3d, draw_knife_2d_matplotlib
from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QPoint

from OpenGL.GL import *
from OpenGL.GLU import gluPerspective
from OpenGL.GLUT import glutInit, glutBitmapCharacter, GLUT_BITMAP_HELVETICA_18

import numpy as np


class GLViewer(QOpenGLWidget):
    """
    STL + bıçak yolu önizleyici (QOpenGLWidget)

      - Sol tuş: orbit (kamera rotasyonu)
      - Sağ tuş: pan
      - Mouse wheel: zoom
      - Grid + eksenler: makineye sabit (X400 x Y800)
      - STL: sadece user_rot_x/y/z ile döner (Model tabındaki butonlar)
      - Yol: STL ile aynı koordinat sisteminde çizilir (overlay)
      - Zemin rengi ve STL rengi dışarıdan ayarlanabilir
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vertices = None   # Nx3
        self.faces = None      # Mx3 (indis)
        self.face_normals = None   # üçgen başına normal vektörleri
        self.center = np.zeros(3)
        self.radius = 1.0

        # Varsayılan renkler (Windows 3B Görüntüleyici benzeri)
        self.bg_color = (0.27, 0.27, 0.27)      # koyu gri
        self.mesh_color = (0.82, 0.44, 0.56)    # pembe/mor ton

        # STL görünürlüğü
        self.mesh_visible = True

        # Yol noktaları (Nx2) – isteğe bağlı
        self.path_points = None

        # Kamera / kontrol parametreleri
        self.base_dist = 1000.0   # makine zarfını görecek uzaklık
        self.dist = self.base_dist
        self.rot_x = 20.0
        self.rot_y = -30.0
        self.rot_z = 0.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        # Kullanıcı dönüşümü (SADECE STL + YOL için)
        self.user_rot_x = 0.0
        self.user_rot_y = 0.0
        self.user_rot_z = 0.0
        self.user_scale = 1.0  # ölçek sabit 1

        self._last_pos = QPoint()

    # ---- Renk ayarları (ModelTab burayı kullanacak) ----

    def set_bg_color(self, r: float, g: float, b: float):
        """Zemin rengini 0..1 aralığında ayarla."""
        self.bg_color = (float(r), float(g), float(b))
        self.update()

    def set_mesh_color(self, r: float, g: float, b: float):
        """STL rengini 0..1 aralığında ayarla."""
        self.mesh_color = (float(r), float(g), float(b))
        self.update()

    # ---- Yol ayarı (PreviewTab burayı kullanacak) ----

    def set_path_points(self, points_xy):
        """
        Bıçak yolunu ayarla.
        points_xy:  Nx2 array-like (x,y) liste veya numpy array.
        None verilirse yol çizilmez.
        """
        if points_xy is None:
            self.path_points = None
        else:
            arr = np.asarray(points_xy, dtype=float)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                self.path_points = arr[:, :2]
            else:
                self.path_points = None
        self.update()

    # ---- Dışarıdan çağrılan metodlar ----

    def set_mesh(self, vertices, faces):
        """Mesh verisini yükle ve merkez/yarıçap hesapla."""
        self.vertices = vertices
        self.faces = faces
        self.face_normals = None

        if vertices is not None and len(vertices) > 0:
            vmin = vertices.min(axis=0)
            vmax = vertices.max(axis=0)
            self.center = (vmin + vmax) / 2.0
            self.radius = float(np.linalg.norm(vmax - vmin)) / 2.0
            if self.radius <= 0:
                self.radius = 1.0

            # Auto-zoom: modeli ekrana rahat sığdır
            # distance ~ 3x radius => Windows 3B Görüntüleyici benzeri uzaklık
            self.base_dist = self.radius * 3.0

            # Yüzey normallerini önceden hesapla (smooth shading için)
            try:
                f = np.asarray(self.faces, dtype=int)
                v = np.asarray(self.vertices, dtype=float)
                v0 = v[f[:, 0]]
                v1 = v[f[:, 1]]
                v2 = v[f[:, 2]]
                n = np.cross(v1 - v0, v2 - v0)
                lens = np.linalg.norm(n, axis=1)
                lens[lens == 0] = 1.0
                n = n / lens[:, None]
                self.face_normals = n
            except Exception:
                self.face_normals = None

        self.reset_view()
        self.update()

    def set_user_transform(self, rot_x, rot_y, rot_z, scale=1.0):
        """
        Model döndürme butonlarından gelen açıları uygula.
        Grid ve eksenler BU açıdan etkilenmez.
        """
        self.user_rot_x = float(rot_x)
        self.user_rot_y = float(rot_y)
        self.user_rot_z = float(rot_z)
        self.user_scale = 1.0   # manuel ölçek yok
        self.update()

    def reset_view(self):
        """Görüntüyü ortala ve sabit uzaklığa getir."""
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.dist = self.base_dist
        self.update()

    # ---- OpenGL callback'leri ----

    def initializeGL(self):
        glutInit()  # axis yazıları için
        # Başlangıç zemin rengi
        glClearColor(self.bg_color[0], self.bg_color[1], self.bg_color[2], 1.0)
        glEnable(GL_DEPTH_TEST)
        glShadeModel(GL_SMOOTH)

        # --- Basit ışıklandırma (Windows 3B Görüntüleyici benzeri) ---
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_NORMALIZE)

        # Rengi materyal olarak kullan
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

        ambient = [0.3, 0.3, 0.3, 1.0]
        diffuse = [0.8, 0.8, 0.8, 1.0]
        specular = [0.2, 0.2, 0.2, 1.0]
        position = [0.0, 0.0, 1000.0, 1.0]

        glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
        glLightfv(GL_LIGHT0, GL_SPECULAR, specular)
        glLightfv(GL_LIGHT0, GL_POSITION, position)

    def resizeGL(self, w, h):
        if h == 0:
            h = 1
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / h
        gluPerspective(35.0, aspect, 0.1, 5000.0)
        glMatrixMode(GL_MODELVIEW)

    
    def paintGL(self):
        # Zemin rengi değişmiş olabilir, her frame set edelim
        glClearColor(self.bg_color[0], self.bg_color[1], self.bg_color[2], 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # ---- Kamera transformu (her şey için ortak) ----
        glTranslatef(self.pan_x, self.pan_y, -self.dist)
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)
        glRotatef(self.rot_z, 0, 0, 1)
        glScalef(self.user_scale, self.user_scale, self.user_scale)

        # ---- 1) GRID + EKSENLER (makine sabiti, orijinde) ----
        glPushMatrix()
        # Grid ve eksenler için ışığı kapat (daha okunaklı çizgiler)
        glDisable(GL_LIGHTING)
        self._draw_grid()
        self._draw_axes()
        glEnable(GL_LIGHTING)
        glPopMatrix()

        # ---- 2) STL + YOL (merkezi orijine taşınmış, SADECE user_rot ile döner) ----
        if self.vertices is not None and self.faces is not None:
            glPushMatrix()

            # STL için butonlardan gelen dönüşleri uygula
            glRotatef(self.user_rot_x, 1, 0, 0)
            glRotatef(self.user_rot_y, 0, 1, 0)
            glRotatef(self.user_rot_z, 0, 0, 1)

            # Mesh merkezini orijine taşı
            glTranslatef(-self.center[0], -self.center[1], -self.center[2])

            # --- STL çiz (smooth shading + ışık) ---
            if self.mesh_visible:
                glColor3f(self.mesh_color[0], self.mesh_color[1], self.mesh_color[2])
                glBegin(GL_TRIANGLES)
                if self.face_normals is not None:
                    for fi, f in enumerate(self.faces):
                        if fi < len(self.face_normals):
                            nx, ny, nz = self.face_normals[fi]
                            glNormal3f(nx, ny, nz)
                        for idx in f:
                            x, y, z = self.vertices[int(idx)]
                            glVertex3f(x, y, z)
                else:
                    for f in self.faces:
                        for idx in f:
                            x, y, z = self.vertices[int(idx)]
                            glVertex3f(x, y, z)
                glEnd()

            # --- Yol çiz (varsa) ---
            if self.path_points is not None and len(self.path_points) > 1:
                # Yol: hafif kırmızı/portakal renk, STL yüzeyine çok yakın bir Z'de
                glDisable(GL_LIGHTING)
                glLineWidth(2.0)
                glColor3f(1.0, 0.3, 0.0)
                glBegin(GL_LINE_STRIP)
                for x, y in self.path_points:
                    glVertex3f(x, y, 0.5)   # z=0.5 mm yukarıda
                glEnd()
                glLineWidth(1.0)

                # Başlangıç noktasına küçük bir kırmızı nokta
                sx, sy = self.path_points[0]
                glPointSize(6.0)
                glBegin(GL_POINTS)
                glColor3f(1.0, 0.0, 0.0)
                glVertex3f(sx, sy, 1.0)
                glEnd()
                glPointSize(1.0)
                glEnable(GL_LIGHTING)

            glPopMatrix()
    # ---- Fare kontrolleri ----

    def mousePressEvent(self, event):
        self._last_pos = event.pos()

    def mouseMoveEvent(self, event):
        dx = event.x() - self._last_pos.x()
        dy = event.y() - self._last_pos.y()
        if event.buttons() & Qt.LeftButton:
            # Orbit (döndürme)
            self.rot_x += dy * 0.5
            self.rot_y += dx * 0.5
        elif event.buttons() & Qt.RightButton:
            # Pan
            self.pan_x += dx * 0.01
            self.pan_y -= dy * 0.01
        self._last_pos = event.pos()
        self.update()

    def wheelEvent(self, event):
        # Zoom
        delta = event.angleDelta().y() / 120.0
        self.dist *= 0.9 ** delta
        if self.dist < 50.0:
            self.dist = 50.0
        if self.dist > 5000.0:
            self.dist = 5000.0
        self.update()

    # ---- Yardımcı: 3D metin ----

    def _draw_text3d(self, x, y, z, text):
        glColor3f(0.0, 0.0, 0.0)  # siyah
        glRasterPos3f(x, y, z)
        for ch in text:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(ch))

    # ---- Çizim yardımcıları ----

    def _draw_grid(self):
        """
        STL modeline göre ölçeklenen, Windows 3B Görüntüleyici benzeri grid.
        """
        # Model yoksa makine zarfına göre varsayılan grid
        r = float(self.radius) if hasattr(self, "radius") else 200.0
        if not np.isfinite(r) or r <= 1e-3:
            r = 200.0

        # Grid yarıçapı – modelden biraz büyük
        size = max(r * 1.5, 200.0)
        # Izgara aralığı – çok sık/çok seyrek olmasın
        step = max(size / 12.0, 10.0)
        step = min(step, 50.0)

        # İnce grid çizgileri
        glLineWidth(1.0)
        glColor3f(0.35, 0.35, 0.35)
        glBegin(GL_LINES)

        x = -size
        while x <= size + 1e-6:
            glVertex3f(x, -size, 0)
            glVertex3f(x, size, 0)
            x += step

        y = -size
        while y <= size + 1e-6:
            glVertex3f(-size, y, 0)
            glVertex3f(size, y, 0)
            y += step

        glEnd()

        # Ana eksen çizgileri (X, Y) daha parlak
        glLineWidth(2.0)
        glColor3f(0.6, 0.6, 0.6)
        glBegin(GL_LINES)
        # X ekseni
        glVertex3f(-size, 0, 0)
        glVertex3f(size, 0, 0)
        # Y ekseni
        glVertex3f(0, -size, 0)
        glVertex3f(0, size, 0)
        glEnd()
        glLineWidth(1.0)


    def _draw_axes(self):
        # Eksen uzunluğu – grid'e göre ayarlı
        s = 150.0

        glLineWidth(2.0)
        glBegin(GL_LINES)

        # X (kırmızı)
        glColor3f(1.0, 0.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(s, 0, 0)

        # Y (yeşil)
        glColor3f(0.0, 1.0, 0.0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, s, 0)

        # Z (mavi, biraz koyu)
        glColor3f(0.0, 0.2, 0.8)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, s)

        glEnd()
        glLineWidth(1.0)

        # Eksen isimleri
        self._draw_text3d(s + 10, 0, 0, "X")
        self._draw_text3d(0, s + 10, 0, "Y")
        self._draw_text3d(0, 0, s + 10, "Z")
