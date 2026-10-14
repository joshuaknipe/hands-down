# Hands Down

A small tray and menu bar app for Windows and macOS that watches your webcam and plays a gentle sound when your hand rests on your head
or hair for more than a moment. It is a nudge to notice a habit, not a blocker or a scorecard.

- Runs quietly in the system tray (Windows) or menu bar (macOS) while you work in other apps.
- Everything happens on your computer. No images are ever saved and nothing is sent anywhere.
- The log keeps only times, durations and states, so you can see patterns by time of day.

## Install on Windows (easiest)

No Python or other tools needed.

1. Go to the [latest release](https://github.com/joshuaknipe/hands-down/releases/latest) and
   download **HandsDown-windows.zip**.
2. Right-click the downloaded zip, choose **Extract All…**, and extract it somewhere you will keep
   it, for example your **Documents** folder.
3. Open the extracted **HandsDown** folder and double-click **HandsDown.exe**.
   Windows SmartScreen may warn the first time, because the app is not signed: choose
   **More info**, then **Run anyway**.
4. A thin ring appears in the system tray. If you cannot see it, click the **^** arrow by the
   clock, and drag the ring onto the taskbar to keep it visible. Teal means it is watching.
5. To start it automatically: click the ring, choose **Settings…** and tick **Start with Windows**.
   This remembers where the folder is, so if you move the folder later, untick and tick it again.

**To update:** click the ring and choose **Quit**, delete the old **HandsDown** folder, and extract
the new release in the same place. Settings and the log are kept: they live in your user profile,
not in the app folder.

## Install on macOS (easiest)

For Macs with Apple silicon (M1 or later). On an Intel Mac, see [Run from source](#run-from-source-windows-or-macos).

1. Go to the [latest release](https://github.com/joshuaknipe/hands-down/releases/latest) and
   download **HandsDown-macos.zip**.
2. Double-click the zip to unpack it, and drag **HandsDown.app** into your **Applications** folder.
3. Open it. The first time, macOS says it cannot check the app for malicious software, because
   the app is not signed with a paid Apple developer account. Click **Done**, then open
   **System Settings → Privacy & Security**, scroll down to the message about HandsDown, and click
   **Open Anyway**. You only do this once per version.
4. Allow camera access when asked.
5. A thin ring appears in the menu bar, near the clock. Teal means it is watching. If your menu
   bar is very full, a MacBook's notch can still hide it: quit an app or two that have menu bar
   icons, then **⌘-drag** the ring to where you want it.
6. To start it automatically: click the ring, choose **Settings…** and tick **Start at login**.

**To update:** click the ring and choose **Quit**, then replace **HandsDown.app** in Applications
with the new one. macOS treats each version as a new app, so it asks for **Open Anyway** and
camera access again.

## Build it yourself on Windows

To build from the code instead, for example to get changes before they are released.
You need a webcam, **Python 3.12** exactly (newer versions are not supported yet by the vision
library it uses) and **Git**.

Open **PowerShell** (press Start, type `powershell`, press Enter) and run:

```powershell
winget install Python.Python.3.12
winget install Git.Git
```

Close PowerShell and open it again, so it finds them. Then:

```powershell
git clone https://github.com/joshuaknipe/hands-down.git $HOME\hands-down
powershell -ExecutionPolicy Bypass -File $HOME\hands-down\install.ps1
```

The script downloads the components it needs (several minutes the first time), builds the app,
checks that the build works, installs it to `%LOCALAPPDATA%\Programs\HandsDown` and starts it.
Then continue from step 4 above.

**To update:**

```powershell
cd $HOME\hands-down
git pull
powershell -ExecutionPolicy Bypass -File install.ps1
```

The script quits the running copy and replaces it.

## Using it

Click the ring for the menu:

- **Pause for calls (automatic)**: a saved on/off preference, also available in Settings.
  When enabled, Hands Down releases the camera and stops alerts while another app is
  reported as using a camera, then resumes after the camera has been free for two seconds.
  This uses OS camera activity rather than Teams presence; calls with the camera off
  do not trigger it. Camera activity reporting depends on the OS and driver. On macOS and Windows,
  another app using any camera can trigger a pause. macOS tracks camera stream clients
  through the local camera-service event log, including shared-camera use; it does not
  read or record camera images for this check.
- **Pause 15 minutes**, **Pause 1 hour**: manually releases the camera for that duration.
  **Resume** ends a manual pause early. Automatic call pausing never cancels a manual pause.
- **That wasn't me**: marks the last alert as a false alarm.
- **Show camera**: a live view with the detection zone drawn on it. Useful while adjusting
  settings. Press **S** or click **Settings** in the view to open settings beside it.
- **Summary**: today's count, time and a chart by hour, plus the last seven days.
- **Settings…**: sound and volume, screen effects, how long before an alert, repeats, the size of the zone,
  pausing while the screen is locked, and starting at sign-in. Changes apply immediately.
  In **Screen effects**, choose a border color and thickness (up to 500), a custom reminder
  message, and/or screen blur with adjustable strength. Each effect works independently.
  Customize the message size and color, choose one of nine screen positions, and set its
  background color and horizontal/vertical padding. You can also hide the text background.
  Large borders and text panels are fitted to the display so they stay on screen. While this
  tab is open, a live desktop preview updates as you adjust the controls; Settings stays
  above it. Leaving the tab or closing Settings removes the preview. During detection,
  effects appear after the alert delay and disappear when your hand moves away.
  Blur displays a blurred snapshot taken when the effect starts, until your hand moves
  away; it does not continuously update the desktop image. On macOS, blur needs
  **System Settings → Privacy & Security → Screen Recording** permission for Hands Down
  (or Python when running from source). If capture is unavailable, an on-screen message
  explains it and the other effects still work. Screen effects may be visible in screen sharing.
- **Open log folder**: the raw log (`events.jsonl`).
- **Quit**.

The ring's colour shows the state: teal is watching, amber means it cannot see your face,
red means the camera is unavailable, grey is paused. The menu distinguishes a manual pause
from **Paused — camera used by another app**.

## Run from source (Windows or macOS)

Without building, from the `hands-down` folder:

```powershell
.venv\Scripts\python.exe -m handsdown        # Windows
```

```bash
.venv/bin/python -m handsdown                # macOS
```

"Start with Windows" and "Start at login" only work in the built app.

### macOS setup

```bash
brew install python@3.12 python-tk@3.12      # python-tk is needed for the settings window
git clone https://github.com/joshuaknipe/hands-down.git
cd hands-down
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m handsdown
```

macOS asks for camera permission the first time; allow it for your terminal or editor.
To build the app bundle yourself: `.venv/bin/pyinstaller --noconfirm packaging/handsdown.spec`
makes `dist/HandsDown.app`.

## For developers

```bash
.venv/bin/python -m pytest              # the test suite (Windows: .venv\Scripts\python.exe -m pytest)
.venv/bin/python -m feasibility --help  # tools for recording labelled clips and measuring the detector
```

- `handsdown/`: the app. Detection (`zone.py`, `episodes.py`) is pure Python and tested without a camera.
- `feasibility/`: developer tools, including `evaluate`, which runs the detector over recorded clips.
- `models/`: the MediaPipe hand and face models, committed so builds need no network.
- Pushes to `main` and pull requests run the tests on Windows and macOS.
- To try the builds without releasing, press **Run workflow** on the tests workflow in the
  Actions tab. It builds the Windows app with `install.ps1` (twice, to check updating too) and
  the Mac app bundle, and keeps both zips as artifacts there.
- To publish a release, tag a version and push the tag; CI builds both apps and attaches the zips:

  ```bash
  git tag v0.1.0
  git push origin v0.1.0
  ```

## Licence

Hands Down is under the [MIT licence](LICENSE). The bundled MediaPipe hand and face models are
© Google LLC under the Apache License 2.0; see [models/SOURCES.md](models/SOURCES.md).
