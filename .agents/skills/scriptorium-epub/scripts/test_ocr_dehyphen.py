#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""uv run --offline --with=pytest pytest .agents/skills/scriptorium-epub/scripts/test_ocr_dehyphen.py -q"""

import json
import re
import sys
from hashlib import sha256
from pathlib import Path
from types import ModuleType

import ocr_dehyphen
import pytest

CANDIDATE = "Una palabra y una canción.\n\nOtro párrafo.\n"
DEHYPHEN_VERSION = "0.3.4-test"
ARTIFACTS = {"candidato.txt", "cambios.diff", "proveniencia.json"}


@pytest.fixture(autouse=True)
def no_real_dehyphen(monkeypatch):
    monkeypatch.setitem(sys.modules, "dehyphen", None)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    path = tmp_path / "fuente.txt"
    path.write_bytes("Una pala-\nbra y una canción.\n\nOtro párrafo.\n".encode())
    return path


@pytest.fixture
def candidate(monkeypatch):
    calls = []

    def fake_candidate(text: str, lang: str, backward: bool):
        calls.append((text, lang, backward))
        return CANDIDATE, DEHYPHEN_VERSION

    monkeypatch.setattr(ocr_dehyphen, "_candidate", fake_candidate)
    return calls


def test_artifacts_hashes_and_provenance(
    source: Path, tmp_path: Path, monkeypatch, candidate
):
    before = source.read_bytes()
    monkeypatch.chdir(tmp_path)
    output = Path("propuesta")

    result = ocr_dehyphen.propose(Path(source.name), output, "es")

    assert result == output.resolve()
    assert {path.name for path in output.iterdir()} == ARTIFACTS
    assert (output / "candidato.txt").read_bytes() == CANDIDATE.encode("utf-8")
    assert source.read_bytes() == before
    assert candidate == [(before.decode("utf-8"), "es", True)]
    provenance = json.loads((output / "proveniencia.json").read_text(encoding="utf-8"))
    assert provenance["source"] == str(source.resolve())
    assert provenance["sha256"] == sha256(before).hexdigest()
    assert (
        provenance["candidate_sha256"] == sha256(CANDIDATE.encode("utf-8")).hexdigest()
    )
    assert provenance["dehyphen"] == DEHYPHEN_VERSION
    assert provenance["lang"] == "es"
    assert provenance["forward"] is True
    assert provenance["backward"] is True
    assert provenance["fast"] is False
    assert provenance["status"] == "candidato sin cotejar"

    diff = (output / "cambios.diff").read_text(encoding="utf-8")
    assert diff.startswith("--- ")
    assert "\n+++ " in diff
    assert "\n@@ " in diff
    assert "-Una pala-\n-bra y una canción.\n" in diff
    assert "+Una palabra y una canción.\n" in diff


def test_diff_marks_source_without_final_newline(tmp_path: Path, candidate):
    source = tmp_path / "fuente.txt"
    data = "Una pala-\nbra y una canción.".encode()
    source.write_bytes(data)
    output = tmp_path / "propuesta"

    ocr_dehyphen.propose(source, output, "es")

    diff = (output / "cambios.diff").read_text(encoding="utf-8")
    assert "-bra y una canción.\n\\ No newline at end of file\n" in diff
    assert diff.count("\\ No newline at end of file\n") == 1
    assert "+Una palabra y una canción.\n" in diff
    assert (output / "candidato.txt").read_bytes() == CANDIDATE.encode("utf-8")
    assert source.read_bytes() == data
    assert candidate == [(data.decode("utf-8"), "es", True)]


@pytest.mark.parametrize("backward", [True, False])
def test_candidate_wrapper_uses_stubbed_dehyphen(monkeypatch, backward: bool):
    calls = []
    paragraphs = [["Una pala-", "bra y una canción."]]
    joined = [["Una palabra y una canción."]]
    text = "Una pala-\nbra y una canción.\n"
    stub = ModuleType("dehyphen")

    def text_to_format(value):
        calls.append(("text_to_format", value))
        return paragraphs

    class FlairScorer:
        def __init__(self, *, lang, forward=True, backward=True, fast=False):
            calls.append(("FlairScorer", lang, forward, backward, fast))

        def dehyphen(self, value):
            assert value is paragraphs
            calls.append(("dehyphen", value))
            return joined

    def format_to_text(value):
        assert value is joined
        calls.append(("format_to_text", value))
        return "Una palabra y una canción."

    def fake_version(distribution):
        calls.append(("version", distribution))
        return DEHYPHEN_VERSION

    monkeypatch.setattr(stub, "text_to_format", text_to_format, raising=False)
    monkeypatch.setattr(stub, "FlairScorer", FlairScorer, raising=False)
    monkeypatch.setattr(stub, "format_to_text", format_to_text, raising=False)
    monkeypatch.setitem(sys.modules, "dehyphen", stub)
    monkeypatch.setattr(ocr_dehyphen, "version", fake_version)

    assert ocr_dehyphen._candidate(text, "es", backward) == (
        "Una palabra y una canción.\n",
        DEHYPHEN_VERSION,
    )
    assert calls == [
        ("text_to_format", text),
        ("FlairScorer", "es", True, backward, False),
        ("dehyphen", paragraphs),
        ("format_to_text", joined),
        ("version", "dehyphen"),
    ]


