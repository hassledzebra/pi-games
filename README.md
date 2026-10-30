# Pi Brawl

An original 2D versus fighting game in the Street Fighter style, built to run natively on a
**Raspberry Pi 3 / Zero 2 W** (and anything faster) with **Python 3 + pygame-ce**.

- 2 players on one keyboard, or with USB/Bluetooth gamepads, or 1 player vs the CPU (3 levels)
- Best of 3 rounds, a 99-second timer, health bars, blocking (high/low), jumps, crouches,
  knockdowns, hit-stop, combos, and special moves done with stick motions
- 2 fighters with their own move sets: **KAZE** (fast, chargeable orb, 3-hit rising kick) and
  **BRAKK** (heavy, rock pillars that must be blocked low, charging ram with a headbutt follow-up)
- A crowd behind the fence that cheers, jumps and throws confetti, a silver SUV parked at the
  side and an orange cat on its roof that ducks on big hits
- No asset files: fighters, stage, crowd and sounds are all generated in code
- Attract mode: the title screen starts a CPU-vs-CPU demo after 20 s idle (good for an arcade cabinet)

## Controls

|                  | Player 1 | Player 2          |
|------------------|----------|-------------------|
| Move/jump/crouch | W A S D  | Arrow keys        |
| Punch (P)        | F        | K or Numpad 1     |
| Kick (K)         | G        | L or Numpad 2     |
| Pause / start    | Esc      | Enter             |

Gamepads: the first pad plugged in goes to player 1, the second to player 2.
Use the D-pad or left stick, **A/X = Punch**, **B/Y = Kick**, **Start** = pause.
In VS CPU mode, player 1 can use any keyboard keys or any pad.

**Blocking:** hold *back*. Hold *down-back* to block sweeps and Brakk's Quake Wave.
Jump attacks have to be blocked standing.

**Special moves** (written for a fighter facing right; flip left/right when facing left):

| Fighter | Move         | Input            |
|---------|--------------|------------------|
| KAZE    | Tempest Orb  | Down, Down-Forward, Forward + P. Keep P held to charge: 3 hits instead of 2 |
| KAZE    | Cyclone Kick | Forward, Down, Down-Forward + K (invincible start, anti-air, 3 hits, the axe kick lands on crouchers) |
| BRAKK   | Earthsplitter| Down, Down-Forward, Forward + P (rock pillars, 2 hits, must be blocked low) |
| BRAKK   | Ram Charge   | Down, Down-Back, Back + K (when it hits, Brakk follows up with a headbutt) |

Combo: land a Punch, then do a special motion straight away. The special cancels the
Punch's recovery.

Other keys: **F11** toggles fullscreen and **F3** shows FPS.

