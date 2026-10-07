# Hands Down — Design Decisions

Oct 7, 2026 · @Joshua Knipe

## Purpose

Hands Down is a small desktop app that watches the webcam and gently alerts the user when her hand stays on her hair, to interrupt a hand-to-hair habit while she works at her laptop.

- **Primary user:** one person, on a Windows 11 laptop, working in other apps for hours at a time, including video calls in the Teams desktop app. She has agreed to record test clips on her laptop.
- **Goal:** raise awareness at the moment the hand reaches her hair, as an awareness prompt. It is a nudge, not a blocker or a scorecard.
- **Success:** alerts fire on real episodes with few enough false alarms, and little enough friction around calls, that she keeps it running all day. "Few enough" is defined by the acceptance criteria below.
- **Out of scope for v1:** mobile, multi-user accounts, cloud sync, analytics dashboards, screen-edge flash alerts, a packaged Mac build.

**Central uncertainty.** Hands Down assumes that a visible hand near her hair is a good enough stand-in for her actual habit. Nothing else in this plan matters if that is false, so the first milestone exists to test it on her laptop, in her seating position, before anything is tuned.

## Milestones

Each milestone ends with a go / no-go decision. Platform problems are found on Windows early, not after weeks of tuning on the Mac.

1. **Feasibility on her laptop.** A minimal script, run from source on her Windows laptop (Python is installed there for this).
   - Does HandLandmarker find her hand during real hand-to-hair motions, at her camera angle and with as much of her head as her webcam frames?
   - Camera coexistence: start Hands Down then Teams, and Teams then Hands Down. Record what happens with the OpenCV backends, and whether Windows shared camera access is available on her machine (see Camera sharing and calls).
   - Go if her hand is found during most real motions and there is a workable answer for calls. No-go means fixing framing or camera angle first, or rethinking the approach.
2. **Packaged Windows baseline.** Stage 1 detector (head zone), episode logic, chime, tray, pause, built by CI and installed on her laptop. Model-file loading and notifications are checked in the frozen build here.
3. **Ordinary-work trial.** She runs the baseline during normal work for several days, marking false alerts from the tray. Measured against the acceptance criteria.
4. **Hair segmentation (only if needed).** Built only if the trial shows the head zone produces too many false alerts on face-touching. Otherwise it stays out of v1.

## Key decisions

Hands Down is a native Python tray app, developed on macOS and shipped to Windows as a PyInstaller build.

| Decision | Choice | Why | Rejected |
| --- | --- | --- | --- |
| Form factor | Desktop tray app | Must keep working while she uses other apps; browsers throttle or pause camera processing in background tabs and minimised windows | Web app / PWA |
| Language | Python, with both the Python version and the `mediapipe` version pinned to a pair that has wheels for macOS arm64 and Windows x64 | Developer's strongest language; all key libraries are cross-platform | Electron, Tauri (possible later wrapper) |
| Vision | MediaPipe Tasks: HandLandmarker (VIDEO mode) and FaceLandmarker or Pose for the head zone; the multiclass selfie segmenter for hair if milestone 4 goes ahead | Pretrained, runs on CPU in real time, models ship as local files; the multiclass segmenter labels hair and face skin separately | Training a custom model; hair-only segmenter (cannot tell hair from cheek) |
| Camera | OpenCV, explicit backend per OS (AVFoundation on Mac, DirectShow on Windows, Media Foundation as fallback), unless milestone 1 shows shared capture is needed on Windows | Default backend can be slow to open on Windows | — |
| Tray | pystray | Same API on both OSes | rumps (Mac only) |
| Notifications | pystray's own notifications on Windows (osascript on the Mac for development) | Shown by the tray icon itself, so no extra library or app registration is needed | desktop-notifier, plyer, win10toast |
| Sound | winsound on Windows, afplay on Mac, behind one function | Avoids flaky third-party audio packages | playsound, simpleaudio |
| Storage | Settings and event log in the per-user app data folder via platformdirs | Correct location on both OSes | Files next to the .exe |
| Packaging | PyInstaller `--onedir`, zipped or wrapped in a simple installer, built on a GitHub Actions windows-latest runner from milestone 2 | `--onefile` unpacks to a temp folder on every launch and is more often flagged by Defender and SmartScreen; PyInstaller cannot cross-compile | `--onefile`; building by hand on her laptop |

