# PyInstaller spec for Hands Down: a windowed --onedir build named HandsDown,
# wrapped in HandsDown.app on macOS.
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = SPECPATH + "/.."
mac = sys.platform == "darwin"

a = Analysis(
    [root + "/packaging/launcher.py"],
    pathex=[root],
    datas=[
        (root + "/models/hand_landmarker.task", "models"),
        (root + "/models/face_landmarker.task", "models"),
        (root + "/models/LICENSE-APACHE-2.0.txt", "models"),
        (root + "/LICENSE", "."),
        (root + "/assets/sounds", "assets/sounds"),
        *collect_data_files("mediapipe"),
    ],
    binaries=collect_dynamic_libs("mediapipe"),
    hiddenimports=["pystray._darwin" if mac else "pystray._win32", "PIL._tkinter_finder"],
    excludes=["feasibility", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="HandsDown", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="HandsDown")

if mac:
    app = BUNDLE(
        coll,
        name="HandsDown.app",
        bundle_identifier="com.handsdown.app",
        info_plist={
            "CFBundleDisplayName": "Hands Down",
            # Without this, macOS ends the app the moment it opens the camera.
            "NSCameraUsageDescription": "Hands Down watches the camera to notice when your hand rests on your head. Nothing is recorded or sent anywhere.",
            "LSUIElement": True,  # a menu bar app: no Dock icon
            "NSHighResolutionCapable": True,
        },
    )
