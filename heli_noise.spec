# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for HeliNoiseAnalyzer (Windows target).

Build (Windows only, in build-windows.yml): pyinstaller --clean heli_noise.spec
Produces dist/HeliNoiseAnalyzer.exe — a single-file, windowed (no
console) executable with imageio-ffmpeg's bundled ffmpeg binary
included, so end users never install ffmpeg separately.
"""

from PyInstaller.utils.hooks import collect_data_files

# imageio-ffmpeg ships its platform-specific ffmpeg binary as package
# data under imageio_ffmpeg/binaries/; collecting it here is what lets
# imageio_ffmpeg.get_ffmpeg_exe() keep working inside the frozen exe.
datas = collect_data_files("imageio_ffmpeg")

a = Analysis(
    ["src/heli_noise/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # matplotlib picks its Qt backend dynamically at runtime, so
        # PyInstaller's static import scan misses it without this.
        "matplotlib.backends.backend_qtagg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HeliNoiseAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
