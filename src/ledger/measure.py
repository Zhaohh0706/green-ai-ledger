"""Measure the energy a piece of work used, and say which parts were measured.

There are two ways to get a wattage out of a laptop and they are not
interchangeable:

* **Measured.** macOS exposes real per-subsystem power through ``powermetrics``,
  which needs root. Given root, the CPU, GPU and memory figures are readings.
* **Estimated.** Without root, every tool falls back to a nameplate figure for
  the processor and multiplies by elapsed time. That is an assumption about
  average utilisation dressed as a measurement, and on a laptop that idles
  between bursts it can be out by several times.

Both are useful and only one is a measurement, so every record here carries a
``method`` field and the report never averages across the two. A carbon figure
whose provenance is unstated is the thing this project exists not to produce.

The energy itself comes from CodeCarbon, which handles the platform differences.
What this module adds is the honesty layer: it records whether root was
available, pins the grid factor instead of geolocating, and keeps the raw
kilowatt-hours so a later correction does not require re-running the work.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import time
import warnings
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .grid import IP_GEOLOCATION_EXAMPLES, IP_GEOLOCATION_SOURCE, GridFactor, resolve

warnings.filterwarnings("ignore")
logging.getLogger("codecarbon").setLevel(logging.ERROR)

LEDGER = Path(__file__).resolve().parents[2] / "ledger.jsonl"


@dataclass
class Record:
    label: str
    project: str
    started: str
    duration_s: float
    energy_kwh: float
    cpu_kwh: float
    gpu_kwh: float
    ram_kwh: float
    method: str  # "measured" or "estimated"
    method_note: str
    region: str
    grid_factor_kg_per_kwh: float
    co2_kg: float
    host: str
    command: str | None = None
    exit_code: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def co2_g(self) -> float:
        return self.co2_kg * 1000.0


def power_measurement_available() -> tuple[bool, str]:
    """Can real power readings be taken, or only a nameplate estimate?

    ``powermetrics`` exists on every Mac and refuses to run without root, so the
    check is whether this process is root, not whether the tool is installed.
    """
    if platform.system() != "Darwin":
        return False, "not macOS; CodeCarbon uses whatever its platform supports"
    if shutil.which("powermetrics") is None:
        return False, "powermetrics not found"
    if os.geteuid() != 0:
        return (
            False,
            "powermetrics needs root; falling back to the processor's nameplate "
            "power, which is an assumption about utilisation, not a reading",
        )
    return True, "powermetrics readings"


@contextmanager
def track(
    label: str,
    project: str,
    region: str = "广东",
    ledger_path: Path | None = None,
    command: str | None = None,
    extra: dict | None = None,
):
    """Record the energy used inside the block, and append it to the ledger."""
    from codecarbon import EmissionsTracker

    factor = resolve(region)
    measured, note = power_measurement_available()
    tracker = EmissionsTracker(
        project_name=project,
        save_to_file=False,
        log_level="error",
        # Its own emission factor is discarded below; the tracker is used for
        # energy only, because that is the part it is authoritative about.
        allow_multiple_runs=True,
    )
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    clock = time.time()
    tracker.start()
    holder: dict = {}
    try:
        yield holder
    finally:
        tracker.stop()
        data = tracker.final_emissions_data
        elapsed = time.time() - clock
        record = Record(
            label=label,
            project=project,
            started=started,
            duration_s=round(float(getattr(data, "duration", elapsed)), 2),
            energy_kwh=float(getattr(data, "energy_consumed", 0.0)),
            cpu_kwh=float(getattr(data, "cpu_energy", 0.0)),
            gpu_kwh=float(getattr(data, "gpu_energy", 0.0)),
            ram_kwh=float(getattr(data, "ram_energy", 0.0)),
            method="measured" if measured else "estimated",
            method_note=note,
            region=factor.region,
            grid_factor_kg_per_kwh=factor.value,
            co2_kg=float(getattr(data, "energy_consumed", 0.0)) * factor.value,
            host=f"{platform.system()} {platform.machine()} / {getattr(data, 'cpu_model', 'unknown')}",
            command=command,
            exit_code=holder.get("exit_code"),
            extra=extra or {},
        )
        append(record, ledger_path)
        holder["record"] = record


def redact(command: str) -> str:
    """The command as it should appear in a ledger someone else may read.

    A command line carries the absolute path of whichever interpreter ran it,
    and that path carries the user's name. The ledger is meant to be committed
    next to the work it measures, so the home directory is written as ``~``.
    """
    home = str(Path.home())
    return command.replace(home, "~") if home and home != "/" else command


def run_command(
    command: list[str],
    label: str,
    project: str,
    region: str = "广东",
    ledger_path: Path | None = None,
    cwd: str | None = None,
) -> Record:
    """Run a shell command under measurement."""
    with track(
        label, project, region, ledger_path, command=redact(" ".join(command))
    ) as holder:
        completed = subprocess.run(command, cwd=cwd, check=False)
        holder["exit_code"] = completed.returncode
    return holder["record"]


def append(record: Record, path: Path | None = None) -> None:
    path = path or LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load(path: Path | None = None) -> list[Record]:
    path = path or LEDGER
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(Record(**json.loads(line)))
    return out


def counterfactual(record: Record) -> list[dict]:
    """What an IP-geolocating tracker would have reported, by exit country.

    One row per example exit, so the report shows the spread of the error rather
    than one instance of it. The spread is the argument: the same code, on the
    same machine, gives anything from a sixteenth of the right answer to half
    again too much, depending on a routing detail nobody reports.
    """
    rows = []
    for exit_region, factor in IP_GEOLOCATION_EXAMPLES.items():
        theirs = record.energy_kwh * factor
        rows.append(
            {
                "exit": exit_region,
                "factor": factor,
                "co2_kg": theirs,
                # Positive: geolocation overstates; negative: it understates.
                "error_pct": (
                    100.0 * (theirs - record.co2_kg) / record.co2_kg
                    if record.co2_kg
                    else 0.0
                ),
                "source": IP_GEOLOCATION_SOURCE,
            }
        )
    return rows
