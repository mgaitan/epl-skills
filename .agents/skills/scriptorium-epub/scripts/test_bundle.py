#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Contrato portable de la skill, sin manuales fuente ni herramientas externas."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((SKILL / "scripts").glob("*.py"))
MARKDOWN = [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]


def test_skill_frontmatter_matches_directory_and_trigger_contract():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    name = re.search(r"^name: (.+)$", frontmatter, re.MULTILINE)
    description = re.search(r'^description: "(.+)"$', frontmatter, re.MULTILINE)
    assert name is not None and name[1] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name[1])
    assert description is not None and 1 <= len(description[1]) <= 1024


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_scripts_have_uv_metadata_pathlib_and_functional_tests(script: Path):
    text = script.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env -S uv run --script\n")
    block = re.search(r"# /// script\n(.*?)# ///", text, re.DOTALL)
    assert block is not None
    metadata = tomllib.loads(
        "\n".join(line.removeprefix("# ") for line in block[1].splitlines())
    )
    assert metadata["requires-python"] == ">=3.12"
    assert isinstance(metadata["dependencies"], list)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name not in {"os.path", "unittest"} for alias in node.names
            )
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {"os.path", "unittest"}
        if isinstance(node, ast.Attribute):
            assert ast.unparse(node) != "os.path"
    if script.name.startswith("test_"):
        assert any(
            isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
            for n in tree.body
        )
        assert not any(isinstance(n, ast.ClassDef) for n in tree.body)


@pytest.mark.parametrize("document", MARKDOWN, ids=lambda p: p.name)
def test_local_markdown_links_exist_without_source_manuals(document: Path):
    for target in re.findall(r"\]\(([^)\s]+)\)", document.read_text(encoding="utf-8")):
        uri = urlsplit(target)
        if not uri.scheme and uri.path:
            assert (document.parent / unquote(uri.path)).exists(), (document, target)


def test_only_the_immutable_template_is_bundled_as_epub():
    publications = sorted(SKILL.rglob("*.epub"))
    assert publications == [SKILL / "resources" / "epub-base-epl-r2.1.epub"]
    assert not list(SKILL.rglob("*.psd"))
    assert hashlib.sha256(publications[0].read_bytes()).hexdigest() == (
        "bc2d570be7174f7dd8a6fadba58bf925570949f38decd913a286f2f1a3e38940"
    )


def test_manual_alert_catalog_is_data_not_an_autocorrection_program():
    rules = json.loads(
        (SKILL / "resources" / "manual-regex.json").read_text(encoding="utf-8")
    )
    assert len(rules) == 26
    assert len({rule["id"] for rule in rules}) == len(rules)
    assert all(rule["status"] == "alerta" and rule["source"] for rule in rules)
    assert sum(rule["kind"] == "literal" for rule in rules) == 24
    assert sum(not rule["stdlib_re_compatible"] for rule in rules) == 2
