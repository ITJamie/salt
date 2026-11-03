"""Compare real fixture factories without invoking unrelated test/grains setup."""

import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest_helpers_namespace.plugin

# Salt conftest imports register helpers before any fixture is invoked.
pytest_helpers_namespace.plugin.pytest_load_initial_conftests()

import salt.utils.network
from tests.pytests.functional.loader.test_loaded_base_name import opts as loader_opts
from tests.pytests.unit.conftest import master_opts


def measure():
    calls = []
    timings = []
    original = salt.utils.network.generate_minion_id
    current = None

    def discover(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            calls.append({"fixture": current, "seconds": time.perf_counter() - started})

    with tempfile.TemporaryDirectory() as directory:
        with patch("salt.utils.network.generate_minion_id", side_effect=discover):
            for name, factory, args in (
                ("unit.master_opts", master_opts, (Path(directory),)),
                ("loader.opts", loader_opts, ("id_benchmark.loaded",)),
            ):
                current = name
                started = time.perf_counter()
                # Invoke the existing factory, not pytest's fixture wrapper or
                # the functional suite's unrelated autouse loader/grains setup.
                opts = factory.__wrapped__(*args)
                timings.append(
                    {"fixture": name, "seconds": time.perf_counter() - started}
                )
                assert opts["id"], f"{name} did not produce an ID"
    return {
        "harness_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "fixture_revision": sys.argv[2],
        "platform": platform.platform(),
        "python": platform.python_version(),
        "fixture_timings": timings,
        "discovery_calls": calls,
        "discovery_seconds": sum(call["seconds"] for call in calls),
    }


if __name__ == "__main__":
    data = measure()
    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2))
