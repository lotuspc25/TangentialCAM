
import numpy as np

def compute_path_tangent_angle_deg(points_xy, index=0):
    if len(points_xy) < 2:
        return 0.0
    p0=points_xy[index]
    p1=points_xy[index+1]
    dx,dy=p1-p0
    return np.degrees(np.arctan2(dy,dx))

def estimate_visual_length(points_xy, scale=0.1):
    if len(points_xy)<2:
        return 10.0
    d=np.linalg.norm(points_xy[-1]-points_xy[0])
    return max(5.0, d*scale)

def draw_knife_gl_3d(base_xyz, angle_deg, length, lift_z=10.0):
    # placeholder
    return

def draw_knife_2d_matplotlib(ax, base_xy, angle_deg, length, color='orange'):
    x,y=base_xy
    import numpy as np
    ang=np.radians(angle_deg)
    dx=length*np.cos(ang)
    dy=length*np.sin(ang)
    ax.arrow(x,y,dx,dy,head_width=length*0.1,fc=color,ec=color)
