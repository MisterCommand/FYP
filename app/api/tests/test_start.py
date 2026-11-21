import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.fixture
def launcher(tmp_path):
    source = Path(__file__).resolve().parents[2]
    app = tmp_path / "app"
    (app / "api/.venv/bin").mkdir(parents=True)
    (app / "web/node_modules/.bin").mkdir(parents=True)
    shutil.copyfile(source / "start.sh", app / "start.sh")
    shutil.copyfile(source / "api/security.py", app / "api/security.py")
    python = app / "api/.venv/bin/python"
    python.write_text(f'#!/usr/bin/env bash\nexec "{sys.executable}" "$@"\n')
    python.chmod(0o755)
    stub = f'''#!{sys.executable}
import json, os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
folder = pathlib.Path(os.environ["CAPTURE_DIR"])
pending = folder / (name + ".tmp")
pending.write_text(json.dumps(sys.argv[1:]))
pending.rename(folder / (name + ".json"))
deadline = time.monotonic() + 3
while len(list(folder.glob("*.json"))) < 2 and time.monotonic() < deadline:
    time.sleep(.01)
'''
    for target in (app / "api/.venv/bin/uvicorn", app / "web/node_modules/.bin/next"):
        target.write_text(stub)
        target.chmod(0o755)
    captures = tmp_path / "captures"
    captures.mkdir()

    def run(**overrides):
        env = {k: v for k, v in os.environ.items() if k not in (
            "API_HOST", "WEB_HOST", "API_PORT", "PORT", "EVENTLENS_API_TOKEN", "EVENTLENS_ALLOW_UNAUTHENTICATED")}
        env.update(CAPTURE_DIR=str(captures), **overrides)
        result = subprocess.run(["bash", str(app / "start.sh")], env=env, cwd=tmp_path,
                                capture_output=True, text=True, timeout=10)
        args = {p.stem: json.loads(p.read_text()) for p in captures.glob("*.json")}
        return result, args

    return run


def test_launcher_defaults_are_loopback_and_disable_proxy_header_trust(launcher):
    result, args = launcher()
    assert result.returncode == 0, result.stderr
    assert args["uvicorn"] == ["main:app", "--host", "127.0.0.1", "--port", "8000", "--no-proxy-headers"]
    assert args["next"] == ["start", "--hostname", "127.0.0.1", "--port", "3000"]


@pytest.mark.parametrize("variable", ["API_HOST", "WEB_HOST"])
def test_launcher_refuses_public_bind_before_starting_either_service(launcher, variable):
    result, args = launcher(**{variable: "0.0.0.0"})
    assert result.returncode != 0
    assert variable in result.stderr and "EVENTLENS_API_TOKEN" in result.stderr
    assert args == {}


@pytest.mark.parametrize("authorization", [{"EVENTLENS_API_TOKEN": "shared-test-token"},
                                        {"EVENTLENS_ALLOW_UNAUTHENTICATED": "1"}])
def test_launcher_explicit_public_frontend_keeps_api_loopback_and_custom_ports(launcher, authorization):
    result, args = launcher(WEB_HOST="0.0.0.0", API_PORT="8101", PORT="3101", **authorization)
    assert result.returncode == 0, result.stderr
    assert args["uvicorn"] == ["main:app", "--host", "127.0.0.1", "--port", "8101", "--no-proxy-headers"]
    assert args["next"] == ["start", "--hostname", "0.0.0.0", "--port", "3101"]
