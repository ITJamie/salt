"""Fork-only timing of existing tests; never replace or delay ID discovery."""

import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest

import salt.utils.network


class Measurements:
    def __init__(self):
        self.nodeid = "session"
        self.calls = []
        self.reports = []
        self.original = salt.utils.network.generate_minion_id

    def discover(self, *args, **kwargs):
        start = time.perf_counter()
        try:
            return self.original(*args, **kwargs)
        finally:
            self.calls.append(
                {"nodeid": self.nodeid, "seconds": time.perf_counter() - start}
            )

    def pytest_runtest_logstart(self, nodeid, location):
        self.nodeid = nodeid

    def pytest_runtest_logreport(self, report):
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "phase": report.when,
                "seconds": report.duration,
                "outcome": report.outcome,
            }
        )


if __name__ == "__main__":
    output = Path(sys.argv[1])
    measurements = Measurements()
    started = time.perf_counter()
    with patch(
        "salt.utils.network.generate_minion_id", side_effect=measurements.discover
    ):
        result = pytest.main(
            [
                "tests/pytests/unit/runners/test_runner_print_event.py",
                "tests/pytests/functional/loader/test_loaded_base_name.py::test_loader[utils]",
                *sys.argv[2:],
            ],
            plugins=[measurements],
        )
    data = {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "pytest_exit_code": int(result),
        "wall_seconds": time.perf_counter() - started,
        "discovery_calls": measurements.calls,
        "discovery_seconds": sum(call["seconds"] for call in measurements.calls),
        "test_reports": measurements.reports,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2))
    sys.exit(result)
