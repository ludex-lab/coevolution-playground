"""Two-sided step records at an explicit env-trainer wire (stdlib method sketch).

Clean-room method sketch of arXiv 2611.08144 ("Detecting Silent Faults at the
Environment-Trainer Boundary in Reinforcement Learning", Gou & Lu). Nothing
here is taken from any upstream code base; the toy, the wire, the faults and
the numbers are all synthetic and independently authored.

Pieces:
  * CorridorEnv   - a tiny deterministic 1D corridor (float position).
  * Wire          - the only place where env and trainer meet; faults are
                    injected here and nowhere else.
  * Trainer loop  - a scripted, deterministic epsilon policy whose epsilon
                    shrinks per episode, so the logged returns form a
                    learning curve. It does not train anything.
  * StepRecord    - what each side recorded for one step.
  * compare_records - step-by-step, field-by-field comparison that reports
                    the first difference as env / episode / step / field.
  * gain_check    - outcome baseline: logged return gain vs a fixed threshold.

Float rule: recorded Python values are compared with exact equality. Each side
records the value it actually used (env: what it computed and sent; trainer:
what it received after the wire), so a float16 rounding on the wire shows up
as a changed recorded float. No tolerance is applied.
"""

import struct
import time
from collections import namedtuple

# ----------------------------------------------------------------------------
# Toy environment
# ----------------------------------------------------------------------------

START_X = 0.3
GOAL_X = 1.0
STEP_SIZE = 0.1
TIME_LIMIT = 25
GOAL_BONUS = 1.0
FALL_PENALTY = -1.0
DIST_COST = 0.05

FIELDS = ("step_id", "action", "observation", "reward", "terminated", "truncated")

StepRecord = namedtuple(
    "StepRecord",
    ["env_id", "episode_id", "step_id", "action", "observation", "reward",
     "terminated", "truncated"],
)

Difference = namedtuple(
    "Difference",
    ["env_id", "episode_id", "step_id", "field", "env_value", "trainer_value"],
)


class CorridorEnv:
    """1D corridor. Observation = (x, time_left_fraction).

    terminated: x reaches GOAL_X (bonus) or drops below 0.0 (penalty).
    truncated:  TIME_LIMIT env steps taken without termination.
    reward:     -DIST_COST * |GOAL_X - x| per step, plus bonus/penalty.
    """

    def __init__(self, env_id, record=True):
        self.env_id = env_id
        self.record = record
        self.records = []
        self.x = START_X
        self.t = 0
        self.episode_id = None

    def _obs(self):
        return (self.x, (TIME_LIMIT - self.t) / TIME_LIMIT)

    def reset(self, episode_id):
        self.episode_id = episode_id
        self.x = START_X
        self.t = 0
        obs = self._obs()
        if self.record:
            self.records.append(StepRecord(self.env_id, episode_id, 0, None,
                                           obs, 0.0, False, False))
        return {"env_id": self.env_id, "episode_id": episode_id, "step_id": 0,
                "observation": obs, "reward": 0.0,
                "terminated": False, "truncated": False}

    def step(self, msg):
        action = msg["action"]
        self.x = self.x + STEP_SIZE * action
        self.t += 1
        reward = -DIST_COST * abs(GOAL_X - self.x)
        terminated = False
        if self.x >= GOAL_X - 1e-9:
            terminated = True
            reward += GOAL_BONUS
        elif self.x < 0.0:
            terminated = True
            reward += FALL_PENALTY
        truncated = (not terminated) and self.t >= TIME_LIMIT
        obs = self._obs()
        if self.record:
            self.records.append(StepRecord(self.env_id, msg["episode_id"],
                                           msg["step_id"], action, obs, reward,
                                           terminated, truncated))
        return {"env_id": self.env_id, "episode_id": msg["episode_id"],
                "step_id": msg["step_id"], "observation": obs,
                "reward": reward, "terminated": terminated,
                "truncated": truncated}


# ----------------------------------------------------------------------------
# Wire and silent faults
# ----------------------------------------------------------------------------

def float16_round(value):
    """IEEE 754 binary16 round trip using stdlib struct format 'e'."""
    return struct.unpack("<e", struct.pack("<e", value))[0]