## Develop and test on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py              # windowed on Windows
.\.venv\Scripts\python main.py --demo       # watch CPU vs CPU
.\.venv\Scripts\python tests\test_game.py   # headless checks + screenshots in tests\out\
```

Options: `--fullscreen`, `--windowed`, `--demo`, `--mute`, `--fps`, `--level 0|1|2`.

## Deploy to the Raspberry Pi

**1. Prepare the Pi.** Flash **Raspberry Pi OS (64-bit) Bookworm** with Raspberry Pi Imager.
- On a **Zero 2 W (512 MB)**, use the **Lite** image and run the game from the console. That's the fastest option.
- On a **Pi 3**, Desktop works too.

In Imager's settings, set a username/password and enable SSH. The examples below assume the
host name `raspberrypi.local` and the user `pi`; change them to match your setup.

**2. Copy the game from this PC** (Windows 11 has `ssh`/`scp` built in):

```powershell
.\deploy\deploy.ps1 -Target pi@raspberrypi.local
```

From a Mac or Linux machine, use `./deploy/deploy.sh pi@raspberrypi.local`. If the Wi-Fi blocks
IPv4 between devices, force IPv6 with `SSH_OPTS=-6 ./deploy/deploy.sh ...`.

(Or copy the folder over on a USB stick. You need `main.py`, `requirements.txt`, `engine/`, `games/` and `deploy/`.)

**3. Install it on the Pi** (one time):

```sh
cd ~/pi-brawl
./deploy/install_pi.sh
```

The script creates `.venv` and installs `pygame-ce` from PyPI. If there's no pygame-ce wheel
for that Pi, it falls back to Raspberry Pi OS's own `python3-pygame` package via `apt`. That
package is plain pygame 2.x. The game avoids pygame-ce-only APIs so it should run there too,
but so far it has only been tested with pygame-ce.

**4. Run it:**

```sh
cd ~/pi-brawl
.venv/bin/python main.py                          # from the desktop
SDL_VIDEODRIVER=kmsdrm .venv/bin/python main.py   # from the console / Lite (no desktop)
```

On a Pi the game starts fullscreen automatically. Plug in USB pads before or after starting.
Pair Bluetooth pads with `bluetoothctl` first.

To get **Pi Brawl and Pi Rush icons on the desktop** that start the games with a double-click, run
`./deploy/desktop_shortcut.sh` once. It draws the icons with the games' own sprites
(`deploy/make_icon.py`, `deploy/make_icon_rush.py`).

**5. Optional arcade mode** (boots straight into the game on HDMI):

```sh
./deploy/autostart.sh
sudo raspi-config   # System Options -> Boot / Auto Login -> Console Autologin
sudo reboot
```

To leave the game, choose **QUIT** on the title screen, or press Esc during a fight and choose **QUIT**. That drops you to the console.
To undo autostart, delete the `pi-brawl autostart` block from `~/.bash_profile`.

### Pi performance notes

- The game draws at **384×216** and SDL scales it on the GPU to the HDMI resolution
  (exactly 5× on 1080p). Drawing that few pixels is what makes software 2D fast enough on a Cortex-A53.
- Logic is **frame-locked at 60 fps**, like arcade fighting games. If the Pi can't keep up, the game
  slows down slightly rather than skipping input frames, so the frame data stays exact.
- Measured on a Pi 3B+ on the real screen (`PI_TIMING=1 .venv/bin/python racing.py --demo` logs
  the real frame times to the terminal): Pi Brawl spends about 7 ms per frame on update and draw,
  Pi Rush about 7–10 ms in split screen at full detail (the ground drawn one strip per screen row,
  far strips averaged), with vsync absorbing the rest of the 16.7 ms. The headless tests report
  higher totals because the dummy video driver scales the frame in software. On the dev PC both
  games take under 1 ms. Run with `--fps` to check.
- Pi Rush watches its own frame time: if its update and draw work averages over 11 ms for a second
  it drops to a lower detail level (17 ground strips, ground of each split view redrawn every other
  frame, CPU karts stepped at 30 Hz; then 7 strips). `tests/profile_racing.py [frames] [level] [res]`
  prints the per-stage timings, optionally at a forced level 0, 1 or 2 and ground resolution 1 or 0.5.
- If it's slow:
  - Run from the console (`kmsdrm`) instead of the desktop.
  - Use the Lite OS on the Zero 2 W.
  - Set the HDMI output to 1280×720 or 1920×1080 at 60 Hz.

## Pi Rush - split-screen kart racer

An original cartoon kart racer in the same repo, drawn with a mode-7 style rotating ground plane,
hills and jumps, and funny projectiles. Same engine, no asset files. It draws at **480×270**
(4× on a 1080p screen) so the far road keeps its shape in split screen; `WIDTH, HEIGHT` in
`games/racing/data.py` sets it, and 384×216 is the cheaper choice for a slower Pi.

```sh
.venv/bin/python racing.py                   # on the Pi (fullscreen); same options as main.py
.venv/bin/python racing.py --camera overhead # top-down map view instead of the chase camera
.venv/bin/python racing.py --demo            # CPU-only attract race
.venv/bin/python tests/test_racing.py        # headless checks + screenshots in tests/out/
```

Options: `--fullscreen`, `--windowed`, `--demo`, `--mute`, `--fps`, `--level 0|1|2`,
`--camera chase|overhead`.

- **Modes:** 2P Split Screen (two humans plus four CPU racers, stacked views), Quick Race (pick a
  track and laps), Grand Prix (four tracks, points, podium), Time Trial (single view, ghost of
  your best lap, records kept in `~/.pi-rush/records.json`). Every menu has **QUIT**.
- **Racers:** MITZI the cat (kart), GIZMO the robot (buggy), WADDLE the penguin (mower), CHOMP the
  dino (hover-boat), HOPPER the frog (rocket trike), ZORB the alien (saucer). Each has its own
  speed, acceleration, handling and weight.
- **Tracks:** Harbor Loop, Cinder Pass (lava, narrow S-bends), Frostbite Ridge (ice), Neon Rooftops
  (boost pads on bridges), Orchard Oval (practice). All have hills, dips and jump crests.
- **Driving:** tap brake while steering at speed to **drift**; hold the drift and release for a
  boost. Boost pads and slipstreaming behind another kart also speed you up.
- **Items** from the `?` crates (racers further back get the better ones):

| Item | What it does |
|---|---|
| Banana | dropped behind; whoever drives over it spins out |
| Rubber Chicken | squawks ahead and bonks the first kart it meets |
| Cream Pie | thrown ahead; the victim's half of the screen gets creamed |
| Bubble Gum | dropped behind; sticks whoever drives over it |
| Water Balloon | lobbed; the splash soaks everyone near |
| Hot Pepper | big speed boost with flames out the back |
| Bubble Shield | absorbs the next hit |
| Pogo Spring | big jump that clears hazards and small walls |
| Magnet | pulls crates and dropped items to you |

| Action | Player 1 | Player 2 | Gamepad |
|---|---|---|---|
| Steer | A / D | Left / Right | D-pad or stick |
| Gas | F | K | A / X |
| Brake, reverse, drift | G | L | B / Y |
| Use item | W | Up | D-pad up |
| Throw item backwards | S + W | Down + Up | down + up |
| Look behind | S | Down | D-pad down |
| Pause, confirm | Esc | Enter | Start |

## Pi Strum - guitar trainer

A Yousician-style trainer in the same repo: plug a guitar into a USB audio interface, the Pi
listens, shows the song as a scrolling tab and scores every note for pitch and timing.

```sh
.venv/bin/python guitar.py --list-devices   # find the USB interface
.venv/bin/python guitar.py --tuner          # console pitch test: play a note, see E2 82.4 Hz +3 cents
.venv/bin/python guitar.py                  # the trainer
.venv/bin/python guitar.py --demo           # watch it play itself (no guitar needed)
```

Options: `--device N` (input device index), `--latency MS` (input delay compensation, default 40),
`--song FILE.mid`, `--songs DIR`, `--render` (re-render backing tracks), `--no-input`,
plus the usual `--windowed`, `--fullscreen`, `--mute`, `--fps`.

Keys: **Left/Right** stage, **Up/Down** exercise, **Enter** play, **-/+** practice speed (50-100%),
**Space** pause, **R** restart, **M** metronome, **Esc** back.

**The learning path** has nine stages and 35 exercises, each with a one-line tip. Chord stages
show a chord diagram and strum arrows; the band plays the tune while you strum.

| Stage | What you learn | Exercises |
|---|---|---|
| 1 Open strings | clean picking on the beat | Open Strings, String Pairs, String Skips |
| 2 First frets | one finger per fret | First Frets, Chromatic Warm-up, Spider Walk |
| 3 First chords | Em, Am, D, G, C and clean changes | Em and Am; D and G; G, C and D Changes; Em Am D G |
| 4 First tunes | melodies on the top strings | Mary Had a Little Lamb, Twinkle Twinkle, Ode to Joy, Jingle Bells, Happy Birthday |
| 5 Strumming | patterns and progressions | Down Down-Up, The Pop Pattern, 12-Bar Blues, Waltz Strum |
| 6 Scales | positions, even notes, eighth notes | C Major, G Major, E Minor Pentatonic, A Minor Pentatonic Box |
| 7 Chord songs | strum while the band plays the tune | Twinkle Twinkle, Ode to Joy, Jingle Bells, Happy Birthday, Greensleeves, House of the Rising Sun |
| 8 Riffs and rhythm | low strings, drums, rests | Power Riff in E, Blues Shuffle in A, E Minor Groove |
| 9 Classics | longer, faster, higher frets | Greensleeves, Minuet in G, Fur Elise |

A stage unlocks when every exercise of the previous one has at least 2 stars at full speed
(`--unlock-all` opens everything and is remembered; `--lock` reverts). Slower practice speeds re-render the backing track at that tempo;
their stars are shown but don't unlock. Best results are kept in `songs/progress.json`.
All tunes are traditional or public domain; the drills and riffs are original. They are generated
into `songs/path/` on first start (`games/guitar/curriculum.py`), so edit that file to add exercises.

**Hardware:** any Pi (tested logic on a Pi 3B+, a Pi 4 is comfortable) plus a USB audio interface
with a 1/4-inch instrument input, e.g. Behringer UMC22 / UM2 or a Focusrite Scarlett Solo. They are
USB class-compliant, so no driver. Put the guitar on input 1 and headphones on the interface.

**Install on the Pi** (after `./deploy/install_pi.sh`): `./deploy/install_guitar.sh` adds
`libportaudio2` (audio capture), `fluidsynth` + `fluid-soundfont-gm` (backing tracks) and the Python
packages `numpy`, `mido`, `sounddevice`.

**Songs** live in `songs/`. Drop in any standard MIDI file: the track named guitar/lead/melody (or the
first melodic track) becomes the part to play, string/fret are chosen automatically, and every other
track is rendered into a backing WAV with FluidSynth (or a built-in synth if FluidSynth is missing).
A folder with `song.json` (`{"title", "artist", "midi", "track", "backing", "offset"}`) can point at
a hand-made backing track instead. Your own files show up in a "Your songs" stage that is always open.
If a MIDI track puts each string on its own channel (0 = low E, as Guitar Pro exports do), that fingering is used.

**How it works:** `games/guitar/pitch.py` runs the YIN pitch algorithm in numpy on 46 ms frames every
11.6 ms (about 3 cents accurate on guitar tones) and detects plucks from level jumps.
`scoring.py` counts a note as hit when the right pitch is heard and the pluck landed within 120 ms
before to 250 ms after the note start; repeated notes need separate plucks. For chords,
`chords.py` folds the spectrum of a 186 ms window into a 12-bin chroma and compares it with the
expected chord's template; a strum is hit when a pluck lands in its window and the chroma matches
the expected chord better than the other chords in the exercise.

**Backing tracks** are rendered from the exercise MIDI with the free GeneralUser GS soundfont
(downloaded into `soundfonts/` on first run) through the `tinysoundfont` package, or FluidSynth
if installed; a built-in synth is the last fallback. `games/guitar/curriculum.py` arranges drums,
bass and rhythm guitar per style. `tools/jam_track.py` (PC/Mac only, needs PyTorch) generates an AI
jam track with MusicGen and installs it as an exercise's backing.

**Open resources** the chord path follows: the University of Kansas *Guitar Chord Handbook*
(CC BY-NC) and *Chord Progression Handbook* (CC BY), and the Wikibooks *Guitar* book (CC BY-SA).
All tunes are traditional or public domain. `tests/test_guitar.py`
checks all of this headlessly and writes screenshots to `tests/out/`.

## Project layout

```
main.py                 entry point (Pi Brawl); racing.py = Pi Rush; guitar.py = Pi Strum
engine/                 shared, reusable for future games
  app.py                window (pygame.SCALED), 60 fps loop, scene switching
  input.py              keyboard + gamepad -> actions per player, VirtualInput for AI
  text.py               cached text rendering
  sfx.py                synthesised sound effects
