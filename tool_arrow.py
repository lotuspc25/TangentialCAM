
import math
from OpenGL.GL import *

def draw_tool_arrow(origin, angle_deg, length=50.0, lift_z=20.0):
    x,y,z = origin
    z = z + lift_z
    ang = math.radians(angle_deg)
    dx = length*math.cos(ang)
    dy = length*math.sin(ang)
    glColor3f(1.0,0.0,0.0)
    glBegin(GL_LINES)
    glVertex3f(x,y,z)
    glVertex3f(x+dx, y+dy, z)
    glEnd()