**Architecture.** Three layers, so only one small module differs by OS:

1. **Detection core** (pure Python): takes a frame and its timestamp, returns per-frame contact plus landmarks, and runs the episode state machine. No camera, UI or OS code, so it can be tested on recorded clips and on logged landmark streams.
2. **Platform layer:** camera open and release, sound, notification, launch at startup, meeting-app detection. Branches on `sys.platform`.
3. **App shell:** tray icon, settings, pause, event log. The camera loop runs on a background thread because macOS requires the tray on the main thread; this layout also works on Windows.

## Detection approach

An alert fires when a hand touches hair anywhere it hangs, from the scalp to long hair below the jaw, and holds for longer than a dwell time. Any hair contact counts: touching, stroking, twirling or gripping, including tucking hair behind an ear. There is no grip or gesture check.

**Crown is out of scope for v1.** A front-facing webcam loses a hand once it is behind the head: in the Mac rehearsal (2026-10-07), the hand was found in 1–25% of frames for crown clips, against 92–100% for every other position. The detection does not need to be perfect, so missing the occasional episode at the crown is accepted. If that changes, the fallback is a raised-arm signal from pose landmarks (elbow and wrist up beside the head stay visible when the hand does not).

- **Stage 1, head zone (baseline):** a zone around the head, extending down over the shoulders to cover long hair, built from face or pose landmarks. How well it holds up in poor light is measured in milestones 1 and 3, not assumed.
- **Stage 2, hair mask (milestone 4, if needed):** contact is checked against where her hair actually is, so a hand on the cheek or chin does not count.

**Per-frame pipeline**

1. Capture frames at 5–10 fps to keep CPU use light.
2. Find the face or pose landmarks. If no head is found (looking away, poor light), report "not tracking".
3. Run HandLandmarker on every frame, in VIDEO mode so it tracks from frame to frame rather than re-detecting.
4. If no hand overlaps the check region, there is no contact this frame. The check region is the head zone plus a margin, sized from her recorded motions so it covers long hair below the jaw; it is not simply the upper part of the frame.
5. Otherwise check contact using all 21 hand landmarks or the hand's outline, not only fingertips, since a grip may show knuckles or the back of the hand rather than fingertips. Which landmarks give the best signal is decided from her recorded motions. In stage 2, contact means the hand overlaps the hair mask (see below) and not face skin.
6. Feed per-frame contact into the episode state machine.

**Episodes.** Alerts and the event log work on episodes, not frames. All timings are in seconds, not frames, since fps varies.

| State | Enters when | Leaves when |
| --- | --- | --- |
| Idle | Start, resume, or an episode ends | Contact begins → Candidate |
| Candidate | Contact begins | Contact holds for the dwell time (starting point 0.5 s) → Active, and the alert fires. Contact lost → Idle |
| Active | Dwell time passed | No contact for the release time (starting point 3 s) → Idle, and the episode is logged |

- **Grace window:** a gap in contact or in hand tracking shorter than the grace window (starting point 1 s) does not end a Candidate or Active episode, because a hand in hair is often briefly lost by the tracker.
- **One alert per episode.** An optional reminder alert fires if an episode stays Active past a long threshold (starting point 60 s). Off by default.
- **Reset:** pause, camera loss, resume and a switch between stage 1 and stage 2 all clear episode state and return to Idle. An episode cut short this way is logged as interrupted.
- **Log entry:** start time, duration, whether it alerted, and how it ended (released, interrupted).

**Hair mask (milestone 4).** A hand on hair hides the hair it touches, so the current frame's segmentation labels those pixels as hand or skin, not hair. Hands Down therefore keeps a rolling hair mask from recent clean frames and tests the hand against that, dilated by a contact margin. The rolling mask follows these rules:

