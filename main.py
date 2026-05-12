#!/usr/bin/env python3
"""
Custom Windows Shell Bar  —  v9
================================
Requirements:
    pip install pyvda psutil pillow
Optional:
    pip install pynvml   (NVIDIA GPU stats)

Hotkeys:
    Alt+1..9   – switch virtual desktop
    Alt+Space  – open / close launcher
    Alt+C      – open config panel

Config:
    %LOCALAPPDATA%\\CustomShellBar\\shellbar_config.json
    Edit via the interactive config panel (power button → Config) or Alt+C.
"""

import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox as mb
import tkinter.filedialog as fd
import tkinter.ttk as ttk
import threading
import time
import os
import sys
import json
import shutil
import ctypes
import ctypes.wintypes
import subprocess
from datetime import datetime

# ── Optional deps ──────────────────────────────────────────────────────────────
try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("Pillow missing — icons disabled")

try:
    from pyvda import VirtualDesktop, get_virtual_desktops
    PYVDA_OK = True
except ImportError:
    PYVDA_OK = False

GPU_BACKEND = None
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_BACKEND = "nvml"
except Exception:
    pass

# ── Win32 ──────────────────────────────────────────────────────────────────────
user32  = ctypes.windll.user32
shell32 = ctypes.windll.shell32
gdi32   = ctypes.windll.gdi32
dwmapi  = ctypes.windll.dwmapi

SW_HIDE, SW_SHOW         = 0, 5
ABM_NEW, ABM_REMOVE      = 0, 1
ABM_QUERYPOS, ABM_SETPOS = 2, 3
ABE_BOTTOM               = 3
MOD_ALT, MOD_NOREPEAT    = 0x0001, 0x4000
WM_HOTKEY                = 0x0312
SHGFI_ICON               = 0x100
SHGFI_SMALLICON          = 0x001
SHGFI_LARGEICON          = 0x000
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND             = 2
WCA_ACCENT_POLICY        = 19


class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState",   ctypes.c_int),
                ("AccentFlags",   ctypes.c_int),
                ("GradientColor", ctypes.c_uint),
                ("AnimationId",   ctypes.c_int)]

class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int),
                ("pData",     ctypes.c_void_p),
                ("cbData",    ctypes.c_size_t)]

class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize",           ctypes.wintypes.DWORD),
                ("hWnd",             ctypes.wintypes.HWND),
                ("uCallbackMessage", ctypes.wintypes.UINT),
                ("uEdge",            ctypes.wintypes.UINT),
                ("rc",               ctypes.wintypes.RECT),
                ("lParam",           ctypes.wintypes.LPARAM)]

class SHFILEINFOW(ctypes.Structure):
    _fields_ = [("hIcon",         ctypes.wintypes.HANDLE),
                ("iIcon",         ctypes.c_int),
                ("dwAttributes",  ctypes.wintypes.DWORD),
                ("szDisplayName", ctypes.c_wchar * 260),
                ("szTypeName",    ctypes.c_wchar * 80)]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize",          ctypes.wintypes.DWORD),
                ("biWidth",         ctypes.wintypes.LONG),
                ("biHeight",        ctypes.wintypes.LONG),
                ("biPlanes",        ctypes.wintypes.WORD),
                ("biBitCount",      ctypes.wintypes.WORD),
                ("biCompression",   ctypes.wintypes.DWORD),
                ("biSizeImage",     ctypes.wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.wintypes.LONG),
                ("biYPelsPerMeter", ctypes.wintypes.LONG),
                ("biClrUsed",       ctypes.wintypes.DWORD),
                ("biClrImportant",  ctypes.wintypes.DWORD)]


# ══════════════════════════════════════════════════════════════════════════════
# INSTALL PATHS
# ══════════════════════════════════════════════════════════════════════════════
APPDATA_DIR  = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")),
                             "CustomShellBar")
CONFIG_FILE  = os.path.join(APPDATA_DIR, "shellbar_config.json")
INSTALL_PY   = os.path.join(APPDATA_DIR, "shellbar.py")
CACHE_DIR    = os.path.join(APPDATA_DIR, "icache")
FIRSTRUN_FLAG= os.path.join(APPDATA_DIR, ".firstrun_done")
os.makedirs(APPDATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN THEMES
# ══════════════════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "_name": "Dark",
        "bar_bg":       "#0b0b16",
        "bar_pill":     "#17172c",
        "pill_act":     "#5b5fc7",
        "border":       "#20203a",
        "border_bright":"#3a3a6a",
        "launch_bg":    "#0a0a18",
        "row_hov":      "#13132a",
        "row_sel":      "#1a1a38",
        "row_accent":   "#5b5fc7",
        "search_bg":    "#0f0f22",
        "search_focus": "#5b5fc7",
        "fg":           "#e8e5ff",
        "fg2":          "#5e5a92",
        "fg3":          "#2a2845",
        "fg_path":      "#3a3760",
        "accent":       "#5b5fc7",
        "accent_glow":  "#4a4eb8",
        "green":        "#3ecf7a",
        "red":          "#f06b6b",
        "cyan":         "#22d0e8",
        "violet":       "#9b7ff5",
        "badge_bg":     "#17172c",
        "badge_fg":     "#5e5a92",
        "category":     "#3d3a6a",
        "acrylic_tint": "0xE0060414",
    },
    "light": {
        "_name": "Light",
        "bar_bg":       "#f0f0f8",
        "bar_pill":     "#dcdcee",
        "pill_act":     "#5b5fc7",
        "border":       "#c8c8e0",
        "border_bright":"#9898cc",
        "launch_bg":    "#f5f5fc",
        "row_hov":      "#eaeaf8",
        "row_sel":      "#dcdcf4",
        "row_accent":   "#5b5fc7",
        "search_bg":    "#eaeaf8",
        "search_focus": "#5b5fc7",
        "fg":           "#1a1a3a",
        "fg2":          "#6666aa",
        "fg3":          "#c0c0e0",
        "fg_path":      "#9898cc",
        "accent":       "#5b5fc7",
        "accent_glow":  "#4a4eb8",
        "green":        "#1a9952",
        "red":          "#d93232",
        "cyan":         "#0891b2",
        "violet":       "#7c3aed",
        "badge_bg":     "#dcdcee",
        "badge_fg":     "#6666aa",
        "category":     "#9898cc",
        "acrylic_tint": "0xD0F0F0F8",
    },
    "mocha": {
        "_name": "Mocha",
        "bar_bg":       "#1e1916",
        "bar_pill":     "#2d2520",
        "pill_act":     "#c07a40",
        "border":       "#3a3028",
        "border_bright":"#5a4838",
        "launch_bg":    "#191512",
        "row_hov":      "#242018",
        "row_sel":      "#2e2820",
        "row_accent":   "#c07a40",
        "search_bg":    "#1c1814",
        "search_focus": "#c07a40",
        "fg":           "#f0e8d8",
        "fg2":          "#907060",
        "fg3":          "#3a3028",
        "fg_path":      "#5a4838",
        "accent":       "#c07a40",
        "accent_glow":  "#a06030",
        "green":        "#7abf6a",
        "red":          "#e05050",
        "cyan":         "#60b8c0",
        "violet":       "#c080e0",
        "badge_bg":     "#2d2520",
        "badge_fg":     "#907060",
        "category":     "#5a4838",
        "acrylic_tint": "0xE0100800",
    },
    "nord": {
        "_name": "Nord",
        "bar_bg":       "#2e3440",
        "bar_pill":     "#3b4252",
        "pill_act":     "#88c0d0",
        "border":       "#434c5e",
        "border_bright":"#4c566a",
        "launch_bg":    "#292e3a",
        "row_hov":      "#3b4252",
        "row_sel":      "#434c5e",
        "row_accent":   "#88c0d0",
        "search_bg":    "#3b4252",
        "search_focus": "#88c0d0",
        "fg":           "#eceff4",
        "fg2":          "#4c566a",
        "fg3":          "#3b4252",
        "fg_path":      "#4c566a",
        "accent":       "#88c0d0",
        "accent_glow":  "#6eb0c0",
        "green":        "#a3be8c",
        "red":          "#bf616a",
        "cyan":         "#8fbcbb",
        "violet":       "#b48ead",
        "badge_bg":     "#3b4252",
        "badge_fg":     "#4c566a",
        "category":     "#4c566a",
        "acrylic_tint": "0xE0202830",
    },
    "rose": {
        "_name": "Rose Pine",
        "bar_bg":       "#191724",
        "bar_pill":     "#1f1d2e",
        "pill_act":     "#eb6f92",
        "border":       "#26233a",
        "border_bright":"#403d52",
        "launch_bg":    "#16141f",
        "row_hov":      "#1f1d2e",
        "row_sel":      "#26233a",
        "row_accent":   "#eb6f92",
        "search_bg":    "#1a1826",
        "search_focus": "#eb6f92",
        "fg":           "#e0def4",
        "fg2":          "#6e6a86",
        "fg3":          "#26233a",
        "fg_path":      "#403d52",
        "accent":       "#eb6f92",
        "accent_glow":  "#c85070",
        "green":        "#31748f",
        "red":          "#eb6f92",
        "cyan":         "#9ccfd8",
        "violet":       "#c4a7e7",
        "badge_bg":     "#1f1d2e",
        "badge_fg":     "#6e6a86",
        "category":     "#403d52",
        "acrylic_tint": "0xE006040C",
    },
    "hacker": {
        "_name": "Hacker",
        "bar_bg":       "#000000",
        "bar_pill":     "#0a0f0a",
        "pill_act":     "#00ff41",
        "border":       "#0a1a0a",
        "border_bright":"#1a3a1a",
        "launch_bg":    "#000000",
        "row_hov":      "#050f05",
        "row_sel":      "#0a1e0a",
        "row_accent":   "#00ff41",
        "search_bg":    "#050f05",
        "search_focus": "#00ff41",
        "fg":           "#00ff41",
        "fg2":          "#006620",
        "fg3":          "#001a00",
        "fg_path":      "#003310",
        "accent":       "#00ff41",
        "accent_glow":  "#00cc33",
        "green":        "#00ff41",
        "red":          "#ff2222",
        "cyan":         "#00ffff",
        "violet":       "#cc00ff",
        "badge_bg":     "#0a0f0a",
        "badge_fg":     "#006620",
        "category":     "#003310",
        "acrylic_tint": "0xF0000000",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# BAR ELEMENT DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════
BAR_ELEMENTS = [
    {"key": "desktop_switcher", "label": "Desktop Switcher", "side": "left",
     "desc": "Virtual desktop number buttons (Alt+1-9 to switch)"},
    {"key": "pinned_apps",      "label": "Pinned Apps",       "side": "left",
     "desc": "Quick-launch icon buttons for your chosen apps"},
    {"key": "clock",            "label": "Clock",             "side": "center",
     "desc": "Date and time display in the centre of the bar"},
    {"key": "gpu",              "label": "GPU Usage",         "side": "right",
     "desc": "GPU utilisation % (requires NVIDIA or WMI fallback)"},
    {"key": "cpu",              "label": "CPU Usage",         "side": "right",
     "desc": "CPU utilisation %"},
    {"key": "ram",              "label": "RAM Usage",         "side": "right",
     "desc": "Memory usage %"},
    {"key": "net",              "label": "Network Speed",     "side": "right",
     "desc": "Total upload + download bandwidth in KB/s"},
    {"key": "power_button",     "label": "Power Button",      "side": "right",
     "desc": "Shutdown / sleep / config menu button"},
]

# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN BAR LAYOUT PRESETS
# ══════════════════════════════════════════════════════════════════════════════
BAR_PRESETS = {
    "default": {
        "_name": "Default",
        "_desc": "All elements, clock centred",
        "element_order": ["desktop_switcher","pinned_apps","clock",
                          "gpu","cpu","ram","net","power_button"],
        "element_visible": {k: True for k in
                            ["desktop_switcher","pinned_apps","clock",
                             "gpu","cpu","ram","net","power_button"]},
    },
    "minimal": {
        "_name": "Minimal",
        "_desc": "Clock + power only — clean and distraction-free",
        "element_order": ["clock","power_button"],
        "element_visible": {"clock": True, "power_button": True,
                            "desktop_switcher": False, "pinned_apps": False,
                            "gpu": False, "cpu": False, "ram": False, "net": False},
    },
    "developer": {
        "_name": "Developer",
        "_desc": "Stats-heavy: CPU, RAM, GPU, net + desktops",
        "element_order": ["desktop_switcher","clock","gpu","cpu","ram","net","power_button"],
        "element_visible": {"desktop_switcher": True, "clock": True,
                            "gpu": True, "cpu": True, "ram": True, "net": True,
                            "power_button": True, "pinned_apps": False},
    },
    "gamer": {
        "_name": "Gamer",
        "_desc": "GPU & CPU front-and-centre, no clock clutter",
        "element_order": ["gpu","cpu","ram","net","desktop_switcher","power_button"],
        "element_visible": {"gpu": True, "cpu": True, "ram": True, "net": True,
                            "desktop_switcher": True, "power_button": True,
                            "clock": False, "pinned_apps": False},
    },
    "classic": {
        "_name": "Classic Taskbar",
        "_desc": "Pinned apps + clock on the right, like Windows 7",
        "element_order": ["pinned_apps","clock","power_button"],
        "element_visible": {"pinned_apps": True, "clock": True, "power_button": True,
                            "desktop_switcher": False, "gpu": False,
                            "cpu": False, "ram": False, "net": False},
    },
    "status": {
        "_name": "Status Only",
        "_desc": "Stats bar with no launcher or clock",
        "element_order": ["gpu","cpu","ram","net","power_button"],
        "element_visible": {"gpu": True, "cpu": True, "ram": True, "net": True,
                            "power_button": True, "clock": False,
                            "desktop_switcher": False, "pinned_apps": False},
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT CONFIG
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "_comment": "CustomShellBar v9 — edit via the config panel or directly",
    "theme": "dark",
    "custom_theme": {},
    "bar": {
        "height": 40,
        "position": "top",
        "show_clock": True,
        "clock_format": "%a %d %b   %H:%M:%S",
        "show_cpu": True,
        "show_ram": True,
        "show_net": True,
        "show_gpu": True,
        "show_desktop_switcher": True,
        "font_family": "Segoe UI",
        "font_size": 9,
        "element_order": ["desktop_switcher","pinned_apps","clock",
                          "gpu","cpu","ram","net","power_button"],
        "element_visible": {k: True for k in
                            ["desktop_switcher","pinned_apps","clock",
                             "gpu","cpu","ram","net","power_button"]},
    },
    "pinned_apps": [],
    "launcher": {
        "width": 680,
        "max_height": 500,
        "icon_size": 28,
        "row_height": 48,
        "font_family": "Segoe UI",
        "font_size": 10,
        "show_path": True,
        "max_results": 60,
    },
    "hotkeys": {
        "launcher": "Alt+Space",
        "desktop_switch": "Alt+1..9",
        "config": "Alt+C",
    },
}


def _load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            print(f"Config load error: {e} — using defaults")
    if "element_order" not in cfg["bar"]:
        cfg["bar"]["element_order"] = DEFAULT_CONFIG["bar"]["element_order"][:]
    if "element_visible" not in cfg["bar"]:
        ev = {}
        ev["desktop_switcher"] = cfg["bar"].get("show_desktop_switcher", True)
        ev["clock"]            = cfg["bar"].get("show_clock", True)
        ev["cpu"]              = cfg["bar"].get("show_cpu", True)
        ev["ram"]              = cfg["bar"].get("show_ram", True)
        ev["net"]              = cfg["bar"].get("show_net", True)
        ev["gpu"]              = cfg["bar"].get("show_gpu", True)
        ev["power_button"]     = True
        ev["pinned_apps"]      = True
        cfg["bar"]["element_visible"] = ev
    return cfg


def _save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Config save error: {e}")


def _ensure_config():
    if not os.path.exists(CONFIG_FILE):
        _save_config(DEFAULT_CONFIG)


def _build_palette(cfg: dict) -> dict:
    theme_name = cfg.get("theme", "dark")
    base = dict(THEMES.get(theme_name, THEMES["dark"]))
    base.update(cfg.get("custom_theme", {}))
    return base


CFG = _load_config()
C   = _build_palette(CFG)

BAR_HEIGHT   = CFG["bar"].get("height", 40)
ICON_SZ      = CFG["launcher"].get("icon_size", 28)
ROW_H        = CFG["launcher"].get("row_height", 48)
LAUNCHER_W   = CFG["launcher"].get("width", 680)
LAUNCHER_H_MIN = 62
LAUNCHER_H_MAX = CFG["launcher"].get("max_height", 500)
MAX_RESULTS  = CFG["launcher"].get("max_results", 60)


# ── DWM helpers ────────────────────────────────────────────────────────────────
def _dwm_round(hwnd, pref=DWMWCP_ROUND):
    try:
        v = ctypes.c_int(pref)
        dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass

def _dwm_acrylic(hwnd, tint=0xD0080818):
    try:
        a = ACCENT_POLICY()
        a.AccentState   = 3
        a.AccentFlags   = 0x20
        a.GradientColor = tint
        d = WINDOWCOMPOSITIONATTRIBDATA()
        d.Attribute = WCA_ACCENT_POLICY
        d.pData     = ctypes.cast(ctypes.pointer(a), ctypes.c_void_p)
        d.cbData    = ctypes.sizeof(a)
        user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(d))
    except Exception:
        pass


_VK = {str(i): 0x30+i for i in range(10)}
_VK["space"] = 0x20
_VK["c"]     = 0x43


def _taskbar_vis(show: bool):
    sw = SW_SHOW if show else SW_HIDE
    for cls in ("Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        h = user32.FindWindowW(cls, None)
        if h:
            user32.ShowWindow(h, sw)


def _desk_count():
    if PYVDA_OK:
        try: return len(get_virtual_desktops())
        except: pass
    return 1

def _desk_cur():
    if not PYVDA_OK: return 0
    try:
        c = VirtualDesktop.current()
        for i, d in enumerate(get_virtual_desktops()):
            if d == c: return i
        return c.number - 1
    except: return 0

def _desk_go(idx):
    if not PYVDA_OK: return
    try: VirtualDesktop(idx+1).go()
    except Exception as e: print(f"desk_go: {e}")


# ── Icon extraction ────────────────────────────────────────────────────────────
def _resolve_lnk(path):
    try:
        r = subprocess.run(
            ["powershell", "-WindowStyle", "Hidden", "-NoProfile", "-Command",
             "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
             "$t=$s.TargetPath;$i=$s.IconLocation.Split(',')[0];"
             "if($t -and (Test-Path $t)){$t}"
             "elseif($i -and (Test-Path $i)){$i}"
             "else{''}" % path.replace("'", "''")],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=4)
        t = r.stdout.strip()
        if t and os.path.exists(t):
            return t
    except Exception:
        pass
    return path


def _hicon_to_pil(hicon, size):
    if not hicon:
        return None
    try:
        hdc = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(hdc)
        bmi = BITMAPINFOHEADER()
        bmi.biSize        = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth       = size
        bmi.biHeight      = -size
        bmi.biPlanes      = 1
        bmi.biBitCount    = 32
        bmi.biCompression = 0
        pb  = ctypes.c_void_p()
        hb  = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0,
                                      ctypes.byref(pb), None, 0)
        old = gdi32.SelectObject(mem, hb)
        gdi32.PatBlt(mem, 0, 0, size, size, 0x00000042)
        user32.DrawIconEx(mem, 0, 0, hicon, size, size, 0, None, 0x0003)
        buf = (ctypes.c_ubyte * (size * size * 4))()
        gdi32.GetDIBits(mem, hb, 0, size, buf, ctypes.byref(bmi), 0)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(hb)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, hdc)
        user32.DestroyIcon(hicon)
        raw = bytes(buf)
        img = Image.frombuffer("RGBA", (size, size), raw, "raw", "RGBA", 0, 1)
        r, g, b, a = img.split()
        img = Image.merge("RGBA", (b, g, r, a))
        return img if img.getbbox() else None
    except Exception as e:
        print(f"hicon_to_pil: {e}")
        return None


