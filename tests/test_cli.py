from __future__ import annotations

import pathlib
import subprocess
import sys
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from codeman.cli import greet


class GreetTests(unittest.TestCase):
    def test_greet_uses_given_name(self) -> None:
        self.assertEqual(greet("BMAD"), "Hello, BMAD!")

    def test_greet_falls_back_to_world_for_blank_values(self) -> None:
        self.assertEqual(greet("   "), "Hello, world!")

    def test_module_entry_point_runs(self) -> None:
        env = dict()
        env.update(PYTHONPATH=str(SRC_PATH))
        result = subprocess.run(
            [sys.executable, "-m", "codeman", "--name", "Python"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "Hello, Python!")

