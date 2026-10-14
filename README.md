# Hands Down

A free desktop app that gives you a gentle reminder when your hand stays near your head or hair while you're using your computer.

Made with trichotillomania in mind, Hands Down runs quietly while you work, study, or use other apps. You can choose a sound, a colored screen border, your own reminder message, or screen blur. Everything runs on your computer, and you can adjust the reminders to suit you.

**Free to use · Open source · Runs offline · Windows and macOS**

## Download

You don't need to know how to code, install Python, or use a terminal to use the downloads.

| Your computer | Download |
| --- | --- |
| Windows | [Download for Windows](https://github.com/joshuaknipe/hands-down/releases/latest/download/HandsDown-windows.zip) |
| Mac with an Apple chip (M1 or newer) | [Download for Mac](https://github.com/joshuaknipe/hands-down/releases/latest/download/HandsDown-macos.zip) |

[View the latest release and what's changed](https://github.com/joshuaknipe/hands-down/releases/latest).

You'll need a webcam that can see your face and hands. The Mac download is for **Apple Silicon**: check **Apple menu → About This Mac** if you're unsure which Mac you have. There isn't a ready-made Intel Mac download; the [developer instructions](#for-developers) explain how to try running from source.

## Getting started

### Windows

1. Download **HandsDown-windows.zip** using the link above.
2. Right-click the downloaded file and choose **Extract All…**. Put the extracted folder somewhere you'll keep it, such as Documents. Keep the whole folder together.
3. Open the extracted **HandsDown** folder and double-click **HandsDown.exe**.
4. Look for a small ring beside the clock, in the bottom-right corner of your screen. You may need to click the **^** arrow to find it. Click the ring to open the app's menu.

Windows may show **Windows protected your PC** because the download doesn't have a publisher signature. If you trust the download from this repository and the option is available, choose **More info → Run anyway**. Some Windows security policies block unsigned apps altogether; [Microsoft explains these checks here](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

### Mac

1. Download **HandsDown-macos.zip** using the link above.
2. Double-click the downloaded file to unpack it. Drag **HandsDown.app** into your Applications folder, then open it from there.
3. Allow camera access when asked.
4. Look for a small ring near the clock at the top of your screen. Click it to open the app's menu.

The app isn't notarized by Apple, so macOS may block the first launch. After trying to open it, go to **System Settings → Privacy & Security** and look for the HandsDown message. If you trust the download, choose **Open Anyway**, then confirm **Open**. [Apple's guide explains the warning and these steps](https://support.apple.com/en-gb/102445).

**There isn't a main app window.** Hands Down stays in the small ring menu while you use other apps. If the ring is teal, it's watching.

### Try your first reminder

1. Click the ring and choose **Show camera**. You'll see the area around your head that the app is watching.
2. Sit where the camera can see your face and hands, then move a hand near your head or hair for a moment. On a fresh install, you'll hear a reminder sound after about half a second.
3. Choose **Settings…** from the ring menu to change the sound or add a visual reminder. You can also press **S** or click **Settings** in the camera window.
4. Close the camera window when you're finished adjusting things. Closing this window doesn't stop detection; **Quit** in the ring menu does.

Hand position triggers the reminders, so scratching your head or adjusting your hair can trigger them too. You can change the watched area and the delay before a reminder appears.

## Make the reminders your own

Settings are saved as you change them. You don't need to click a Save button.

- **Alerts:** choose a sound, adjust its volume, try it with **Play**, or enable a notification.
- **Screen effects:** choose a border color and thickness (up to 500), add a message, or turn on adjustable blur. Change the message's size, color and position, and choose its background color. The padding sliders change the amount of space around the message; you can also hide its background.
- **Detection:** adjust the delay before alerting, repeat reminders, and the area around your head that counts as contact. You can also choose pause options, start at sign-in, or select a different camera.

**Screen effects has a live desktop preview.** It shows your chosen effects while that tab is open, even if your hand isn't near your head. Switch to another tab or close Settings to remove the preview. Close Settings before testing normal detection or automatic pausing for calls.

During detection, visual reminders appear after the alert delay and disappear when your hand moves away. Blur shows a blurred snapshot of your desktop while the reminder is active; the snapshot doesn't update continuously. Screen effects can be visible to others if you share your screen.

### Using blur on a Mac

Blur needs permission to take a screenshot. Go to **System Settings → Privacy & Security → Screen & System Audio Recording** (called **Screen Recording** on some macOS versions) and allow HandsDown. Follow any request to quit and reopen the app. [Apple's screen-access guide](https://support.apple.com/en-gb/guide/mac-help/mchld6aa7d23/mac) has more details.

You can use sound, borders and reminder text without enabling screen blur.

## Pausing for calls or taking a break

Click the ring to find these options:

- **Pause for calls (automatic):** turn this on if you'd like Hands Down to stop using the camera and stop detection alerts when another app uses a camera. It resumes automatically after the camera has been free for two seconds. You can also enable **Pause for calls** in Settings → Detection. This option is off by default.
- **Pause 15 minutes / Pause 1 hour:** take a timed break. Choose **Resume** to end the break early.
- **Pause while the screen is locked:** available in Settings → Detection and on by default. Hands Down releases the camera while your computer is locked.

Automatic call pausing uses camera activity. A call with its camera off won't trigger it, and another app using a different camera can trigger it too. The shared-camera behavior has been checked with Teams on macOS. Windows support is implemented and passes automated tests, but still needs a real Teams-call check. Camera activity reporting can vary by computer and driver.

An automatic call pause won't end a manual timed break.

## What does the ring color mean?

| Color | What's happening |
| --- | --- |
| Teal | Watching for your hand near your head. |
| Amber | The camera can't currently see your face. Try adjusting your position or lighting. |
| Red | The camera is unavailable. It may be busy, disconnected, or blocked by camera permissions. |
| Gray | Starting up or paused. Open the menu to see why. |

The menu shows **Paused — camera used by another app** during an automatic call pause.

## Privacy and your data

Hands Down runs offline once you've downloaded it. No account or subscription is needed, and the app doesn't upload camera footage, screenshots, or your reminder history.

- **Webcam:** frames are processed on your computer. Webcam video and images aren't recorded or saved by the app.
- **Optional blur:** uses a temporary screenshot of your desktop. On macOS, the screenshot tool writes a temporary image file and removes it after loading it; the app holds the snapshot in memory while showing the effect. Screenshots aren't added to your reminder history or uploaded.
- **Call pausing:** checks local camera-use information. On macOS, it reads narrowly filtered camera-service events to identify other camera users, without capturing their video.
- **Local history:** the app saves reminder timings, durations, status changes and diagnostic messages on your computer. **Summary** shows today's activity and the last seven days. It counts detected hand-near-head episodes, not confirmed hair pulling. **That wasn't me** marks the last alert as a false alarm.

Open source means the code is public: anyone can inspect it, change it, or build their own copy. You can browse the files in this repository, and the [developer instructions](#for-developers) explain how to build from them. Downloading the app or installing developer dependencies requires internet access; normal use doesn't.

## Common questions

**I opened it, but nothing appeared.**

Look for the ring beside the clock. On Windows, check the **^** arrow. On a Mac with a crowded menu bar, the camera notch can hide icons; closing another menu-bar app can make room. Once visible, you can **⌘-drag** the ring to a different spot.

**It keeps reminding me when I'm not pulling.**

Open **Show camera** and adjust the watched area in Settings → Detection. Try increasing **Wait before alerting** so a quick scratch doesn't trigger it. The mouth and chin have an ignored area by default; **Ignored chin area** changes its size, and setting it to 0 includes that area too.

**The screen effects won't go away.**

Check whether Settings → Screen effects is open: that's the live preview. Leave that tab or close Settings. During normal detection, the effects clear shortly after your hand moves away.

**The camera won't start, or another app needs it.**

Check that the camera is connected and camera access is allowed in your computer's privacy settings. Try a manual pause before opening your call app. If you have several cameras, choose a different **Camera number** in Settings → Detection.

**Can it start when I turn on my computer?**

Yes. In Settings → Detection, enable **Start with Windows** or **Start at login**. If you later move the app to a different folder, switch this off and on again. This works with the downloaded/built app, not when running directly from Python.

**How do I stop it?**

Click the ring and choose **Quit**. Closing the camera or Settings window leaves the background app running.

## Updating

1. Click the ring and choose **Quit**.
2. Download the new version from the [latest release](https://github.com/joshuaknipe/hands-down/releases/latest).
3. On Windows, replace the old HandsDown folder with the newly extracted folder. On a Mac, replace HandsDown.app in Applications.
4. Open the new copy. Your settings and local history are kept separately and will still be there.

macOS may ask you to approve the new download or grant permissions again after an update.

## Feedback and contributions

Found a bug or have an idea? [Open an issue](https://github.com/joshuaknipe/hands-down/issues). Please include your operating system, what you were trying to do, and what happened. **Open log folder** in the ring menu can help with troubleshooting; check its contents before sharing anything.

This is a small free project, so I can't promise ongoing support or every requested improvement. If you code, you're welcome to fork the repository and submit a pull request with fixes or new features.

## For developers

The instructions below are optional. The downloads above are the easiest way to use Hands Down.

<details>
<summary>Run or build from source</summary>

The build workflow uses **Python 3.12**. The Windows installer checks for that version. You'll also need Git; installation downloads dependencies and the repository's bundled models.

### Windows

Install Python and Git, then close and reopen PowerShell:

```powershell
winget install Python.Python.3.12
winget install Git.Git
```

Clone and build the app:

```powershell
git clone https://github.com/joshuaknipe/hands-down.git $HOME\hands-down
powershell -ExecutionPolicy Bypass -File $HOME\hands-down\install.ps1
```

The script creates the Python environment, downloads dependencies, builds and checks the app, then installs it in `%LOCALAPPDATA%\Programs\HandsDown` and starts it. Keep the full installed folder together.

To update a source-built installation:

```powershell
cd $HOME\hands-down
git pull
powershell -ExecutionPolicy Bypass -File install.ps1
```

The script stops the running packaged app and replaces it, keeping settings and history. Pass `-NoStart` to install without launching it.

After setup, run directly from the repository with:

```powershell
.venv\Scripts\python.exe -m handsdown
```

### macOS

Install Python and Tk with Homebrew, then set up the environment:

```bash
brew install python@3.12 python-tk@3.12
git clone https://github.com/joshuaknipe/hands-down.git
cd hands-down
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m handsdown
```

Allow camera access for the terminal/editor or Python app macOS identifies. Screen blur needs screen-access permission for that process too. Starting at login is available only in a packaged app.

Build the Mac app bundle with:

```bash
.venv/bin/pyinstaller --noconfirm packaging/handsdown.spec
```

The output is `dist/HandsDown.app`. The published Mac download is Apple Silicon; an Intel source build isn't verified here.

</details>

<details>
<summary>Tests, project structure and releases</summary>

Run the tests from the repository:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m feasibility --help
```

On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

- `handsdown/`: the app. Detection logic in `zone.py` and `episodes.py` is tested without a camera.
- `feasibility/`: tools for recording labeled clips and evaluating detection.
- `models/`: bundled MediaPipe hand and face models; runtime doesn't need model downloads.
- Pushes to `main` and pull requests run tests on Windows and macOS.
- **Run workflow** in GitHub Actions tests and builds both apps without publishing a release. The Windows build checks fresh installation and updating; both packaged apps run a self-test. The ZIPs are saved as workflow artifacts.
- A version tag triggers those checks and publishes a release with both ZIPs. Replace `vX.Y.Z` below with a new, unused version:

```bash
git tag -a vX.Y.Z -m "Hands Down vX.Y.Z"
git push origin vX.Y.Z
```

</details>

## Licence

Hands Down is available under the [MIT licence](LICENSE). The bundled MediaPipe hand and face models are © Google LLC under the Apache License 2.0; see [models/SOURCES.md](models/SOURCES.md).
