from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "openai-skills-superpowers"
FIXTURE_SKILLS = REPO / "tests" / "fixtures" / "openai-skills"


class SuperpowersPluginTests(unittest.TestCase):
    def _run(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "ouroboros_superpowers", *args],
            cwd=cwd or REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def _catalog(self, td: str) -> Path:
        catalog = Path(td) / "catalog.json"
        proc = self._run(
            "catalog",
            "refresh",
            "--source-path",
            str(FIXTURE_SKILLS),
            "--ref",
            "fixture-sha",
            "--out",
            "catalog.json",
            cwd=Path(td),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return catalog

    def test_catalog_refresh_projects_resources_permissions_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            catalog_path = self._catalog(td)
            catalog = json.loads(catalog_path.read_text())

        self.assertEqual(catalog["skill_count"], 7)
        self.assertEqual(catalog["duplicates"], ["openai-docs"])
        openai_docs = [s for s in catalog["skills"] if s["name"] == "openai-docs" and s["bucket"] == "curated"][0]
        self.assertTrue(openai_docs["resources"]["skill_md"])
        self.assertTrue(openai_docs["resources"]["references"])
        self.assertEqual(openai_docs["permissions"]["risk"], "read_only")
        pdf = [s for s in catalog["skills"] if s["name"] == "pdf"][0]
        self.assertEqual(pdf["permissions"]["risk"], "write")
        self.assertIn("filesystem:write", pdf["permissions"]["optional"])
        hatch = [s for s in catalog["skills"] if s["name"] == "hatch-pet"][0]
        self.assertTrue(hatch["resources"]["scripts"])
        self.assertIn("shell:execute", hatch["permissions"]["optional"])

    def test_list_hides_system_by_default_and_inspect_prefers_curated_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = self._catalog(td)
            listed = self._run("--catalog", str(catalog), "catalog", "list")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            rows = json.loads(listed.stdout)
            self.assertEqual(rows["skill_count"], 6)
            self.assertNotIn("system/openai-docs", [s["target"] for s in rows["skills"]])

            inspected = self._run("--catalog", str(catalog), "inspect", "openai-docs")
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout)["bucket"], "curated")

            system = self._run("--catalog", str(catalog), "inspect", "system/openai-docs")
            self.assertEqual(system.returncode, 0, system.stderr)
            self.assertEqual(json.loads(system.stdout)["bucket"], "system")

    def test_handoff_writes_ouroboros_artifact_and_audit_event(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = self._catalog(td)
            out = Path(td) / "handoff.json"
            audit = Path(td) / "audit.jsonl"
            proc = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                "audit.jsonl",
                "handoff",
                "security-threat-model",
                "--task",
                "model this repo",
                "--out",
                "handoff.json",
                cwd=Path(td),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(out.read_text())
            self.assertEqual(payload["kind"], "superpower_handoff")
            self.assertEqual(payload["skill"]["name"], "security-threat-model")
            self.assertEqual(payload["permissions"]["risk"], "read_only")
            event = json.loads(audit.read_text().splitlines()[-1])
            self.assertEqual(event["event_type"], "plugin.completed")
            self.assertEqual(event["plugin"]["name"], "openai-skills-superpowers")

    def test_run_allows_read_only_blocks_external_and_requires_script_trust(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = self._catalog(td)
            audit = Path(td) / "audit.jsonl"
            ok = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                "audit.jsonl",
                "run",
                "openai-docs",
                "--",
                "explain plugins",
                cwd=Path(td),
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)
            self.assertEqual(json.loads(ok.stdout)["status"], "success")

            blocked_external = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                "blocked-external.jsonl",
                "run",
                "yeet",
                "--",
                "open a PR",
                cwd=Path(td),
            )
            self.assertEqual(blocked_external.returncode, 3)
            self.assertEqual(json.loads(blocked_external.stdout)["status"], "blocked")
            blocked_events = [
                json.loads(line)
                for line in (Path(td) / "blocked-external.jsonl").read_text().splitlines()
            ]
            self.assertEqual([event["event_type"] for event in blocked_events], ["plugin.failed"])
            self.assertEqual(blocked_events[0]["trust_state"], "blocked")

            blocked_script = self._run("--catalog", str(catalog), "run", "hatch-pet", "--", "validate pet")
            self.assertEqual(blocked_script.returncode, 3)

            pdf_create = self._run(
                "--catalog",
                str(catalog),
                "run",
                "pdf",
                "--",
                "create a PDF artifact",
            )
            self.assertEqual(pdf_create.returncode, 3)

            pdf_read = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                "audit-pdf.jsonl",
                "run",
                "pdf",
                "--",
                "read and summarize this PDF",
                cwd=Path(td),
            )
            self.assertEqual(pdf_read.returncode, 0, pdf_read.stderr)
            shell_without_trust = self._run(
                "--catalog",
                str(catalog),
                "run",
                "hatch-pet",
                "--allow-shell",
                "--",
                "validate pet",
            )
            self.assertEqual(shell_without_trust.returncode, 3)

            self_attested_trust = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                "self-trust.jsonl",
                "run",
                "hatch-pet",
                "--trusted",
                "--allow-shell",
                "--",
                "validate pet",
                cwd=Path(td),
            )
            self.assertEqual(self_attested_trust.returncode, 3)
            self.assertIn("not an authority source", self_attested_trust.stdout)
            self_events = [
                json.loads(line)
                for line in (Path(td) / "self-trust.jsonl").read_text().splitlines()
            ]
            self.assertEqual([event["event_type"] for event in self_events], ["plugin.failed"])

    def test_handoff_output_path_must_stay_inside_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = self._catalog(td)
            proc = self._run(
                "--catalog",
                str(catalog),
                "handoff",
                "security-threat-model",
                "--task",
                "model this repo",
                "--out",
                "../escape.json",
                cwd=Path(td),
            )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("--out must stay inside", proc.stderr)

    def test_catalog_refresh_rejects_output_escape(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run(
                "catalog",
                "refresh",
                "--source-path",
                str(FIXTURE_SKILLS),
                "--ref",
                "fixture-sha",
                "--out",
                "../catalog.json",
                cwd=Path(td),
            )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("--out must stay inside", proc.stderr)
    def test_catalog_refresh_rejects_work_dir_escape(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run(
                "catalog",
                "refresh",
                "--source-path",
                str(FIXTURE_SKILLS),
                "--ref",
                "fixture-sha",
                "--out",
                "catalog.json",
                "--work-dir",
                "../tmp",
                cwd=Path(td),
            )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("--work-dir must stay inside", proc.stderr)


    def test_run_rejects_audit_log_escape_before_writing(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = self._catalog(td)
            proc = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                "../audit.jsonl",
                "run",
                "openai-docs",
                "--",
                "explain plugins",
                cwd=Path(td),
            )

        self.assertEqual(proc.returncode, 1)
        self.assertIn("--audit-log must stay inside", proc.stderr)

    def test_write_paths_reject_absolute_paths(self):
        with tempfile.TemporaryDirectory() as td:
            catalog = self._catalog(td)
            absolute = str(Path(td) / "absolute.json")

            handoff = self._run(
                "--catalog",
                str(catalog),
                "handoff",
                "security-threat-model",
                "--task",
                "model this repo",
                "--out",
                absolute,
                cwd=Path(td),
            )
            self.assertEqual(handoff.returncode, 1)
            self.assertIn("--out must be relative", handoff.stderr)

            catalog_refresh = self._run(
                "catalog",
                "refresh",
                "--source-path",
                str(FIXTURE_SKILLS),
                "--ref",
                "fixture-sha",
                "--out",
                absolute,
                cwd=Path(td),
            )
            self.assertEqual(catalog_refresh.returncode, 1)
            self.assertIn("--out must be relative", catalog_refresh.stderr)

            audit = self._run(
                "--catalog",
                str(catalog),
                "--audit-log",
                absolute,
                "run",
                "openai-docs",
                "--",
                "explain plugins",
                cwd=Path(td),
            )
            self.assertEqual(audit.returncode, 1)
            self.assertIn("--audit-log must be relative", audit.stderr)

            work_dir = self._run(
                "catalog",
                "refresh",
                "--source-path",
                str(FIXTURE_SKILLS),
                "--ref",
                "fixture-sha",
                "--out",
                "catalog-2.json",
                "--work-dir",
                absolute,
                cwd=Path(td),
            )
            self.assertEqual(work_dir.returncode, 1)
            self.assertIn("--work-dir must be relative", work_dir.stderr)


if __name__ == "__main__":
    unittest.main()
