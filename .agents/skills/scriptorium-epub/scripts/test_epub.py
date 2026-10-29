#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Pruebas pytest de epub.py, sin EPUBs externos ni EPUBCheck.

Runner: uv run -p 3.15 --with=pytest pytest <scripts>/test_epub.py
Los libros y directorios de trabajo usan tmp_path fuera del repositorio.
Cero errores estructurales no certifica ortografía ni conformidad ePL.
"""

from __future__ import annotations

import contextlib
import io
import json
import stat
import struct
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

import epub
import pytest

SCRIPT = Path(__file__).resolve().with_name("epub.py")
SKILL = SCRIPT.parent.parent
TEMPLATE = SKILL / "resources" / "epub-base-epl-r2.1.epub"
OPF_NAME = Path("OEBPS/content.opf")
NCX_NAME = Path("OEBPS/toc.ncx")
CHAPTER = Path("OEBPS/Text/capitulo.xhtml")
NOTES = Path("OEBPS/Text/notas.xhtml")
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
SKIPPED_REGEX = {
    "I-3-3.3.2.1.ErrataOrtotipograficas-04",
    "I-3-3.3.2.2.ErroresTipograficos-01",
}


@pytest.fixture(autouse=True)
def external_working_directory(tmp_path: Path, monkeypatch):
    assert not tmp_path.resolve().is_relative_to(SKILL.parents[2])
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def template_files() -> dict[str, bytes]:
    with zipfile.ZipFile(TEMPLATE) as archive:
        return {
            i.filename: archive.read(i) for i in archive.infolist() if not i.is_dir()
        }


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return tmp_path / "libro"


@pytest.fixture
def source_book(book: Path) -> Path:
    initialize(book)
    return book


@pytest.fixture
def output(tmp_path: Path) -> Path:
    return tmp_path / "libro.epub"


def snapshot(root: Path) -> dict:
    """No contar atime: una lectura puede actualizarlo sin modificar el libro."""
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        if path.is_symlink():
            payload = path.readlink()
        elif path.is_file():
            payload = path.read_bytes()
        else:
            payload = None
        result[path.relative_to(root)] = (info.st_mode, info.st_mtime_ns, payload)
    return result


def initialize(output: Path):
    with contextlib.redirect_stdout(io.StringIO()):
        epub.initialize(output)


def pack(root: Path, output: Path):
    with contextlib.redirect_stdout(io.StringIO()):
        epub.pack(root, output)


def write_files(files: dict[str, bytes], root: Path):
    root.mkdir(parents=True)
    for name, data in files.items():
        path = root / Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def write_zip(output: Path, files: dict[str, bytes]):
    with zipfile.ZipFile(output, "w") as archive:
        for name in ["mimetype", *sorted(set(files) - {"mimetype"})]:
            if name in files:
                archive.writestr(name, files[name], compress_type=zipfile.ZIP_STORED)
    return output


def xml(files: dict[str, bytes], name: Path):
    return ET.fromstring(files[name.as_posix()])


def save_xml(files: dict[str, bytes], name: Path, root):
    files[name.as_posix()] = ET.tostring(root, encoding="utf-8", xml_declaration=True)


def xhtml(title: str, body: str) -> bytes:
    return f'<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="{epub.XHTML}" xml:lang="es"><head><title>{title}</title>\n<link rel="stylesheet" type="text/css" href="../Styles/epl.css"/>\n</head><body>{body}</body></html>'.encode()


def minimal_book(template_files) -> dict[str, bytes]:
    """Derivar de la base: reemplazar o retirar todas las páginas de muestra."""
    keep = {"mimetype", "OEBPS/Styles/epl.css", "OEBPS/Images/cover.jpg"}
    files = {
        name: data
        for name, data in template_files.items()
        if name in keep or name.startswith("META-INF/")
    }
    pages = {
        "cubierta": '<div><svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 600 900"><image xlink:href="../Images/cover.jpg" width="600" height="900"/></svg></div>',
        "sinopsis": '<div class="sinopsis"><p>Un viaje por el río.</p></div>',
        "titulo": '<p class="ttitulo">El río</p><p class="tautor">Ana Ruiz</p><p class="trevision">ePub r1.0</p>',
        "info": "<p>Edición de prueba. Publicación original de 2020.</p>",
        "TOC": '<p><a href="capitulo.xhtml#inicio">El viaje</a></p>',
        "capitulo": '<h1 id="inicio">El viaje</h1><p>El río pasa junto al pueblo. <a id="rf1" href="notas.xhtml#nt1"><sup>[1]</sup></a></p>',
        "notas": '<h1>Notas</h1><p id="nt1">[1] Una aclaración. <a href="capitulo.xhtml#rf1">Volver</a></p>',
    }
    for name, body in pages.items():
        files[(Path("OEBPS/Text") / f"{name}.xhtml").as_posix()] = xhtml(
            name.capitalize(), body
        )
    package = ET.fromstring(template_files[OPF_NAME.as_posix()])
    metadata = package.find(f"{{{epub.OPF}}}metadata")
    for key, value in {
        "title": "El río",
        "creator": "Ana Ruiz",
        "description": "Un viaje por el río.",
        "subject": "Novela, Aventuras",
    }.items():
        metadata.find(f"{{{epub.DC}}}{key}").text = value
    metadata.find(f"{{{epub.DC}}}creator").set(f"{{{epub.OPF}}}file-as", "Ruiz, Ana")
    for node in list(metadata):
        if node.tag == f"{{{epub.DC}}}contributor" or (
            node.tag == f"{{{epub.OPF}}}meta"
            and node.get("name", "").startswith("calibre:")
        ):
            metadata.remove(node)
    identifier = metadata.find(f"{{{epub.DC}}}identifier[@id='BookId']")
    identifier.text = "urn:uuid:" + str(uuid.uuid4())
    manifest = package.find(f"{{{epub.OPF}}}manifest")
    manifest.clear()
    for name in sorted(files):
        if name == "mimetype" or name.startswith("META-INF/"):
            continue
        path = Path(name)
        ET.SubElement(
            manifest,
            f"{{{epub.OPF}}}item",
            {
                "id": path.name,
                "href": path.relative_to(Path("OEBPS")).as_posix(),
                "media-type": epub.MEDIA[path.suffix],
            },
        )
    ET.SubElement(
        manifest,
        f"{{{epub.OPF}}}item",
        {"id": "ncx", "href": "toc.ncx", "media-type": "application/x-dtbncx+xml"},
    )
    spine = package.find(f"{{{epub.OPF}}}spine")
    spine.clear()
    spine.set("toc", "ncx")
    for name in pages:
        ET.SubElement(spine, f"{{{epub.OPF}}}itemref", {"idref": f"{name}.xhtml"})
    guide = package.find(f"{{{epub.OPF}}}guide")
    guide.clear()
    ET.SubElement(
        guide,
        f"{{{epub.OPF}}}reference",
        {"type": "toc", "title": "Índice", "href": "Text/TOC.xhtml"},
    )
    save_xml(files, OPF_NAME, package)
    files[NCX_NAME.as_posix()] = (
        f'<?xml version="1.0" encoding="utf-8"?>\n<ncx xmlns="{epub.NCX}" version="2005-1"><head>\n<meta name="dtb:uid" content="{identifier.text}"/>\n<meta name="dtb:depth" content="1"/><meta name="dtb:totalPageCount" content="0"/>\n<meta name="dtb:maxPageNumber" content="0"/></head><docTitle><text>El río</text></docTitle>\n<navMap><navPoint id="nav-1" playOrder="1"><navLabel><text>El viaje</text></navLabel>\n<content src="Text/capitulo.xhtml#inicio"/></navPoint></navMap></ncx>'.encode()
    )
    return files


def audit_report(files: dict[str, bytes], infos=None):
    before = files.copy()
    report = epub.Audit(files, infos).run()
    assert before == files, "Audit modificó los bytes de entrada"
    return report


def assert_finding(report, code: str, level: str = "error", file: Path | None = None):
    matches = [
        f for f in report["findings"] if f["code"] == code and f["level"] == level
    ]
    if file is not None:
        matches = [f for f in matches if f["file"] == file.as_posix()]
    assert matches, f"Falta {level} {code}: {report['findings']}"
    return matches


def rename_xml_resource(files: dict[str, bytes], old: Path, new: Path):
    """Renombrar un recurso de la fixture sin cambiar su media-type declarado."""
    files[new.as_posix()] = files.pop(old.as_posix())
    for name, data in list(files.items()):
        if name == new.as_posix() or Path(name).suffix in {
            ".xml",
            ".opf",
            ".ncx",
            ".xhtml",
        }:
            files[name] = data.replace(old.name.encode(), new.name.encode())


def run_cli(tmp_path: Path, *args):
    return subprocess.run(
        [str(Path(sys.executable)), "-B", str(SCRIPT), *[str(arg) for arg in args]],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


def test_exact_copy_except_fresh_uuid_and_immutable_template(
    tmp_path: Path, template_files, book: Path
):
    resources_before = snapshot(SKILL / "resources")
    initialize(book)
    actual = epub.read_directory(book)
    assert set(template_files) == set(actual)
    package = xml(actual, OPF_NAME)
    uid = package.find(
        f"{{{epub.OPF}}}metadata/{{{epub.DC}}}identifier[@id='BookId']"
    ).text
    identifier = uuid.UUID(uid.removeprefix("urn:uuid:"))
    assert 0 != identifier.int
    assert 4 == identifier.version
    ncx_uid = (
        xml(actual, NCX_NAME)
        .find(f"{{{epub.NCX}}}head/{{{epub.NCX}}}meta[@name='dtb:uid']")
        .get("content")
    )
    assert uid == ncx_uid
    for name, data in template_files.items():
        expected = (
            data.replace(ZERO_UUID.encode(), str(identifier).encode())
            if Path(name) in (OPF_NAME, NCX_NAME)
            else data
        )
        assert expected == actual[name], name
    second = tmp_path / "otro libro"
    initialize(second)
    assert actual[OPF_NAME.as_posix()] != (second / OPF_NAME).read_bytes()
    assert resources_before == snapshot(SKILL / "resources")


def test_refuses_existing_directory_or_file_without_changes(tmp_path: Path):
    for kind in ("directory", "file"):
        output = tmp_path / kind
        if kind == "directory":
            output.mkdir()
            (output / "conservar.txt").write_bytes(b"no tocar")
        else:
            output.write_bytes(b"no tocar")
        before = snapshot(tmp_path)
        with pytest.raises(ValueError):
            initialize(output)
        assert before == snapshot(tmp_path)


def test_refuses_symlink_destination_and_symlink_parent(tmp_path: Path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "enlace"
    link.symlink_to(target, target_is_directory=True)
    for output in (link, link / "nuevo"):
        before = snapshot(tmp_path)
        with pytest.raises((ValueError, epub.nav.NavigationError)):
            initialize(output)
        assert before == snapshot(tmp_path)


def test_mimetype_first_stored_without_extra_and_exact_contents(
    source_book: Path, output: Path
):
    before = snapshot(source_book)
    pack(source_book, output)
    with zipfile.ZipFile(output) as archive:
        infos = archive.infolist()
        first = infos[0]
        assert "mimetype" == first.filename
        assert zipfile.ZIP_STORED == first.compress_type
        assert b"" == first.extra
        assert 0 == first.header_offset
        assert b"application/epub+zip" == archive.read(first)
        assert sorted(i.filename for i in infos[1:]) == [i.filename for i in infos[1:]]
        assert epub.read_directory(source_book) == {
            info.filename: archive.read(info) for info in infos
        }
        for info in infos[1:]:
            assert zipfile.ZIP_DEFLATED == info.compress_type
    header = output.read_bytes()[:30]
    assert b"PK\x03\x04" == header[:4]
    assert 0 == struct.unpack_from("<H", header, 8)[0]
    assert (8, 0) == struct.unpack_from("<HH", header, 26)
    assert before == snapshot(source_book)


def test_output_is_byte_stable(tmp_path: Path, source_book: Path, output: Path):
    other = tmp_path / "segunda.epub"
    pack(source_book, output)
    pack(source_book, other)
    assert output.read_bytes() == other.read_bytes()


def test_refuses_overwrite_without_changes(
    tmp_path: Path, source_book: Path, output: Path
):
    output.write_bytes(b"archivo existente")
    before = snapshot(tmp_path)
    with pytest.raises(FileExistsError):
        pack(source_book, output)
    assert before == snapshot(tmp_path)


def test_refuses_output_inside_source_even_when_nested(
    tmp_path: Path, source_book: Path
):
    for output in (source_book / "salida.epub", source_book / "OEBPS" / "salida.epub"):
        before = snapshot(tmp_path)
        with pytest.raises(ValueError):
            pack(source_book, output)
        assert before == snapshot(tmp_path)


def test_refuses_wrong_mimetype_or_missing_container_without_output(
    tmp_path: Path, source_book: Path, output: Path
):
    for name, replacement in (
        (Path("mimetype"), b"application/epub+zip\n"),
        (Path("META-INF/container.xml"), None),
    ):
        path = source_book / name
        original = path.read_bytes()
        try:
            if replacement is None:
                path.unlink()
            else:
                path.write_bytes(replacement)
            before = snapshot(tmp_path)
            with pytest.raises(ValueError):
                pack(source_book, output)
            assert not output.exists()
            assert before == snapshot(tmp_path)
        finally:
            path.write_bytes(original)


def test_refuses_symlink_file_or_directory_in_source(
    tmp_path: Path, source_book: Path, output: Path
):
    for name, target in (
        ("archivo", source_book / OPF_NAME),
        ("directorio", source_book / "OEBPS"),
    ):
        link = source_book / name
        link.symlink_to(target, target_is_directory=target.is_dir())
        try:
            before = snapshot(tmp_path)
            with pytest.raises((ValueError, epub.nav.NavigationError)):
                pack(source_book, output)
            assert before == snapshot(tmp_path)
            assert not output.exists()
        finally:
            link.unlink()


def test_refuses_symlink_source_root(tmp_path: Path, source_book: Path, output: Path):
    link = tmp_path / "origen-enlazado"
    link.symlink_to(source_book, target_is_directory=True)
    before = snapshot(tmp_path)
    with pytest.raises((ValueError, epub.nav.NavigationError)):
        pack(link, output)
    assert before == snapshot(tmp_path)
    assert not output.exists()


def test_refuses_symlink_output_or_parent(tmp_path: Path, source_book: Path):
    existing = tmp_path / "existente.epub"
    existing.write_bytes(b"conservar")
    output_link = tmp_path / "enlazado.epub"
    output_link.symlink_to(existing)
    parent_link = tmp_path / "directorio-enlazado"
    parent_link.symlink_to(tmp_path, target_is_directory=True)
    for output in (output_link, parent_link / "nuevo.epub"):
        before = snapshot(source_book)
        with pytest.raises((ValueError, epub.nav.NavigationError)):
            pack(source_book, output)
        assert before == snapshot(source_book)
        assert b"conservar" == existing.read_bytes()
        assert not (tmp_path / "nuevo.epub").exists()


def test_read_directory_rejects_symlink_root_and_nested_links(
    tmp_path: Path, template_files, book: Path
):
    write_files(minimal_book(template_files), book)
    root_link = tmp_path / "enlace"
    root_link.symlink_to(book, target_is_directory=True)
    with pytest.raises((ValueError, epub.nav.NavigationError)):
        epub.read_directory(root_link)
    nested = book / "enlace"
    nested.symlink_to(book / CHAPTER)
    with pytest.raises((ValueError, epub.nav.NavigationError)):
        epub.read_directory(book)


def test_zip_rejects_traversal_absolute_and_ambiguous_names(tmp_path: Path):
    unsafe = (
        "../fuera",
        "OEBPS/../../fuera",
        "/absoluta",
        "C:/fuera",
        "OEBPS\\fuera",
        "OEBPS//doble",
        "OEBPS/./punto",
        "OEBPS/control\x01.xhtml",
    )
    for index, name in enumerate(unsafe):
        path = tmp_path / f"inseguro-{index}.epub"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(name, b"contenido")
        before = snapshot(tmp_path)
        with pytest.raises(ValueError):
            epub.read_zip(path)
        assert before == snapshot(tmp_path)


def test_zip_rejects_symlink_and_special_entries(tmp_path: Path):
    for mode in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK):
        path = tmp_path / f"especial-{mode}.epub"
        info = zipfile.ZipInfo("OEBPS/enlace")
        info.create_system = 3
        info.external_attr = (mode | 511) << 16
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(info, b"../destino")
        with pytest.raises(ValueError):
            epub.read_zip(path)


def test_zip_rejects_duplicate_members(tmp_path: Path):
    path = tmp_path / "duplicado.epub"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", epub.MIMETYPE)
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("mimetype", b"otro")
    with pytest.raises(ValueError):
        epub.read_zip(path)


def test_zip_rejects_corruption_truncation_and_bad_crc(tmp_path: Path):
    path = tmp_path / "corrupto.epub"
    for payload in (b"no es ZIP", b"PK\x03\x04\x00"):
        path.write_bytes(payload)
        with pytest.raises(zipfile.BadZipFile):
            epub.read_zip(path)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("contenido.txt", b"original payload")
    path.write_bytes(
        path.read_bytes().replace(b"original payload", b"alterado payload", 1)
    )
    with pytest.raises(zipfile.BadZipFile):
        epub.read_zip(path)


def test_local_uri_traversal_rejected_including_percent_encoding(template_files):
    for value in (
        "../../../fuera.xhtml",
        "%2e%2e/%2e%2e/%2e%2e/fuera.xhtml",
        "/fuera.xhtml",
        "..%5cfuera.xhtml",
    ):
        with pytest.raises(ValueError):
            epub.uri_target(CHAPTER.as_posix(), value)
        files = minimal_book(template_files)
        files[CHAPTER.as_posix()] = xhtml("Enlace", f'<p><a href="{value}">Ir</a></p>')
        assert_finding(audit_report(files), "URI", file=CHAPTER)


def test_base_report_has_placeholders_pending_work_and_consistent_counts(
    template_files,
):
    report = audit_report(template_files.copy())
    assert_finding(report, "PLACEHOLDER", "warning")
    assert_finding(report, "SAMPLE_IMAGE", "warning")
    assert_finding(report, "BOOK_UUID")
    assert_finding(report, "EPL_ID_PENDING", "warning")
    assert not report["compliance_certified"]
    assert "EPUB2" in report["profile"]
    counts = Counter(f["level"] for f in report["findings"])
    assert {"error": counts["error"], "warning": counts["warning"]} == report["counts"]
    for finding in report["findings"]:
        assert {"level", "code", "file", "message"} <= finding.keys()


def test_minimal_adapted_book_has_no_structural_errors_not_editorial_certification(
    template_files,
):
    files = minimal_book(template_files)
    for name, data in template_files.items():
        if Path(name).suffix == ".xhtml":
            assert name not in files or files[name] != data, name
    report = audit_report(files)
    errors = [f for f in report["findings"] if f["level"] == "error"]
    assert [] == errors
    assert 0 == report["counts"]["error"]
    assert not report["compliance_certified"]
    assert_finding(report, "EPL_ID_PENDING", "warning")
    assert_finding(report, "SAMPLE_IMAGE", "warning")
    assert "PLACEHOLDER" not in {f["code"] for f in report["findings"]}
    pending = {item["code"]: item["reason"] for item in report["skipped"]}
    assert "ortografía" in pending["EDITORIAL_VISUAL"]
    assert "EPUB_SCHEMA" in pending


def test_two_incompatible_regex_are_explicitly_skipped_with_original_reasons(
    template_files,
):
    rules = json.loads(
        (SKILL / "resources" / "manual-regex.json").read_text(encoding="utf-8")
    )
    incompatible = {
        r["id"]: r for r in rules if not r.get("stdlib_re_compatible", True)
    }
    assert SKIPPED_REGEX == set(incompatible)
    report = audit_report(minimal_book(template_files))
    regex_skips = [
        s for s in report["skipped"] if s["code"] in {r["id"] for r in rules}
    ]
    assert 2 == len(regex_skips)
    assert SKIPPED_REGEX == {s["code"] for s in regex_skips}
    for skipped in regex_skips:
        assert (
            incompatible[skipped["code"]]["stdlib_re_skip_reason"] == skipped["reason"]
        )
        assert "look-behind" in skipped["reason"]
    assert SKIPPED_REGEX.isdisjoint(f["code"] for f in report["findings"])


def test_changed_epl_css_is_an_error(template_files):
    files = minimal_book(template_files)
    name = Path("OEBPS/Styles/epl.css")
    files[name.as_posix()] += b"\n/* cambio */\n"
    assert_finding(audit_report(files), "EPL_CSS_CHANGED", file=name)


def test_missing_manifest_resource(template_files):
    files = minimal_book(template_files)
    del files["OEBPS/Images/cover.jpg"]
    assert_finding(audit_report(files), "MISSING_TARGET", file=OPF_NAME)


def test_file_missing_from_manifest(template_files):
    files = minimal_book(template_files)
    name = Path("OEBPS/Images/sobrante.png")
    files[name.as_posix()] = b"sin declarar"
    assert_finding(audit_report(files), "UNMANIFESTED", file=name)


def test_spine_reference_missing_or_not_xhtml(template_files):
    for idref in ("inexistente", "epl.css"):
        files = minimal_book(template_files)
        package = xml(files, OPF_NAME)
        spine = package.find(f"{{{epub.OPF}}}spine")
        ET.SubElement(spine, f"{{{epub.OPF}}}itemref", {"idref": idref})
        save_xml(files, OPF_NAME, package)
        assert_finding(audit_report(files), "SPINE_REF", file=OPF_NAME)


def test_missing_fragment(template_files):
    files = minimal_book(template_files)
    files[CHAPTER.as_posix()] = xhtml(
        "Fragmento",
        '<h1 id="inicio">El viaje</h1><p><a href="notas.xhtml#ausente">Ir</a></p>',
    )
    assert_finding(audit_report(files), "MISSING_FRAGMENT", file=CHAPTER)


def test_duplicate_ids(template_files):
    files = minimal_book(template_files)
    files[CHAPTER.as_posix()] = xhtml(
        "Duplicado", '<h1 id="inicio">El viaje</h1><p id="inicio">Otra vez.</p>'
    )
    assert_finding(audit_report(files), "DUPLICATE_ID", file=CHAPTER)


def test_ncx_uid_must_match_opf(template_files):
    files = minimal_book(template_files)
    ncx = xml(files, NCX_NAME)
    ncx.find(f"{{{epub.NCX}}}head/{{{epub.NCX}}}meta[@name='dtb:uid']").set(
        "content", "urn:uuid:" + str(uuid.uuid4())
    )
    save_xml(files, NCX_NAME, ncx)
    assert_finding(audit_report(files), "NCX_UID", file=NCX_NAME)


def test_taxonomy_accepts_one_genre_and_one_to_five_same_type_subgenres():
    for subject in (
        "Novela, Aventuras",
        "Novela, Aventuras, Bélico, Drama, Histórico, Humor",
    ):
        audit = epub.Audit({})
        audit.taxonomy(subject)
        assert [] == audit.findings


def test_taxonomy_rejects_type_unknown_duplicates_wrong_case_and_mixed_types(
    template_files,
):
    catalog = json.loads(
        (SKILL / "resources" / "genres.json").read_text(encoding="utf-8")
    )
    fiction, other = catalog["tipos"][:2]
    foreign = next(
        s["nombre"]
        for s in other["subgeneros"]
        if s["nombre"] not in {s["nombre"] for s in fiction["subgeneros"]}
    )
    invalid = (
        "Novela",
        "Novela, No existe",
        "Ficción, Novela, Aventuras",
        "Novela, Aventuras, Aventuras",
        "novela, Aventuras",
        "Novela, Relato, Aventuras",
        "Novela, Aventuras, Bélico, Drama, Histórico, Humor, Infantil",
        f"Novela, {foreign}",
    )
    for subject in invalid:
        audit = epub.Audit({})
        audit.taxonomy(subject)
        assert_finding(audit.report(), "GENRES")
    files = minimal_book(template_files)
    package = xml(files, OPF_NAME)
    package.find(f"{{{epub.OPF}}}metadata/{{{epub.DC}}}subject").text = "Novela"
    save_xml(files, OPF_NAME, package)
    assert_finding(audit_report(files), "GENRES", file=OPF_NAME)


def test_note_forward_and_return_links_are_valid(template_files):
    report = audit_report(minimal_book(template_files))
    assert {"NOTE_FORWARD", "NOTE_BACK", "NOTE_LABEL", "ORPHAN_NOTE"}.isdisjoint(
        f["code"] for f in report["findings"]
    )


def test_note_forward_must_target_matching_number(template_files):
    files = minimal_book(template_files)
    files[CHAPTER.as_posix()] = files[CHAPTER.as_posix()].replace(
        b"notas.xhtml#nt1", b"#inicio"
    )
    report = audit_report(files)
    assert_finding(report, "NOTE_FORWARD", file=CHAPTER)
    assert_finding(report, "ORPHAN_NOTE", "warning", NOTES)


def test_note_return_must_target_original_call(template_files):
    files = minimal_book(template_files)
    files[NOTES.as_posix()] = files[NOTES.as_posix()].replace(
        b"capitulo.xhtml#rf1", b"capitulo.xhtml#inicio"
    )
    assert_finding(audit_report(files), "NOTE_BACK", file=NOTES)


def test_note_label_requires_sup_and_matching_number(template_files):
    for old, new, name in (
        (b"<sup>[1]</sup>", b"[1]", CHAPTER),
        (b"[1] Una", b"[2] Una", NOTES),
    ):
        files = minimal_book(template_files)
        files[name.as_posix()] = files[name.as_posix()].replace(old, new)
        assert_finding(audit_report(files), "NOTE_LABEL", file=name)


def test_broken_xml_reported_without_mutating_input(template_files):
    files = minimal_book(template_files)
    files[CHAPTER.as_posix()] = b"<html><sin-cerrar>"
    assert_finding(audit_report(files), "XML", file=CHAPTER)


def test_zip_mimetype_order_compression_and_extra_are_audited(
    tmp_path: Path, template_files
):
    files = minimal_book(template_files)
    output = tmp_path / "orden.epub"
    for defect in ("order", "compression", "extra"):
        with zipfile.ZipFile(output, "w") as archive:
            if defect == "order":
                archive.writestr("primero.txt", b"antes")
            for name, data in files.items():
                info = zipfile.ZipInfo(name)
                if name == "mimetype":
                    if defect == "compression":
                        info.compress_type = zipfile.ZIP_DEFLATED
                    elif defect == "extra":
                        info.extra = b"\xfe\xca\x00\x00"
                archive.writestr(info, data)
        loaded, infos = epub.read_zip(output)
        assert_finding(
            audit_report(loaded, infos),
            "MIMETYPE_FIRST" if defect == "order" else "MIMETYPE_ZIP",
        )


def test_init_and_pack_from_external_working_directory_with_spaces(tmp_path: Path):
    source = tmp_path / "libro con espacios"
    result = run_cli(tmp_path, "init", source)
    assert 0 == result.returncode, result.stderr
    assert (source / OPF_NAME).is_file()
    output = tmp_path / "libro con espacios.epub"
    before = snapshot(source)
    result = run_cli(tmp_path, "pack", source, output)
    assert 0 == result.returncode, result.stderr
    assert before == snapshot(source)
    assert zipfile.is_zipfile(output)
    before = snapshot(tmp_path)
    for args in (("init", source), ("pack", source, output)):
        result = run_cli(tmp_path, *args)
        assert 0 != result.returncode
        assert before == snapshot(tmp_path)


def test_json_valid_book_is_read_only_and_not_certified(
    tmp_path: Path, template_files, book: Path
):
    files = minimal_book(template_files)
    write_files(files, book)
    output = write_zip(tmp_path / "mínimo.epub", files)
    before = snapshot(tmp_path)
    result = run_cli(tmp_path, "check", output, "--json")
    assert 0 == result.returncode, result.stderr
    assert "" == result.stderr
    report = json.loads(result.stdout)
    assert 0 == report["counts"]["error"]
    assert not report["compliance_certified"]
    assert before == snapshot(tmp_path)


def test_json_invalid_book_returns_nonzero_and_does_not_modify_any_file(
    tmp_path: Path, template_files, book: Path
):
    files = minimal_book(template_files)
    del files["OEBPS/Images/cover.jpg"]
    write_files(files, book)
    output = write_zip(tmp_path / "inválido.epub", files)
    before = snapshot(tmp_path)
    result = run_cli(tmp_path, "check", output, "--json")
    report = json.loads(result.stdout)
    assert 1 == result.returncode, result.stderr
    assert "" == result.stderr
    assert report["counts"]["error"] > 0
    assert_finding(report, "MISSING_TARGET")
    assert before == snapshot(tmp_path)


def test_json_corrupt_missing_and_traversal_inputs_report_input_error(tmp_path: Path):
    corrupt = tmp_path / "corrupto.epub"
    corrupt.write_bytes(b"PK\x03\x04truncado")
    unsafe = tmp_path / "traversal.epub"
    with zipfile.ZipFile(unsafe, "w") as archive:
        archive.writestr("../fuera.txt", b"no extraer")
    for path in (corrupt, unsafe, tmp_path / "ausente.epub"):
        before = snapshot(tmp_path)
        result = run_cli(tmp_path, "check", path, "--json")
        report = json.loads(result.stdout)
        assert 1 == result.returncode, result.stderr
        assert "" == result.stderr
        assert_finding(report, "INPUT")
        assert ["ALL_CHECKS"] == [s["code"] for s in report["skipped"]]
        assert not report["compliance_certified"]
        assert before == snapshot(tmp_path)


def test_strict_returns_nonzero_for_warnings_only(tmp_path: Path, template_files):
    output = write_zip(tmp_path / "alertas.epub", minimal_book(template_files))
    before = snapshot(tmp_path)
    result = run_cli(tmp_path, "check", output, "--json", "--strict")
    report = json.loads(result.stdout)
    assert 1 == result.returncode, result.stderr
    assert 0 == report["counts"]["error"]
    assert report["counts"]["warning"] > 0
    assert before == snapshot(tmp_path)


def test_real_template_cover_dimensions(template_files):
    cover = template_files["OEBPS/Images/cover.jpg"]
    assert cover.startswith(b"\xff\xd8")
    assert (600, 900) == epub.image_size(cover)


def test_malformed_short_jpeg_returns_none_without_exception():
    malformed = (
        b"",
        b"not an image",
        b"\xff\xd8",
        b"\xff\xd8\xff",
        b"\xff\xd8\xff\xff\xff",
        b"\xff\xd8\xff\xc0\x00",
        b"\xff\xd8\xff\xc0\x00\x07\x08\x03\x84",
        b"\xff\xd8\xff\xc0\x00\x01\x00\x00",
        b"\xff\xd8\xff\xe0\xff\xff\x00\x00",
        b"\xff\xd8\x00\x00\x00\x00",
        b"\xff\xd8\xff\xd9\x00\x00",
    )
    for data in malformed:
        assert epub.image_size(data) is None


def test_png_gif_headers_and_short_headers():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 600, 900)
    gif = b"GIF89a" + struct.pack("<HH", 320, 200)
    assert (600, 900) == epub.image_size(png)
    assert (320, 200) == epub.image_size(gif)
    assert epub.image_size(png[:20]) is None
    assert epub.image_size(gif[:8]) is None


@pytest.mark.parametrize("original", [CHAPTER, NCX_NAME], ids=["xhtml", "ncx"])
def test_manifest_xml_media_type_is_parsed_despite_txt_suffix(
    template_files, original: Path
):
    files = minimal_book(template_files)
    renamed = original.with_suffix(".txt")
    rename_xml_resource(files, original, renamed)
    package = xml(files, OPF_NAME)
    item = next(
        node
        for node in package.findall(f"{{{epub.OPF}}}manifest/{{{epub.OPF}}}item")
        if node.get("href") == renamed.relative_to(Path("OEBPS")).as_posix()
    )
    expected_type = (
        "application/xhtml+xml" if original == CHAPTER else "application/x-dtbncx+xml"
    )
    assert item.get("media-type") == expected_type
    before = files.copy()
    auditor = epub.Audit(files)
    report = auditor.run()
    assert renamed.as_posix() in auditor.documents
    assert report["counts"]["error"] == 0, report["findings"]
    assert "UNCHECKED_FRAGMENT" not in {f["code"] for f in report["findings"]}
    assert files == before


def test_container_requires_parsing_package_with_txt_suffix(template_files):
    files = minimal_book(template_files)
    renamed = OPF_NAME.with_suffix(".txt")
    rename_xml_resource(files, OPF_NAME, renamed)
    auditor = epub.Audit(files)
    before = files.copy()
    report = auditor.run()
    assert auditor.package == renamed.as_posix()
    assert renamed.as_posix() in auditor.documents
    assert report["counts"]["error"] == 0, report["findings"]
    assert files == before


@pytest.mark.parametrize(
    ("defect", "code"),
    [
        ("unclosed", "XML"),
        ("missing", "BODY"),
        ("namespace", "BODY"),
        ("empty", "EMPTY_BODY"),
    ],
)
def test_manifest_xhtml_txt_invalid_body_cannot_pass(
    tmp_path: Path, template_files, defect, code
):
    files = minimal_book(template_files)
    renamed = CHAPTER.with_suffix(".txt")
    rename_xml_resource(files, CHAPTER, renamed)
    if defect == "unclosed":
        data = xhtml("Cuerpo inválido", "<p>Sin cerrar")
    elif defect == "empty":
        data = xhtml("Cuerpo vacío", "")
    else:
        data = xhtml("Cuerpo inválido", "<p>Texto.</p>")
        if defect == "missing":
            data = data.replace(b"<body>", b"<cuerpo>").replace(
                b"</body>", b"</cuerpo>"
            )
        else:
            data = data.replace(b"<body>", b'<body xmlns="">')
    files[renamed.as_posix()] = data
    report = audit_report(files)
    assert report["counts"]["error"] > 0
    assert_finding(report, code, file=renamed)
    archive = write_zip(tmp_path / "cuerpo-invalido.epub", files)
    before = snapshot(tmp_path)
    result = run_cli(tmp_path, "check", archive, "--json")
    assert result.returncode == 1, result.stderr
    assert result.stderr == ""
    assert_finding(json.loads(result.stdout), code, file=renamed)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("suffix", [".xhtml", ".txt"])
def test_copy_entity_without_dtd_is_rejected(tmp_path: Path, template_files, suffix):
    files = minimal_book(template_files)
    chapter = CHAPTER.with_suffix(suffix)
    if chapter != CHAPTER:
        rename_xml_resource(files, CHAPTER, chapter)
    files[chapter.as_posix()] = files[chapter.as_posix()].replace(
        b"</body>", b"<p>&copy;</p></body>"
    )
    report = audit_report(files)
    assert_finding(report, "XML", file=chapter)
    archive = write_zip(tmp_path / "entidad-no-declarada.epub", files)
    before = snapshot(tmp_path)
    result = run_cli(tmp_path, "check", archive, "--json")
    assert result.returncode == 1, result.stderr
    assert result.stderr == ""
    assert_finding(json.loads(result.stdout), "XML", file=chapter)
    assert snapshot(tmp_path) == before


def test_copy_entity_with_standard_xhtml_dtd_remains_accepted(template_files):
    files = minimal_book(template_files)
    data = files[CHAPTER.as_posix()].replace(b"</body>", b"<p>&copy;</p></body>")
    files[CHAPTER.as_posix()] = data.replace(
        b"<html ", epub.nav.XHTML_DTD.encode() + b"\n<html ", 1
    )
    report = audit_report(files)
    assert report["counts"]["error"] == 0, report["findings"]


def test_parse_required_handles_txt_and_does_not_repeat_xml_errors():
    resource = Path("OEBPS/Text/declarado.txt")
    files = {resource.as_posix(): b"<html><body><p>Sin cerrar"}
    before = files.copy()
    auditor = epub.Audit(files)
    auditor.parse()
    assert not auditor.findings
    assert resource.as_posix() not in auditor.documents
    auditor.parse([resource.as_posix()])
    assert len(assert_finding(auditor.report(), "XML", file=resource)) == 1
    first_findings = auditor.findings.copy()
    auditor.parse([resource.as_posix()])
    assert auditor.findings == first_findings
    assert files == before


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).resolve()), *sys.argv[1:]]))
