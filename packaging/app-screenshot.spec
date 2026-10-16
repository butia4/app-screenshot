# PyInstaller spec: onedir, console (the console banner is the "recording" indicator).
# Build from the repository root:  pyinstaller packaging/app-screenshot.spec
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("mss")

a = Analysis(
    ["../src/app_screenshot/__main__.py"],
    pathex=["../src"],
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="app-screenshot",
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, name="app-screenshot")
