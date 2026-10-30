"""Best results per exercise, kept in songs/progress.json."""
import json
import os

from .curriculum import STAGES

FILE = "progress.json"
STARS_TO_UNLOCK = 2         # on every exercise of the previous stage, at full speed


class Progress:
    def __init__(self, songs_dir, unlock_all=None):
        """unlock_all: True/False sets the persistent "everything open" switch, None keeps it."""
        self.path = os.path.join(songs_dir, FILE)
        self.best = {}
        try:
            with open(self.path) as f:
                self.best = json.load(f)
        except (OSError, ValueError):
            pass
        if unlock_all is not None:
            self.best["_unlock_all"] = bool(unlock_all)
            self._save()
        self.unlock_all = bool(self.best.get("_unlock_all", False))

    def _save(self):
        try:
            with open(self.path, "w") as f:
                json.dump(self.best, f, indent=1, sort_keys=True)
        except OSError:
            pass

    def record(self, ex_id, stars, accuracy, score, speed):
        """Keep the best run at full speed and the best run at any speed."""
        cur = self.best.setdefault(ex_id, {})
        for key, ok in (("full", speed >= 0.999), ("any", True)):
            if ok and (key not in cur or (stars, accuracy, score) > (cur[key]["stars"], cur[key]["accuracy"], cur[key]["score"])):
                cur[key] = {"stars": stars, "accuracy": round(accuracy, 3), "score": score, "speed": speed}
        self._save()

    def stars(self, ex_id, full=True):
        r = self.best.get(ex_id, {}).get("full" if full else "any")
        return r["stars"] if r else 0

    def stage_done(self, k):
        return all(self.stars(ex.id) >= STARS_TO_UNLOCK for ex in STAGES[k].exercises)

    def unlocked(self, k):
        return self.unlock_all or k == 0 or self.stage_done(k - 1)

    def first_open(self):
        """Index of the stage and exercise the player should work on next."""
        for k, st in enumerate(STAGES):
            if not self.unlocked(k):
                break
            for i, ex in enumerate(st.exercises):
                if self.stars(ex.id) < STARS_TO_UNLOCK:
                    return k, i
        return len(STAGES) - 1, 0
