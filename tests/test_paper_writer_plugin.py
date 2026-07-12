from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO / "plugins" / "paper-writer"


def make_target_repo(root: Path) -> None:
    (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "WHITEPAPER.md").write_text("# Whitepaper\n", encoding="utf-8")
    (root / "spec").mkdir()
    (root / "spec" / "core.md").write_text("# Core Spec\n", encoding="utf-8")
    (root / "rfds").mkdir()
    (root / "rfds" / "0001-design.md").write_text("# RFD 1: Design\n", encoding="utf-8")
    (root / "domain-packs" / "coding").mkdir(parents=True)
    (root / "domain-packs" / "coding" / "pack.md").write_text("# Coding\n", encoding="utf-8")
    (root / "domain-packs" / "billing").mkdir(parents=True)
    (root / "domain-packs" / "billing" / "pack.md").write_text("# Billing\n", encoding="utf-8")
    (root / "conformance").mkdir()
    (root / "conformance" / "suite.md").write_text("# Suite\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_demo.py").write_text(
        "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n",
        encoding="utf-8",
    )
    (root / "src").mkdir()
    (root / "src" / "core.py").write_text("VALUE = 1\n\n\ndef run():\n    return VALUE\n", encoding="utf-8")
    (root / "artifacts").mkdir()
    (root / "artifacts" / "study.json").write_text(
        json.dumps({"aggregate": {"counts": {"recorded": 4, "accepted": 1}}}),
        encoding="utf-8",
    )


class PaperWriterPluginTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "ouroboros_paper_writer", *args],
            cwd=REPO,
            env={**os.environ, "PYTHONPATH": str(PLUGIN_PATH)},
            capture_output=True,
            text=True,
            check=False,
        )

    def _prepare_through_gap(self, root: Path, test_log: Path | None = None) -> dict:
        proc = self._run(
            "prepare",
            str(root),
            "--thesis",
            "A contract plane is required to extend agent protocols across domains.",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        harvest_args = ["harvest", str(root)]
        if test_log is not None:
            harvest_args += ["--test-log", str(test_log)]
        proc = self._run(*harvest_args)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = self._run("gap", str(root))
        return json.loads(proc.stdout)

    def test_inspect_reports_evidence_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            proc = self._run("inspect", str(root))

        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["evidence_sources"]["spec"])
        self.assertTrue(payload["evidence_sources"]["domain-packs"])

    def test_inspect_empty_repo_not_ready(self):
        with tempfile.TemporaryDirectory() as td:
            proc = self._run("inspect", td)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["status"], "missing_prerequisites")

    def test_gap_unsupported_without_test_log(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            payload = self._prepare_through_gap(root)
            gap = json.loads((root / ".ouroboros" / "paper-writer" / "gap_report.json").read_text())

        self.assertEqual(payload["status"], "evidence_gaps")
        c3 = next(claim for claim in gap["claims"] if claim["id"] == "C3")
        self.assertEqual(c3["status"], "unsupported")
        actions = {action["action"] for action in c3["suggested_actions"]}
        self.assertIn("run_additional_experiment", actions)
        self.assertIn("downgrade_claim", actions)
        auto = next(
            action for action in c3["suggested_actions"]
            if action["action"] == "run_additional_experiment"
        )
        self.assertEqual(auto["entrypoint"], "ouroboros_start_auto")
        self.assertIn("test_log", auto["auto_goal"])

    def test_full_pipeline_with_test_log_and_compose(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            test_log = root / "pytest.log"
            test_log.write_text("==== 12 passed, 1 skipped in 3.21s ====\n", encoding="utf-8")

            payload = self._prepare_through_gap(root, test_log=test_log)
            self.assertEqual(payload["status"], "writing_ready")
            self.assertTrue(payload["summary"]["writing_ready"])

            proc = self._run("brief", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            brief = (root / ".ouroboros" / "paper-writer" / "writing_brief.md").read_text()
            self.assertIn("claude-opus-4-8", brief)
            self.assertIn("## Claims", brief)
            self.assertIn("[E-...]", brief)
            self.assertIn("Reproducibility Statement", brief)

            bundle = json.loads(
                (root / ".ouroboros" / "paper-writer" / "research_bundle.json").read_text()
            )
            self.assertEqual(bundle["summary"]["pytest"]["passed"], 12)
            experiment_items = [e for e in bundle["evidence"] if e["kind"] == "experiment"]
            self.assertTrue(
                any(e["path"] == "artifacts/study.json" for e in experiment_items)
            )
            study_item = next(e for e in experiment_items if e["path"] == "artifacts/study.json")
            self.assertEqual(study_item["detail"]["aggregate"], {"recorded": 4, "accepted": 1})
            evidence_id = bundle["evidence"][0]["id"]

            sections = [
                "Abstract", "Introduction", "Related Work", "Design", "Evaluation",
                "Discussion and Limitations", "Conclusion", "Reproducibility Statement",
            ]
            draft_lines = ["# Demo Paper", ""]
            for section in sections:
                draft_lines += [
                    f"## {section}",
                    "",
                    f"C1 C2 C3 C4 as measured [{evidence_id}], following [cite:demo].",
                    "",
                ]
            draft_lines += [
                "![F1: System architecture overview](figures/f1-architecture.pdf)",
                "",
                "![F2: Governed run pipeline](figures/f2-pipeline.pdf)",
                "",
                "![F3: Headline results](figures/f3-results.pdf)",
                "",
            ]
            draft_lines += [
                "| A & B | C_D |",
                "|---|---|",
                "| **bold** 100% | `code` |",
                "",
                "A *multi",
                "line emphasis* paragraph.",
                "",
                "- first bullet",
                "- second bullet",
                "",
            ]
            draft = root / "draft.md"
            draft.write_text("\n".join(draft_lines), encoding="utf-8")

            proc = self._run("compose", str(root), "--draft", str(draft))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            handoff = json.loads(proc.stdout)
            self.assertEqual(handoff["status"], "verified")
            self.assertEqual(handoff["verification"]["failures"], [])
            self.assertTrue((root / ".ouroboros" / "paper-writer" / "paper.md").is_file())
            self.assertTrue((root / ".ouroboros" / "paper-writer" / "handoff.md").is_file())

            contract = json.loads(
                (root / ".ouroboros" / "paper-writer" / "paper_contract.json").read_text()
            )
            self.assertIn("web_research_plan", contract)
            self.assertTrue(contract["web_research_plan"]["queries"])
            self.assertIn("host query:", brief)

            proc = self._run("latex", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            latex_payload = json.loads(proc.stdout)
            tex = Path(latex_payload["tex_path"]).read_text(encoding="utf-8")
            bib = Path(latex_payload["bib_path"]).read_text(encoding="utf-8")
            self.assertIn(r"\begin{abstract}", tex)
            self.assertIn(r"\section{Introduction}", tex)
            self.assertIn(r"\evtag{" + evidence_id + "}", tex)
            self.assertIn(r"\bibliography{references}", tex)
            self.assertIn("UNRESOLVED CITATION: demo", bib)
            self.assertEqual(latex_payload["unresolved_citations"], ["demo"])
            self.assertIn(r"\emph{multi line emphasis}", tex)
            self.assertIn(r"\item first bullet", tex)
            self.assertIn(r"\includegraphics[width=\linewidth]{figures/f1-architecture.pdf}", tex)
            self.assertIn(r"\caption{F1: System architecture overview}", tex)
            self.assertEqual(latex_payload["style"], "generic-preprint")

            (root / ".ouroboros" / "paper-writer" / "iclr2099_conference.sty").write_text(
                "% fake venue style for test\n", encoding="utf-8"
            )
            (root / ".ouroboros" / "paper-writer" / "iclr2099_conference.bst").write_text(
                "% fake bst\n", encoding="utf-8"
            )
            proc = self._run("latex", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            latex_payload = json.loads(proc.stdout)
            self.assertEqual(latex_payload["style"], "iclr2099_conference")
            tex = Path(latex_payload["tex_path"]).read_text(encoding="utf-8")
            self.assertIn(r"\usepackage{iclr2099_conference,times}", tex)
            self.assertIn(r"\bibliographystyle{iclr2099_conference}", tex)
            self.assertIn(r"%\iclrfinalcopy", tex)
            self.assertNotIn("*", tex.split(r"\begin{abstract}")[1].split(r"\bibliography")[0].replace(r"$\times$", ""))

            (root / ".ouroboros" / "paper-writer" / "iclr2099_conference.sty").unlink()
            (root / ".ouroboros" / "paper-writer" / "iclr2099_conference.bst").unlink()
            (root / ".ouroboros" / "paper-writer" / "icml2099.sty").write_text(
                "% fake icml style for test\n", encoding="utf-8"
            )
            (root / ".ouroboros" / "paper-writer" / "icml2099.bst").write_text(
                "% fake bst\n", encoding="utf-8"
            )
            proc = self._run("latex", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            latex_payload = json.loads(proc.stdout)
            self.assertEqual(latex_payload["style"], "icml2099")
            tex = Path(latex_payload["tex_path"]).read_text(encoding="utf-8")
            self.assertIn(r"\usepackage{icml2099}", tex)
            self.assertIn(r"\twocolumn[", tex)
            self.assertIn(r"\icmltitle{", tex)
            self.assertIn(r"\printAffiliationsAndNotice{}", tex)
            self.assertIn(r"\bibliographystyle{icml2099}", tex)
            self.assertIn(r"\begin{table*}[t]", tex)
            self.assertNotIn(r"\begin{table}[ht]", tex)

    def test_icml_venue_contract_and_reviewer_criteria(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            proc = self._run(
                "prepare",
                str(root),
                "--thesis",
                "Agent claims need deterministic verification.",
                "--venue",
                "icml",
                "--page-limit",
                "4",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            contract = json.loads(
                (root / ".ouroboros" / "paper-writer" / "paper_contract.json").read_text()
            )

        self.assertEqual(contract["venue"]["name"], "ICML")
        self.assertEqual(contract["venue"]["page_limit_main_text"], 4)
        self.assertTrue(contract["venue"]["review_criteria"])
        self.assertTrue(
            any("automatic desk reject" in item for item in contract["venue"]["readiness_checklist"])
        )

        sys.path.insert(0, str(PLUGIN_PATH))
        try:
            from ouroboros_paper_writer.contract import REVIEW_PERSONAS
            from ouroboros_paper_writer.report import build_reviewer_brief
        finally:
            sys.path.pop(0)
        brief = build_reviewer_brief(
            contract,
            dict(REVIEW_PERSONAS[0]),
            paper_path="paper.md",
            bundle_path="bundle.json",
            gap_path="gap.json",
            output_path="review.json",
        )
        self.assertIn("Venue review criteria", brief)
        self.assertIn("Claims and evidence", brief)

    def test_compose_rejects_fabricated_evidence_and_missing_sections(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            test_log = root / "pytest.log"
            test_log.write_text("==== 3 passed in 0.10s ====\n", encoding="utf-8")
            self._prepare_through_gap(root, test_log=test_log)

            draft = root / "draft.md"
            draft.write_text(
                "## Abstract\n\nC1 only, with a fabricated number [E-FAKE-999].\n",
                encoding="utf-8",
            )
            proc = self._run("compose", str(root), "--draft", str(draft))

        self.assertEqual(proc.returncode, 1)
        handoff = json.loads(proc.stdout)
        self.assertEqual(handoff["status"], "rejected")
        failures = "\n".join(handoff["verification"]["failures"])
        self.assertIn("E-FAKE-999", failures)
        self.assertIn("missing required sections", failures)
        self.assertIn("never references claims", failures)

    def test_empty_adapter_dirs_are_not_counted_as_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            (root / "adapters" / "reserved-a").mkdir(parents=True)
            (root / "adapters" / "reserved-b").mkdir(parents=True)
            claims = root / "claims.json"
            claims.write_text(
                json.dumps(
                    [
                        {
                            "id": "C1",
                            "statement": "adapters exist",
                            "evidence_required": [{"kind": "adapter", "min_count": 1}],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            proc = self._run(
                "prepare", str(root), "--thesis", "t", "--claims-file", str(claims)
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = self._run("harvest", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = self._run("gap", str(root))
            payload = json.loads(proc.stdout)
            bundle = json.loads(
                (root / ".ouroboros" / "paper-writer" / "research_bundle.json").read_text()
            )

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(payload["summary"]["unsupported"], 1)
        adapter_items = [item for item in bundle["evidence"] if item["kind"] == "adapter"]
        self.assertEqual(len(adapter_items), 2)
        self.assertTrue(all(item["detail"]["file_count"] == 0 for item in adapter_items))

    def test_review_briefs_and_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            test_log = root / "pytest.log"
            test_log.write_text("==== 3 passed in 0.10s ====\n", encoding="utf-8")
            self._prepare_through_gap(root, test_log=test_log)

            sections = [
                "Abstract", "Introduction", "Related Work", "Design", "Evaluation",
                "Discussion and Limitations", "Conclusion", "Reproducibility Statement",
            ]
            draft = root / "draft.md"
            draft.write_text(
                "# T\n\n" + "\n\n".join(f"## {s}\n\nC1 C2 C3 C4." for s in sections),
                encoding="utf-8",
            )
            proc = self._run("compose", str(root), "--draft", str(draft))
            self.assertEqual(proc.returncode, 1)
            handoff = json.loads(proc.stdout)
            self.assertTrue(
                any("F1" in failure for failure in handoff["verification"]["failures"])
            )
            draft.write_text(
                "# T\n\n"
                + "\n\n".join(f"## {s}\n\nC1 C2 C3 C4." for s in sections)
                + "\n\n![F1: arch](f1.pdf)\n\n![F2: pipe](f2.pdf)\n\n![F3: results](f3.pdf)\n",
                encoding="utf-8",
            )
            proc = self._run("compose", str(root), "--draft", str(draft))
            self.assertEqual(proc.returncode, 0, proc.stderr)

            proc = self._run("review", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "review_briefs_ready")
            self.assertEqual(payload["reviewer_model"], "claude-opus-4-8")
            self.assertEqual(len(payload["briefs"]), 3)
            self.assertIn("FRESH subagent", payload["note"])

            reviews_dir = root / ".ouroboros" / "paper-writer" / "reviews"
            for rid, score, weaknesses in (
                ("R1", 7, []),
                ("R2", 6, [{"severity": "minor", "text": "tighten related work"}]),
                ("R3", 8, []),
            ):
                (reviews_dir / f"{rid}.json").write_text(
                    json.dumps(
                        {
                            "reviewer_id": rid,
                            "summary": "s",
                            "strengths": ["a"],
                            "weaknesses": weaknesses,
                            "questions": [],
                            "score": score,
                            "confidence": 4,
                        }
                    ),
                    encoding="utf-8",
                )
            proc = self._run("review", str(root), "--ingest")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["status"], "review_passed")

            major = {
                "reviewer_id": "R1",
                "summary": "s",
                "strengths": [],
                "weaknesses": [{"severity": "major", "text": "no second domain"}],
                "questions": [],
                "score": 4,
                "confidence": 5,
            }
            (reviews_dir / "R1.json").write_text(json.dumps(major), encoding="utf-8")
            proc = self._run("review", str(root), "--ingest")
            self.assertEqual(proc.returncode, 1)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "revision_required")
            self.assertTrue(payload["revision_actions"])

            proc = self._run("revise", str(root))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["status"], "revision_brief_ready")
            self.assertEqual(payload["round"], 1)
            brief = Path(payload["brief_path"]).read_text(encoding="utf-8")
            self.assertIn("Evidence-bound", brief)
            self.assertIn("no second domain", brief)
            self.assertTrue(
                (root / ".ouroboros" / "paper-writer" / "rounds" / "round-1" / "review_report.json").is_file()
            )
            ledger = json.loads(
                (root / ".ouroboros" / "paper-writer" / "loop_ledger.json").read_text()
            )
            self.assertEqual(len(ledger["rounds"]), 1)

            for round_index in (2, 3):
                for rid in ("R1", "R2", "R3"):
                    (reviews_dir / f"{rid}.json").write_text(json.dumps(major | {"reviewer_id": rid}), encoding="utf-8")
                self._run("review", str(root), "--ingest")
                proc = self._run("revise", str(root))
            payload = json.loads(proc.stdout)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(payload["status"], "loop_budget_exhausted")
            self.assertTrue(any("stagnation" in w for w in payload["warnings"]))

    def test_prepare_rejects_bad_claims_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_target_repo(root)
            claims = root / "claims.json"
            claims.write_text(
                json.dumps([{"id": "C1", "statement": "x", "evidence_required": [{"kind": "nope"}]}]),
                encoding="utf-8",
            )
            proc = self._run("prepare", str(root), "--thesis", "t", "--claims-file", str(claims))

        self.assertEqual(proc.returncode, 1)
        self.assertIn("unknown evidence kind", proc.stderr)


if __name__ == "__main__":
    unittest.main()
