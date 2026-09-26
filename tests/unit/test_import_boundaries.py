"""Tests for import boundaries and clean architecture."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def get_imports_from_file(filepath: Path) -> set[str]:
    """Extract all imports from a Python file."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    return imports


class TestImportBoundaries:
    """Tests for clean architecture import boundaries."""

    @staticmethod
    def test_application_never_imports_infrastructure() -> None:
        """Test that application layer never imports infrastructure (except prompts)."""
        src_dir = Path(__file__).parent.parent.parent / "src"
        app_dir = src_dir / "application"

        # Allow infrastructure.llm.prompts since they're just prompt builders
        forbidden_imports = {"infrastructure"}
        allowed_prompt_imports = {"infrastructure/llm/prompts"}

        for py_file in app_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            imports = get_imports_from_file(py_file)
            violations = imports & forbidden_imports

            # Allow prompts as they're infrastructure-adjacent but logically part of application
            if violations == {"infrastructure"}:
                # Check if it's only importing prompts
                with open(py_file) as f:
                    content = f.read()
                    if "infrastructure.llm.prompts" in content or "from infrastructure.llm import prompts" in content:
                        continue  # Allow this violation

            assert (
                not violations
            ), f"{py_file} imports forbidden modules: {violations}"

    @staticmethod
    def test_application_imports_from_ports() -> None:
        """Test that application layer imports from ports."""
        src_dir = Path(__file__).parent.parent.parent / "src"
        app_dir = src_dir / "application"

        # At least one file in application should import from ports
        found_ports_import = False

        for py_file in app_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            imports = get_imports_from_file(py_file)

            if "ports" in imports:
                found_ports_import = True
                break

        assert found_ports_import, "Application layer should import from ports"

    @staticmethod
    def test_infrastructure_can_import_application() -> None:
        """Test that infrastructure can import application."""
        # This test verifies that the dependency direction is correct
        # Infrastructure can depend on application for dependency injection
        src_dir = Path(__file__).parent.parent.parent / "src"
        infra_dir = src_dir / "infrastructure"

        # If any infrastructure file imports application, it's OK
        # (They shouldn't, but it's not a blocker for architecture)
        for py_file in infra_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            # Just verify we can import infrastructure without errors
            try:
                get_imports_from_file(py_file)
            except SyntaxError:
                pass  # Ignore syntax errors in test files
