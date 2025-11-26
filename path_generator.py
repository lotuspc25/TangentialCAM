import numpy as np
import trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union

from stl_loader import apply_transform


class PathData:
    """Yol verisi: XY, Z, A açıları.

    Attributes
    ----------
    xy : (N,2) array
        Makine eksenlerine göre hizalanmış XY (G-kodu için kullanılacak).
    z : (N,) array
        Takım merkezinin dünya koordinatındaki Z değeri (mm).
    angles : (N,) array
        A ekseni açıları (derece).
    xy_geom : (N,2) array
        Modelin kendi koordinat sistemindeki XY (mesh ile çakışan kontur).
    meta : dict
        İlave bilgileri tutmak için serbest sözlük.
    """
    def __init__(self, xy: np.ndarray, z: np.ndarray, angles: np.ndarray,
                 xy_geom: np.ndarray = None, meta: dict | None = None):
        self.xy = xy    # (N,2) - makine XY
        self.z = z      # (N,)  - dünya Z
        self.angles = angles  # (N,) A ekseni açıları
        # Geometri XY: verilmezse makine XY ile aynı kabul et
        self.xy_geom = xy if xy_geom is None else xy_geom
        # İlave bilgiler (ör: rotate_90, offsetler vs.)
        self.meta = {} if meta is None else dict(meta)


def _get_concave_outline_xy(mesh: trimesh.Trimesh,
                            min_area: float,
                            step_decimate: int,
                            progress=lambda p, msg="": None) -> np.ndarray:
    """
    Mesh'in XY düzlemindeki concave (dış) konturunu bulur.
    """
    verts = mesh.vertices
    faces = mesh.faces

    # Tüm üçgenlerin XY projeksiyonunu al
    polys = []
    for f in faces:
        tri = verts[f]
        poly = Polygon(tri[:, :2])
        if poly.is_valid and not poly.is_empty:
            polys.append(poly)

    if not polys:
        raise RuntimeError("Geçerli üçgen poligonu bulunamadı.")

    progress(10, "XY üçgenleri birleştiriliyor...")
    merged = unary_union(polys)

    # Concave dış sınır (en büyük alanlı polygon)
    if isinstance(merged, Polygon):
        outer = merged
    else:
        # Çoklu geometri olabilir, en büyük alanlıyı seç
        max_area = 0.0
        outer = None
        for g in merged.geoms:
            if isinstance(g, Polygon) and g.area > max_area:
                max_area = g.area
                outer = g
        if outer is None:
            raise RuntimeError("Dış kontur bulunamadı.")

    progress(20, "XY dış kontur örnekleniyor...")

    # Alan filtresi (çok küçük adacıkları eleyelim)
    if min_area > 0.0:
        if outer.area < min_area:
            raise RuntimeError(
                f"Dış kontur alanı çok küçük: {outer.area:.6f} < {min_area:.6f}"
            )

    # Kontur koordinatları
    coords = np.array(outer.exterior.coords)
    xy = coords[:, :2]

    # Nokta seyreltme
    if step_decimate > 1 and len(xy) > step_decimate:
        xy = xy[::step_decimate]

    return xy


def _sample_surface_z(mesh: trimesh.Trimesh,
                      contour_xy: np.ndarray,
                      progress=lambda p, msg="": None) -> np.ndarray:
    """
    Verilen XY kontur noktaları için mesh yüzeyinden Z örnekler.
    """
    verts = mesh.vertices
    verts_xy = verts[:, :2]
    zs = []
    N = len(contour_xy)

    for i, p in enumerate(contour_xy):
        diff = verts_xy - p
        d2 = (diff * diff).sum(axis=1)
        idx = int(d2.argmin())
        zs.append(float(verts[idx, 2]))

        if i % 200 == 0:
            progress(40 + 30 * i / max(1, N), "Z yüzeyi örnekleniyor...")

    return np.array(zs, dtype=float)


