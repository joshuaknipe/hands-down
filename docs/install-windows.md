# Installing Hands Down on Windows

1. Open the repository's **Actions** tab on GitHub, choose the latest green **tests** run on
   `main`, and download the **HandsDown** artifact (a zip).
2. Unzip it to `%LOCALAPPDATA%\Programs\HandsDown` (paste that into File Explorer's address bar;
   create the folder if needed).
3. Double-click `HandsDown.exe`. Windows SmartScreen will warn because the app is not signed:
   choose **More info**, then **Run anyway**. This happens once.
4. A ring appears in the system tray (click the **^** arrow by the clock if it is hidden; drag
   it onto the taskbar to keep it visible). Teal means watching.
5. Right-click the ring, choose **Settings…**, tick **Start with Windows**, and Save.

## Using it

- **Pause for call** before a Teams or Zoom call that needs the camera; **Resume** afterwards.
- **That wasn't me** marks the last alert as a false alarm. Please use it during the trial.
- **Open log folder** shows `events.jsonl`: times, durations and states only, never images.

## Updating

Quit Hands Down from the tray, replace the folder's contents with the new artifact, and start it again.
Settings and the log are kept, since they live in your user profile, not in the app folder.
