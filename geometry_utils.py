# geometry_utils.py
"""
Yol üretimi için temel geometri fonksiyonları.

Şimdilik sadece:
    - get_concave_outline_xy(mesh, min_area, step_decimate)

kullanıyoruz.
"""

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union


def get_concave_outline_xy(mesh, min_area: float = 0.0, step_decimate: int = 1):
    """
    Verilen mesh'in XY düzlemindeki dış konturunu yaklaşık olarak hesaplar.

    Adımlar:
      1) Mesh yüzeylerini (triangles) XY düzlemine projeler.
      2) Her üçgenden bir Shapely Polygon oluşturur.
      3) Tüm poligonları birleştirir (unary_union).
      4) Ortaya çıkan bölgenin dış sınır koordinatlarını alır.
      5) STEP_DECIMATE ile noktaları seyreltir.

    Parametreler:
        mesh           : trimesh.Trimesh (vertices, faces)
        min_area       : Çok küçük yüzeyleri elemek için alan eşiği (mm²).
        step_decimate  : 1=her nokta, 2=her 2. nokta, 3=her 3. nokta...

    Dönen:
        contour_xy : (N,2) numpy.ndarray  -> [ [x1,y1], [x2,y2], ... ]
    """
    if mesh is None or mesh.vertices is None or mesh.faces is None:
        raise ValueError("Geçerli bir mesh (Trimesh) verilmedi.")

    verts_xy = mesh.vertices[:, :2]  # sadece X,Y

    polygons = []
    for f in mesh.faces:
        tri = verts_xy[f]  # (3,2)
        poly = Polygon(tri)
        if not poly.is_valid:
            continue
        if poly.area <= float(min_area):
            continue
        polygons.append(poly)

    if not polygons:
        raise RuntimeError("Kontur oluşturacak yeterli yüzey bulunamadı.")

    region = unary_union(polygons)

    # Birden fazla parça çıkarsa, en büyük alanlıyı al
    if region.geom_type == "MultiPolygon":
        region = max(region.geoms, key=lambda g: g.area)

    exterior = region.exterior
    coords = np.array(exterior.coords, dtype=float)  # (N,2)

    if step_decimate < 1:
        step_decimate = 1
    if step_decimate > 1 and coords.shape[0] > step_decimate:
        coords = coords[::step_decimate, :]

    return coords
