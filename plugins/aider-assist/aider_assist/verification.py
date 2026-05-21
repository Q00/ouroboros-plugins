from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class VerificationResult:
    name: str
    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def run_command(name: str, command: str, repo_root: Path, timeout: int = 3600) -> VerificationResult:
    completed = subprocess.run(command, cwd=repo_root, shell=True, text=True, capture_output=True, check=False, timeout=timeout)
    return VerificationResult(name=name, command=command, exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)


def run_verifications(test_cmd: str | None, lint_cmd: str | None, repo_root: Path, timeout: int = 3600) -> list[VerificationResult]:
    results: list[VerificationResult] = []
    if lint_cmd:
        results.append(run_command("lint", lint_cmd, repo_root, timeout))
    if test_cmd:
        results.append(run_command("test", test_cmd, repo_root, timeout))
    return results


def serialize(results: list[VerificationResult]) -> list[dict[str, object]]:
    return [asdict(result) | {"passed": result.passed} for result in results]


def all_passed(results: list[VerificationResult]) -> bool:
    return all(result.passed for result in results)


def failure_context(results: list[VerificationResult]) -> str:
    chunks: list[str] = []
    for result in results:
        if result.passed:
            continue
        chunks.append(f"{result.name} command failed: {result.command}\nexit={result.exit_code}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return "\n\n".join(chunks)