_ole32   = ctypes.windll.ole32
_shlwapi = ctypes.windll.shlwapi

_IID_IShellItem             = "{43826D1E-E718-42EE-BC55-A1E261C37BFE}"
_IID_IShellItemImageFactory = "{BCC18B79-BA16-442F-80C4-8A59C30C463B}"

def _guid(s):
    import uuid
    g = uuid.UUID(s)
    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8)]
    gg = GUID()
    gg.Data1 = g.time_low
    gg.Data2 = g.time_mid
    gg.Data3 = g.time_hi_version
    for i, b in enumerate(g.bytes[8:]):
        gg.Data4[i] = b
    return gg

def _shell_item_image(path, size):
    if not PIL_OK:
        return None
    try:
        iid_si   = _guid(_IID_IShellItem)
        iid_siif = _guid(_IID_IShellItemImageFactory)
        SHCreateItemFromParsingName = ctypes.windll.shell32.SHCreateItemFromParsingName
        SHCreateItemFromParsingName.restype  = ctypes.HRESULT
        SHCreateItemFromParsingName.argtypes = [
            ctypes.c_wchar_p, ctypes.c_void_p,
            ctypes.POINTER(type(iid_si)), ctypes.POINTER(ctypes.c_void_p)]
        psi = ctypes.c_void_p()
        hr  = SHCreateItemFromParsingName(path, None, ctypes.byref(iid_si), ctypes.byref(psi))
        if hr != 0 or not psi:
            return None
        psi_ptr = ctypes.cast(psi, ctypes.POINTER(ctypes.c_void_p))
        vtable  = ctypes.cast(psi_ptr[0], ctypes.POINTER(ctypes.c_void_p))
        QueryInterface = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p,
            ctypes.POINTER(type(iid_siif)), ctypes.POINTER(ctypes.c_void_p))(vtable[0])
        pfactory = ctypes.c_void_p()
        hr = QueryInterface(psi, ctypes.byref(iid_siif), ctypes.byref(pfactory))
        Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
            ctypes.cast(psi_ptr[0], ctypes.POINTER(ctypes.c_void_p))[2])
        Release(psi)
        if hr != 0 or not pfactory:
            return None
        fvtable = ctypes.cast(
            ctypes.cast(pfactory, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p))
        class SIZE(ctypes.Structure):
            _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]
        GetImage = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, SIZE,
            ctypes.c_uint, ctypes.POINTER(ctypes.wintypes.HBITMAP))(fvtable[3])
        hbmp = ctypes.wintypes.HBITMAP()
        sz   = SIZE(size, size)
        hr   = GetImage(pfactory, sz, 0x4, ctypes.byref(hbmp))
        RelF = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(fvtable[2])
        RelF(pfactory)
        if hr != 0 or not hbmp:
            return None
        img = _hbitmap_to_pil(hbmp, size)
        gdi32.DeleteObject(hbmp)
        return img
    except Exception as e:
        print(f"shell_item_image({path}): {e}")
        return None


def _hbitmap_to_pil(hbmp, size):
    try:
        hdc = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(hdc)
        bmi = BITMAPINFOHEADER()
        bmi.biSize        = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth       = size
        bmi.biHeight      = -size
        bmi.biPlanes      = 1
        bmi.biBitCount    = 32
        bmi.biCompression = 0
        buf = (ctypes.c_ubyte * (size * size * 4))()
        old = gdi32.SelectObject(mem, hbmp)
        gdi32.GetDIBits(mem, hbmp, 0, size, buf, ctypes.byref(bmi), 0)
        gdi32.SelectObject(mem, old)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, hdc)
        raw = bytes(buf)
        img = Image.frombuffer("RGBA", (size, size), raw, "raw", "RGBA", 0, 1)
        b, g, r, a = img.split()
        img = Image.merge("RGBA", (r, g, b, a))
        return img if img.getbbox() else None
    except Exception as e:
        print(f"hbitmap_to_pil: {e}")
        return None


import hashlib, pickle

_icache:      dict = {}
_icache_pend: set  = set()
_icache_lock        = threading.Lock()