@pytest.mark.parametrize("backward", [True, False])
def test_propose_direction(source: Path, tmp_path: Path, candidate, backward: bool):
    output = tmp_path / "propuesta"
    assert (
        ocr_dehyphen.propose(source, output, "es", backward=backward)
        == output.resolve()
    )
    assert candidate == [(source.read_text(encoding="utf-8"), "es", backward)]
    provenance = json.loads((output / "proveniencia.json").read_text(encoding="utf-8"))
    assert provenance["forward"] is True
    assert provenance["backward"] is backward
    assert provenance["fast"] is False


@pytest.mark.parametrize(
    "data",
    [
        "Canción.\r\nOtra línea.\r\n".encode(),
        "\ufeffCanción sin salto final".encode("utf-8"),
    ],
)
def test_source_bytes_preserved(tmp_path: Path, candidate, data: bytes):
    source = tmp_path / "fuente.txt"
    source.write_bytes(data)
    output = tmp_path / "propuesta"
    ocr_dehyphen.propose(source, output, "es")
    assert source.read_bytes() == data
    provenance = json.loads((output / "proveniencia.json").read_text(encoding="utf-8"))
    assert provenance["sha256"] == sha256(data).hexdigest()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("modelo no disponible"),
        ImportError("dehyphen no instalado"),
    ],
)
def test_model_failure_creates_nothing_and_same_destination_can_be_retried(
    source: Path, tmp_path: Path, monkeypatch, candidate, error: Exception
):
    output = tmp_path / "propuesta"
    before = source.read_bytes()
    attempted = []

    def failing_candidate(text: str, lang: str, backward: bool):
        attempted.append((text, lang, backward))
        if output.exists() or output.is_symlink():
            pytest.fail("El destino se creó antes de terminar el modelo")
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(ocr_dehyphen, "_candidate", failing_candidate)
        with pytest.raises(Exception):
            ocr_dehyphen.propose(source, output, "es")

    assert attempted == [(before.decode("utf-8"), "es", True)]
    assert not output.exists()
    assert not output.is_symlink()
    assert source.read_bytes() == before
    assert {path.name for path in tmp_path.iterdir()} == {source.name}
    assert ocr_dehyphen.propose(source, output, "es") == output.resolve()
    assert len(candidate) == 1
    assert {path.name for path in output.iterdir()} == ARTIFACTS


@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "broken-symlink"])
def test_existing_destination_preserved_without_calling_model(
    source: Path, tmp_path: Path, candidate, kind: str
):
    output = tmp_path / "propuesta"
    before = source.read_bytes()
    target = tmp_path / "destino-del-enlace"
    if kind == "directory":
        output.mkdir()
        (output / "conservar.txt").write_bytes(b"KEEP")
    elif kind == "file":
        output.write_bytes(b"KEEP")
    else:
        if kind == "symlink":
            target.mkdir()
            (target / "conservar.txt").write_bytes(b"KEEP")
        output.symlink_to(target, target_is_directory=True)

    with pytest.raises(Exception):
        ocr_dehyphen.propose(source, output, "es")

    assert candidate == []
    assert source.read_bytes() == before
    if kind == "directory":
        assert {path.name for path in output.iterdir()} == {"conservar.txt"}
        assert (output / "conservar.txt").read_bytes() == b"KEEP"
    elif kind == "file":
        assert output.read_bytes() == b"KEEP"
    else:
        assert output.is_symlink()
        assert output.readlink() == target
        if kind == "symlink":
            assert {path.name for path in target.iterdir()} == {"conservar.txt"}
            assert (target / "conservar.txt").read_bytes() == b"KEEP"
        else:
            assert not target.exists()


def test_source_cannot_be_destination(source: Path, candidate):
    before = source.read_bytes()
    with pytest.raises(Exception):
        ocr_dehyphen.propose(source, source, "es")
    assert source.read_bytes() == before
    assert candidate == []


@pytest.mark.parametrize("parent_kind", ["missing", "file"])
def test_parent_must_already_be_a_directory(
    source: Path, tmp_path: Path, candidate, parent_kind: str
):
    parent = tmp_path / "parent"
    if parent_kind == "file":
        parent.write_bytes(b"KEEP")
    output = parent / "propuesta"
    with pytest.raises(Exception):
        ocr_dehyphen.propose(source, output, "es")
    assert candidate == []
    assert not output.exists()
    if parent_kind == "file":
        assert parent.read_bytes() == b"KEEP"
    else:
        assert not parent.exists()