def _compute_angles(contour_xy: np.ndarray,
                    progress=lambda p, msg="": None) -> np.ndarray:
    """
    XY kontur boyunca tangential bıçak açısını (derece) hesaplar.
    """
    N = len(contour_xy)
    if N < 2:
        raise RuntimeError("Açı hesaplamak için yeterli nokta yok.")

    angles = np.zeros(N, dtype=float)

    for i in range(N):
        p_prev = contour_xy[i - 1]
        p_curr = contour_xy[i]
        p_next = contour_xy[(i + 1) % N]

        # Merkezdeki noktanın eğimi: (p_next - p_prev)
        v = p_next - p_prev
        dx, dy = v[0], v[1]
        angle = np.degrees(np.arctan2(dy, dx))
        angles[i] = angle

        if i % 200 == 0:
            progress(70 + 15 * i / max(1, N), "Açı hesaplanıyor...")

    return angles


def _rotate_for_machine(xy: np.ndarray, angles_deg: np.ndarray, rotate_90: bool):
    x_old = xy[:, 0]
    y_old = xy[:, 1]

    if rotate_90:
        x_rot = -y_old
        y_rot = x_old
        angles_new = angles_deg + 90.0
    else:
        x_rot = x_old
        y_rot = y_old
        angles_new = angles_deg

    x_min = float(x_rot.min())
    y_min = float(y_rot.min())
    x_new = x_rot - x_min
    y_new = y_rot - y_min

    xy_rot = np.column_stack((x_new, y_new))
    return xy_rot, angles_new


def generate_tangential_path(
    mesh: trimesh.Trimesh,
    transform_matrix: np.ndarray,
    min_area: float,
    step_decimate: int,
    rotate_90_for_machine: bool,
    depth_from_top: float,
    progress_callback=lambda p, msg="": None,
) -> PathData:
    """
    Ana yol üretim fonksiyonu.

    mesh:
        STL'den yüklenen Trimesh modeli.
    transform_matrix:
        Model sekmesindeki rotasyon/ölçek matrisini kullanarak mesh'e uygulanacak
        4x4 homojen matris.
    min_area:
        Concave kontur için minimum alan (mm^2).
    step_decimate:
        Kontur noktalarını seyreltme adımı.
    rotate_90_for_machine:
        Makineye göre 90° döndür (X400/Y800) seçeneği.
    depth_from_top:
        Yüzeyden aşağı doğru bıçak derinliği (mm, + değer).
    progress_callback:
        UI'dan gelen progress bar güncelleme fonksiyonu.
    """

    def progress(p, msg=""):
        progress_callback(int(p), msg)

    progress(5, "Transform uygulanıyor...")
    t_mesh = apply_transform(mesh, transform_matrix)

    progress(15, "Concave kontur hesaplanıyor...")
    contour_xy = _get_concave_outline_xy(
        t_mesh, min_area=min_area, step_decimate=step_decimate, progress=progress
    )

    progress(40, "Z örnekleniyor...")
    zs = _sample_surface_z(t_mesh, contour_xy, progress=progress)

    # Takım merkezinin gerçek Z konumu: yüzey Z'si - derinlik
    depth = abs(depth_from_top)
    z_tool = zs - depth

    progress(70, "Açı (A ekseni) hesaplanıyor...")
    angles = _compute_angles(contour_xy, progress=progress)

    progress(85, "Makine eksenlerine göre hizalanıyor...")
    xy_rot, angles_rot = _rotate_for_machine(
        contour_xy, angles, rotate_90=rotate_90_for_machine
    )

    meta = {
        "rotate_90": bool(rotate_90_for_machine),
        "depth": float(depth),
    }

    progress(100, "Yol hazır.")
    return PathData(xy_rot, z_tool, angles_rot, xy_geom=contour_xy, meta=meta)
# ---------------------------------------------------------
# Geriye dönük uyumluluk: eski kodlar generate_path diyordu
# ---------------------------------------------------------
def generate_path(*args, **kwargs):
    """
    Eski isim. Yeni fonksiyon generate_tangential_path'i çağırır.
    tab_path.py içinde 'from path_generator import generate_path'
    satırı bu sayede sorunsuz çalışır.
    """
    return generate_tangential_path(*args, **kwargs)
