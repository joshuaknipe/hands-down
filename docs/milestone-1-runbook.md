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

She sits as she normally works. For each label, run the command, then for each clip:
get her hand into position first, press **Space**, do what her hand naturally does there for
5–10 seconds, press **Space** again. **Q** quits. The preview shows green dots when a hand is
found; that is for reassurance only and is not saved.

Record **4 clips for each of these** (the 4th of each is set aside for later evaluation):

| Label | Hand position |
| --- | --- |
| `hair_scalp` | fingers in the hair on top or at the front of the head |
| `hair_crown` | fingers in the hair at the back or crown |
| `hair_side` | fingers in the hair beside the face or at the temple |
| `hair_long` | fingers in long hair below the jaw or over the shoulder |
| `ear_tuck` | tucking hair behind an ear |

Record **2 clips for each of these** (they are for later milestones):

| Label | Hand position |
| --- | --- |
| `chin_rest` | chin resting on the hand |
| `cheek_rest` | cheek resting on the hand |
| `glasses` | adjusting glasses |
| `drinking` | drinking from a cup or bottle |
| `phone` | phone held to the ear |

Example:

```
python -m feasibility record --label hair_scalp
```

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