Fault = namedtuple("Fault", ["kind", "env_id", "episode_id", "step_id"])
# env_id / episode_id / step_id of None means "every". For "swap_end" the
# step_id is ignored: it fires on the step whose feedback ends that episode.

FAULT_KINDS = (
    "float16_obs",      # observation[0] rounded through binary16
    "float16_reward",   # reward rounded through binary16
    "stale_reward",     # reward replaced by the previous step's reward
    "swap_end",         # terminated <-> truncated swapped on the end step
    "skip_step",        # action never reaches env; feedback filled in
    "zero_action",      # action replaced by 0 before the env applies it
    "zero_reward",      # reward replaced by 0.0
)


def _hits(fault, env_id, episode_id, step_id):
    return ((fault.env_id is None or fault.env_id == env_id)
            and (fault.episode_id is None or fault.episode_id == episode_id)
            and (fault.step_id is None or fault.step_id == step_id))


class Wire:
    """Explicit in-process wire. Messages are plain dicts copied at the wire."""

    def __init__(self, envs, faults=()):
        self.envs = {e.env_id: e for e in envs}
        self.faults = list(faults)
        for f in self.faults:
            if f.kind not in FAULT_KINDS:
                raise ValueError("unknown fault kind: %r" % (f.kind,))
        self.last = {}  # env_id -> last feedback forwarded to the trainer

    def _active(self, kind, env_id, episode_id, step_id):
        for f in self.faults:
            if f.kind != kind:
                continue
            if kind == "swap_end":
                if _hits(f._replace(step_id=None), env_id, episode_id, step_id):
                    return True
            elif _hits(f, env_id, episode_id, step_id):
                return True
        return False

    def reset(self, env_id, episode_id):
        fb = dict(self.envs[env_id].reset(episode_id))
        self.last[env_id] = dict(fb)
        return fb

    def step(self, msg):
        msg = dict(msg)
        e, ep, s = msg["env_id"], msg["episode_id"], msg["step_id"]
        prev = self.last[e]
        if self._active("skip_step", e, ep, s):
            # The env never sees this step; the trainer gets a filled-in,
            # contiguous feedback built from the previous one.
            fb = dict(prev)
            fb["step_id"] = s
            fb["terminated"] = False
            fb["truncated"] = False
        else:
            if self._active("zero_action", e, ep, s):
                msg["action"] = 0
            fb = dict(self.envs[e].step(msg))
        if self._active("float16_obs", e, ep, s):
            obs = list(fb["observation"])
            obs[0] = float16_round(obs[0])
            fb["observation"] = tuple(obs)
        if self._active("float16_reward", e, ep, s):
            fb["reward"] = float16_round(fb["reward"])
        if self._active("stale_reward", e, ep, s):
            fb["reward"] = prev["reward"]
        if self._active("zero_reward", e, ep, s):
            fb["reward"] = 0.0
        if (fb["terminated"] or fb["truncated"]) and \
                self._active("swap_end", e, ep, s):
            fb["terminated"], fb["truncated"] = fb["truncated"], fb["terminated"]
        self.last[e] = dict(fb)
        return fb


# ----------------------------------------------------------------------------
# Scripted trainer-side loop
# ----------------------------------------------------------------------------

def _draw(env_id, episode_id, step_id):
    """Deterministic uniform draw in [0, 1) from a small integer hash."""
    h = (env_id * 73856093) ^ (episode_id * 19349663) ^ (step_id * 83492791)
    h = (h * 2654435761 + 12345) & 0xFFFFFFFF
    return h / 4294967296.0


def epsilon(episode_id):
    return max(0.05, 0.6 * (0.75 ** episode_id))


def policy(env_id, episode_id, step_id, observation):
    """Scripted policy: move right, except with probability epsilon."""
    return -1 if _draw(env_id, episode_id, step_id) < epsilon(episode_id) else 1


RunResult = namedtuple(
    "RunResult", ["env_records", "trainer_records", "returns", "curve"])


