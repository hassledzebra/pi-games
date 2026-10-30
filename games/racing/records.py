"""Time-trial records (best lap + ghost) in ~/.pi-rush/records.json."""
import json
import os

PATH = os.path.join(os.path.expanduser("~"), ".pi-rush", "records.json")
_data = None


def load():
    global _data
    if _data is None:
        try:
            with open(PATH) as f:
                _data = json.load(f)
        except (OSError, ValueError):
            _data = {}
    return _data


def get(track_name):
    return load().get(track_name)


def save(track_name, lap_frames, racer_name, ghost):
    """ghost: list of (x, y, heading, alt) per frame of the lap."""
    data = load()
    best = data.get(track_name)
    if best and best["best_lap"] <= lap_frames:
        return False
    data[track_name] = {"best_lap": lap_frames, "racer": racer_name,
                        "ghost": [[round(x), round(y), round(h), round(a)] for (x, y, h, a) in ghost]}
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w") as f:
            json.dump(data, f)
    except OSError:
        pass
    return True
