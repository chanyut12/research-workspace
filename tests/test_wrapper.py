import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(env_extra):
    env = {**os.environ, **env_extra}
    return subprocess.run(["sh", str(ROOT / "scripts" / "rw"), "check_deps.py"], capture_output=True, text=True, env=env)


def test_wrapper_uses_rw_python():
    r = run({"RW_PYTHON": sys.executable})
    assert r.returncode == 0 and "OK" in r.stdout


def test_wrapper_skips_bad_candidates(tmp_path):
    r = run({"RW_PYTHON": str(tmp_path / "missing-python"), "HOME": str(tmp_path)})
    assert r.returncode == 0 and "OK" in r.stdout   # falls through to the repo .venv
