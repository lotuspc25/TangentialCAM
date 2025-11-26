import numpy as np


def _fmt(v: float, decimals: int = 3) -> str:
    """Kısa float formatı."""
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return str(v)


def _ensure_xy(path_data):
    if path_data is None or not hasattr(path_data, "xy"):
        raise ValueError("Geçerli path_data.xy yok.")
    xy = np.asarray(path_data.xy, dtype=float)
    if xy.ndim != 2 or xy.shape[0] == 0 or xy.shape[1] < 2:
        raise ValueError("path_data.xy boş veya hatalı.")
    return xy


def _compute_origin_offset(xy: np.ndarray, origin_mode: str):
    """XY noktalarından G54 parça orjini için offset hesapla."""
    if xy is None or xy.size == 0:
        return 0.0, 0.0
    xs = xy[:, 0]
    ys = xy[:, 1]
    minx, maxx = float(xs.min()), float(xs.max())
    miny, maxy = float(ys.min()), float(ys.max())
    cx = 0.5 * (minx + maxx)
    cy = 0.5 * (miny + maxy)

    mode = (origin_mode or "bottom_left").lower()
    if mode == "bottom_left":
        return minx, miny
    elif mode == "bottom_right":
        return maxx, miny
    elif mode == "top_left":
        return minx, maxy
    elif mode == "top_right":
        return maxx, maxy
    elif mode == "center":
        return cx, cy
    # tanınmayan durumda offset yok
    return 0.0, 0.0

def generate_gcode_flat(
    path_data,
    feed_xy: float = 2000.0,
    safe_z: float = 5.0,
    cut_z: float = -1.0,
    knife_axis: str = "A",
    knife_offset_deg: float = 0.0,
    origin_mode: str = "bottom_left",
) -> str:
    """Z takibi OLMAYAN (sabit Z'li) basit XY + bıçak ekseni G-kodu üretir.

    - path_data.xy kullanılır
    - path_data.angles varsa, bıçak eksenini (A vb.) döndürmek için kullanılır
    - path_data.z göz ardı edilir
    - Z ekseni sabit `cut_z` derinliğine iner

    Not: path_data.meta["depth"] varsa onu kullanıp cut_z = -depth yapar.
    """
    xy = _ensure_xy(path_data)

    # G54 parça orjini için offset uygula
    ox, oy = _compute_origin_offset(xy, origin_mode)
    xy = xy - np.array([ox, oy])

    # INI'deki derinlik bilgisini kullan (varsa)
    depth = None
    if hasattr(path_data, "meta") and isinstance(path_data.meta, dict):
        if "depth" in path_data.meta:
            try:
                depth = float(path_data.meta["depth"])
            except Exception:
                depth = None
    if depth is not None:
        # Model tepesinin Z=0 olduğunu varsayıp sabit kesme derinliği
        cut_z = -abs(depth)

    # Açı vektörü (opsiyonel)
    angles = None
    if hasattr(path_data, "angles") and path_data.angles is not None:
        import numpy as _np
        try:
            angles = _np.asarray(path_data.angles, dtype=float)
            if angles.shape[0] != _ensure_xy(path_data).shape[0]:
                angles = None
        except Exception:
            angles = None

    lines = []
    lines.append("(Tangential CAM - 2D G-kodu, Z takibi yok)")
    lines.append("G21  (mm)")
    lines.append("G90  (mutlak koordinat)")
    lines.append("G54")
    lines.append(f"G0 Z{_fmt(safe_z)}")

    x0, y0 = xy[0]
    a0 = angles[0] + knife_offset_deg if angles is not None else None

    # İlk noktaya hızlı geçiş
    cmd0 = f"G0 X{_fmt(x0)} Y{_fmt(y0)}"
    if a0 is not None:
        cmd0 += f" {knife_axis}{_fmt(a0)}"
    lines.append(cmd0)

    # Sabit kesme derinliğine in
    lines.append(f"G1 Z{_fmt(cut_z)} F{_fmt(feed_xy)}")

    # Yol boyunca ilerle
    for i, (x, y) in enumerate(xy[1:], start=1):
        cmd = f"G1 X{_fmt(x)} Y{_fmt(y)}"
        if angles is not None:
            a = angles[i] + knife_offset_deg
            cmd += f" {knife_axis}{_fmt(a)}"
        cmd += f" F{_fmt(feed_xy)}"
        lines.append(cmd)

    lines.append(f"G0 Z{_fmt(safe_z)}")
    lines.append("M30")
    return "\n".join(lines)


def generate_gcode_3d(
    path_data,
    feed_xy: float = 2000.0,
    feed_z: float = 800.0,
    safe_z: float = 5.0,
    knife_axis: str = "A",
    knife_offset_deg: float = 0.0,
    origin_mode: str = "bottom_left",
) -> str:
    """Z derinliği + bıçak açısı (A ekseni) içeren G-kodu üretir.

    - path_data.xy, path_data.z, path_data.angles kullanılır.
    - knife_offset_deg ile bıçak yönü (+0, +180 vb.) kaydırılabilir.
    """
    xy = _ensure_xy(path_data)

    # G54 parça orjini için offset uygula
    ox, oy = _compute_origin_offset(xy, origin_mode)
    xy = xy - np.array([ox, oy])

    z = None
    if hasattr(path_data, "z") and path_data.z is not None:
        z = np.asarray(path_data.z, dtype=float)
        if z.shape[0] != xy.shape[0]:
            z = None  # güvenli tarafta kal

    angles = None
    if hasattr(path_data, "angles") and path_data.angles is not None:
        angles = np.asarray(path_data.angles, dtype=float)
        if angles.shape[0] != xy.shape[0]:
            angles = None

    n = xy.shape[0]
    lines = []
    lines.append("(Tangential CAM - 3D G-kodu, Z takipli)")
    lines.append("G21  (mm)")
    lines.append("G90  (mutlak koordinat)")
    lines.append("G54")
    lines.append(f"G0 Z{_fmt(safe_z)}")

    x0, y0 = xy[0]
    z0 = z[0] if z is not None else None
    a0 = angles[0] + knife_offset_deg if angles is not None else None

    # İlk noktaya hızlı geçiş
    cmd = f"G0 X{_fmt(x0)} Y{_fmt(y0)}"
    if a0 is not None:
        cmd += f" {knife_axis}{_fmt(a0)}"
    lines.append(cmd)

    # Z'ye in
    if z0 is not None:
        lines.append(f"G1 Z{_fmt(z0)} F{_fmt(feed_z)}")

    # Kalan noktalar
    for i in range(1, n):
        x, y = xy[i]
        cmd = f"G1 X{_fmt(x)} Y{_fmt(y)} F{_fmt(feed_xy)}"
        if z is not None:
            cmd += f" Z{_fmt(z[i])}"
        if angles is not None:
            a = angles[i] + knife_offset_deg
            cmd += f" {knife_axis}{_fmt(a)}"
        lines.append(cmd)

    lines.append(f"G0 Z{_fmt(safe_z)}")
    lines.append("M30")
    return "\n".join(lines)
