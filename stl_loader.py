import numpy as np
import trimesh


def load_stl(path: str) -> trimesh.Trimesh:
    mesh = trimesh.load(path)
    if isinstance(mesh, trimesh.Scene):
        parts = [
            g for g in mesh.geometry.values()
            if isinstance(g, trimesh.Trimesh)
        ]
        if not parts:
            raise RuntimeError("STL içinde geçerli mesh bulunamadı.")
        mesh = trimesh.util.concatenate(parts)
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError("STL Trimesh değil.")
    return mesh


def make_transform_matrix(rot_x_deg: float,
                          rot_y_deg: float,
                          rot_z_deg: float,
                          scale: float) -> np.ndarray:
    """Rx, Ry, Rz ve scale'den 4x4 homogeneous matris üret."""
    sx = sy = sz = scale
    rx = np.radians(rot_x_deg)
    ry = np.radians(rot_y_deg)
    rz = np.radians(rot_z_deg)

    Rx = np.array([
        [1, 0, 0, 0],
        [0, np.cos(rx), -np.sin(rx), 0],
        [0, np.sin(rx), np.cos(rx), 0],
        [0, 0, 0, 1],
    ])

    Ry = np.array([
        [np.cos(ry), 0, np.sin(ry), 0],
        [0, 1, 0, 0],
        [-np.sin(ry), 0, np.cos(ry), 0],
        [0, 0, 0, 1],
    ])

    Rz = np.array([
        [np.cos(rz), -np.sin(rz), 0, 0],
        [np.sin(rz), np.cos(rz), 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
    ])

    S = np.diag([sx, sy, sz, 1.0])

    # S * Rz * Ry * Rx
    M = S @ Rz @ Ry @ Rx
    return M


def apply_transform(mesh: trimesh.Trimesh,
                    matrix: np.ndarray) -> trimesh.Trimesh:
    new_mesh = mesh.copy()
    new_mesh.apply_transform(matrix)
    return new_mesh
