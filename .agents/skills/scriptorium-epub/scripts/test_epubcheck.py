#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Integración CLI de EPUBCheck, sin Java, Docker, daemon ni red.

Runner: uv run --with=pytest pytest <scripts>/test_epubcheck.py -q
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

import epub
import pytest


@pytest.fixture(autouse=True)
def process(monkeypatch):
    state = {
        "calls": [],
        "returncode": 0,
        "stdout": "EPUBCheck: sin errores\n",
        "stderr": "",
        "exception": None,
    }

    def run(command, **kwargs):
        state["calls"].append((command, kwargs))
        if state["exception"] is not None:
            raise state["exception"]
        return subprocess.CompletedProcess(
            command, state["returncode"], state["stdout"], state["stderr"]
        )

    monkeypatch.setattr(epub.subprocess, "run", run)
    return state


@pytest.fixture
def audited_book(tmp_path, monkeypatch):
    # La lectura ZIP es real; aislar el resultado del auditor local de EPUBCheck.
    book = tmp_path / "Libro con espacios, edición.epub"
    with epub.zipfile.ZipFile(book, "w") as archive:
        archive.writestr("mimetype", epub.MIMETYPE)

    def report(self):
        return {
            "counts": {"error": 0, "warning": 1},
            "findings": [
                {"level": "warning", "code": "LOCAL", "file": "", "message": "Revisar"}
            ],
            "skipped": [
                {"code": "EPUB_SCHEMA", "reason": "Ejecutar EPUBCheck"},
                {"code": "EDITORIAL_VISUAL", "reason": "Revisión pendiente"},
            ],
            "compliance_certified": False,
        }

    monkeypatch.setattr(epub.Audit, "run", report)
    return book


@pytest.fixture
def jar(tmp_path):
    path = tmp_path / "EPUBCheck local, versión.jar"
    path.write_bytes(b"JAR simulado; nunca se ejecuta")
    return path


def cli_report(book, capsys, *options):
    status = epub.main(["check", str(book), "--json", *map(str, options)])
    output = capsys.readouterr()
    assert output.err == ""
    report = json.loads(output.out)
    counts = Counter(f["level"] for f in report["findings"])
    assert report["counts"] == {"error": counts["error"], "warning": counts["warning"]}
    assert report["compliance_certified"] is False
    return status, report


def test_default_image_is_pinned():
    assert epub.DEFAULT_EPUBCHECK_IMAGE == (
        "yamamotoatshoeisha/epubcheck:epub5.4.0_jdk27"
        "@sha256:c69bb8ea600157e774b7682b15f9a3d49f7d6b45c187966ca95fa4d04c3dc503"
    )


@pytest.mark.parametrize(
    "name", ["Libro con espacios, edición.epub", 'Libro, "citado".epub']
)
def test_docker_command_mounts_only_resolved_file(tmp_path, process, name):
    book = tmp_path / name
    book.write_bytes(b"EPUB simulado")
    link = tmp_path / "enlace.epub"
    link.symlink_to(book)
    result = epub.run_epubcheck_docker(link)
    command, options = process["calls"][0]
    mount = command[command.index("--mount") + 1]
    assert list(csv.reader(io.StringIO(mount))) == [
        ["type=bind", f"source={book.resolve()}", "target=/data/book.epub", "readonly"]
    ]
    assert command == [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        "--mount",
        mount,
        "--",
        epub.DEFAULT_EPUBCHECK_IMAGE,
        "/data/book.epub",
    ]
    assert options == {
        "capture_output": True,
        "text": True,
        "errors": "replace",
        "timeout": 300,
        "check": False,
        "shell": False,
    }
    assert result == {
        "command": command,
        "returncode": 0,
        "stdout": process["stdout"],
        "stderr": "",
        "completed": True,
    }
    assert book.read_bytes() == b"EPUB simulado"


def test_jar_command_remains_available(audited_book, jar, process):
    result = epub.run_epubcheck(audited_book, jar)
    command, options = process["calls"][0]
    assert command == ["java", "-jar", str(jar.resolve()), str(audited_book.resolve())]
    assert options["timeout"] == 120
    assert options["shell"] is False
    assert result["command"] == command
    assert result["returncode"] == 0
    assert result["completed"] is True


