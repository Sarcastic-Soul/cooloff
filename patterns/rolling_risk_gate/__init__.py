"""rolling_risk_gate: a Strands Decider 2B decision pattern (label: policy).

    from patterns.rolling_risk_gate import StreamingRiskGate, SIGNALS, QUESTIONS, load_config, TransactionHold
"""
from pathlib import Path

import yaml

from .gate import AMBER, GREEN, RED, GateConfig, GateState, Signal, StreamingRiskGate
from .questions import DANGEROUS_PAYMENT, QUESTIONS, SIGNALS


def load_config(path: str | Path | None = None) -> GateConfig:
    """Read thresholds.yaml (or another file) into a GateConfig."""
    path = Path(path) if path else Path(__file__).with_name("thresholds.yaml")
    return GateConfig(**yaml.safe_load(path.read_text()))


def make_gate(config: GateConfig | None = None) -> StreamingRiskGate:
    return StreamingRiskGate(SIGNALS, config or load_config())


def __getattr__(name):  # TransactionHold needs strands; import it only when asked for
    if name == "TransactionHold":
        from .hold import TransactionHold
        return TransactionHold
    raise AttributeError(name)