- **Clean frames only.** A frame refreshes the mask only if the hand tracker reports no hand anywhere in the frame, the face is found with high confidence, and the previous several frames (starting point 1 s) were also clean. "No hand detected" alone is not enough, since a missed or hidden hand is exactly the hard case.
- **Anchored to the face.** The mask is stored relative to face landmarks and moved with them, so small head movements carry the mask along.
- **Invalidation.** The mask is thrown away when the head moves or turns more than a threshold since it was captured, or when it is older than a maximum age (starting point 30 s).
- **No valid mask means stage 1.** At startup, after invalidation, or if a hand is already in her hair when Hands Down starts, detection uses the stage 1 head zone with a longer dwell time until a clean mask exists.
- **Unreliable masks.** If the mask is too small, flickers between refreshes, or hair is close to the background colour, fall back to stage 1 in the same way.

Segmentation runs only on clean frames (to refresh the mask, at a low rate) and when a hand overlaps the check region (to read face skin), so it never runs on every frame.

**Known false positives to tune against:** chin or cheek resting on hand, adjusting glasses, drinking, phone held to ear. In stage 1 these rely on dwell time alone. In stage 2 the hair and face-skin labels are the main filter, backed by dwell time. Video is 2D, so a hand on the cheek with long hair hanging behind it will still overlap the hair mask; some false positives here are expected and are measured, not assumed away.

## Camera sharing and calls

Whether Hands Down and a meeting app can use the camera at the same time on her laptop is unknown, and milestone 1 settles it before any auto-pause logic is built.

- **What is known:** Windows supports shared, read-only camera access through the WinRT `MediaCapture` API, and Windows 11 adds a multi-app camera setting. OpenCV's DirectShow and Media Foundation backends do not use shared mode, so with OpenCV the first app to open the camera may lock out the second. macOS lets apps share the camera, so none of this shows up during development.
- **What milestone 1 tests:** both launch orders (Hands Down then Teams, Teams then Hands Down) with OpenCV on her laptop and webcam, and whether shared capture through WinRT works on her machine.
- **Outcomes:**
  - If Teams and Hands Down coexist with OpenCV, no special handling is needed beyond camera-busy retries.
  - If they coexist only with shared capture, the Windows camera module in the platform layer switches from OpenCV to WinRT `MediaCapture` (via the `winrt` Python packages). The detection core is unaffected.
  - If they cannot coexist, Hands Down must release the camera before a call, using the measures below.
- **Release measures (if needed):** "Pause for call" is the first item in the tray menu, and a global hotkey pauses and resumes. Automatic meeting detection is added only once a reliable signal is found. A running Teams or Zoom process does not mean a call is in progress, and the Windows camera-usage registry entries (`CapabilityAccessManager\ConsentStore\webcam`) only record an app that already has the camera, not one that failed to get it.
- **Camera busy:** if another app already holds the camera, Hands Down shows "camera busy", retries quietly in the background, and never blocks the call.

## Alerts and app shell

Alerts are gentle and configurable; the app stays out of the way and is discreet if her screen is shared.

- **Alert types:** soft chime (default) and native notification, in any combination. Windows Focus Assist / Do Not Disturb silently suppresses notifications, which is why the chime is the default.
- **Tray icon:** a thin ring. States: watching, paused, not tracking, camera busy.
- **Tray menu:** pause for call, pause for 15 min / 1 hour / until resumed, "that wasn't me" (marks the last alert as false), settings, open log, quit.
- **Settings:** zone margin, dwell time, grace window, release time, reminder alert, alert types, alert sound and volume, pause while the screen is locked, pause hotkey, start with Windows.
- **Event log:** one entry per episode (see Episodes), stored locally, so she can spot patterns by time of day or task.
- **Naming:** nothing user-visible names the habit.

## Cross-platform build and packaging

Develop on macOS, but run on Windows from milestone 1 and ship a CI-built package from milestone 2, so platform problems surface before tuning.

