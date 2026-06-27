"""Pipeline 7 — Maintenance & Execution Engine — 15 agents."""

from hermes.agents.maintenance.m00_supervisor import run as m00
from hermes.agents.maintenance.m01_decay import run as m01
from hermes.agents.maintenance.m02_core_update import run as m02
from hermes.agents.maintenance.m03_dispatcher import run as m03
from hermes.agents.maintenance.m04_generator import run as m04
from hermes.agents.maintenance.m05_optimizer import run as m05
from hermes.agents.maintenance.m06_publisher import run as m06
from hermes.agents.maintenance.m07_monitor import run as m07
from hermes.agents.maintenance.m08_safety import run as m08
from hermes.agents.maintenance.m09_rollback import run as m09
from hermes.agents.maintenance.m10_dependencies import run as m10
from hermes.agents.maintenance.m11_approval import run as m11
from hermes.agents.maintenance.m12_pipeline_editorial import run as m12
from hermes.agents.maintenance.m13_cms_intervention import run as m13
from hermes.agents.maintenance.m14_auto_reports import run as m14
from hermes.agents.maintenance.m15_gsc_auto_submit import run as m15

MAINTENANCE_REGISTRY = {
    "m00": m00, "m01": m01, "m02": m02, "m03": m03,
    "m04": m04, "m05": m05, "m06": m06, "m07": m07,
    "m08": m08, "m09": m09, "m10": m10, "m11": m11, "m12": m12,
    "m13": m13, "m14": m14, "m15": m15,
}

MAINTENANCE_ORDER = [
    "m00", "m01", "m02", "m03",
    "m08", "m09", "m10", "m11",
    "m04", "m05", "m06",
    "m07", "m12", "m13", "m14",
]
