# Hands Down

A small tray app that watches your webcam and plays a gentle sound when your hand rests on your head
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

- **Pause for call**, **Pause 15 minutes**, **Pause 1 hour**: releases the camera, for example
  before a Teams or Zoom call. **Resume** turns it back on.
- **That wasn't me**: marks the last alert as a false alarm.
- **Show camera**: a live view with the detection zone drawn on it. Useful while adjusting
  settings. Press **S** or click **Settings** in the view to open settings beside it.
- **Summary**: today's count, time and a chart by hour, plus the last seven days.
- **Settings…**: sound and volume, how long before an alert, repeats, the size of the zone,
  pausing while the screen is locked, and starting with Windows. Changes apply immediately.
- **Open log folder**: the raw log (`events.jsonl`).
- **Quit**.

The ring's colour shows the state: teal is watching, amber means it cannot see your face,
red means another app is using the camera, grey is paused.

## Run from source (Windows or macOS)

Without building, from the `hands-down` folder:

```powershell
.venv\Scripts\python.exe -m handsdown        # Windows
```

```bash
.venv/bin/python -m handsdown                # macOS
```

"Start with Windows" only works in the built app.

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
On a MacBook with a notch, a crowded menu bar can hide the ring. To place it near the clock, quit
Hands Down and run `defaults write org.python.python "NSStatusItem Preferred Position Item-0" -float 300`,
then start it again.

## For developers

```bash
.venv/bin/python -m pytest              # the test suite (Windows: .venv\Scripts\python.exe -m pytest)
.venv/bin/python -m feasibility --help  # tools for recording labelled clips and measuring the detector
```

- `handsdown/`: the app. Detection (`zone.py`, `episodes.py`) is pure Python and tested without a camera.
- `feasibility/`: developer tools, including `evaluate`, which runs the detector over recorded clips.
- `models/`: the MediaPipe hand and face models, committed so builds need no network.
- Pushes to GitHub run the tests on Windows, then build the app with `install.ps1` (twice, to check
  updating too) and keep the zip as an artifact in the Actions tab.
- To publish a release, tag a version and push the tag; CI attaches `HandsDown-windows.zip`:

  ```bash
  git tag v0.1.0
  git push origin v0.1.0
  ```