def _disk_key(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()

def _load_disk(key: str):
    p = os.path.join(CACHE_DIR, _disk_key(key) + ".pkl")
    try:
        if os.path.exists(p):
            with open(p, "rb") as f:
                return pickle.load(f)
    except Exception:
        pass
    return None

def _save_disk(key: str, img):
    p = os.path.join(CACHE_DIR, _disk_key(key) + ".pkl")
    try:
        with open(p, "wb") as f:
            pickle.dump(img, f)
    except Exception:
        pass

def _icon_cached(key: str):
    with _icache_lock:
        if key in _icache:
            return True, _icache[key]
        if key in _icache_pend:
            return True, None
        img = _load_disk(key)
        if img is not None:
            _icache[key] = img
            return True, img
        _icache_pend.add(key)
        return False, None

def _icon_store(key: str, img):
    with _icache_lock:
        _icache[key] = img
        _icache_pend.discard(key)
    if img is not None:
        _save_disk(key, img)

def _icon_pil(path, size=None):
    if size is None:
        size = ICON_SZ
    if not PIL_OK:
        return None
    key = f"{path}:{size}"
    hit, img = _icon_cached(key)
    if hit:
        return img
    try: ctypes.windll.ole32.CoInitialize(None)
    except: pass
    img  = None
    real = _resolve_lnk(path) if path.lower().endswith(".lnk") else path
    img = _shell_item_image(path, size)
    if img is None and real != path and os.path.isfile(real):
        img = _shell_item_image(real, size)
    if img is None:
        target = real if (real and os.path.isfile(real)) else path
        if os.path.isfile(target):
            try:
                large = (ctypes.wintypes.HICON * 1)()
                small = (ctypes.wintypes.HICON * 1)()
                n     = shell32.ExtractIconExW(target, 0, large, small, 1)
                hicon = (small[0] if size <= 20 else large[0]) or large[0] or small[0]
                other = large[0] if size <= 20 else small[0]
                if n > 0 and hicon:
                    img = _hicon_to_pil(hicon, size)
                if other:
                    user32.DestroyIcon(other)
            except Exception as e:
                print(f"ExtractIconEx({target}): {e}")
    if img is None:
        for probe in ([path, real] if real != path else [path]):
            if not probe or not os.path.exists(probe):
                continue
            try:
                flag = 0x101 if size <= 20 else 0x100
                fi   = SHFILEINFOW()
                ret  = shell32.SHGetFileInfoW(
                    probe, 0, ctypes.byref(fi), ctypes.sizeof(SHFILEINFOW), flag)
                if ret and fi.hIcon:
                    img = _hicon_to_pil(fi.hIcon, size)
                if img is not None:
                    break
            except Exception as e:
                print(f"SHGetFileInfoW({probe}): {e}")
    _icon_store(key, img)
    return img

def _letter_pil(name, size=None):
    if size is None:
        size = ICON_SZ
    if not PIL_OK: return None
    PAL = ["#5b5fc7","#8b5cf6","#ec4899","#ef4444","#f97316",
           "#eab308","#22c55e","#14b8a6","#0ea5e9","#3b82f6"]
    col = PAL[ord(name[0].upper()) % len(PAL)] if name else PAL[0]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    r   = size // 2
    d.rounded_rectangle([0, 0, size-1, size-1], radius=r//2, fill=col)
    letter = name[0].upper() if name else "?"
    fnt = None
    for fn in ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]:
        try: fnt = ImageFont.truetype(fn, int(size * 0.52)); break
        except: pass
    if fnt is None: fnt = ImageFont.load_default()
    bb = d.textbbox((0, 0), letter, font=fnt)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    d.text(((size-tw)//2-bb[0], (size-th)//2-bb[1]),
           letter, font=fnt, fill="white")
    return img


_gpu_usage = -1

def _gpu_thread():
    global _gpu_usage
    if GPU_BACKEND == "nvml":
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        while True:
            try: _gpu_usage = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
            except: _gpu_usage = -1
            time.sleep(1.5)
        return
    ps = (
        "while($true){"
        "$u=(Get-Counter '\\GPU Engine(*)\\Utilization Percentage'"
        " -ErrorAction SilentlyContinue);"
        "if($u){$v=($u.CounterSamples|Measure-Object -Property CookedValue -Sum).Sum;"
        "Write-Output([math]::Round($v))}else{Write-Output -1};"
        "Start-Sleep 2}"
    )
    try:
        p = subprocess.Popen(
            ["powershell","-WindowStyle","Hidden","-NoProfile","-Command",ps],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, text=True)
        for ln in p.stdout:
            try: _gpu_usage = min(100, int(ln.strip()))
            except: pass
    except: _gpu_usage = -1

threading.Thread(target=_gpu_thread, daemon=True).start()


def _set_bg(widget, bg):
    try: widget.configure(bg=bg)
    except: pass
    for ch in widget.winfo_children():
        _set_bg(ch, bg)


# ── Restart helper ─────────────────────────────────────────────────────────────
def _restart_app():
    """Save config then relaunch this script via subprocess and exit."""
    try:
        _taskbar_vis(True)
    except Exception:
        pass
    python = sys.executable
    script = os.path.abspath(__file__)
    subprocess.Popen([python, script],
                     creationflags=subprocess.CREATE_NO_WINDOW)
    os._exit(0)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — styled widgets
# ══════════════════════════════════════════════════════════════════════════════
def _mk_btn(parent, text, cmd, bg=None, fg=None, font=None, padx=14, pady=5):
    bg  = bg  or C["accent"]
    fg  = fg  or "#ffffff"
    fnt = font or (CFG["bar"]["font_family"], 9, "bold")
    b = tk.Label(parent, text=text, bg=bg, fg=fg,
                 font=fnt, padx=padx, pady=pady, cursor="hand2")
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>",    lambda e: b.configure(bg=C["accent_glow"]))
    b.bind("<Leave>",    lambda e: b.configure(bg=bg))
    return b

def _mk_toggle(parent, var: tk.BooleanVar, label, bg, fg, fg2, on_change=None):
    row = tk.Frame(parent, bg=bg)
    chk = tk.Checkbutton(row, variable=var, bg=bg, fg=fg,
                          selectcolor=C["bar_pill"],
                          activebackground=bg, activeforeground=fg,
                          relief="flat", bd=0, highlightthickness=0,
                          command=on_change)
    chk.pack(side="left", padx=(0,6))
    tk.Label(row, text=label, bg=bg, fg=fg,
             font=(CFG["bar"]["font_family"], 9)).pack(side="left")
    return row

def _section_hdr(parent, text, bg, fg):
    f = tk.Frame(parent, bg=bg)
    tk.Label(f, text=text.upper(), bg=bg, fg=fg,
             font=(CFG["bar"]["font_family"], 7, "bold"),
             anchor="w", pady=4).pack(fill="x")
    tk.Frame(f, bg=C["border"], height=1).pack(fill="x")
    return f


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class ConfigWindow(tk.Toplevel):
    TAB_NAMES = ["General", "Bar Layout", "Stats", "Launcher", "Pinned Apps", "Import / Export"]

    def __init__(self, master):
        super().__init__(master)
        self.title("CustomShellBar — Settings")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(bg=C["launch_bg"])

        W, H = 760, 560
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        self._cfg = json.loads(json.dumps(CFG))
        self._active_tab = tk.StringVar(value=self.TAB_NAMES[0])
        self._tab_frames: dict[str, tk.Frame] = {}

        # Pre-initialise state so _collect_cfg is always safe
        self._elem_order   = list(self._cfg["bar"].get("element_order",
                                  [e["key"] for e in BAR_ELEMENTS]))
        self._elem_visible = dict(self._cfg["bar"].get("element_visible",
                                  {e["key"]: True for e in BAR_ELEMENTS}))
        self._elem_label_map = {e["key"]: e["label"] for e in BAR_ELEMENTS}
        self._elem_desc_map  = {e["key"]: e["desc"]  for e in BAR_ELEMENTS}
        self._elem_side_map  = {e["key"]: e["side"]  for e in BAR_ELEMENTS}
        self._stat_vars      = {}
        self._launch_vars    = {}
        self._pinned_list: list[dict] = list(self._cfg.get("pinned_apps", []))

        self._build()

    # ── Shell ──────────────────────────────────────────────────────────────────
    def _build(self):
        BG  = C["launch_bg"]
        ACC = C["accent"]
        FG  = C["fg"]
        FG2 = C["fg2"]

        tk.Frame(self, bg=ACC, height=3).pack(fill="x", side="top")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # ── Sidebar ────────────────────────────────────────────────────────────
        sidebar = tk.Frame(body, bg=C["bar_pill"], width=160)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="Settings", bg=C["bar_pill"], fg=FG,
                 font=(CFG["bar"]["font_family"], 13, "bold"),
                 anchor="w", padx=16, pady=14).pack(fill="x")
        tk.Frame(sidebar, bg=C["border"], height=1).pack(fill="x")

        self._tab_btns = {}
        for name in self.TAB_NAMES:
            btn = tk.Label(sidebar, text=name, bg=C["bar_pill"], fg=FG2,
                           font=(CFG["bar"]["font_family"], 10),
                           anchor="w", padx=16, pady=9, cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda e, n=name: self._show_tab(n))
            btn.bind("<Enter>",
                lambda e, b=btn, n=name: b.configure(
                    fg=FG, bg=C["row_hov"] if n != self._active_tab.get() else b.cget("bg")))
            btn.bind("<Leave>",
                lambda e, b=btn, n=name: b.configure(
                    fg=FG if n == self._active_tab.get() else FG2,
                    bg=C["row_sel"] if n == self._active_tab.get() else C["bar_pill"]))
            self._tab_btns[name] = btn

        tk.Frame(sidebar, bg=C["bar_pill"]).pack(fill="both", expand=True)
        tk.Label(sidebar, text="v9  •  CustomShellBar", bg=C["bar_pill"],
                 fg=C["fg3"], font=(CFG["bar"]["font_family"], 7),
                 padx=16, pady=8).pack(fill="x")

        # ── Content area ───────────────────────────────────────────────────────
        content_wrap = tk.Frame(body, bg=BG)
        content_wrap.pack(side="left", fill="both", expand=True)

        self._content_area = tk.Frame(content_wrap, bg=BG)
        self._content_area.pack(fill="both", expand=True, padx=20, pady=14)

        # ── Bottom bar ─────────────────────────────────────────────────────────
        foot = tk.Frame(self, bg=C["bar_pill"], pady=8, padx=14)
        foot.pack(fill="x", side="bottom")

        tk.Frame(foot, bg=C["border"], height=1).pack(fill="x", pady=(0, 8))
        btn_row = tk.Frame(foot, bg=C["bar_pill"])
        btn_row.pack()

        _mk_btn(btn_row, "💾  Save & Restart", self._save_and_restart,
                bg=C["accent"]).pack(side="left", padx=4)
        _mk_btn(btn_row, "Save (no restart)", self._save_only,
                bg=C["bar_pill"], fg=C["fg"]).pack(side="left", padx=4)
        _mk_btn(btn_row, "Discard", self.destroy,
                bg=C["bar_pill"], fg=C["red"]).pack(side="left", padx=4)

        # Build all tab frames — wrapped so one failure doesn't block others
        for build_fn in (
            self._build_general,
            self._build_bar_layout,
            self._build_stats,
            self._build_launcher,
            self._build_pinned,
            self._build_import_export,
        ):
            try:
                build_fn()
            except Exception as e:
                print(f"Tab build error ({build_fn.__name__}): {e}")

        self._show_tab(self.TAB_NAMES[0])

    def _show_tab(self, name: str):
        if name not in self._tab_frames:
            return
        for n, f in self._tab_frames.items():
            f.pack_forget()
        self._tab_frames[name].pack(fill="both", expand=True)
        self._active_tab.set(name)
        for n, btn in self._tab_btns.items():
            if n == name:
                btn.configure(bg=C["row_sel"], fg=C["fg"])
            else:
                btn.configure(bg=C["bar_pill"], fg=C["fg2"])

    def _scrollable(self, parent):
        """Return (outer_frame, inner_frame, canvas) for a scrollable tab body."""
        BG = C["launch_bg"]
        outer = tk.Frame(parent, bg=BG)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                          width=4, bg=C["border"], troughcolor=BG)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(win, width=e.width))

        def _scroll(e):
            canvas.yview_scroll(-1 * (e.delta // 120), "units")

        canvas.bind("<MouseWheel>", _scroll)
        outer.bind("<MouseWheel>", _scroll)
        inner.bind("<MouseWheel>", _scroll)
        return outer, inner, canvas

    def _bind_mousewheel(self, widget, canvas):
        """Recursively bind mousewheel on all children to scroll the given canvas."""
        widget.bind("<MouseWheel>",
            lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        for child in widget.winfo_children():
            self._bind_mousewheel(child, canvas)

    # ── Tab: General ───────────────────────────────────────────────────────────
    def _build_general(self):
        outer, f, canvas = self._scrollable(self._content_area)
        self._tab_frames["General"] = outer
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]
        BFNT = (CFG["bar"]["font_family"], 9)

        _section_hdr(f, "Theme", BG, C["category"]).pack(fill="x", pady=(0, 10))

        theme_grid = tk.Frame(f, bg=BG)
        theme_grid.pack(fill="x", padx=4)

        self._theme_var = tk.StringVar(value=self._cfg.get("theme", "dark"))
        for col, (tid, tdata) in enumerate(THEMES.items()):
            self._make_theme_card(theme_grid, tid, tdata, col)

        tk.Frame(f, bg=BG, height=14).pack()
        _section_hdr(f, "Bar", BG, C["category"]).pack(fill="x", pady=(0, 10))

        bar_grid = tk.Frame(f, bg=BG)
        bar_grid.pack(fill="x", padx=4)

        self._bar_height_v = tk.IntVar(value=self._cfg["bar"].get("height", 40))
        self._make_slider_row(bar_grid, "Bar height (px)", self._bar_height_v, 20, 80, 0)

        self._bar_font_v = tk.StringVar(value=self._cfg["bar"].get("font_family", "Segoe UI"))
        self._make_entry_row(bar_grid, "Font family", self._bar_font_v, 1)

        self._bar_fontsize_v = tk.IntVar(value=self._cfg["bar"].get("font_size", 9))
        self._make_slider_row(bar_grid, "Font size (pt)", self._bar_fontsize_v, 7, 16, 2)

        self._bar_pos_v = tk.StringVar(value=self._cfg["bar"].get("position", "top"))
        self._make_choice_row(bar_grid, "Position", self._bar_pos_v,
                              [("Top", "top"), ("Bottom", "bottom")], 3)

        tk.Frame(f, bg=BG, height=14).pack()
        _section_hdr(f, "Clock", BG, C["category"]).pack(fill="x", pady=(0, 10))

        clk_grid = tk.Frame(f, bg=BG)
        clk_grid.pack(fill="x", padx=4)

        self._clock_fmt_v = tk.StringVar(
            value=self._cfg["bar"].get("clock_format", "%a %d %b   %H:%M:%S"))
        self._make_entry_row(clk_grid, "Clock format", self._clock_fmt_v, 0)

        def _set_fmt(fmt):
            self._clock_fmt_v.set(fmt)

        fmt_row = tk.Frame(clk_grid, bg=BG, pady=4)
        fmt_row.grid(row=1, column=0, columnspan=3, sticky="w")
        tk.Label(fmt_row, text="Presets:", bg=BG, fg=FG2,
                 font=BFNT).pack(side="left", padx=(0, 8))
        for label, fmt in [
            ("%H:%M",               "HH:MM"),
            ("%H:%M:%S",            "HH:MM:SS"),
            ("%a %d %b  %H:%M",     "Day date  HH:MM"),
            ("%a %d %b   %H:%M:%S", "Day date  HH:MM:SS (default)"),
            ("%d/%m/%Y  %H:%M",     "DD/MM/YYYY  HH:MM"),
        ]:
            b = tk.Label(fmt_row, text=label, bg=C["bar_pill"], fg=FG2,
                         font=(CFG["bar"]["font_family"], 8),
                         padx=7, pady=2, cursor="hand2")
            b.pack(side="left", padx=2)
            b.bind("<Button-1>", lambda e, f=fmt: _set_fmt(f))
            b.bind("<Enter>",    lambda e, b=b: b.configure(fg=FG))
            b.bind("<Leave>",    lambda e, b=b: b.configure(fg=FG2))

        clk_grid.columnconfigure(1, weight=1)
        self.after(100, lambda: self._bind_mousewheel(f, canvas))

    def _make_theme_card(self, parent, tid, tdata, col):
        BG  = C["launch_bg"]
        ACC = tdata.get("accent", "#888")
        is_cur = (tid == self._theme_var.get())

        card = tk.Frame(parent, bg=C["bar_pill"] if is_cur else BG,
                        highlightbackground=ACC if is_cur else C["border"],
                        highlightthickness=2 if is_cur else 1,
                        padx=10, pady=8, cursor="hand2")
        card.grid(row=col // 3, column=col % 3, padx=5, pady=5, sticky="ew")
        parent.columnconfigure(col % 3, weight=1)

        swatch_row = tk.Frame(card, bg=C["bar_pill"] if is_cur else BG)
        swatch_row.pack(fill="x", pady=(0, 4))
        for ck in ["bar_bg", "accent", "green", "cyan", "violet"]:
            col_val = tdata.get(ck, "#888")
            tk.Frame(swatch_row, bg=col_val, width=14, height=14).pack(
                side="left", padx=1)

        tk.Label(card, text=tdata.get("_name", tid),
                 bg=C["bar_pill"] if is_cur else BG,
                 fg=ACC if is_cur else C["fg"],
                 font=(CFG["bar"]["font_family"], 9,
                       "bold" if is_cur else "normal")).pack(anchor="w")

        def _select(t=tid, td=tdata):
            self._theme_var.set(t)
            self._cfg["theme"] = t
            _save_config(self._collect_cfg())
            # Reopen config window with new theme applied
            master = self.master
            self.destroy()
            global C, CFG
            CFG = _load_config()
            C   = _build_palette(CFG)
            ConfigWindow(master)

        card.bind("<Button-1>", lambda e: _select())
        for ch in card.winfo_children():
            ch.bind("<Button-1>", lambda e: _select())
            for gch in ch.winfo_children():
                gch.bind("<Button-1>", lambda e: _select())

    def _make_slider_row(self, parent, label, var, lo, hi, row):
        BG = C["launch_bg"]
        FG = C["fg"]
        FG2 = C["fg2"]
        tk.Label(parent, text=label, bg=BG, fg=FG2,
                 font=(CFG["bar"]["font_family"], 9),
                 width=22, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        sl = tk.Scale(parent, from_=lo, to=hi, orient="horizontal",
                      variable=var, bg=BG, fg=FG, troughcolor=C["bar_pill"],
                      activebackground=C["accent"], highlightthickness=0,
                      sliderrelief="flat", bd=1, length=200)
        sl.grid(row=row, column=1, sticky="ew", padx=8)
        val_lbl = tk.Label(parent, textvariable=var, bg=BG, fg=C["accent"],
                           font=(CFG["bar"]["font_family"], 9, "bold"), width=4)
        val_lbl.grid(row=row, column=2, sticky="w")

    def _make_entry_row(self, parent, label, var, row):
        BG = C["launch_bg"]
        FG = C["fg"]
        FG2 = C["fg2"]
        tk.Label(parent, text=label, bg=BG, fg=FG2,
                 font=(CFG["bar"]["font_family"], 9),
                 width=22, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        e = tk.Entry(parent, textvariable=var, bg=C["search_bg"],
                     fg=FG, insertbackground=C["accent"],
                     relief="flat", bd=0,
                     font=(CFG["bar"]["font_family"], 10),
                     highlightthickness=1, highlightbackground=C["border"],
                     highlightcolor=C["accent"])
        e.grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=2)

    def _make_choice_row(self, parent, label, var, choices, row):
        BG = C["launch_bg"]
        FG = C["fg"]
        FG2 = C["fg2"]
        tk.Label(parent, text=label, bg=BG, fg=FG2,
                 font=(CFG["bar"]["font_family"], 9),
                 width=22, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        btn_f = tk.Frame(parent, bg=BG)
        btn_f.grid(row=row, column=1, columnspan=2, sticky="w", padx=8)
        for label2, val in choices:
            b = tk.Radiobutton(btn_f, text=label2, variable=var, value=val,
                               bg=BG, fg=FG2, selectcolor=C["bar_pill"],
                               activebackground=BG, activeforeground=FG,
                               indicatoron=True,
                               font=(CFG["bar"]["font_family"], 9))
            b.pack(side="left", padx=(0, 12))

    # ── Tab: Bar Layout ────────────────────────────────────────────────────────
    def _build_bar_layout(self):
        outer, f, canvas = self._scrollable(self._content_area)
        self._tab_frames["Bar Layout"] = outer
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]

        _section_hdr(f, "Layout Presets", BG, C["category"]).pack(fill="x", pady=(0, 10))
        preset_grid = tk.Frame(f, bg=BG)
        preset_grid.pack(fill="x", padx=4, pady=(0, 14))
        for col, (pid, pd) in enumerate(BAR_PRESETS.items()):
            self._make_preset_card(preset_grid, pid, pd, col)

        _section_hdr(f, "Element Order & Visibility", BG, C["category"]).pack(
            fill="x", pady=(0, 4))

        tk.Label(f, text="Use ▲ ▼ to reorder  •  toggle checkbox to show/hide",
                 bg=BG, fg=FG2, font=(CFG["bar"]["font_family"], 8),
                 anchor="w").pack(fill="x", padx=4, pady=(0, 8))

        self._layout_frame = tk.Frame(f, bg=BG)
        self._layout_frame.pack(fill="x", padx=4)

        # _elem_order and _elem_visible already initialised in __init__
        self._drag_idx = None
        self._layout_rows = {}
        self._elem_vis_vars = {}
        self._render_layout_rows()
        self.after(100, lambda: self._bind_mousewheel(f, canvas))

    def _make_preset_card(self, parent, pid, pd, col):
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]

        card = tk.Frame(parent, bg=C["bar_pill"],
                        highlightbackground=C["border"],
                        highlightthickness=1,
                        padx=10, pady=8, cursor="hand2")
        card.grid(row=col // 3, column=col % 3, padx=4, pady=4, sticky="nsew")
        parent.columnconfigure(col % 3, weight=1)

        tk.Label(card, text=pd["_name"], bg=C["bar_pill"], fg=FG,
                 font=(CFG["bar"]["font_family"], 9, "bold"),
                 anchor="w").pack(fill="x")
        tk.Label(card, text=pd["_desc"], bg=C["bar_pill"], fg=FG2,
                 font=(CFG["bar"]["font_family"], 8),
                 anchor="w", wraplength=160, justify="left").pack(fill="x", pady=(2, 6))

        prev = tk.Frame(card, bg=C["bar_bg"], height=18)
        prev.pack(fill="x", pady=(2, 0))
        for key in pd.get("element_order", []):
            if pd.get("element_visible", {}).get(key, True):
                dot_col = {"left": C["accent"], "center": C["cyan"],
                           "right": C["green"]}.get(self._elem_side_map.get(key, "right"), C["fg2"])
                tk.Frame(prev, bg=dot_col, width=4, height=10).pack(
                    side="left", padx=1, pady=4)

        def _apply(p=pd):
            self._elem_order = [k for k in p.get("element_order", [])
                                 if k in self._elem_label_map]
            self._elem_visible = dict(p.get("element_visible", {}))
            self._render_layout_rows()

        card.bind("<Button-1>", lambda e: _apply())
        for ch in card.winfo_children():
            ch.bind("<Button-1>", lambda e: _apply())
            for gch in ch.winfo_children():
                gch.bind("<Button-1>", lambda e: _apply())

    def _render_layout_rows(self):
        for w in self._layout_frame.winfo_children():
            w.destroy()
        self._layout_rows.clear()
        self._elem_vis_vars.clear()

        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]

        all_keys = [e["key"] for e in BAR_ELEMENTS]
        for k in all_keys:
            if k not in self._elem_order:
                self._elem_order.append(k)
            if k not in self._elem_visible:
                self._elem_visible[k] = True

        for i, key in enumerate(self._elem_order):
            var = tk.BooleanVar(value=self._elem_visible.get(key, True))
            self._elem_vis_vars[key] = var

            row = tk.Frame(self._layout_frame, bg=BG,
                           highlightbackground=C["border"],
                           highlightthickness=1, pady=6, padx=8)
            row.pack(fill="x", pady=2)

            handle = tk.Label(row, text="⠿", bg=BG, fg=FG2,
                              font=(CFG["bar"]["font_family"], 14),
                              cursor="fleur", padx=6)
            handle.pack(side="left")

            chk = tk.Checkbutton(row, variable=var, bg=BG,
                                  selectcolor=C["bar_pill"],
                                  activebackground=BG,
                                  relief="flat", bd=0, highlightthickness=0,
                                  command=lambda k=key, v=var:
                                      self._elem_visible.update({k: v.get()}))
            chk.pack(side="left", padx=(0, 4))

            side = self._elem_side_map.get(key, "right")
            side_col = {"left": C["accent"], "center": C["cyan"],
                        "right": C["green"]}.get(side, C["fg2"])
            tk.Label(row, text=side, bg=side_col,
                     fg=BG, font=(CFG["bar"]["font_family"], 7, "bold"),
                     padx=5, pady=1).pack(side="left", padx=(0, 8))

            tk.Label(row, text=self._elem_label_map.get(key, key),
                     bg=BG, fg=FG,
                     font=(CFG["bar"]["font_family"], 9, "bold"),
                     anchor="w").pack(side="left")
            tk.Label(row, text="  —  " + self._elem_desc_map.get(key, ""),
                     bg=BG, fg=FG2,
                     font=(CFG["bar"]["font_family"], 8),
                     anchor="w").pack(side="left")

            btn_f = tk.Frame(row, bg=BG)
            btn_f.pack(side="right")
            up = tk.Label(btn_f, text="▲", bg=BG, fg=FG2, cursor="hand2",
                          font=(CFG["bar"]["font_family"], 8), padx=4)
            up.pack(side="left")
            up.bind("<Button-1>", lambda e, k=key: self._move_elem(k, -1))
            dn = tk.Label(btn_f, text="▼", bg=BG, fg=FG2, cursor="hand2",
                          font=(CFG["bar"]["font_family"], 8), padx=4)
            dn.pack(side="left")
            dn.bind("<Button-1>", lambda e, k=key: self._move_elem(k, +1))

            self._layout_rows[key] = row

    def _move_elem(self, key, delta):
        idx = self._elem_order.index(key)
        new = idx + delta
        if 0 <= new < len(self._elem_order):
            self._elem_order.insert(new, self._elem_order.pop(idx))
        self._render_layout_rows()

    # ── Tab: Stats ────────────────────────────────────────────────────────────
    def _build_stats(self):
        outer, f, canvas = self._scrollable(self._content_area)
        self._tab_frames["Stats"] = outer
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]

        _section_hdr(f, "Visible Stats", BG, C["category"]).pack(fill="x", pady=(0, 10))

        stat_defs = [
            ("show_cpu", "CPU Usage",    "Processor utilisation percentage",       C["green"]),
            ("show_ram", "RAM Usage",    "Physical memory utilisation percentage", C["red"]),
            ("show_net", "Network Speed","Combined up+down bandwidth in KB/s",     C["cyan"]),
            ("show_gpu", "GPU Usage",    "GPU utilisation % (NVIDIA / WMI)",       C["violet"]),
        ]
        self._stat_vars = {}
        for key, label, desc, col in stat_defs:
            var = tk.BooleanVar(value=self._cfg["bar"].get(key, True))
            self._stat_vars[key] = var

            row = tk.Frame(f, bg=BG, pady=5, padx=6,
                           highlightbackground=C["border"], highlightthickness=1)
            row.pack(fill="x", pady=2)

            tk.Frame(row, bg=col, width=4, height=30).pack(side="left", pady=2)

            chk = tk.Checkbutton(row, variable=var, bg=BG,
                                  selectcolor=C["bar_pill"],
                                  activebackground=BG, relief="flat",
                                  bd=0, highlightthickness=0)
            chk.pack(side="left", padx=(8, 4))

            tk.Label(row, text=label, bg=BG, fg=FG,
                     font=(CFG["bar"]["font_family"], 9, "bold"),
                     width=16, anchor="w").pack(side="left")
            tk.Label(row, text=desc, bg=BG, fg=FG2,
                     font=(CFG["bar"]["font_family"], 8),
                     anchor="w").pack(side="left", padx=8)

        tk.Frame(f, bg=BG, height=14).pack()
        _section_hdr(f, "Notes", BG, C["category"]).pack(fill="x", pady=(0, 10))
        for note in [
            "GPU stats require pynvml (NVIDIA) or fall back to PowerShell WMI.",
            "Net speed shows aggregate of all interfaces.",
            "Stats refresh every ~1 second.",
        ]:
            tk.Label(f, text=f"• {note}", bg=BG, fg=FG2,
                     font=(CFG["bar"]["font_family"], 8),
                     anchor="w", wraplength=500, justify="left").pack(
                         fill="x", padx=8, pady=1)
        self.after(100, lambda: self._bind_mousewheel(f, canvas))

    # ── Tab: Launcher ─────────────────────────────────────────────────────────
    def _build_launcher(self):
        outer, f, canvas = self._scrollable(self._content_area)
        self._tab_frames["Launcher"] = outer
        BG  = C["launch_bg"]

        _section_hdr(f, "Launcher Settings", BG, C["category"]).pack(fill="x", pady=(0, 10))
        g = tk.Frame(f, bg=BG)
        g.pack(fill="x", padx=4)
        g.columnconfigure(1, weight=1)

        self._launch_vars = {}
        rows = [
            ("width",       "Width (px)",       "int", 300, 1200),
            ("max_height",  "Max height (px)",  "int", 200, 900),
            ("icon_size",   "Icon size (px)",   "int", 16, 64),
            ("row_height",  "Row height (px)",  "int", 28, 80),
            ("font_family", "Font family",      "str", None, None),
            ("font_size",   "Font size (pt)",   "int", 7, 18),
            ("max_results", "Max results",      "int", 10, 200),
        ]
        for row_idx, (key, label, typ, lo, hi) in enumerate(rows):
            val = self._cfg["launcher"].get(key, DEFAULT_CONFIG["launcher"].get(key))
            if typ == "int":
                var = tk.IntVar(value=val)
                self._make_slider_row(g, label, var, lo, hi, row_idx)
            else:
                var = tk.StringVar(value=val)
                self._make_entry_row(g, label, var, row_idx)
            self._launch_vars[key] = var

        tk.Frame(f, bg=BG, height=14).pack()
        _section_hdr(f, "Display Options", BG, C["category"]).pack(fill="x", pady=(0, 10))

        self._launch_showpath_v = tk.BooleanVar(
            value=self._cfg["launcher"].get("show_path", True))
        row = _mk_toggle(f, self._launch_showpath_v,
                         "Show app folder path below name",
                         BG, C["fg"], C["fg2"])
        row.pack(fill="x", padx=8, pady=4)
        self.after(100, lambda: self._bind_mousewheel(f, canvas))

    # ── Tab: Pinned Apps ──────────────────────────────────────────────────────
    def _build_pinned(self):
        outer, f, canvas = self._scrollable(self._content_area)
        self._tab_frames["Pinned Apps"] = outer
        BG  = C["launch_bg"]
        FG2 = C["fg2"]

        hdr = tk.Frame(f, bg=BG)
        hdr.pack(fill="x", pady=(0, 8))
        _section_hdr(hdr, "Pinned Apps", BG, C["category"]).pack(side="left", fill="x", expand=True)
        _mk_btn(hdr, "+ Add App", self._add_pinned_app,
                bg=C["accent"]).pack(side="right")

        tk.Label(f, text="These apps appear as quick-launch buttons in the bar. "
                         "Click × to remove.",
                 bg=BG, fg=FG2, font=(CFG["bar"]["font_family"], 8),
                 anchor="w", wraplength=500).pack(fill="x", padx=4, pady=(0, 10))

        self._pinned_frame = tk.Frame(f, bg=BG)
        self._pinned_frame.pack(fill="x", padx=4)

        self._render_pinned()
        self.after(100, lambda: self._bind_mousewheel(f, canvas))

    def _render_pinned(self):
        for w in self._pinned_frame.winfo_children():
            w.destroy()
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]

        if not self._pinned_list:
            tk.Label(self._pinned_frame,
                     text="No pinned apps yet. Click '+ Add App' to add one.",
                     bg=BG, fg=FG2,
                     font=(CFG["bar"]["font_family"], 9),
                     pady=20).pack()
            return

        for i, pin in enumerate(self._pinned_list):
            row = tk.Frame(self._pinned_frame, bg=C["bar_pill"],
                           pady=6, padx=10,
                           highlightbackground=C["border"],
                           highlightthickness=1)
            row.pack(fill="x", pady=2)

            tk.Label(row, text=f"{i+1}.", bg=C["bar_pill"], fg=FG2,
                     font=(CFG["bar"]["font_family"], 9), width=2).pack(side="left")

            name_v = tk.StringVar(value=pin.get("name", ""))
            path_v = tk.StringVar(value=pin.get("path", ""))

            name_e = tk.Entry(row, textvariable=name_v, width=14,
                              bg=C["search_bg"], fg=FG,
                              insertbackground=C["accent"],
                              relief="flat", bd=0, highlightthickness=1,
                              highlightbackground=C["border"],
                              highlightcolor=C["accent"],
                              font=(CFG["bar"]["font_family"], 9))
            name_e.pack(side="left", padx=(4, 6))

            path_e = tk.Entry(row, textvariable=path_v,
                              bg=C["search_bg"], fg=FG,
                              insertbackground=C["accent"],
                              relief="flat", bd=0, highlightthickness=1,
                              highlightbackground=C["border"],
                              highlightcolor=C["accent"],
                              font=(CFG["bar"]["font_family"], 9))
            path_e.pack(side="left", fill="x", expand=True, padx=(0, 6))

            def _browse(pv=path_v):
                p = fd.askopenfilename(
                    title="Select application",
                    filetypes=[("Executables & Shortcuts", "*.exe *.lnk *.bat"),
                               ("All files", "*.*")])
                if p: pv.set(p)

            _mk_btn(row, "…", _browse, bg=C["bar_pill"], fg=FG,
                    padx=8, pady=2).pack(side="left", padx=2)

            def _remove(idx=i):
                self._pinned_list.pop(idx)
                self._render_pinned()

            rm = tk.Label(row, text="×", bg=C["bar_pill"], fg=C["red"],
                          font=(CFG["bar"]["font_family"], 12, "bold"),
                          padx=8, cursor="hand2")
            rm.pack(side="right")
            rm.bind("<Button-1>", lambda e, r=_remove: r())

            def _sync(pn=pin, nv=name_v, pv=path_v):
                pn["name"] = nv.get()
                pn["path"] = pv.get()
            name_e.bind("<FocusOut>", lambda e, s=_sync: s())
            path_e.bind("<FocusOut>", lambda e, s=_sync: s())

    def _add_pinned_app(self):
        p = fd.askopenfilename(
            title="Select application to pin",
            filetypes=[("Executables & Shortcuts", "*.exe *.lnk *.bat"),
                       ("All files", "*.*")])
        if not p:
            return
        name = os.path.splitext(os.path.basename(p))[0]
        self._pinned_list.append({"name": name, "path": p})
        self._render_pinned()

    # ── Tab: Import / Export ──────────────────────────────────────────────────
    def _build_import_export(self):
        outer, f, canvas = self._scrollable(self._content_area)
        self._tab_frames["Import / Export"] = outer
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]
        ACC = C["accent"]

        _section_hdr(f, "Export Profile", BG, C["category"]).pack(fill="x", pady=(0, 10))
        tk.Label(f, text="Save the entire current configuration as a shareable .json profile.",
                 bg=BG, fg=FG2, font=(CFG["bar"]["font_family"], 9),
                 anchor="w", wraplength=500).pack(fill="x", padx=4, pady=(0, 8))
        exp_row = tk.Frame(f, bg=BG)
        exp_row.pack(fill="x", padx=4, pady=4)
        _mk_btn(exp_row, "Export as JSON…", self._export_profile).pack(side="left", padx=(0, 8))
        _mk_btn(exp_row, "Copy to clipboard", self._copy_profile,
                bg=C["bar_pill"], fg=FG).pack(side="left")

        tk.Frame(f, bg=BG, height=14).pack()

        _section_hdr(f, "Import Profile", BG, C["category"]).pack(fill="x", pady=(0, 10))
        tk.Label(f, text="Load a .json profile to replace the current configuration. "
                         "The bar restarts after import.",
                 bg=BG, fg=FG2, font=(CFG["bar"]["font_family"], 9),
                 anchor="w", wraplength=500).pack(fill="x", padx=4, pady=(0, 8))
        imp_row = tk.Frame(f, bg=BG)
        imp_row.pack(fill="x", padx=4, pady=4)
        _mk_btn(imp_row, "Import from JSON…", self._import_profile).pack(side="left", padx=(0, 8))

        tk.Label(f, text="— or paste JSON below and click Import Pasted —",
                 bg=BG, fg=FG2, font=(CFG["bar"]["font_family"], 8)).pack(pady=(10, 4))
        self._paste_box = tk.Text(f, bg=C["search_bg"], fg=FG,
                                  insertbackground=ACC, relief="flat", bd=0,
                                  height=8, font=("Consolas", 9),
                                  highlightthickness=1,
                                  highlightbackground=C["border"],
                                  highlightcolor=ACC)
        self._paste_box.pack(fill="x", padx=4, pady=(0, 8))
        _mk_btn(f, "Import Pasted JSON", self._import_pasted).pack(anchor="w", padx=4)

        tk.Frame(f, bg=BG, height=14).pack()

        _section_hdr(f, "Built-in Profile Presets", BG, C["category"]).pack(fill="x", pady=(0, 10))
        presets = [
            ("Developer Dark",   {"theme": "dark",   "bar": {"height": 36}, **dict(BAR_PRESETS["developer"])}),
            ("Minimal Light",    {"theme": "light",  "bar": {"height": 32}, **dict(BAR_PRESETS["minimal"])}),
            ("Gamer Hacker",     {"theme": "hacker", "bar": {"height": 44}, **dict(BAR_PRESETS["gamer"])}),
            ("Classic Nord",     {"theme": "nord",   "bar": {"height": 40}, **dict(BAR_PRESETS["classic"])}),
            ("Status Rose Pine", {"theme": "rose",   "bar": {"height": 30}, **dict(BAR_PRESETS["status"])}),
            ("Cozy Mocha",       {"theme": "mocha",  "bar": {"height": 42}, **dict(BAR_PRESETS["default"])}),
        ]
        preset_grid = tk.Frame(f, bg=BG)
        preset_grid.pack(fill="x", padx=4)
        for col, (pname, pcfg) in enumerate(presets):
            theme = THEMES.get(pcfg.get("theme", "dark"), THEMES["dark"])
            card = tk.Frame(preset_grid, bg=theme["bar_pill"],
                            padx=10, pady=8, cursor="hand2")
            card.grid(row=col // 3, column=col % 3, padx=4, pady=4, sticky="nsew")
            preset_grid.columnconfigure(col % 3, weight=1)

            sw = tk.Frame(card, bg=theme["bar_pill"])
            sw.pack(fill="x", pady=(0, 4))
            for ck in ["bar_bg", "accent", "green"]:
                tk.Frame(sw, bg=theme.get(ck, "#888"), width=14, height=6).pack(
                    side="left", padx=1)

            tk.Label(card, text=pname, bg=theme["bar_pill"], fg=theme["fg"],
                     font=(CFG["bar"]["font_family"], 9, "bold")).pack(anchor="w")

            def _apply(cfg_override=pcfg, pn=pname):
                merged = json.loads(json.dumps(self._cfg))
                for k, v in cfg_override.items():
                    if isinstance(v, dict) and isinstance(merged.get(k), dict):
                        merged[k].update(v)
                    else:
                        merged[k] = v
                _save_config(merged)
                mb.showinfo("Profile Applied",
                            f"'{pn}' applied. Restarting now…",
                            parent=self)
                _restart_app()

            card.bind("<Button-1>", lambda e, a=_apply: a())
            for ch in card.winfo_children():
                ch.bind("<Button-1>", lambda e, a=_apply: a())
                for gch in ch.winfo_children():
                    gch.bind("<Button-1>", lambda e, a=_apply: a())

        self.after(100, lambda: self._bind_mousewheel(f, canvas))

    def _export_profile(self):
        p = fd.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON profile", "*.json")],
            initialfile="shellbar_profile.json",
            title="Export ShellBar profile")
        if not p: return
        try:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self._collect_cfg(), f, indent=2)
            mb.showinfo("Exported", f"Profile saved to:\n{p}", parent=self)
        except Exception as e:
            mb.showerror("Export failed", str(e), parent=self)

    def _copy_profile(self):
        self.clipboard_clear()
        self.clipboard_append(json.dumps(self._collect_cfg(), indent=2))
        mb.showinfo("Copied", "JSON copied to clipboard.", parent=self)

    def _import_profile(self):
        p = fd.askopenfilename(
            filetypes=[("JSON profile", "*.json"), ("All files", "*.*")],
            title="Import ShellBar profile")
        if not p: return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_import(data)
        except Exception as e:
            mb.showerror("Import failed", str(e), parent=self)

    def _import_pasted(self):
        raw = self._paste_box.get("1.0", "end").strip()
        if not raw:
            mb.showwarning("Nothing to import", "Paste JSON in the box first.", parent=self)
            return
        try:
            data = json.loads(raw)
            self._apply_import(data)
        except Exception as e:
            mb.showerror("Invalid JSON", str(e), parent=self)

    def _apply_import(self, data: dict):
        cfg = _load_config()
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
        _save_config(cfg)
        mb.showinfo("Imported", "Profile imported. Restarting now…", parent=self)
        _restart_app()

    # ── Collect & Save ────────────────────────────────────────────────────────
    def _collect_cfg(self) -> dict:
        cfg = json.loads(json.dumps(self._cfg))

        # General — only if widgets exist
        if hasattr(self, "_theme_var"):
            cfg["theme"] = self._theme_var.get()
        if hasattr(self, "_bar_height_v"):
            cfg["bar"]["height"]      = self._bar_height_v.get()
        if hasattr(self, "_bar_font_v"):
            cfg["bar"]["font_family"] = self._bar_font_v.get()
        if hasattr(self, "_bar_fontsize_v"):
            cfg["bar"]["font_size"]   = self._bar_fontsize_v.get()
        if hasattr(self, "_bar_pos_v"):
            cfg["bar"]["position"]    = self._bar_pos_v.get()
        if hasattr(self, "_clock_fmt_v"):
            cfg["bar"]["clock_format"]= self._clock_fmt_v.get()

        # Bar layout
        cfg["bar"]["element_order"]   = list(self._elem_order)
        cfg["bar"]["element_visible"] = dict(self._elem_visible)
        ev = cfg["bar"]["element_visible"]
        cfg["bar"]["show_clock"]            = ev.get("clock", True)
        cfg["bar"]["show_cpu"]              = ev.get("cpu", True)
        cfg["bar"]["show_ram"]              = ev.get("ram", True)
        cfg["bar"]["show_net"]              = ev.get("net", True)
        cfg["bar"]["show_gpu"]              = ev.get("gpu", True)
        cfg["bar"]["show_desktop_switcher"] = ev.get("desktop_switcher", True)

        # Stats
        for key, var in self._stat_vars.items():
            cfg["bar"][key] = var.get()

        # Launcher
        for key, var in self._launch_vars.items():
            cfg["launcher"][key] = var.get()
        if hasattr(self, "_launch_showpath_v"):
            cfg["launcher"]["show_path"] = self._launch_showpath_v.get()

        # Pinned apps — sync any open entries first
        cfg["pinned_apps"] = [
            {"name": p.get("name", ""), "path": p.get("path", "")}
            for p in self._pinned_list
            if p.get("path", "").strip()
        ]

        return cfg

    def _save_only(self):
        cfg = self._collect_cfg()
        _save_config(cfg)
        global CFG, C
        CFG = cfg
        C   = _build_palette(cfg)
        mb.showinfo("Saved",
                    "Settings saved.\nRestart CustomShellBar to apply all changes.",
                    parent=self)

    def _save_and_restart(self):
        cfg = self._collect_cfg()
        _save_config(cfg)
        _restart_app()