@pytest.mark.parametrize("image", [None, "example.org/epubcheck:custom"])
def test_cli_optional_docker_image(audited_book, process, capsys, image):
    options = ["--epubcheck-docker"] + ([] if image is None else [image])
    status, report = cli_report(audited_book, capsys, *options)
    assert status == 0
    assert len(process["calls"]) == 1
    assert process["calls"][0][0][-2:] == [
        image or epub.DEFAULT_EPUBCHECK_IMAGE,
        "/data/book.epub",
    ]
    assert report["epubcheck"]["completed"] is True
    assert [s["code"] for s in report["skipped"]] == ["EDITORIAL_VISUAL"]
    assert report["counts"] == {"error": 0, "warning": 1}


@pytest.mark.parametrize("backend", ["jar", "docker"])
def test_success_does_not_erase_local_errors(
    audited_book, jar, process, capsys, monkeypatch, backend
):
    original = epub.Audit.run

    def report_with_error(self):
        report = original(self)
        report["findings"].append(
            {
                "level": "error",
                "code": "LOCAL_ERROR",
                "file": "",
                "message": "Error local",
            }
        )
        report["counts"]["error"] += 1
        return report

    monkeypatch.setattr(epub.Audit, "run", report_with_error)
    options = ["--epubcheck", jar] if backend == "jar" else ["--epubcheck-docker"]
    status, report = cli_report(audited_book, capsys, *options)
    assert status == 1
    assert report["counts"]["error"] == 1
    assert "EPUB_SCHEMA" not in {s["code"] for s in report["skipped"]}


@pytest.mark.parametrize("options", [[], ["--strict"]])
def test_no_validator_option_never_runs_external(
    audited_book, process, capsys, options
):
    status, report = cli_report(audited_book, capsys, *options)
    assert status == int(bool(options))
    assert process["calls"] == []
    assert "epubcheck" not in report
    assert "EPUB_SCHEMA" in {s["code"] for s in report["skipped"]}


@pytest.mark.parametrize("reverse", [False, True])
def test_cli_backends_are_mutually_exclusive(
    audited_book, jar, process, capsys, reverse
):
    options = [["--epubcheck", str(jar)], ["--epubcheck-docker"]]
    if reverse:
        options.reverse()
    with pytest.raises(SystemExit) as exc:
        epub.main(["check", str(audited_book), *options[0], *options[1]])
    assert exc.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err
    assert process["calls"] == []


@pytest.mark.parametrize("backend", ["jar", "docker"])
@pytest.mark.parametrize("returncode", [1, 125, 126, -9])
def test_nonzero_exit_is_a_finding(
    audited_book, jar, process, capsys, backend, returncode
):
    process.update(
        returncode=returncode,
        stdout="Resultado parcial",
        stderr="Validación o ejecutor falló",
    )
    options = ["--epubcheck", jar] if backend == "jar" else ["--epubcheck-docker"]
    status, report = cli_report(audited_book, capsys, *options)
    assert status == 1
    assert report["counts"] == {"error": 1, "warning": 1}
    assert report["findings"][-1]["code"] == "EPUBCHECK"
    assert str(returncode) in report["findings"][-1]["message"]
    assert report["epubcheck"]["returncode"] == returncode
    assert report["epubcheck"]["stdout"] == process["stdout"]
    assert report["epubcheck"]["stderr"] == process["stderr"]
    assert report["epubcheck"]["completed"] is True
    assert "EPUB_SCHEMA" in {s["code"] for s in report["skipped"]}


