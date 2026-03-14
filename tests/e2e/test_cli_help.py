from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_uv_run_codeman_help_succeeds() -> None:
    project_root = Path(__file__).resolve().parents[2]
    cache_dir = project_root / ".local" / "uv-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(cache_dir))

    result = subprocess.run(
        ["uv", "run", "codeman", "--help"],
        capture_output=True,
        check=False,
        text=True,
        cwd=project_root,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Usage:" in result.stdout
    assert "repo" in result.stdout