# ══════════════════════════════════════════════════════════════════════════════
# HELP WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class HelpWindow(tk.Toplevel):
    SECTIONS = [
        ("Hotkeys", [
            ("Alt + Space", "Open / close the app launcher"),
            ("Alt + C",     "Open the settings / config panel"),
            ("Alt + 1–9",   "Switch virtual desktops"),
            ("↑ / ↓",       "Navigate launcher results"),
            ("Enter",       "Launch selected app"),
            ("Escape",      "Close launcher"),
        ]),
        ("Themes", [
            ("dark",    "Deep indigo (default)"),
            ("light",   "Clean white / lavender"),
            ("mocha",   "Warm coffee browns"),
            ("nord",    "Arctic blue-grey"),
            ("rose",    "Rose Pinè"),
            ("hacker",  "Terminal green on black"),
        ]),
        ("Bar Layout", [
            ("Settings → Bar Layout", "Use ▲ ▼ to reorder, toggle to show/hide"),
            ("Presets",               "One-click layout profiles (Minimal, Developer, etc.)"),
        ]),
        ("Pinned Apps", [
            ("Settings → Pinned Apps", "Add / remove / edit pinned app buttons"),
            ("Browse button",          "Pick an .exe, .lnk, or .bat to pin"),
        ]),
        ("Import / Export", [
            ("Export profile", "Save current config as shareable JSON"),
            ("Import profile", "Load a JSON profile or paste one directly"),
            ("Built-in presets", "One-click theme + layout combos"),
        ]),
        ("Command Line", [
            ("--install",   "Register startup task (requires admin)"),
            ("--uninstall", "Remove startup task"),
            ("--help",      "Show this window"),
        ]),
    ]

    def __init__(self, master):
        super().__init__(master)
        self.title("CustomShellBar — Help")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.configure(bg=C["launch_bg"])
        W, H = 640, 540
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self._build()

    def _build(self):
        BG  = C["launch_bg"]
        FG  = C["fg"]
        FG2 = C["fg2"]
        ACC = C["accent"]

        tk.Frame(self, bg=ACC, height=3).pack(fill="x")

        title_frame = tk.Frame(self, bg=BG)
        title_frame.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(title_frame, text="CustomShellBar", bg=BG, fg=ACC,
                 font=(CFG["bar"]["font_family"], 18, "bold")).pack(side="left")
        tk.Label(title_frame, text="  v9 — keyboard-first Windows shell bar",
                 bg=BG, fg=FG2, font=(CFG["bar"]["font_family"], 10)).pack(
                     side="left", pady=6)

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", padx=20, pady=6)

        # Scrollable content area
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=0, pady=0)

        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview,
                          width=6, bg=C["border"], troughcolor=BG)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(win, width=e.width))

        def _scroll(e):
            canvas.yview_scroll(-1 * (e.delta // 120), "units")

        canvas.bind("<MouseWheel>", _scroll)
        inner.bind("<MouseWheel>",  _scroll)
        self.bind("<MouseWheel>",   _scroll)

        # Content
        for section_title, rows in self.SECTIONS:
            sec_frame = tk.Frame(inner, bg=BG, padx=20, pady=4)
            sec_frame.pack(fill="x")

            tk.Label(sec_frame, text=section_title, bg=BG, fg=ACC,
                     font=(CFG["bar"]["font_family"], 11, "bold"),
                     anchor="w", pady=6).pack(fill="x")

            for key, val in rows:
                row = tk.Frame(sec_frame, bg=BG, pady=2)
                row.pack(fill="x")
                row.bind("<MouseWheel>", _scroll)

                key_lbl = tk.Label(row, text=key, bg=C["bar_pill"], fg=FG,
                                   font=("Consolas", 9), padx=8, pady=3,
                                   width=22, anchor="w")
                key_lbl.pack(side="left", padx=(0, 8))
                key_lbl.bind("<MouseWheel>", _scroll)

                val_lbl = tk.Label(row, text=val, bg=BG, fg=FG2,
                                   font=(CFG["bar"]["font_family"], 9),
                                   anchor="w", wraplength=360, justify="left")
                val_lbl.pack(side="left", fill="x", expand=True)
                val_lbl.bind("<MouseWheel>", _scroll)

            tk.Frame(sec_frame, bg=C["border"], height=1).pack(fill="x", pady=(6, 2))

        # Footer
        foot = tk.Frame(self, bg=C["bar_pill"], pady=8)
        foot.pack(fill="x", side="bottom")
        tk.Frame(foot, bg=C["border"], height=1).pack(fill="x", pady=(0, 8))
        btn_row = tk.Frame(foot, bg=C["bar_pill"])
        btn_row.pack()
        _mk_btn(btn_row, "Open Settings", lambda: ConfigWindow(self)).pack(side="left", padx=4)
        _mk_btn(btn_row, "Open Config Folder", lambda: os.startfile(APPDATA_DIR),
                bg=C["bar_pill"], fg=C["fg"]).pack(side="left", padx=4)
        _mk_btn(btn_row, "Close", self.destroy,
                bg=C["bar_pill"], fg=C["red"]).pack(side="left", padx=4)


# ══════════════════════════════════════════════════════════════════════════════
# LAUNCHER
# ══════════════════════════════════════════════════════════════════════════════
class AppLauncher(tk.Toplevel):
    START_PATHS = [
        os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    ]

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)
        self.configure(bg=C["launch_bg"])
        self._apps:      list[tuple[str,str]] = []
        self._cur_list:  list[tuple[str,str]] = []
        self._selected   = 0
        self._photos:    list = []
        self._render_gen = 0
        self._expanded   = False
        self._apps_ready = False
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._x      = (sw - LAUNCHER_W) // 2
        self._y_min  = sh - BAR_HEIGHT - LAUNCHER_H_MIN - 6
        self._y_max  = sh - BAR_HEIGHT - LAUNCHER_H_MAX - 6
        self.geometry(f"{LAUNCHER_W}x{LAUNCHER_H_MIN}+{self._x}+{self._y_min}")
        self.update_idletasks()
        hwnd = self.winfo_id()
        tint_str = C.get("acrylic_tint", "0xE0060414")
        tint = int(tint_str, 16) if isinstance(tint_str, str) else tint_str
        _dwm_acrylic(hwnd, tint=tint)
        _dwm_round(hwnd, DWMWCP_ROUND)
        self._build_ui()
        self._load_apps_async()
        self.bind("<Escape>",   lambda e: self.destroy())
        self.bind("<FocusOut>", self._on_focus_out)
        self._entry.focus_force()

    def _set_collapsed(self):
        self.geometry(f"{LAUNCHER_W}x{LAUNCHER_H_MIN}+{self._x}+{self._y_min}")
        self._results_frame.pack_forget()
        self._expanded = False

    def _set_expanded(self):
        self.geometry(f"{LAUNCHER_W}x{LAUNCHER_H_MAX}+{self._x}+{self._y_max}")
        self._results_frame.pack(fill="both", expand=True)
        self._expanded = True

    def _build_ui(self):
        BG   = C["launch_bg"]
        FG   = C["fg"]
        FG2  = C["fg2"]
        ACC  = C["accent"]
        outer = tk.Frame(self, bg=C["border_bright"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        root = tk.Frame(outer, bg=BG)
        root.pack(fill="both", expand=True)
        search_row = tk.Frame(root, bg=BG, pady=11, padx=14)
        search_row.pack(fill="x")
        tk.Label(search_row, text="⌕", bg=BG, fg=ACC,
                 font=("Segoe UI Symbol", 17)).pack(side="left", padx=(2, 8))
        self._ef = tk.Frame(search_row, bg=C["search_bg"],
                             highlightbackground=C["border"],
                             highlightthickness=1, padx=12, pady=6)
        self._ef.pack(side="left", fill="x", expand=True)
        self._query = tk.StringVar()
        self._query.trace_add("write", lambda *_: self._on_type())
        self._entry = tk.Entry(
            self._ef, textvariable=self._query,
            bg=C["search_bg"], fg=FG, insertbackground=ACC,
            relief="flat", bd=0,
            font=(CFG["launcher"]["font_family"], 13),
            highlightthickness=0)
        self._entry.pack(fill="x")
        self._entry.bind("<Down>",   self._move_down)
        self._entry.bind("<Up>",     self._move_up)
        self._entry.bind("<Return>", lambda e: self._launch())
        self._entry.bind("<FocusIn>",
            lambda e: self._ef.configure(highlightbackground=C["search_focus"]))
        self._entry.bind("<FocusOut>",
            lambda e: self._ef.configure(highlightbackground=C["border"]))
        self._clear_btn = tk.Label(search_row, text="×", bg=BG, fg=FG2,
                                   font=("Segoe UI", 14), cursor="hand2", padx=6)
        self._clear_btn.bind("<Button-1>", lambda e: (
            self._query.set(""), self._entry.focus_set()))
        cfg_btn = tk.Label(search_row, text="⚙", bg=C["bar_pill"], fg=FG2,
                            font=(CFG["bar"]["font_family"], 11),
                            padx=7, pady=2, cursor="hand2")
        cfg_btn.pack(side="right", padx=(4, 0))
        cfg_btn.bind("<Button-1>", lambda e: ConfigWindow(self))
        cfg_btn.bind("<Enter>", lambda e: cfg_btn.configure(fg=FG))
        cfg_btn.bind("<Leave>", lambda e: cfg_btn.configure(fg=FG2))
        help_btn = tk.Label(search_row, text="?", bg=C["bar_pill"], fg=FG2,
                            font=(CFG["bar"]["font_family"], 10, "bold"),
                            padx=7, pady=2, cursor="hand2")
        help_btn.pack(side="right", padx=(4, 0))
        help_btn.bind("<Button-1>", lambda e: HelpWindow(self))
        help_btn.bind("<Enter>", lambda e: help_btn.configure(fg=FG))
        help_btn.bind("<Leave>", lambda e: help_btn.configure(fg=FG2))
        self._results_frame = tk.Frame(root, bg=BG)
        tk.Frame(self._results_frame, bg=C["border"], height=1).pack(fill="x")
        meta_row = tk.Frame(self._results_frame, bg=BG, padx=14, pady=5)
        meta_row.pack(fill="x")
        tk.Label(meta_row, text="APPLICATIONS", bg=BG, fg=C["category"],
                 font=(CFG["bar"]["font_family"], 7, "bold")).pack(side="left")
        self._hint = tk.StringVar(value="")
        tk.Label(meta_row, textvariable=self._hint, bg=BG, fg=FG2,
                 font=(CFG["bar"]["font_family"], 8)).pack(side="right")
        list_wrap = tk.Frame(self._results_frame, bg=BG)
        list_wrap.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(list_wrap, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(list_wrap, orient="vertical",
                          command=self._canvas.yview,
                          width=4, bg=C["border"], troughcolor=BG)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self._canvas, bg=BG)
        self._cwin  = self._canvas.create_window((0,0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
            lambda _: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._cwin, width=e.width))
        self._canvas.bind("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1*(e.delta//120), "units"))
        foot = tk.Frame(self._results_frame, bg=C["bar_pill"], pady=7, padx=14)
        foot.pack(fill="x", side="bottom")
        def _badge(parent, key, desc):
            tk.Label(parent, text=key, bg=C["badge_bg"], fg=C["badge_fg"],
                     font=("Consolas", 8), padx=5, pady=1).pack(side="left", padx=(0,2))
            tk.Label(parent, text=desc, bg=C["bar_pill"], fg=C["fg2"],
                     font=(CFG["bar"]["font_family"], 8)).pack(side="left", padx=(0,10))
        _badge(foot, "↑↓", "navigate")
        _badge(foot, "↵",  "launch")
        _badge(foot, "Esc","close")
        _badge(foot, "⚙",  "settings")

    def _load_apps_async(self):
        threading.Thread(target=self._scan_apps, daemon=True).start()

    def _scan_apps(self):
        seen, apps = set(), []
        for pin in CFG.get("pinned_apps", []):
            name = pin.get("name", "")
            path = pin.get("path", "")
            if name and path:
                seen.add(name.lower())
                apps.append((name, path))
        for base in self.START_PATHS:
            if not os.path.isdir(base): continue
            for root, _, files in os.walk(base):
                for f in files:
                    if f.lower().endswith(".lnk"):
                        name = f[:-4]; key = name.lower()
                        if key not in seen:
                            seen.add(key)
                            apps.append((name, os.path.join(root, f)))
        apps.sort(key=lambda x: x[0].lower())
        self._apps = apps
        self._apps_ready = True
        q = self._query.get().strip()
        if q:
            self.after(0, self._on_type)

    def _on_type(self):
        q = self._query.get().strip().lower()
        if q:
            self._clear_btn.pack(side="right", padx=(4, 0))
        else:
            self._clear_btn.pack_forget()
        if not q:
            self._clear_rows()
            self._set_collapsed()
            return
        if not self._expanded:
            self._set_expanded()
        if not self._apps_ready:
            self._hint.set("scanning apps…")
            self._show([])
            return
        pre = [(n,p) for n,p in self._apps if n.lower().startswith(q)]
        sub = [(n,p) for n,p in self._apps
               if q in n.lower() and not n.lower().startswith(q)]
        results = (pre + sub)[:MAX_RESULTS]
        total   = len(pre) + len(sub)
        self._hint.set(f"{total} result{'s' if total != 1 else ''}")
        self._show(results)

    def _clear_rows(self):
        self._render_gen += 1
        for w in self._inner.winfo_children():
            w.destroy()
        self._photos.clear()
        self._cur_list.clear()
        self._selected = 0

    def _show(self, items: list):
        self._clear_rows()
        self._canvas.yview_moveto(0.0)
        self._cur_list = list(items)
        if not items:
            msg = "Scanning…" if not self._apps_ready else "No results"
            tk.Label(self._inner, text=msg,
                     bg=C["launch_bg"], fg=C["fg2"],
                     font=(CFG["launcher"]["font_family"], 11)).pack(pady=30)
            return
        for i, (name, path) in enumerate(items):
            self._make_row(i, name, path)
        self.after(20, lambda: self._highlight(0, scroll=False))

    def _make_row(self, idx, name, path):
        BG   = C["launch_bg"]
        LFNT = (CFG["launcher"]["font_family"], CFG["launcher"]["font_size"])
        outer = tk.Frame(self._inner, bg=BG)
        outer.pack(fill="x", padx=6, pady=1)
        accent_bar = tk.Frame(outer, bg=C["row_accent"], width=3)
        accent_bar.pack(side="left", fill="y")
        accent_bar.pack_forget()
        row = tk.Frame(outer, bg=BG, height=ROW_H)
        row.pack(side="left", fill="both", expand=True)
        row.pack_propagate(False)
        icon_lbl = tk.Label(row, bg=BG, text="", width=ICON_SZ, height=ICON_SZ)
        icon_lbl.place(x=12, y=(ROW_H - ICON_SZ) // 2, width=ICON_SZ, height=ICON_SZ)
        name_lbl = tk.Label(row, text=name, bg=BG, fg=C["fg"],
                             font=LFNT, anchor="w")
        name_lbl.place(x=12 + ICON_SZ + 12, y=6,
                       width=LAUNCHER_W - 12 - ICON_SZ - 30 - 30, height=20)
        if CFG["launcher"].get("show_path", True):
            short_path = os.path.dirname(path).split(os.sep)[-1]
            path_lbl = tk.Label(row, text=short_path, bg=BG, fg=C["fg_path"],
                                 font=(CFG["launcher"]["font_family"], 7), anchor="w")
            path_lbl.place(x=12 + ICON_SZ + 12, y=26,
                           width=LAUNCHER_W - 12 - ICON_SZ - 30 - 30, height=14)
        else:
            path_lbl = None
        def _enter(e, i=idx): self._highlight(i)
        def _click(e): self._launch()
        widgets = [outer, row, icon_lbl, name_lbl]
        if path_lbl: widgets.append(path_lbl)
        for w in widgets:
            w.bind("<Enter>",    _enter)
            w.bind("<Button-1>", _click)
        outer._accent_bar = accent_bar
        outer._row_inner  = row
        my_gen = self._render_gen
        def _fetch(lbl=icon_lbl, p=path, n=name, gen=my_gen):
            try: ctypes.windll.ole32.CoInitialize(None)
            except: pass
            img = _icon_pil(p, ICON_SZ)
            if img is None:
                img = _letter_pil(n, ICON_SZ)
            if img is None:
                return
            def _apply(img=img, lbl=lbl, gen=gen):
                if not self.winfo_exists(): return
                if gen != self._render_gen: return
                try:
                    if not lbl.winfo_exists(): return
                    ph = ImageTk.PhotoImage(img)
                    self._photos.append(ph)
                    lbl.configure(image=ph, width=ICON_SZ, height=ICON_SZ)
                except Exception: pass
            try: self.after(0, _apply)
            except Exception: pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _highlight(self, idx, scroll=True):
        outers = [w for w in self._inner.winfo_children() if isinstance(w, tk.Frame)]
        for i, outer in enumerate(outers):
            selected = (i == idx)
            row_bg = C["row_sel"] if selected else C["launch_bg"]
            _set_bg(outer, row_bg)
            try:
                if selected: outer._accent_bar.pack(side="left", fill="y")
                else:        outer._accent_bar.pack_forget()
            except AttributeError: pass
        self._selected = idx
        if scroll and len(outers) > 1:
            self._canvas.yview_moveto(max(0.0, (idx - 1) / len(outers)))

    def _move_down(self, _=None):
        outers = [w for w in self._inner.winfo_children() if isinstance(w, tk.Frame)]
        if outers: self._highlight((self._selected + 1) % len(outers))
        return "break"

    def _move_up(self, _=None):
        outers = [w for w in self._inner.winfo_children() if isinstance(w, tk.Frame)]
        if outers: self._highlight((self._selected - 1) % len(outers))
        return "break"

    def _launch(self):
        if self._selected < len(self._cur_list):
            try: os.startfile(self._cur_list[self._selected][1])
            except Exception as e: print(f"launch: {e}")
        self.destroy()

    def _on_focus_out(self, _):
        self.after(200, lambda:
            self.destroy() if self.winfo_exists() and not self.focus_get() else None)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN BAR
# ══════════════════════════════════════════════════════════════════════════════
class CustomBar(tk.Tk):
    def __init__(self):
        super().__init__()
        self.running   = True
        self._abd_hwnd = None
        self._launcher = None
        self.title("CustomShellBar")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=C["bar_bg"])
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{BAR_HEIGHT}+0+0")
        self.update_idletasks()
        _dwm_round(self.winfo_id(), DWMWCP_ROUND)
        self._build_bar()
        self.after(120, self._register_appbar)
        self._poll_desktop()
        self._update_stats()
        threading.Thread(target=self._hotkey_thread, daemon=True).start()

    def _register_appbar(self):
        hwnd = self.winfo_id()
        self._abd_hwnd = hwnd
        sw = self.winfo_screenwidth()
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        abd.hWnd   = hwnd
        abd.uCallbackMessage = 0xBBBB
        abd.uEdge  = 1   # ABE_TOP
        if not shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd)):
            print("⚠ AppBar reg failed"); return
        abd.rc.left = 0; abd.rc.right = sw
        abd.rc.top  = 0; abd.rc.bottom = BAR_HEIGHT
        shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))
        abd.rc.bottom = abd.rc.top + BAR_HEIGHT
        shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))
        self.geometry(f"{sw}x{BAR_HEIGHT}+{abd.rc.left}+{abd.rc.top}")

    def _unregister_appbar(self):
        if not self._abd_hwnd: return
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        abd.hWnd   = self._abd_hwnd
        shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))

    def _build_bar(self):
        BG   = C["bar_bg"]
        FG   = C["fg"]
        FG2  = C["fg2"]
        PILL = C["bar_pill"]
        BFNT = (CFG["bar"]["font_family"], CFG["bar"]["font_size"], "bold")
        SFNT = (CFG["bar"]["font_family"], CFG["bar"]["font_size"])
        tk.Frame(self, bg=C["accent"], height=1).pack(side="bottom", fill="x")
        left   = tk.Frame(self, bg=BG)
        left.pack(side="left", padx=10, pady=3)
        centre = tk.Frame(self, bg=BG)
        centre.place(relx=0.5, rely=0.5, anchor="center")
        right  = tk.Frame(self, bg=BG)
        right.pack(side="right", padx=10, pady=3)

        ev    = CFG["bar"].get("element_visible", {})
        order = CFG["bar"].get("element_order", [e["key"] for e in BAR_ELEMENTS])

        self._dbts       = []
        self._pin_photos = []
        self._clk        = tk.StringVar()
        self._net_v      = tk.StringVar(value="↕ --")
        self._ram_v      = tk.StringVar(value="RAM --")
        self._cpu_v      = tk.StringVar(value="CPU --")
        self._gpu_v      = tk.StringVar(value="")
        self._gpu_lbl    = None

        for key in order:
            if not ev.get(key, True):
                continue

            if key == "desktop_switcher":
                n = _desk_count()
                for i in range(max(n, 1)):
                    lbl = tk.Label(left, text=str(i+1),
                                   bg=PILL, fg=FG2, font=BFNT,
                                   padx=10, pady=2, cursor="hand2")
                    lbl.pack(side="left", padx=2)
                    lbl.bind("<Button-1>", lambda e, idx=i: self._on_desk(idx))
                    lbl.bind("<Enter>",    lambda e, l=lbl: l.configure(fg=FG))
                    lbl.bind("<Leave>",    lambda e, l=lbl: self._restore_btn(l))
                    self._dbts.append(lbl)

            elif key == "pinned_apps":
                pinned = CFG.get("pinned_apps", [])
                if pinned and self._dbts:
                    tk.Frame(left, bg=C["fg3"], width=1).pack(
                        side="left", fill="y", padx=(8, 4), pady=4)
                for pin in pinned:
                    name = pin.get("name", "?")
                    path = pin.get("path", "")
                    lbl = tk.Label(left, text=name[:2].upper(),
                                   bg=PILL, fg=FG2, font=BFNT,
                                   padx=8, pady=2, cursor="hand2")
                    lbl.pack(side="left", padx=2)
                    lbl.bind("<Button-1>", lambda e, p=path: self._launch_pin(p))
                    lbl.bind("<Enter>",
                        lambda e, l=lbl: l.configure(bg=C["pill_act"], fg="#fff"))
                    lbl.bind("<Leave>",
                        lambda e, l=lbl: l.configure(bg=PILL, fg=FG2))
                    def _load_pin_icon(label=lbl, p=path, n=name):
                        img = _icon_pil(p, 16)
                        if img is None: img = _letter_pil(n, 16)
                        if img and PIL_OK:
                            def _apply(img=img, label=label):
                                try:
                                    ph = ImageTk.PhotoImage(img)
                                    self._pin_photos.append(ph)
                                    label.configure(image=ph, text="",
                                                    width=22, height=22)
                                except Exception: pass
                            self.after(0, _apply)
                    threading.Thread(target=_load_pin_icon, daemon=True).start()

            elif key == "clock":
                self._clk = tk.StringVar()
                tk.Label(centre, textvariable=self._clk,
                         bg=BG, fg=FG, font=BFNT).pack()

            elif key == "power_button":
                pwr = tk.Label(right, text="⏻", bg=PILL, fg=C["red"],
                               font=(CFG["bar"]["font_family"], 11),
                               padx=9, pady=1, cursor="hand2")
                pwr.pack(side="right", padx=(4, 0))
                pwr.bind("<Button-1>", lambda e: self._power_menu())
                pwr.bind("<Enter>",    lambda e: pwr.configure(bg=C["red"], fg=BG))
                pwr.bind("<Leave>",    lambda e: pwr.configure(bg=PILL, fg=C["red"]))
                tk.Frame(right, bg=C["fg3"], width=1).pack(
                    side="right", fill="y", padx=6, pady=5)

            elif key == "net":
                tk.Label(right, textvariable=self._net_v, bg=BG,
                         fg=C["cyan"], font=SFNT, padx=5).pack(side="right")

            elif key == "ram":
                tk.Label(right, textvariable=self._ram_v, bg=BG,
                         fg=C["red"], font=SFNT, padx=5).pack(side="right")

            elif key == "cpu":
                tk.Label(right, textvariable=self._cpu_v, bg=BG,
                         fg=C["green"], font=SFNT, padx=5).pack(side="right")

            elif key == "gpu":
                self._gpu_lbl = tk.Label(right, textvariable=self._gpu_v, bg=BG,
                                          fg=C["violet"], font=SFNT, padx=5)
                self._gpu_lbl.pack(side="right")

    def _launch_pin(self, path: str):
        try: os.startfile(path)
        except Exception as e: print(f"pin launch: {e}")

    def _restore_btn(self, lbl):
        if lbl in self._dbts:
            idx = self._dbts.index(lbl)
            lbl.configure(fg="#fff" if idx == _desk_cur() else C["fg2"])

    def _poll_desktop(self):
        if not self.running: return
        self._refresh_desks()
        self.after(450, self._poll_desktop)

    def _refresh_desks(self):
        if not self._dbts: return
        cur = _desk_cur()
        for i, l in enumerate(self._dbts):
            l.configure(bg=C["pill_act"] if i == cur else C["bar_pill"],
                        fg="#fff" if i == cur else C["fg2"])

    def _on_desk(self, idx):
        _desk_go(idx)
        self.after(200, self._refresh_desks)

    def _update_stats(self):
        if not self.running: return
        fmt = CFG["bar"].get("clock_format", "%a %d %b   %H:%M:%S")
        if CFG["bar"].get("show_clock", True):
            try: self._clk.set(datetime.now().strftime(fmt))
            except: pass
        if PSUTIL_OK:
            if CFG["bar"].get("show_cpu", True):
                self._cpu_v.set(f"CPU {psutil.cpu_percent():.0f}%")
            if CFG["bar"].get("show_ram", True):
                self._ram_v.set(f"RAM {psutil.virtual_memory().percent:.0f}%")
            if CFG["bar"].get("show_net", True):
                try:
                    n = psutil.net_io_counters()
                    if hasattr(self, "_pnet"):
                        d = (n.bytes_recv - self._pnet.bytes_recv +
                             n.bytes_sent - self._pnet.bytes_sent)
                        self._net_v.set(f"↕ {d/1024:.0f} KB/s")
                    self._pnet = n
                except: pass
        if CFG["bar"].get("show_gpu", True):
            self._gpu_v.set(f"GPU {_gpu_usage}%" if _gpu_usage >= 0 else "")
        self.after(1000, self._update_stats)

    def _open_launcher(self):
        if self._launcher and self._launcher.winfo_exists():
            self._launcher.destroy()
            self._launcher = None
        else:
            self._launcher = AppLauncher(self)

    def _open_config(self):
        ConfigWindow(self)

    def _power_menu(self):
        m = tk.Menu(self, tearoff=0,
                    bg=C["launch_bg"], fg=C["fg"],
                    activebackground=C["row_hov"], activeforeground=C["fg"],
                    font=(CFG["bar"]["font_family"], 10), bd=0, relief="flat")
        m.add_command(label="  ⚙  Settings / Config",
            command=lambda: ConfigWindow(self))
        m.add_command(label="  ❓  Help / Shortcuts",
            command=lambda: HelpWindow(self))
        m.add_command(label="  📁  Open Config Folder",
            command=lambda: os.startfile(APPDATA_DIR))
        m.add_separator()
        m.add_command(label="  🔄  Restart Bar",
            command=_restart_app)
        m.add_separator()
        m.add_command(label="  💤  Sleep",
            command=lambda: os.system(
                "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"))
        m.add_separator()
        m.add_command(label="  🔄  Restart Windows",
            command=lambda: os.system("shutdown /r /t 0"))
        m.add_command(label="  ⏹  Shutdown",
            command=lambda: os.system("shutdown /s /t 0"))
        m.post(self.winfo_pointerx(), self.winfo_pointery() - 4)

    def _hotkey_thread(self):
        hk = {}
        for n in range(1, 10):
            if user32.RegisterHotKey(None, n, MOD_ALT | MOD_NOREPEAT, _VK[str(n)]):
                hk[n] = f"d{n-1}"
        if user32.RegisterHotKey(None, 10, MOD_ALT | MOD_NOREPEAT, _VK["space"]):
            hk[10] = "launcher"
        if user32.RegisterHotKey(None, 11, MOD_ALT | MOD_NOREPEAT, _VK["c"]):
            hk[11] = "config"
        msg = ctypes.wintypes.MSG()
        while self.running:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret <= 0: break
            if msg.message == WM_HOTKEY:
                a = hk.get(msg.wParam)
                if a and a.startswith("d"):
                    _desk_go(int(a[1:]))
                    self.after(0, self._refresh_desks)
                elif a == "launcher":
                    self.after(0, self._open_launcher)
                elif a == "config":
                    self.after(0, self._open_config)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        for k in hk:
            user32.UnregisterHotKey(None, k)

    def _on_close(self):
        self.running = False
        self._unregister_appbar()
        _taskbar_vis(True)
        try: self.destroy()
        except: pass


