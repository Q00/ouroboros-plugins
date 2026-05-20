from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "autoresearch"


class AutoresearchPluginTests(unittest.TestCase):
    def _run(
        self, *args: str, env_extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess:
        env = {**os.environ, "PYTHONPATH": str(PLUGIN_PATH)}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, "-m", "ouroboros_autoresearch", *args],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_inspect_reports_ready_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "program.md").write_text("Improve the model.\n", encoding="utf-8")
            (root / "prepare.py").write_text("MAX_SEQ_LEN = 1024\n", encoding="utf-8")
            (root / "train.py").write_text("print('val_bpb=1.0')\n", encoding="utf-8")

            proc = self._run("inspect", str(root))

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["ooo_auto_ready"])
        self.assertEqual(payload["missing"], [])

    def test_prepare_writes_seed_and_handoff(self):
        with tempfile.TemporaryDirectory(prefix="autoresearch path with spaces ") as td:
            root = Path(td)
            (root / "program.md").write_text(
                "Improve val_bpb.\n\n```python\nprint('example')\n```\n",
                encoding="utf-8",
            )
            (root / "prepare.py").write_text("MAX_SEQ_LEN = 1024\n", encoding="utf-8")
            (root / "train.py").write_text("print('val_bpb=1.0')\n", encoding="utf-8")

            proc = self._run(
                "prepare",
                str(root),
                "--goal",
                "Find a smaller validation bpb.",
                "--max-experiments",
                "2",
                "--experiment-seconds",
                "60",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            seed_path = Path(payload["seed_path"])
            auto_goal_path = Path(payload["auto_goal_path"])
            handoff_path = Path(payload["handoff_path"])
            self.assertTrue(seed_path.is_file())
            self.assertTrue(auto_goal_path.is_file())
            self.assertTrue(handoff_path.is_file())
            seed = seed_path.read_text(encoding="utf-8")
            auto_goal = auto_goal_path.read_text(encoding="utf-8")
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
            self.assertIn("Find a smaller validation bpb.", seed)
            self.assertIn("Run at most 2 experiments.", seed)
            self.assertIn("Keep each experiment bounded to 60 seconds.", seed)
            self.assertIn("`prepare.py` as fixed data prep", seed)
            self.assertIn("````markdown", seed)
            self.assertIn("Use the prepared autoresearch handoff brief", auto_goal)
            self.assertIn("Do not run training during Seed creation", auto_goal)
            self.assertEqual(handoff, payload)
            self.assertIn("ouroboros auto \"$(cat", payload["ooo_auto"]["recommended_command"])
            self.assertIn("autoresearch path with spaces", payload["ooo_auto"]["recommended_command"])
            self.assertIn("'", payload["ooo_auto"]["recommended_command"])
            self.assertEqual(payload["ooo_auto"]["editable_files"], ["train.py"])
            provenance = payload["provenance"]
            self.assertEqual(provenance["upstream"], "https://github.com/karpathy/autoresearch")
            self.assertFalse(provenance["git"]["is_git_repository"])
            self.assertEqual(provenance["files"]["program"]["path"], "program.md")
            self.assertEqual(provenance["files"]["target"]["path"], "train.py")
            self.assertEqual(provenance["files"]["support"]["path"], "prepare.py")
            for file_record in provenance["files"].values():
                self.assertEqual(len(file_record["sha256"]), 64)
                self.assertGreater(file_record["bytes"], 0)
            mapping = payload["ouroboros_capability_mapping"]
            self.assertEqual(mapping["seed:write"]["artifact"], payload["seed_path"])
            self.assertEqual(mapping["provenance:write"]["json_pointer"], "/provenance")
            self.assertIn(payload["handoff_path"], mapping["handoff:attach"]["artifacts"])
            self.assertEqual(mapping["progress:write"]["artifact"], "stdout-json")

    def test_prepare_records_custom_declared_options(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "brief.md").write_text("Improve perplexity.\n", encoding="utf-8")
            (root / "setup.py").write_text("MAX_SEQ_LEN = 512\n", encoding="utf-8")
            (root / "model.py").write_text("print('loss=1.0')\n", encoding="utf-8")

            proc = self._run(
                "prepare",
                str(root),
                "--program-file",
                "brief.md",
                "--support-file",
                "setup.py",
                "--target-file",
                "model.py",
                "--goal",
                "Reduce validation loss.",
                "--metric",
                "loss",
                "--max-experiments",
                "3",
                "--experiment-seconds",
                "45",
                "--train-command",
                "uv run python model.py",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            seed = Path(payload["seed_path"]).read_text(encoding="utf-8")
            auto_goal = Path(payload["auto_goal_path"]).read_text(encoding="utf-8")
            self.assertEqual(payload["ooo_auto"]["metric"], "loss")
            self.assertEqual(payload["ooo_auto"]["max_experiments"], 3)
            self.assertEqual(payload["ooo_auto"]["experiment_seconds"], 45)
            self.assertEqual(payload["ooo_auto"]["train_command"], "uv run python model.py")
            self.assertEqual(payload["ooo_auto"]["editable_files"], ["model.py"])
            self.assertIn("Treat `brief.md` as the research program", seed)
            self.assertIn("Treat `setup.py` as fixed data prep", seed)
            self.assertIn("Use `loss` as the primary comparison metric", seed)
            self.assertIn("Verification command: `uv run python model.py`", auto_goal)
            self.assertEqual(payload["provenance"]["files"]["program"]["path"], "brief.md")
            self.assertEqual(payload["provenance"]["files"]["support"]["path"], "setup.py")
            self.assertEqual(payload["provenance"]["files"]["target"]["path"], "model.py")

    def test_prepare_handles_missing_git_executable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "program.md").write_text("Improve the model.\n", encoding="utf-8")
            (root / "prepare.py").write_text("MAX_SEQ_LEN = 1024\n", encoding="utf-8")
            (root / "train.py").write_text("print('val_bpb=1.0')\n", encoding="utf-8")

            proc = self._run(
                "prepare",
                str(root),
                "--goal",
                "Improve the model.",
                env_extra={"PATH": ""},
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["provenance"]["git"]["is_git_repository"])

    def test_prepare_requires_autoresearch_files(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("prepare", td, "--goal", "Improve the model.")

        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing required file", proc.stderr)

    def test_layout_paths_must_stay_inside_repository(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "program.md").write_text("Improve the model.\n", encoding="utf-8")
            (root / "prepare.py").write_text("MAX_SEQ_LEN = 1024\n", encoding="utf-8")
            (root / "train.py").write_text("print('val_bpb=1.0')\n", encoding="utf-8")

            proc = self._run("inspect", str(root), "--program-file", "../program.md")

        self.assertEqual(proc.returncode, 2)
        self.assertIn("--program-file must stay inside", proc.stderr)

    def test_layout_paths_must_be_relative(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "program.md").write_text("Improve the model.\n", encoding="utf-8")
            (root / "prepare.py").write_text("MAX_SEQ_LEN = 1024\n", encoding="utf-8")
            (root / "train.py").write_text("print('val_bpb=1.0')\n", encoding="utf-8")

            proc = self._run("inspect", str(root), "--program-file", str(root / "program.md"))

        self.assertEqual(proc.returncode, 2)
        self.assertIn("--program-file must be a path relative", proc.stderr)


if __name__ == "__main__":
    unittest.main()
