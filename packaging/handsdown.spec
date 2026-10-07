# PyInstaller spec for Hands Down: a windowed --onedir build named HandsDown.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = SPECPATH + "/.."

a = Analysis(
    [root + "/packaging/launcher.py"],
    pathex=[root],
    datas=[
        (root + "/models/hand_landmarker.task", "models"),
        (root + "/models/face_landmarker.task", "models"),
        (root + "/assets/sounds", "assets/sounds"),
        *collect_data_files("mediapipe"),
    ],
    binaries=collect_dynamic_libs("mediapipe"),
    hiddenimports=["pystray._win32", "PIL._tkinter_finder"],
    excludes=["feasibility", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HandsDown", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="HandsDown")