# ══════════════════════════════════════════════════════════════════════════════
# SELF-INSTALL / STARTUP
# ══════════════════════════════════════════════════════════════════════════════
TASK_NAME = "CustomShellBar"

def _is_running_from_install() -> bool:
    return os.path.abspath(__file__) == os.path.abspath(INSTALL_PY)

def _self_install():
    src = os.path.abspath(__file__)
    if src != INSTALL_PY:
        shutil.copy2(src, INSTALL_PY)
        print(f"✓ Copied script to: {INSTALL_PY}")

def _is_scheduled() -> bool:
    r = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode == 0

def _install_startup():
    _self_install()
    _ensure_config()
    py  = sys.executable
    scr = INSTALL_PY
    pyw = py.replace("python.exe", "pythonw.exe")
    if os.path.exists(pyw):
        py = pyw
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Custom Windows Shell Bar</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>4</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{py}</Command>
      <Arguments>"{scr}"</Arguments>
      <WorkingDirectory>{APPDATA_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""
    tmp = os.path.join(os.getenv("TEMP", ""), "customshellbar_task.xml")
    with open(tmp, "w", encoding="utf-16") as f:
        f.write(xml)
    r = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", tmp, "/F"],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try: os.remove(tmp)
    except: pass
    if r.returncode == 0:
        print(f"✓ Startup task '{TASK_NAME}' registered.")
    else:
        print(f"✗ Failed: {r.stderr.strip()}")

def _uninstall_startup():
    r = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode == 0:
        print(f"✓ Startup task '{TASK_NAME}' removed.")
    else:
        print(f"✗ Could not remove: {r.stderr.strip()}")


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY
# ══════════════════════════════════════════════════════════════════════════════
def main():
    is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())

    if "--help" in sys.argv:
        root = tk.Tk(); root.withdraw()
        HelpWindow(root)
        root.mainloop()
        return

    if "--config" in sys.argv:
        root = tk.Tk(); root.withdraw()
        ConfigWindow(root)
        root.mainloop()
        return

    if "--install" in sys.argv:
        if not is_admin:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{os.path.abspath(__file__)}" --install', None, 1)
            return
        _install_startup()
        return

    if "--uninstall" in sys.argv:
        if not is_admin:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{os.path.abspath(__file__)}" --uninstall', None, 1)
            return
        _uninstall_startup()
        return

    _ensure_config()
    first_run = not os.path.exists(FIRSTRUN_FLAG)

    if not _is_scheduled() and not _is_running_from_install():
        root = tk.Tk(); root.withdraw()
        ans = mb.askyesno(
            "CustomShellBar — First Run",
            "Install CustomShellBar to startup?\n\n"
            f"Script → {INSTALL_PY}\nConfig → {CONFIG_FILE}\n\n"
            "Runs at logon with admin rights.\n"
            "(Remove: python shellbar.py --uninstall)")
        root.destroy()
        if ans:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                f'"{os.path.abspath(__file__)}" --install', None, 1)

    if not is_admin:
        print("⚠ Not admin — some features limited")

    try: open(FIRSTRUN_FLAG, "w").close()
    except: pass

    _taskbar_vis(False)
    bar = CustomBar()
    bar.protocol("WM_DELETE_WINDOW", bar._on_close)

    # Show help on first run as a proper standalone window
    if first_run:
        bar.after(800, lambda: HelpWindow(bar))

    try:
        bar.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        bar._on_close()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "desktop":
        _desk_go(int(sys.argv[2]))
    else:
        main()