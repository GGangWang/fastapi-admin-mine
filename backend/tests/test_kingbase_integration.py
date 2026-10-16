"""Opt-in real Kingbase probes in dedicated *_test databases; never use dev databases."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv("KINGBASE_RUN_INTEGRATION") != "1", reason="No explicitly enabled Kingbase instance")
def test_kingbase_real_instance():
    # Subprocess avoids the SQLite settings/Redis mocks installed by conftest.
    result = subprocess.run([sys.executable, str(Path(__file__).with_name("kingbase_probe.py"))], env=os.environ.copy(), cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=180)
    # Never include connection exception text: it may contain supplied credentials.
    assert result.returncode == 0, "金仓实机探测失败；在本机直接运行 tests/kingbase_probe.py 查看失败阶段（不会打印凭据）"
