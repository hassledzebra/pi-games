import argparse
import os
import sys
import time

from engine.app import App, on_pi

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def tuner_loop(device):
    """Console pitch test: prints the detected note until Ctrl-C. Step one of bringing up the rig."""
    from .pitch import AudioInput, PitchTracker, midi_to_freq, note_name
    if device is None:
        device = AudioInput.pick_device()
    inp = AudioInput(device)
    tr = PitchTracker()
    print("Listening on: %s   (Ctrl-C to stop)" % inp.name)
    try:
        while True:
            for samples, t_end in inp.poll():
                tr.feed(samples, t_end)
            db = tr.levels[-1] if tr.levels else -90
            if tr.current is None:
                line = "  --        %6.1f dB" % db
            else:
                cents = (tr.current - round(tr.current)) * 100
                line = "  %-4s %7.1f Hz %+4d cents  %6.1f dB" % (note_name(tr.current), midi_to_freq(tr.current), cents, db)
            sys.stdout.write("\r" + line + "   ")
            sys.stdout.flush()
            time.sleep(0.03)
    except KeyboardInterrupt:
        print()
    finally:
        inp.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pi Strum - guitar trainer")
    ap.add_argument("--song", help="a .mid file or song folder to put at the top of the list")
    ap.add_argument("--songs", default=os.path.join(ROOT, "songs"), help="song folder (default: songs/)")
    ap.add_argument("--device", type=int, help="audio input device index (see --list-devices)")
    ap.add_argument("--list-devices", action="store_true", help="print audio input devices and exit")
    ap.add_argument("--tuner", action="store_true", help="console pitch test, no window")
    ap.add_argument("--no-input", action="store_true", help="don't open an audio input")
    ap.add_argument("--demo", action="store_true", help="auto-play songs perfectly (shows the UI)")
    ap.add_argument("--latency", type=float, default=40.0, help="input latency compensation in ms")
    ap.add_argument("--render", action="store_true", help="(re)render backing tracks for all songs and exit")
    ap.add_argument("--unlock-all", action="store_true", help="open every stage of the learning path (remembered)")
    ap.add_argument("--start", metavar="ID", help="open the path on this exercise, e.g. 4-3")
    ap.add_argument("--lock", action="store_true", help="stages unlock by earning stars again (remembered)")
    ap.add_argument("--speed", type=int, default=100, choices=(50, 60, 70, 80, 90, 100), help="start at this practice speed (%%)")
    ap.add_argument("--fullscreen", dest="fullscreen", action="store_true", help="default on a Raspberry Pi")
    ap.add_argument("--windowed", dest="fullscreen", action="store_false", help="default elsewhere")
    ap.add_argument("--mute", action="store_true", help="no sound output")
    ap.add_argument("--fps", action="store_true", help="show the frame rate (toggle with F3)")
    ap.set_defaults(fullscreen=None)
    args = ap.parse_args(argv)

    if args.list_devices:
        from .pitch import AudioInput
        print("\n".join(AudioInput.list_devices()) or "no input devices")
        return
    if args.tuner:
        tuner_loop(args.device)
        return
    if args.render:
        from . import backing, curriculum
        from .song import find_songs, load_song
        paths = list(curriculum.write_all(args.songs).values()) + find_songs(args.songs)
        for p in paths:
            s = load_song(p)
            custom = os.path.splitext(s.midi_path)[0] + ".arranged.wav"
            if os.path.exists(custom):                  # a jam track was installed over the arrangement
                print("%-30s %s" % (s.title, "(custom backing kept)"))
                continue
            out = backing.ensure_backing(s, force=True)
            print("%-30s %s" % (s.title, os.path.basename(out) if out else "(no accompaniment)"))
        return

    import pygame  # noqa: F401
    from engine.sfx import Sfx
    from .scenes import HEIGHT, WIDTH, Ear, TitleScene

    app = App("Pi Strum", (WIDTH, HEIGHT), fullscreen=on_pi() if args.fullscreen is None else args.fullscreen)
    if not args.mute and pygame.mixer.get_init():           # the engine opens 22 kHz mono; music wants stereo 44.1 kHz
        pygame.mixer.quit()
        try:
            pygame.mixer.init(44100, -16, 2, 1024)
        except pygame.error:
            pygame.mixer.init(22050, -16, 1, 512)
    app.show_fps = args.fps
    app.settings["songs_dir"] = args.songs
    app.settings["song"] = os.path.abspath(args.song) if args.song else None
    app.settings["demo"] = args.demo
    app.settings["latency"] = args.latency / 1000.0
    app.settings["metronome"] = True
    app.settings["speed"] = args.speed / 100.0
    app.settings["start"] = args.start
    from . import curriculum
    from .progress import Progress
    app.settings["paths"] = curriculum.write_all(args.songs)
    app.settings["progress"] = Progress(args.songs, unlock_all=True if args.unlock_all else False if args.lock else None)
    app.sfx = Sfx(enabled=not args.mute)
    app.sfx.synth("hit", 0.06, lambda t, k: __import__("math").sin(t * 2 * 3.14159 * 880) * (1 - k), 0.25)
    app.sfx.synth("miss", 0.08, lambda t, k: __import__("math").sin(t * 2 * 3.14159 * 160) * (1 - k), 0.25)
    ear = Ear(device=args.device, enabled=not args.no_input)
    app.settings["ear"] = ear
    try:
        app.run(TitleScene(app))
    finally:
        ear.close()