def run(n_envs=2, n_episodes=10, faults=(), record=True):
    """Run the toy. Returns env records, trainer records and logged returns.

    `returns[(env_id, episode_id)]` is the trainer-logged episode return;
    `curve[episode_id]` is the mean logged return across envs.
    """
    envs = [CorridorEnv(i, record=record) for i in range(n_envs)]
    wire = Wire(envs, faults)
    trainer_records = []
    returns = {}
    for ep in range(n_episodes):
        for env_id in range(n_envs):
            fb = wire.reset(env_id, ep)
            if record:
                trainer_records.append(StepRecord(
                    env_id, ep, fb["step_id"], None, fb["observation"],
                    fb["reward"], fb["terminated"], fb["truncated"]))
            total = 0.0
            step_id = 0
            obs = fb["observation"]
            while True:
                step_id += 1
                action = policy(env_id, ep, step_id, obs)
                fb = wire.step({"env_id": env_id, "episode_id": ep,
                                "step_id": step_id, "action": action})
                if record:
                    trainer_records.append(StepRecord(
                        env_id, ep, fb["step_id"], action, fb["observation"],
                        fb["reward"], fb["terminated"], fb["truncated"]))
                total += fb["reward"]
                obs = fb["observation"]
                if fb["terminated"] or fb["truncated"]:
                    break
                if step_id > 4 * TIME_LIMIT:  # guard; never reached here
                    break
            returns[(env_id, ep)] = total
    curve = [sum(returns[(e, ep)] for e in range(n_envs)) / n_envs
             for ep in range(n_episodes)]
    env_records = [r for e in envs for r in e.records]
    return RunResult(env_records, trainer_records, returns, curve)


# ----------------------------------------------------------------------------
# Step-record comparison (the check of the run)
# ----------------------------------------------------------------------------

MISSING = "<missing>"


def compare_records(env_records, trainer_records):
    """Compare both sides step by step, field by field.

    Records are keyed by (env_id, episode_id, step_id) and walked in
    (episode_id, step_id, env_id) order. Returns the first Difference, or None
    when every recorded field agrees. A step present on only one side is
    reported with field "step_id" and MISSING for the absent side.
    """
    env_map = {(r.env_id, r.episode_id, r.step_id): r for r in env_records}
    tr_map = {(r.env_id, r.episode_id, r.step_id): r for r in trainer_records}
    if len(env_map) != len(env_records) or len(tr_map) != len(trainer_records):
        raise ValueError("duplicate step key in a record")
    keys = sorted(set(env_map) | set(tr_map), key=lambda k: (k[1], k[2], k[0]))
    for key in keys:
        er, tr = env_map.get(key), tr_map.get(key)
        if er is None or tr is None:
            return Difference(key[0], key[1], key[2], "step_id",
                              MISSING if er is None else key[2],
                              MISSING if tr is None else key[2])
        for field in FIELDS[1:]:
            ev, tv = getattr(er, field), getattr(tr, field)
            if type(ev) is not type(tv) or ev != tv:
                return Difference(key[0], key[1], key[2], field, ev, tv)
    return None


def detect(result):
    """Report: 'detect' with the first difference, or 'agree'."""
    diff = compare_records(result.env_records, result.trainer_records)
    return ("detect", diff) if diff is not None else ("agree", None)


# ----------------------------------------------------------------------------
# Outcome baseline (the check of the outcome)
# ----------------------------------------------------------------------------

GAIN_WINDOW = 3
GAIN_THRESHOLD = 0.4


def gain(curve, window=GAIN_WINDOW):
    """Mean logged return over the last `window` episodes minus the first."""
    head = sum(curve[:window]) / window
    tail = sum(curve[-window:]) / window
    return tail - head


def gain_check(curve, threshold=GAIN_THRESHOLD):
    """Report 'detect' when the logged gain falls below the fixed threshold."""
    g = gain(curve)
    return ("detect" if g < threshold else "pass", g)


# ----------------------------------------------------------------------------
# Overhead measurement
# ----------------------------------------------------------------------------

def measure_overhead(repeats=20, n_envs=2, n_episodes=10, faults=()):
    """Wall time of baseline-only runs vs runs that also keep+compare records.

    Returns (baseline_seconds, ledger_seconds, ratio). Synthetic toy timing.
    """
    t0 = time.perf_counter()
    for _ in range(repeats):
        r = run(n_envs, n_episodes, faults, record=False)
        gain_check(r.curve)
    base = time.perf_counter() - t0
    t0 = time.perf_counter()
    for _ in range(repeats):
        r = run(n_envs, n_episodes, faults, record=True)
        gain_check(r.curve)
        detect(r)
    led = time.perf_counter() - t0
    return base, led, led / base
