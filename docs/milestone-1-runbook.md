# Milestone 1 runbook

Everything below runs on her Windows 11 laptop, at her usual desk, in her usual lighting.
Allow about an hour: 10 minutes setup, 15 minutes for the Teams test, 30 minutes of recording.

## 1. Setup (once)

1. Install Python 3.12 from python.org. On the first installer screen, tick **Add python.exe to PATH**.
2. Get the code. Either install Git for Windows and run `git clone https://github.com/joshuaknipe/hands-down.git`
   (sign in to GitHub when asked; the repo is private), or on the Mac run
   `git archive --format=zip -o hands-down.zip HEAD`, copy `hands-down.zip` over and unzip it.
3. In a terminal in the project folder:

   ```
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. Check Settings > Privacy & security > Camera: **Camera access** and **Let desktop apps access your camera** are on.
5. Close Teams and anything else that might be using the camera.

## 2. Probe the camera

```
python -m feasibility probe
```

Expect a line each for `dshow` and `msmf`, at least one saying it opened at 10+ fps.
If both fail, or the laptop has an external webcam too, try `--camera 1`, and add the same
`--camera` option to every command below.

## 3. Teams coexistence test

Have Teams open and signed in, but not in a meeting.

```
python -m feasibility coexist
```

Follow the prompts. Each backend is tested twice: once with Hands Down opening the camera first, once
with Teams first. When asked, start a "Meet now" meeting with the camera on, and answer honestly
whether her own video shows in Teams. Leave each meeting when told to.

The last line is the conclusion. It is one of:

- **OpenCV works alongside Teams** — no special camera handling is needed.
- **Only Windows shared capture works** — Hands Down's Windows camera code will use WinRT instead of OpenCV.
- **No backend worked** — Hands Down will need "pause for call".

If a backend gets stuck, press Ctrl+C, then rerun with the remaining backends only, for example
`python -m feasibility coexist --backends msmf,winrt_shared`.

## 4. Record clips

She sits as she normally works. Run:

```
python -m feasibility record
```

A window opens showing the camera. **Click the window first** so it receives key presses.
The top of the window says which position to record, what to do and which clip she is on.
The clips measure whether the camera can see her hand while it is in each position, so the
hand must be in position for the **whole** clip. For each clip:

1. Put one hand in the position shown, and keep the other hand near the **Space** bar.
2. Press **Space** with the other hand.
3. Keep the first hand there for 5–10 seconds, doing what it naturally does there: touching,
   twirling, stroking, gripping. Keep it moving rather than frozen.
4. Press **Space** again with the other hand, then move the first hand away.

After the last clip for a position, the window moves on to the next one by itself.

- **N** / **P** skip to the next or previous position (for example to come back to one later).
- **Q** quits. Running `record` again resumes at the first position that still needs clips.
- To redo one position only: `python -m feasibility record --label hair_crown`.

The green dots on her hand show tracking is working; they are not saved. A red dot in the
bottom-right corner means a clip is recording.

It asks for 4 clips of each hair position (the 4th is set aside for later evaluation) and 2 of
each other position (those are for later milestones). The positions, in order:

| Label | Hand position |
| --- | --- |
| `hair_scalp` | fingers in the hair on top or at the front of the head |
| `hair_crown` | fingers in the hair at the back or crown |
| `hair_side` | fingers in the hair beside the face or at the temple |
| `hair_long` | fingers in long hair below the jaw or over the shoulder |
| `ear_tuck` | tucking hair behind an ear |
| `chin_rest` | chin resting on the hand |
| `cheek_rest` | cheek resting on the hand |
| `glasses` | adjusting glasses |
| `drinking` | drinking from a cup or bottle |
| `phone` | phone held to the ear |

Clips are saved in the `clips` folder on this laptop only. They are never uploaded and git
ignores them. She can watch or delete any clip at any time; delete a clip's `.mp4` and `.json`
together.

## 5. Analyse

```
python -m feasibility analyse
```

The table shows, per clip, the share of frames with a hand found (`hand`) and a face found
(`face`), and the longest stretch with no hand (`gap s`). The verdict line is:

- **GO** — at least 80% of hair clips had a hand found in at least 80% of frames.
- **NO-GO** — fewer did. Look at which labels fail and at the `face` column: a low face rate
  usually means the head is partly out of frame. Try raising or tilting the laptop screen,
  delete the clips, and record again before giving up.
- **INCOMPLETE** — some hair labels have fewer than 3 clips.

"Weak spots" lists labels where most clips failed; expect `hair_crown` here if the webcam crops
the top of her head.

## 6. Bring back the results

Copy the two newest files from the `reports` folder (`coexist-….json` and `analyse-….json`).
They contain numbers and labels only, no images. Record the two conclusions under milestone 1
in `plan.md`.

## 7. Afterwards

Keep the `clips` folder on her laptop for milestone 3, or delete it whenever she wants.
