# settings.py
import configparser
import os

INI_FILE = os.path.join(os.path.dirname(__file__), "tangential_cam.ini")

DEFAULTS = {
    "bg_color": "#444444",     # koyu gri (3B Görüntüleyici tarzı)
    "mesh_color": "#D07090",   # pembe / morumsu
}


def load_settings():
    cfg = configparser.ConfigParser()
    data = DEFAULTS.copy()

    if os.path.exists(INI_FILE):
        cfg.read(INI_FILE, encoding="utf-8")
        if "view" in cfg:
            section = cfg["view"]
            for key in DEFAULTS:
                if key in section:
                    data[key] = section[key]

    return data


def save_settings(data: dict):
    cfg = configparser.ConfigParser()
    cfg["view"] = {}
    for key, val in data.items():
        cfg["view"][key] = str(val)

    with open(INI_FILE, "w", encoding="utf-8") as f:
        cfg.write(f)