@pytest.mark.parametrize("backend", ["jar", "docker"])
@pytest.mark.parametrize("failure", ["missing", "permission", "timeout"])
def test_execution_failures_are_reported(
    audited_book, jar, process, capsys, backend, failure
):
    if failure == "timeout":
        process["exception"] = subprocess.TimeoutExpired(
            [backend], 300, output=b"salida parcial\xff", stderr=b"diagnostico parcial"
        )
    elif failure == "permission":
        process["exception"] = PermissionError("Ejecutable no permitido")
    else:
        process["exception"] = FileNotFoundError("Ejecutable no encontrado")
    options = ["--epubcheck", jar] if backend == "jar" else ["--epubcheck-docker"]
    status, report = cli_report(audited_book, capsys, *options)
    assert status == 1
    assert report["counts"]["error"] == 1
    assert report["findings"][-1]["code"] == "EPUBCHECK"
    external = report["epubcheck"]
    assert external["completed"] is False
    assert external["returncode"] is None
    assert external["command"] == process["calls"][0][0]
    assert external["error"]
    if failure == "timeout":
        assert external["stdout"] == "salida parcial\ufffd"
        assert external["stderr"] == "diagnostico parcial"
    assert "EPUB_SCHEMA" in {s["code"] for s in report["skipped"]}


def test_missing_jar_is_a_finding(audited_book, tmp_path, process, capsys):
    status, report = cli_report(
        audited_book, capsys, "--epubcheck", tmp_path / "ausente.jar"
    )
    assert status == 1
    assert report["findings"][-1]["code"] == "EPUBCHECK"
    assert "No existe JAR" in report["epubcheck"]["error"]
    assert report["epubcheck"]["completed"] is False
    assert process["calls"] == []
    assert "EPUB_SCHEMA" in {s["code"] for s in report["skipped"]}


@pytest.mark.parametrize("backend", ["jar", "docker"])
@pytest.mark.parametrize("exists", [False, True])
def test_unreadable_input_never_runs_validator(
    tmp_path, jar, process, capsys, backend, exists
):
    book = tmp_path / "roto.epub"
    if exists:
        book.write_bytes(b"No es un ZIP")
    options = ["--epubcheck", jar] if backend == "jar" else ["--epubcheck-docker"]
    status, report = cli_report(book, capsys, *options)
    assert status == 1
    assert process["calls"] == []
    assert [s["code"] for s in report["skipped"]] == ["ALL_CHECKS"]
    assert report["epubcheck"]["completed"] is False
    assert "ALL_CHECKS" in report["epubcheck"]["error"]
    assert [f["code"] for f in report["findings"]] == ["INPUT"]


@pytest.mark.parametrize("image", ["", "--privileged"])
def test_invalid_image_never_runs_docker(audited_book, process, capsys, image):
    status, report = cli_report(audited_book, capsys, "--epubcheck-docker=" + image)
    assert status == 1
    assert report["findings"][-1]["code"] == "EPUBCHECK"
    assert process["calls"] == []
    assert "EPUB_SCHEMA" in {s["code"] for s in report["skipped"]}


def test_shell_metacharacters_stay_literal(tmp_path, process):
    book = tmp_path / "libro; touch INJECTED.epub"
    book.write_bytes(b"EPUB simulado")
    image = "example.org/check:tag; touch INJECTED"
    epub.run_epubcheck_docker(book, image)
    command, options = process["calls"][0]
    assert options["shell"] is False
    assert command[-3:] == ["--", image, "/data/book.epub"]
    mount = command[command.index("--mount") + 1]
    assert f"source={book.resolve()}" in next(csv.reader(io.StringIO(mount)))
    assert len(process["calls"]) == 1
    assert not (tmp_path / "INJECTED").exists()


def test_text_output_exposes_external_diagnostics(audited_book, process, capsys):
    process.update(returncode=125, stderr="daemon unavailable")
    assert epub.main(["check", str(audited_book), "--epubcheck-docker"]) == 1
    output = capsys.readouterr()
    assert "ERROR EPUBCHECK" in output.out
    assert "daemon unavailable" in output.out
    assert "PENDIENTE EPUB_SCHEMA" in output.out
    assert output.err == ""


def test_real_audit_keeps_other_pending_checks(process, capsys):
    status, report = cli_report(epub.TEMPLATE, capsys, "--epubcheck-docker")
    assert status == 1  # La plantilla conserva contenido y metadatos de ejemplo.
    assert report["epubcheck"]["returncode"] == 0
    assert "EPUB_SCHEMA" not in {s["code"] for s in report["skipped"]}
    assert {"NAVIGATION_SEMANTICS", "EDITORIAL_VISUAL", "OFFICIAL_INI"} <= {
        s["code"] for s in report["skipped"]
    }
    assert len(process["calls"]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__)), "-q"]))
