#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["dehyphen==0.6.0"]
# ///
"""Propone uniones de líneas/guiones OCR; nunca acepta cambios ni modifica la fuente."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from difflib import unified_diff
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path


def _candidate(text: str, lang: str, backward: bool) -> tuple[str, str]:
    # Importación diferida: --help y validación de entrada no necesitan cargar modelos.
    from dehyphen import FlairScorer, format_to_text, text_to_format

    paragraphs = text_to_format(text)
    if not paragraphs:
        raise ValueError("No hay párrafos de prosa para revisar")
    scorer = FlairScorer(lang=lang, backward=backward)
    candidate = format_to_text(scorer.dehyphen(paragraphs)) + "\n"
    if not candidate.strip():
        raise ValueError("El modelo devolvió un candidato vacío; no se creó salida")
    return candidate, version("dehyphen")


def propose(source: Path, output: Path, lang: str, *, backward: bool = True) -> Path:
    if output.exists() or output.is_symlink():
        raise ValueError(f"El destino ya existe; usa un directorio nuevo: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"El directorio padre del destino no existe: {output.parent}")
    if not lang.strip():
        raise ValueError("Selecciona el idioma real con --lang")
    data = source.read_bytes()
    text = data.decode("utf-8")
    if not text.strip():
        raise ValueError("No hay párrafos de prosa para revisar")

    candidate, library_version = _candidate(text, lang, backward)
    diff_lines = unified_diff(
        text.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile=str(source),
        tofile="candidato.txt",
    )
    diff = "".join(
        line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
        for line in diff_lines
    )
    report = {
        "source": str(source.resolve()),
        "sha256": sha256(data).hexdigest(),
        "candidate_sha256": sha256(candidate.encode("utf-8")).hexdigest(),
        "dehyphen": library_version,
        "lang": lang,
        "forward": True,
        "backward": backward,
        "fast": False,
        "status": "candidato sin cotejar",
    }
    artifacts = {
        "candidato.txt": candidate,
        "cambios.diff": diff,
        "proveniencia.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    # No reservar el destino antes de terminar la inferencia: los fallos permiten reintentar.
    output.mkdir()
    try:
        for name, content in artifacts.items():
            with (output / name).open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
    except BaseException:
        shutil.rmtree(output)
        raise
    return output.resolve()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera candidatos OCR para cotejar; no corrige la obra automáticamente."
    )
    parser.add_argument("source", type=Path, help="Fragmento de prosa OCR en UTF-8")
    parser.add_argument(
        "output", type=Path, help="Directorio nuevo, fuera del árbol EPUB"
    )
    parser.add_argument(
        "--lang", required=True, help="Idioma/modelo real, por ejemplo es"
    )
    parser.add_argument(
        "--forward-only", action="store_true", help="Para modelos sin variante backward"
    )
    args = parser.parse_args(argv)
    try:
        output = propose(
            args.source, args.output, args.lang, backward=not args.forward_only
        )
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"Error: no se pudo generar el candidato: {exc}", file=sys.stderr)
        return 2
    print(f"Candidato sin cotejar: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