@pytest.mark.parametrize("data", [b"", b"texto\xff\xfe\n"])
def test_empty_or_invalid_utf8_source_rejected_before_model(
    tmp_path: Path, candidate, data: bytes
):
    source = tmp_path / "fuente.txt"
    source.write_bytes(data)
    output = tmp_path / "propuesta"
    with pytest.raises(Exception):
        ocr_dehyphen.propose(source, output, "es")
    assert candidate == []
    assert source.read_bytes() == data
    assert not output.exists()


@pytest.mark.parametrize("artifact", sorted(ARTIFACTS))
def test_write_failure_removes_created_destination_and_allows_retry(
    source: Path, tmp_path: Path, monkeypatch, candidate, artifact: str
):
    output = tmp_path / "propuesta"
    before = source.read_bytes()
    original_open = Path.open
    failed = []

    def failing_open(path, mode="r", *args, **kwargs):
        if path == output / artifact and any(flag in mode for flag in "wax+"):
            failed.append(path)
            raise OSError("fallo de escritura simulado")
        return original_open(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", failing_open)
        with pytest.raises(Exception):
            ocr_dehyphen.propose(source, output, "es")

    assert failed == [output / artifact]
    assert len(candidate) == 1
    assert not output.exists()
    assert source.read_bytes() == before
    assert {path.name for path in tmp_path.iterdir()} == {source.name}
    assert ocr_dehyphen.propose(source, output, "es") == output.resolve()
    assert len(candidate) == 2
    assert {path.name for path in output.iterdir()} == ARTIFACTS


@pytest.mark.parametrize("forward_only", [False, True])
def test_cli_success_and_forward_only(
    source: Path, tmp_path: Path, monkeypatch, candidate, forward_only: bool
):
    monkeypatch.chdir(tmp_path)
    args = [source.name, "propuesta", "--lang", "es"]
    if forward_only:
        args.append("--forward-only")
    assert ocr_dehyphen.main(args) == 0
    assert candidate == [(source.read_text(encoding="utf-8"), "es", not forward_only)]
    output = tmp_path / "propuesta"
    assert {path.name for path in output.iterdir()} == ARTIFACTS
    provenance = json.loads((output / "proveniencia.json").read_text(encoding="utf-8"))
    assert provenance["lang"] == "es"
    assert provenance["forward"] is True
    assert provenance["backward"] is (not forward_only)


@pytest.mark.parametrize(
    "kind", ["missing", "empty", "invalid-utf8", "existing-output"]
)
def test_cli_errors_are_spanish_and_leave_files_intact(
    tmp_path: Path, candidate, capsys, kind: str
):
    source = tmp_path / "fuente.txt"
    output = tmp_path / "propuesta"
    data = b"texto\xff" if kind == "invalid-utf8" else b""
    if kind == "existing-output":
        data = "Una canción.\n".encode()
        output.write_bytes(b"KEEP")
    if kind != "missing":
        source.write_bytes(data)

    assert ocr_dehyphen.main([str(source), str(output), "--lang", "es"]) == 2

    error = capsys.readouterr().err
    assert error.startswith("Error: no se pudo generar el candidato: "), error
    if kind == "invalid-utf8":
        assert re.search(r"utf-?8", error, re.IGNORECASE), error
    assert candidate == []
    if kind == "missing":
        assert not source.exists()
    else:
        assert source.read_bytes() == data
    if kind == "existing-output":
        assert output.read_bytes() == b"KEEP"
    else:
        assert not output.exists()


def test_cli_model_error_is_spanish_and_leaves_no_output(
    source: Path, tmp_path: Path, monkeypatch, capsys
):
    output = tmp_path / "propuesta"
    before = source.read_bytes()
    calls = []

    def failing_candidate(text: str, lang: str, backward: bool):
        calls.append((text, lang, backward))
        raise RuntimeError("MODEL_UNAVAILABLE")

    monkeypatch.setattr(ocr_dehyphen, "_candidate", failing_candidate)
    assert ocr_dehyphen.main([str(source), str(output), "--lang", "es"]) == 2
    error = capsys.readouterr().err
    assert error.startswith("Error: no se pudo generar el candidato: "), error
    assert "MODEL_UNAVAILABLE" in error
    assert calls == [(before.decode("utf-8"), "es", True)]
    assert not output.exists()
    assert source.read_bytes() == before


def test_cli_requires_lang(source: Path, tmp_path: Path, candidate, capsys):
    output = tmp_path / "propuesta"
    with pytest.raises(SystemExit) as exc:
        ocr_dehyphen.main([str(source), str(output)])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "--lang" in error
    assert candidate == []
    assert not output.exists()
