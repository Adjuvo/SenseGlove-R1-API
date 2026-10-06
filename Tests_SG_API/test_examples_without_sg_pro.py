"""
Ensure public examples work without SG_Pro (as filtered from GitHub releases).

Merge/release run Tests_SG_API/ (with Tests_SG_Pro/ and Tests_install_process/), so these gate merges before auto-release.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
SG_API_DIR = REPO_ROOT / "SG_API"


def example_files() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.py"))


def test_public_examples_exist():
    assert EXAMPLES_DIR.is_dir()
    assert example_files(), "expected at least one examples/*.py file"


@pytest.mark.parametrize("example", example_files(), ids=lambda p: p.name)
def test_example_does_not_reference_sg_pro(example: Path):
    source = example.read_text(encoding="utf-8")
    assert "SG_Pro" not in source, (
        f"{example.name} references SG_Pro; public releases exclude SG_API/SG_Pro/"
    )


@pytest.fixture(scope="module")
def public_release_tree(tmp_path_factory) -> Path:
    """Simulate GitHub release tree: SG_API without SG_Pro + examples."""
    root = tmp_path_factory.mktemp("public_release")
    shutil.copytree(
        SG_API_DIR,
        root / "SG_API",
        ignore=shutil.ignore_patterns("SG_Pro", "__pycache__", "*.pyc", ".pytest_cache"),
    )
    shutil.copytree(EXAMPLES_DIR, root / "examples")
    assert not (root / "SG_API" / "SG_Pro").exists()
    return root


@pytest.mark.parametrize("example", example_files(), ids=lambda p: p.name)
def test_example_compiles_without_sg_pro(example: Path, public_release_tree: Path):
    public_example = public_release_tree / "examples" / example.name
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(public_example)],
        cwd=public_release_tree,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"py_compile failed for {example.name} without SG_Pro:\n"
        f"{result.stdout}\n{result.stderr}"
    )


_IMPORT_CHECKER = r"""
import ast
import importlib
import sys
from pathlib import Path

root = Path(sys.argv[1])
example = Path(sys.argv[2])
sys.path.insert(0, str(root))

if (root / "SG_API" / "SG_Pro").exists():
    raise SystemExit("SG_Pro must not be present in the public test tree")

tree = ast.parse(example.read_text(encoding="utf-8"), filename=str(example))
for node in tree.body:
    if isinstance(node, ast.Import):
        for alias in node.names:
            importlib.import_module(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module is None:
            continue
        for alias in node.names:
            if alias.name == "*":
                importlib.import_module(node.module)
                continue
            # Match `from pkg import name` (attribute or submodule).
            full_name = f"{node.module}.{alias.name}"
            try:
                importlib.import_module(full_name)
            except ImportError:
                mod = importlib.import_module(node.module)
                if not hasattr(mod, alias.name):
                    raise ImportError(
                        f"cannot import name {alias.name!r} from {node.module!r}"
                    ) from None
print("OK", example.name)
"""


@pytest.mark.parametrize("example", example_files(), ids=lambda p: p.name)
def test_example_imports_resolve_without_sg_pro(
    example: Path, public_release_tree: Path
):
    public_example = public_release_tree / "examples" / example.name
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _IMPORT_CHECKER,
            str(public_release_tree),
            str(public_example),
        ],
        cwd=public_release_tree,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"Imports failed for {example.name} without SG_Pro:\n"
        f"{result.stdout}\n{result.stderr}"
    )
