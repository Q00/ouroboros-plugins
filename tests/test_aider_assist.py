from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((REPO / "schemas" / "0.1" / "plugin.schema.json").read_text())


class AiderAssistTests(unittest.TestCase):
    def test_aider_assist_manifest_validates(self):
        manifest = json.loads((REPO / "plugins" / "aider-assist" / "ouroboros.plugin.json").read_text())
        errors = list(Draft202012Validator(SCHEMA).iter_errors(manifest))
        self.assertEqual(errors, [])

    def test_ask_writes_handoff_with_fake_aider(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake = tmp / "fake-aider"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('aider fake 0.0')\n"
                "else:\n"
                "    print('answer from fake aider')\n"
            )
            fake.chmod(0o755)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "src.py").write_text("print('hi')\n")

            env = os.environ.copy()
            env["AIDER_ASSIST_AIDER_BIN"] = str(fake)
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "ask", "--message", "Explain", "--file", "src.py"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact_dir = Path(completed.stdout.strip())
            self.assertTrue((artifact_dir / "invocation.json").is_file())
            self.assertEqual((artifact_dir / "answer.md").read_text(), "answer from fake aider\n")
            handoff = (artifact_dir / "handoff.md").read_text()
            self.assertIn("Aider Assist Handoff", handoff)
            self.assertIn("src.py", handoff)

    def test_ask_missing_aider_writes_failed_artifacts(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            env = os.environ.copy()
            env["AIDER_ASSIST_AIDER_BIN"] = str(Path(td) / "does-not-exist")
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "ask", "--message", "Explain"],
                cwd=REPO, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 127)
            artifact_dir = Path(completed.stdout.strip())
            invocation = json.loads((artifact_dir / "invocation.json").read_text())
            self.assertEqual(invocation["result"]["status"], "failed")
            self.assertIn("executable not found", (artifact_dir / "stderr.txt").read_text())

    def test_edit_refuses_missing_editable_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "edit", "--message", "Change safely"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("requires at least one --file", completed.stderr)

    def test_edit_writes_diff_and_touched_files_with_fake_aider(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake = tmp / "fake-aider"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('aider fake 0.0')\n"
                "else:\n"
                "    Path('src.py').write_text(\"print('changed')\\n\")\n"
                "    print('edited by fake aider')\n"
            )
            fake.chmod(0o755)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "src.py").write_text("print('hi')\n")
            subprocess.run(["git", "add", "src.py"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

            env = os.environ.copy()
            env["AIDER_ASSIST_AIDER_BIN"] = str(fake)
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "edit", "--message", "Change", "--file", "src.py"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact_dir = Path(completed.stdout.strip())
            self.assertIn("src.py", (artifact_dir / "touched-files.txt").read_text())
            self.assertIn("changed", (artifact_dir / "diff.patch").read_text())
            invocation = json.loads((artifact_dir / "invocation.json").read_text())
            self.assertEqual(invocation["editable_files"], ["src.py"])

    def test_edit_fails_when_aider_touches_undeclared_file(self):
    def test_edit_captures_verification_output(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake = tmp / "fake-aider"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('aider fake 0.0')\n"
                "else:\n"
                "    Path('src.py').write_text(\"print('changed')\\n\")\n"
                "    Path('secret.py').write_text(\"print('outside')\\n\")\n"
                "    print('edited by fake aider')\n"
            )
            fake.chmod(0o755)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "src.py").write_text("print('hi')\n")
            subprocess.run(["git", "add", "src.py"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

            env = os.environ.copy()
            env["AIDER_ASSIST_AIDER_BIN"] = str(fake)
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "edit", "--message", "Change", "--file", "src.py"],
                cwd=REPO,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1)
            artifact_dir = Path(completed.stdout.strip())
            invocation = json.loads((artifact_dir / "invocation.json").read_text())
            self.assertEqual(invocation["result"]["status"], "failed")
            self.assertEqual(invocation["unauthorized_touched_files"], ["secret.py"])
            self.assertIn("secret.py", (artifact_dir / "handoff.md").read_text())

    def test_edit_fails_when_aider_touches_unlisted_file(self):
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "edit", "--message", "Change", "--file", "src.py", "--test-cmd", "python -c \"print('tests ok')\""],
                cwd=REPO, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            artifact_dir = Path(completed.stdout.strip())
            verification = json.loads((artifact_dir / "verification.json").read_text())
            self.assertEqual(verification["status"], "passed")
            self.assertIn("tests ok", verification["after"][0]["stdout"])

    def test_fix_requires_verification_command(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "fix", "--file", "src.py"],
                cwd=REPO, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("fix requires --test-cmd or --lint-cmd", completed.stderr)

    def test_fix_reports_failed_post_verification(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            fake = tmp / "fake-aider"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                "if '--version' in sys.argv:\n"
                "    print('aider fake 0.0')\n"
                "else:\n"
                "    Path('other.py').write_text(\"print('oops')\\n\")\n"
                "    print('edited outside bounds')\n"
                "    print('attempted repair')\n"
            )
            fake.chmod(0o755)
            repo = tmp / "repo"
            repo.mkdir()
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            (repo / "src.py").write_text("print('hi')\n")
            subprocess.run(["git", "add", "src.py"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

            env = os.environ.copy()
            env["AIDER_ASSIST_AIDER_BIN"] = str(fake)
            env["PYTHONPATH"] = str(REPO / "plugins" / "aider-assist")
            completed = subprocess.run(
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "edit", "--message", "Change", "--file", "src.py"],
                [sys.executable, "-m", "aider_assist", "--repo", str(repo), "fix", "--file", "src.py", "--test-cmd", "python -c \"import sys; sys.exit(3)\""],
                cwd=REPO, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(completed.returncode, 1)
            artifact_dir = Path(completed.stdout.strip())
            invocation = json.loads((artifact_dir / "invocation.json").read_text())
            self.assertEqual(invocation["result"]["status"], "failed")
            self.assertEqual(invocation["unauthorized_touched_files"], ["other.py"])
            verification = json.loads((artifact_dir / "verification.json").read_text())
            self.assertEqual(verification["status"], "failed")
            self.assertEqual(verification["after"][0]["exit_code"], 3)


if __name__ == "__main__":
    unittest.main()