- **Model files:** HandLandmarker and FaceLandmarker ship as `.task` bundles and the segmenter as `.tflite`. All are listed as PyInstaller data and loaded through a resource-path helper that works from source and from the frozen build. This is the most likely Mac-works, Windows-crashes bug, and milestone 2 checks it.
- **Paths:** pathlib everywhere; no hard-coded separators.
- **Mac camera permission:** Terminal or the IDE needs camera access in development.
- **CI:** a GitHub Actions workflow on windows-latest installs pinned requirements, runs detection-core tests, builds the package and uploads it as an artifact.
- **Code signing:** the build is unsigned in v1, so she should expect a SmartScreen prompt on first launch.
- **Start with Windows:** the packaged build adds itself to the per-user `Run` registry key, toggled from settings. (A Startup-folder shortcut would need pywin32 to create the `.lnk`.)
- **Windows-only checks on her laptop:** camera coexistence with Teams (milestone 1), notification appearance and app name, startup behaviour, lighting and camera angle.

## Privacy and testing

No video leaves the laptop, and in normal use none touches disk; detection quality is measured against agreed criteria, not judged by feel.

**Privacy**

- All processing is local; no network calls at runtime.
- In normal use, frames are held in memory only and discarded after analysis. The log stores episodes, never images.
- Recording test clips is a separate developer mode, started on purpose; clips stay on the machine they were recorded on.
- The ordinary-work trial records no video. Hands Down logs only its own outputs: alerts, tracking state, her "that wasn't me" marks, and landmark summaries.
- The webcam light will be on while Hands Down watches; pausing releases the camera.

**Acceptance criteria**

Measured in milestone 3, and again for stage 2 if milestone 4 goes ahead. Starting targets, to be agreed with her before the trial:

| Metric | Measured on | Starting target |
| --- | --- | --- |
| False alerts per hour of ordinary work | Ordinary-work trial ("that wasn't me" marks) | At most 1 per hour |
| Episode recall | Held-out true-positive clips | At least 80% of episodes alert |
| Alert latency (contact begins → alert) | True-positive clips | Under 1.5 s on average |
| Time not tracking | Ordinary-work trial | Under 10% of watched time |

False alerts per hour is the metric that decides whether she keeps Hands Down running, so it takes priority when targets conflict.

**Testing**

- **Hand visibility (milestone 1):** record her real hand-to-hair motions in her real seating position and check that HandLandmarker finds the hand. MediaPipe is weakest when the hand is half hidden in hair, made into a fist, seen from the back, pressed against the face or at the top edge of the frame, and laptop webcams often crop the crown.
- **Clip harness:** short labelled videos run through the detection core and scored against the acceptance criteria, so threshold changes and stage 1 vs stage 2 can be compared.
  - True positives: touching at the scalp, at the crown, beside the face, and on long hair below the jaw; ear tuck.
  - False positives: chin rest, cheek rest, glasses, drinking, phone to ear.
  - Clips are recorded on her laptop as well as the development Mac, since lighting and camera differ.
  - Some clips are set aside before tuning starts and used only for evaluation. With one person the held-out set is small, but tuning and scoring on the same clips would overstate quality.
- **Unit tests:** zone and mask geometry, mask validity rules (clean-frame streak, face anchoring, invalidation, maximum age), episode state transitions including grace window and reset, settings load and save.
- **Manual:** live webcam on Mac during development; final tuning on her Windows laptop in her real lighting and seating position.

## Open questions for the reviewer

- [ ] Do the starting acceptance targets match what she would tolerate day to day, or should they be set with her before milestone 3?
- [ ] If milestone 1 shows that Hands Down and Teams cannot share the camera, is a manual "pause for call" acceptable for v1, or is automatic meeting detection a must-have?
- [ ] Are the starting timings (0.5 s dwell, 1 s grace, 3 s release) reasonable, given how her episodes actually unfold?
- [ ] Is the "that wasn't me" tray mark enough to measure false alerts, or does she also need a way to flag missed episodes?
