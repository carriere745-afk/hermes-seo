"""Pipeline 8 — Learning Engine — 8 agents."""

from hermes.agents.learning.l00_supervisor import run as l00
from hermes.agents.learning.l01_calibrator import run as l01
from hermes.agents.learning.l02_patterns import run as l02
from hermes.agents.learning.l03_delay import run as l03
from hermes.agents.learning.l04_update_classifier import run as l04
from hermes.agents.learning.l05_model_distributor import run as l05
from hermes.agents.learning.l06_pattern_library import run as l06
from hermes.agents.learning.l07_recommendation_optimizer import run as l07
from hermes.agents.learning.l08_failure_analyzer import run as l08

LEARNING_REGISTRY = {
    "l00": l00, "l01": l01, "l02": l02, "l03": l03,
    "l04": l04, "l05": l05, "l06": l06, "l07": l07, "l08": l08,
}

LEARNING_ORDER = [
    "l00", "l01", "l02", "l03", "l04", "l05", "l06", "l07", "l08",
]
