from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class BoundaryError(ValueError):
    """Raised when a user-supplied path escapes the scan root."""


@dataclass(frozen=True)
class BoundedPath:
    raw: str
    absolute: Path
    relative: str


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_bounded_path(raw: str, *, root: Path, label: str, must_exist: bool = True) -> BoundedPath:
    if not raw:
        raise BoundaryError(f"{label} must not be empty")
    candidate = Path(raw)
    if candidate.is_absolute():
        absolute = candidate.resolve(strict=False)
    else:
        absolute = (root / candidate).resolve(strict=False)
    root_abs = root.resolve(strict=False)
    if not _inside(absolute, root_abs):
        raise BoundaryError(f"{label} must stay inside {root_abs}")
    if must_exist and not absolute.exists():
        raise BoundaryError(f"{label} does not exist: {raw}")
    rel = absolute.relative_to(root_abs).as_posix()
    return BoundedPath(raw=raw, absolute=absolute, relative=rel or ".")


def is_remote_config(config: str) -> bool:
    parsed = urlparse(config)
    if parsed.scheme in {"http", "https"}:
        return True
    if config in {"auto", "r/all", "p/default", "p/ci"}:
        return True
    if config.startswith(("p/", "r/")):
        return True
    return False