games/fighter/
  data.py               poses, frame data, characters (add fighters here)
  fighter.py            state machine, physics, hit/hurt boxes, multi-hit and charge logic
  art.py                fighter, special-move and projectile drawing
  audience.py           the crowd, the SUV and the cat, and how they react to the fight
  ai.py                 CPU opponent (uses real stick motions)
  scenes.py             title, select, controls, fight, HUD
  sounds.py             sound definitions
games/racing/
  data.py               racers, vehicles, items, tracks (add racers and tracks here)
  world.py              track rendering, surface grid, height profile, pre-rotated ground copies
  kart.py               kart physics, drift, hills and jumps
  items.py              crates, projectiles and power-ups
  ai.py                 CPU drivers
  render.py             mode-7 chase view, overhead view, HUD, minimap
  scenes.py             title, select, race, podium, time trial, detail-level safety valve
  sounds.py, records.py sound definitions, time-trial records
tests/test_game.py      headless fighter tests and screenshots
tests/test_racing.py    headless racer tests and screenshots; profile_racing.py = per-stage timings
deploy/                 deploy.ps1 (Windows -> Pi), deploy.sh (Mac/Linux -> Pi), install_pi.sh,
                        autostart.sh, desktop_shortcut.sh + make_icon.py / make_icon_rush.py (launchers)
```

### Adding a fighter

In `games/fighter/data.py`:
1. Make a new `Character` with a `look` (colour dict), a drawing `style` from `art.DRAW`, stats,
   a `moves` dict (the same keys as the others) and a `specials` list. Signature moves can use
   `anim` keyframes, `hits`, `charge` and `followup`.
2. Append it to `ROSTER`. The select screen picks it up automatically.

You can reuse the existing poses or add new ones. A pose is just 11 joint positions.
