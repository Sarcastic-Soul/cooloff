"""StreamingRiskGate: the core of the rolling_risk_gate decision pattern.

Feed it one Decider answer per sentence. It keeps a confidence-weighted moving level for each
signal and returns a state: green, amber or red.

  green  nothing happens
  amber  one signal is active: warn the person, do not block anything
  red    two signals from different groups are active: block the risky tool and ask a human
         (red is latched, it stays red until a human calls clear())

The gate has no model, network or Strands code in it. It only turns numbers into a state, so it can be
unit tested and reused with any stream of Decider answers (a call, a chat, a log, a support ticket).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

GREEN, AMBER, RED = "green", "amber", "red"


@dataclass(frozen=True)
class Signal:
    """One thing the gate watches.

    extract(answers) returns (value, confidence), both between 0 and 1. value is how strongly the
    signal showed up in this sentence. confidence is how sure Decider was, and scales how far one
    sentence can move the level (a shaky answer barely moves it).
    group: signals in the same group do not count as independent (red needs two different groups).
    """

    name: str
    group: str
    extract: Callable[[Mapping[str, Any]], tuple[float, float]]
    weight: float = 1.0  # share of the overall risk number shown on the meter


@dataclass(frozen=True)
class GateConfig:
    attack: float = 0.7          # how fast a level rises (times confidence)
    release: float = 0.12        # how fast a level falls when the sentence is calm
    active_above: float = 0.30   # a signal becomes active at or above this level
    inactive_below: float = 0.15  # and stops being active below this level
    min_groups_for_red: int = 2  # independent groups needed for red
    amber_risk: float = 0.20     # overall risk that also gives amber with no active signal


@dataclass
class GateState:
    state: str = GREEN
    risk: float = 0.0
    levels: dict[str, float] = field(default_factory=dict)
    active: list[str] = field(default_factory=list)
    step: int = 0
    reason: str = ""
    changed: bool = False        # True on the sentence where the state changed
    red_at_step: int | None = None


class StreamingRiskGate:
    def __init__(self, signals: list[Signal], config: GateConfig | None = None):
        self.signals = list(signals)
        self.cfg = config or GateConfig()
        self.clear()

    # --- state ---
    def clear(self) -> None:
        """Human decision: reset everything back to green."""
        self._levels = {s.name: 0.0 for s in self.signals}
        self._active: set[str] = set()
        self._state = GREEN
        self._step = 0
        self._red_at: int | None = None
        self._reason = ""

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_red(self) -> bool:
        return self._state == RED

    def snapshot(self, changed: bool = False) -> GateState:
        total_w = sum(s.weight for s in self.signals) or 1.0
        risk = sum(self._levels[s.name] * s.weight for s in self.signals) / total_w
        return GateState(self._state, round(risk, 4), {k: round(v, 4) for k, v in self._levels.items()},
                         sorted(self._active), self._step, self._reason, changed, self._red_at)

    # --- update ---
    def update(self, answers: Mapping[str, Any]) -> GateState:
        """Feed the Decider answers for one sentence. Returns the new state."""
        self._step += 1
        for s in self.signals:
            value, conf = s.extract(answers)
            value, conf = min(max(value, 0.0), 1.0), min(max(conf, 0.0), 1.0)
            lvl = self._levels[s.name]
            if value > lvl:
                lvl += self.cfg.attack * conf * (value - lvl)
            else:
                lvl += self.cfg.release * (value - lvl)
            self._levels[s.name] = lvl
            if lvl >= self.cfg.active_above:
                self._active.add(s.name)
            elif lvl < self.cfg.inactive_below:
                self._active.discard(s.name)

        before = self._state
        if self._state != RED:  # red is latched
            groups = {s.group for s in self.signals if s.name in self._active}
            snap_risk = self.snapshot().risk
            if len(groups) >= self.cfg.min_groups_for_red:
                self._state, self._red_at = RED, self._step
                self._reason = "two independent signals: " + ", ".join(sorted(self._active))
            elif self._active or snap_risk >= self.cfg.amber_risk:
                self._state = AMBER
                self._reason = "one signal: " + (", ".join(sorted(self._active)) or "risk rising")
            else:
                self._state, self._reason = GREEN, ""
        return self.snapshot(changed=self._state != before)
