#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest"]
# ///
"""Tests: uv run -p 3.15 --with=pytest pytest .agents/skills/scriptorium-epub/scripts/test_navigation.py."""

import socket
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import navigation as nav
import pytest


def write(root: Path, name: str, text: str) -> None:
    (root / name).write_text(text, encoding="utf-8")


def xhtml(root: Path, name: str, body: str) -> None:
    write(
        root,
        f"OEBPS/Text/{name}.xhtml",
        f'''<?xml version="1.0" encoding="utf-8"?>
{nav.XHTML_DTD}
<html xmlns="{nav.XHTML}" xml:lang="es"><head><title>{name}</title></head>
<!-- conservar comentario -->
<body>{body}</body></html>''',
    )


def element(tree: ET.Element, xpath: str) -> ET.Element:
    result = tree.find(xpath)
    assert result is not None, f"Falta el elemento {xpath}"
    return result


def read_opf(root: Path) -> ET.Element:
    return ET.parse(root / "OEBPS/content.opf").getroot()


def save_opf(root: Path, tree: ET.Element) -> None:
    (root / "OEBPS/content.opf").write_bytes(nav.serialize(tree, nav.OPF))


def snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def assert_rejected_unchanged(root: Path, match: str | None = None) -> None:
    before = snapshot(root)
    with pytest.raises(nav.NavigationError, match=match):
        nav.regenerate(root)
    assert snapshot(root) == before
    assert not list(root.rglob(".epl-nav-*"))


def forbid_io(*args, **kwargs):
    raise AssertionError("No debe realizar E/S")


@pytest.fixture
def book(tmp_path: Path) -> Path:
    root = tmp_path / "book"
    for name in ("META-INF", "OEBPS/Text", "OEBPS/Styles"):
        (root / name).mkdir(parents=True)
    write(
        root,
        "META-INF/container.xml",
        f'''<container xmlns="{nav.CONTAINER}" version="1.0">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''',
    )
    write(root, "OEBPS/Styles/epl.css", ".oculto { display: none; }")
    write(root, "OEBPS/Styles/sgc-toc.css", ".sgc-toc-level-1 { margin: 0; }")
    names = ["cubierta", "sinopsis", "titulo", "info", "TOC", "parte", "cap", "final"]
    for name, body in (
        ("cubierta", '<h1 class="oculto" title="Cubierta"></h1><p>Imagen</p>'),
        ("sinopsis", "<p>Sin encabezados</p>"),
        ("titulo", '<h1 title="Título">Título visible</h1>'),
        ("info", "<p>Créditos</p>"),
        ("TOC", "<h1>NO INDEXAR</h1>"),
        ("parte", '<h1 id="parte-existente">Parte I</h1>'),
        (
            "cap",
            '<h2 title="Capítulo &quot;uno&quot;">Otro texto</h2><h3>Detalle<sup>[1]</sup></h3>',
        ),
        ("final", "<h2>Capítulo dos</h2><h1>Epílogo</h1>"),
    ):
        xhtml(root, name, body)
    items = "".join(
        f'<item id="{name}" href="Text/{name}.xhtml" media-type="application/xhtml+xml"/>'
        for name in names
    )
    refs = "".join(f'<itemref idref="{name}"/>' for name in names)
    write(
        root,
        "OEBPS/content.opf",
        f'''<package xmlns="{nav.OPF}" xmlns:dc="{nav.DC}" xmlns:opf="{nav.OPF}" version="2.0" unique-identifier="BookId">
<metadata><dc:title>Libro &amp; prueba</dc:title><dc:identifier id="BookId" opf:scheme="UUID">urn:uuid:prueba</dc:identifier><dc:creator opf:role="aut">Autora</dc:creator><dc:language>es</dc:language></metadata>
<manifest>{items}<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
<item id="epl.css" href="Styles/epl.css" media-type="text/css"/><item id="sgc-toc.css" href="Styles/sgc-toc.css" media-type="text/css"/></manifest>
<spine toc="ncx">{refs}</spine><guide><reference type="toc" href="Text/TOC.xhtml#antiguo" title="Viejo"/></guide></package>''',
    )
    write(
        root,
        "OEBPS/toc.ncx",
        f'<ncx xmlns="{nav.NCX}" version="2005-1"><navMap/></ncx>',
    )
    return root


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", forbid_io)


def test_indices_coherent(book: Path):
    nav.regenerate(book)
    ncx = ET.parse(book / "OEBPS/toc.ncx").getroot()
    toc = ET.parse(book / "OEBPS/Text/TOC.xhtml").getroot()
    points = ncx.findall(f".//{{{nav.NCX}}}navPoint")
    links = toc.findall(f".//{{{nav.XHTML}}}a")
    labels = [
        point.findtext(f"{{{nav.NCX}}}navLabel/{{{nav.NCX}}}text") for point in points
    ]
    assert labels == [link.text for link in links]
    assert labels == [
        "Cubierta",
        "Título",
        "Parte I",
        'Capítulo "uno"',
        "Detalle",
        "Capítulo dos",
        "Epílogo",
    ]
    assert [point.get("playOrder") for point in points] == [str(i) for i in range(1, 8)]
    for point, link in zip(points, links, strict=True):
        destinations = []
        for parent, href in (
            (book / "OEBPS", element(point, f"{{{nav.NCX}}}content").get("src")),
            (book / "OEBPS/Text", link.get("href")),
        ):
            assert href is not None
            filename, fragment = href.split("#")
            path = (parent / filename).resolve()
            document = nav.read_xml(path, f"{{{nav.XHTML}}}html")
            assert fragment in nav.identifiers(document.tree, path)
            destinations.append((path, fragment))
        assert destinations[0] == destinations[1]
    meta = {
        entry.get("name"): entry.get("content")
        for entry in ncx.findall(f"{{{nav.NCX}}}head/{{{nav.NCX}}}meta")
    }
    assert meta["dtb:depth"] == "3"
    assert meta["dtb:uid"] == "urn:uuid:prueba"
    assert ncx.findtext(f"{{{nav.NCX}}}docTitle/{{{nav.NCX}}}text") == "Libro & prueba"
    styles = toc.findall(f"{{{nav.XHTML}}}head/{{{nav.XHTML}}}link")
    assert [style.get("href") for style in styles] == [
        "../Styles/epl.css",
        "../Styles/sgc-toc.css",
    ]
    assert [
        div.get("class")
        for div in toc.findall(f"{{{nav.XHTML}}}body/{{{nav.XHTML}}}div")
        if div.find(f"{{{nav.XHTML}}}a") is not None
    ] == [f"sgc-toc-level-{level}" for level in (1, 1, 1, 2, 3, 2, 1)]
    assert not toc.findall(f".//{{{nav.XHTML}}}h1")
    package = read_opf(book)
    assert (
        element(package, f"{{{nav.OPF}}}metadata/{{{nav.DC}}}creator").get(
            f"{{{nav.OPF}}}role"
        )
        == "aut"
    )
    assert (
        element(package, f"{{{nav.OPF}}}metadata/{{{nav.DC}}}identifier").get(
            f"{{{nav.OPF}}}scheme"
        )
        == "UUID"
    )


def test_ids_stable_and_surgical(book: Path):
    xhtml(
        book,
        "cap",
        '<p id="epl-nav-1">á</p><h2 data-x="&gt;">Capítulo</h2><h3 id="propio">Detalle</h3>',
    )
    path = book / "OEBPS/Text/cap.xhtml"
    original = path.read_bytes()
    nav.regenerate(book)
    assert path.read_bytes() == original.replace(
        b'<h2 data-x="&gt;">', b'<h2 data-x="&gt;" id="epl-nav-2">'
    )
    first = snapshot(book)
    assert nav.regenerate(book) == 0
    assert snapshot(book) == first
    assert b'id="parte-existente"' in (book / "OEBPS/Text/parte.xhtml").read_bytes()


def test_entities_attributes_comments_cdata_and_specials(book: Path):
    xhtml(
        book,
        "cap",
        '<h2 title="&laquo;A&nbsp;&amp;&nbsp;B&raquo; &lt;x&gt;">Visible</h2><h3>Énfasis <em>real</em><a><sup>[3]</sup></a> final<![CDATA[ &unknown; ]]></h3><!-- &unknown; -->',
    )
    path = book / "OEBPS/Text/cap.xhtml"
    original = path.read_bytes()
    nav.regenerate(book)
    toc = ET.parse(book / "OEBPS/Text/TOC.xhtml").getroot()
    labels = [link.text for link in toc.findall(f".//{{{nav.XHTML}}}a")]
    assert "«A & B» <x>" in labels
    assert "Énfasis real final &unknown;" in labels
    assert (
        path.read_bytes()
        .replace(b' id="epl-nav-1"', b"")
        .replace(b' id="epl-nav-2"', b"")
        == original
    )


def test_declared_standard_internal_entity(book: Path):
    xhtml(book, "cap", '<h2 title="A&nbsp;B">Cap</h2>')
    path = book / "OEBPS/Text/cap.xhtml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            nav.XHTML_DTD, '<!DOCTYPE html [<!ENTITY nbsp "&#160;">]>'
        ),
        encoding="utf-8",
    )
    nav.regenerate(book)
    assert b'<!ENTITY nbsp "&#160;">' in path.read_bytes()


def test_global_hierarchy_across_files(book: Path):
    nav.regenerate(book)
    ncx = ET.parse(book / "OEBPS/toc.ncx").getroot()
    part = ncx.findall(f"{{{nav.NCX}}}navMap/{{{nav.NCX}}}navPoint")[2]
    assert len(part.findall(f"{{{nav.NCX}}}navPoint")) == 2
    assert len(part.findall(f"{{{nav.NCX}}}navPoint/{{{nav.NCX}}}navPoint")) == 1


def test_hierarchy_jump_fails(book: Path):
    xhtml(book, "cap", "<h3>Salto</h3>")
    assert_rejected_unchanged(book, "salto de jerarquía")


def test_first_heading_must_be_h1(book: Path):
    xhtml(book, "cubierta", "<h2>No hay padre</h2>")
    assert_rejected_unchanged(book, "salto de jerarquía")


def test_empty_heading_fails(book: Path):
    xhtml(book, "cap", '<h2 class="oculto" title=" "></h2>')
    assert_rejected_unchanged(book, "sin texto")


def test_hidden_self_closing_title_and_xml_id(book: Path):
    xhtml(
        book,
        "cap",
        '<h2 class="oculto" title="Cap oculto"/><h3 xml:id="xml-id">Detalle</h3>',
    )
    nav.regenerate(book)
    document = nav.read_xml(book / "OEBPS/Text/cap.xhtml", f"{{{nav.XHTML}}}html")
    assert element(document.tree, f".//{{{nav.XHTML}}}h2").get("id") == "epl-nav-1"
    assert (
        element(document.tree, f".//{{{nav.XHTML}}}h3").get(f"{{{nav.XML}}}id")
        == "xml-id"
    )


def test_missing_navigation_registered_in_template_locations(book: Path):
    package = read_opf(book)
    manifest = element(package, f"{{{nav.OPF}}}manifest")
    spine = element(package, f"{{{nav.OPF}}}spine")
    for item in list(manifest):
        if item.get("id") in ("TOC", "ncx", "epl.css", "sgc-toc.css"):
            manifest.remove(item)
    spine.remove(spine[4])
    package.remove(element(package, f"{{{nav.OPF}}}guide"))
    save_opf(book, package)
    (book / "OEBPS/Text/TOC.xhtml").unlink()
    (book / "OEBPS/toc.ncx").unlink()
    nav.regenerate(book)
    package = read_opf(book)
    items = {
        item.get("href"): item
        for item in package.findall(f"{{{nav.OPF}}}manifest/{{{nav.OPF}}}item")
    }
    for href in ("Text/TOC.xhtml", "toc.ncx", "Styles/epl.css", "Styles/sgc-toc.css"):
        assert href in items
    spine = element(package, f"{{{nav.OPF}}}spine")
    assert [ref.get("idref") for ref in spine[:4]] == [
        "cubierta",
        "sinopsis",
        "titulo",
        "info",
    ]
    assert spine[4].get("idref") == items["Text/TOC.xhtml"].get("id")
    assert spine.get("toc") == items["toc.ncx"].get("id")
    assert (
        element(package, f"{{{nav.OPF}}}guide/{{{nav.OPF}}}reference").get("href")
        == "Text/TOC.xhtml"
    )


def test_guide_cannot_select_a_chapter_as_toc(
    book: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(nav.tempfile, "mkstemp", forbid_io)
    for href in ("Text/parte.xhtml#parte-existente", "Text/parte.xhtml"):
        package = read_opf(book)
        manifest = element(package, f"{{{nav.OPF}}}manifest")
        spine = element(package, f"{{{nav.OPF}}}spine")
        for item in list(manifest):
            if item.get("id") == "TOC":
                manifest.remove(item)
        for ref in list(spine):
            if ref.get("idref") == "TOC":
                spine.remove(ref)
        element(package, f"{{{nav.OPF}}}guide/{{{nav.OPF}}}reference").set("href", href)
        save_opf(book, package)
        assert_rejected_unchanged(book, "dedicado al índice")


def test_guide_embedded_index_does_not_authorize_chapter_replacement(book: Path):
    xhtml(
        book,
        "parte",
        '<div class="sgc-toc-title">Índice local</div>'
        '<div class="sgc-toc-level-1"><a href="cap.xhtml">Capítulo</a></div>'
        '<h1 id="parte-existente">Parte I</h1><p>Texto que debe conservarse.</p>',
    )
    package = read_opf(book)
    manifest = element(package, f"{{{nav.OPF}}}manifest")
    spine = element(package, f"{{{nav.OPF}}}spine")
    manifest.remove(next(item for item in manifest if item.get("id") == "TOC"))
    spine.remove(next(ref for ref in spine if ref.get("idref") == "TOC"))
    element(package, f"{{{nav.OPF}}}guide/{{{nav.OPF}}}reference").set(
        "href", "Text/parte.xhtml#parte-existente"
    )
    save_opf(book, package)
    assert_rejected_unchanged(book, "dedicado al índice")


def test_existing_toc_at_end_preserved(book: Path):
    package = read_opf(book)
    spine = element(package, f"{{{nav.OPF}}}spine")
    ref = spine[4]
    spine.remove(ref)
    spine.append(ref)
    save_opf(book, package)
    nav.regenerate(book)
    assert element(read_opf(book), f"{{{nav.OPF}}}spine")[-1].get("idref") == "TOC"


def test_invalid_xml_late_has_no_partial_writes(book: Path):
    write(
        book,
        "OEBPS/Text/final.xhtml",
        f'<html xmlns="{nav.XHTML}"><body><h1>Mal</body></html>',
    )
    assert_rejected_unchanged(book, "XML inválido")


def test_invalid_existing_navigation_has_no_partial_writes(book: Path):
    write(book, "OEBPS/toc.ncx", "<ncx>")
    assert_rejected_unchanged(book, "XML inválido")


def test_duplicate_id_fails(book: Path):
    xhtml(book, "final", '<h2 id="x">Dos</h2><h1 id="x">Fin</h1>')
    assert_rejected_unchanged(book, "id duplicado")


def test_external_custom_dtd_and_entity_attacks(book: Path):
    attacks = [
        '<!DOCTYPE html SYSTEM "file:///etc/passwd">',
        '<!DOCTYPE html SYSTEM "https://evil.invalid/evil.dtd">',
        '<!DOCTYPE html [<!ENTITY attack SYSTEM "file:///etc/passwd">]>',
        '<!DOCTYPE html [<!ENTITY % attack SYSTEM "https://evil.invalid/evil.dtd">%attack;]>',
        '<!DOCTYPE html [<!ENTITY a "boom"><!ENTITY b "&a;&a;">]>',
        '<!DOCTYPE html [<!ENTITY nbsp "incorrecto">]>',
        '<!DOCTYPE html [<!ATTLIST html evil CDATA "value">]>',
    ]
    for dtd in attacks:
        write(
            book,
            "OEBPS/Text/final.xhtml",
            f'{dtd}<html xmlns="{nav.XHTML}"><body><h1>Fin</h1></body></html>',
        )
        assert_rejected_unchanged(book)


def test_unknown_entity_even_in_attribute_fails(book: Path):
    xhtml(book, "cap", '<h2 title="&unknown;">Cap</h2>')
    assert_rejected_unchanged(book, "entidad")


def test_no_network_for_standard_dtd(book: Path, no_network):
    nav.regenerate(book)


def test_epub3_rejected(book: Path):
    package = read_opf(book)
    package.set("version", "3.0")
    save_opf(book, package)
    assert_rejected_unchanged(book, "EPUB3")


def test_namespaces_rejected(book: Path):
    for body in (
        "<html><body><h1>Sin namespace</h1></body></html>",
        f'<html xmlns="{nav.XHTML}"><body><h1 xmlns="urn:evil">Mal</h1></body></html>',
    ):
        write(book, "OEBPS/Text/final.xhtml", body)
        assert_rejected_unchanged(book, "namespace")


def test_opf_namespace_rejected(book: Path):
    write(book, "OEBPS/content.opf", '<package version="2.0"/>')
    assert_rejected_unchanged(book, "namespace")


def test_nonlocal_and_escaping_paths_rejected(book: Path):
    for href in (
        "https://evil.invalid/book.xhtml",
        "//evil.invalid/book.xhtml",
        "../../../escape.xhtml",
        "%2e%2e/%2e%2e/escape.xhtml",
        "/etc/passwd",
        "Text/cap.xhtml#id",
        "Text/cap.xhtml?x=1",
        "Text%5ccap.xhtml",
        "Text/cap.xhtml%00",
        "Text/%zz.xhtml",
        "Text/%FF.xhtml",
        "Text/cap%0A.xhtml",
        "C%3A/escape.xhtml",
        "http://[invalid",
    ):
        package = read_opf(book)
        manifest = element(package, f"{{{nav.OPF}}}manifest")
        item = next(item for item in manifest if item.get("id") == "cap")
        item.set("href", href)
        save_opf(book, package)
        assert_rejected_unchanged(book)


def test_symlinks_rejected(book: Path):
    path = book / "OEBPS/Text/cap.xhtml"
    path.unlink()
    path.symlink_to(book / "OEBPS/Text/parte.xhtml")
    assert_rejected_unchanged(book, "simbólicos")


def test_symlink_directory_rejected(book: Path):
    alias = book / "alias"
    alias.symlink_to(book / "OEBPS", target_is_directory=True)
    package = read_opf(book)
    manifest = element(package, f"{{{nav.OPF}}}manifest")
    item = next(item for item in manifest if item.get("id") == "cap")
    item.set("href", "../alias/Text/cap.xhtml")
    save_opf(book, package)
    assert_rejected_unchanged(book, "simbólicos")


def test_fixed_frontmatter_not_reordered(book: Path):
    package = read_opf(book)
    spine = element(package, f"{{{nav.OPF}}}spine")
    spine[0].set("idref", "sinopsis")
    spine[1].set("idref", "cubierta")
    save_opf(book, package)
    assert_rejected_unchanged(book, "primeras cuatro")


def test_container_rootfile_escape_rejected(book: Path):
    write(
        book,
        "META-INF/container.xml",
        f'<container xmlns="{nav.CONTAINER}"><rootfiles><rootfile full-path="../escape.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
    )
    assert_rejected_unchanged(book, "escapa")


def test_stage_failure_leaves_originals(book: Path, monkeypatch: pytest.MonkeyPatch):
    def disk_full(*args, **kwargs):
        raise OSError("disco lleno")

    before = snapshot(book)
    monkeypatch.setattr(nav.tempfile, "mkstemp", disk_full)
    with pytest.raises(OSError, match="disco lleno"):
        nav.regenerate(book)
    assert snapshot(book) == before


def test_standard_entities_without_doctype_rejected_without_writes(book: Path):
    xhtml(book, "cap", '<h2 title="&copy;&nbsp;&euro;">Texto</h2>')
    path = book / "OEBPS/Text/cap.xhtml"
    path.write_bytes(path.read_bytes().replace(nav.XHTML_DTD.encode(), b""))
    assert_rejected_unchanged(book)


def test_parse_xml_requires_entity_declarations(book: Path):
    path = book / "OEBPS/Text/cap.xhtml"
    for dtd in (
        "",
        "<!DOCTYPE html>",
        '<!DOCTYPE html [<!ENTITY nbsp "&#160;">]>',
        '<!DOCTYPE html SYSTEM "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">',
    ):
        for heading in ("<h2>&copy;</h2>", '<h2 title="&copy;">Texto</h2>'):
            data = (
                f'{dtd}<html xmlns="{nav.XHTML}"><body>{heading}</body></html>'.encode()
            )
            before = snapshot(book)
            with pytest.raises(nav.NavigationError):
                nav.parse_xml(path, data)
            assert snapshot(book) == before


def test_parse_xml_public_xhtml_entities_without_network(book: Path, no_network):
    path = book / "OEBPS/Text/cap.xhtml"
    data = (
        nav.XHTML_DTD
        + f'<html xmlns="{nav.XHTML}"><body><h2 title="&copy;&nbsp;">&copy;&nbsp;</h2></body></html>'
    ).encode()
    document = nav.parse_xml(path, data)
    heading = element(document.tree, f".//{{{nav.XHTML}}}h2")
    assert heading.text == "©\u00a0"
    assert heading.get("title") == "©\u00a0"
    assert document.data == data


def test_literal_entity_comments_and_cdata_without_doctype_preserved(book: Path):
    path = book / "OEBPS/Text/cap.xhtml"
    original = (
        f'<html xmlns="{nav.XHTML}"><head><title>Cap</title></head><body>'
        '<h2 title="&amp;copy;">&amp;copy;<!-- &copy; &unknown; -->'
        "<![CDATA[ &copy; &unknown; ]]></h2></body></html>"
    ).encode()
    path.write_bytes(original)
    document = nav.parse_xml(path, original)
    heading = element(document.tree, f".//{{{nav.XHTML}}}h2")
    assert heading.get("title") == "&copy;"
    assert heading.text == "&copy;"
    assert heading[0].text == " &copy; &unknown; "
    assert heading[0].tail == " &copy; &unknown; "
    assert document.data == original
    nav.regenerate(book)
    assert path.read_bytes() == original.replace(
        b'&amp;copy;">', b'&amp;copy;" id="epl-nav-1">'
    )
    assert nav.regenerate(book) == 0


def test_relative_paths_and_encoded_fragments(book: Path):
    for source, target, expected in (
        (book / "toc.ncx", book / "Text/uno.xhtml", "Text/uno.xhtml"),
        (book / "Text/TOC.xhtml", book / "Text/uno.xhtml", "uno.xhtml"),
        (book / "Text/TOC.xhtml", book / "Styles/epl.css", "../Styles/epl.css"),
        (book / "a/b/toc.ncx", book / "c/á uno.xhtml", "../../c/%C3%A1%20uno.xhtml"),
    ):
        assert nav.relative(source, target) == expected
        assert (
            nav.relative(source, target, "índice:uno")
            == expected + "#%C3%ADndice%3Auno"
        )
    assert nav.plan(book) == nav.plan(book / "OEBPS" / "..")


def test_custom_container_rootfile_and_navigation_locations(book: Path):
    xhtml(
        book,
        "TOC",
        '<div class="sgc-toc-title" id="contenido">Índice</div><div class="sgc-toc-level-1"><a href="parte.xhtml#parte-existente">Parte I</a></div>',
    )
    package = read_opf(book)
    for item in element(package, f"{{{nav.OPF}}}manifest"):
        if item.get("id") == "ncx":
            item.set("href", "Text/indice.ncx")
        elif item.get("id") == "TOC":
            item.set("href", "Text/indice.xhtml")
    element(package, f"{{{nav.OPF}}}guide/{{{nav.OPF}}}reference").set(
        "href", "Text/indice.xhtml#contenido"
    )
    save_opf(book, package)
    (book / "OEBPS/toc.ncx").replace(book / "OEBPS/Text/indice.ncx")
    (book / "OEBPS/Text/TOC.xhtml").replace(book / "OEBPS/Text/indice.xhtml")
    (book / "OEBPS/content.opf").replace(book / "OEBPS/libro.opf")
    (book / "OEBPS").replace(book / "Libro con espacios")
    write(
        book,
        "META-INF/container.xml",
        f'<container xmlns="{nav.CONTAINER}"><rootfiles><rootfile full-path="Libro%20con%20espacios/libro.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
    )
    nav.regenerate(book)
    base = book / "Libro con espacios"
    ncx = ET.parse(base / "Text/indice.ncx").getroot()
    toc = ET.parse(base / "Text/indice.xhtml").getroot()
    assert (
        element(ncx, f".//{{{nav.NCX}}}content").get("src")
        == "cubierta.xhtml#epl-nav-1"
    )
    assert element(toc, f".//{{{nav.XHTML}}}link").get("href") == "../Styles/epl.css"
    assert nav.regenerate(book) == 0


def test_comments_in_container_manifest_and_spine(book: Path):
    path = book / "META-INF/container.xml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "<rootfiles>", "<!-- antes --><rootfiles><!-- dentro -->"
        ),
        encoding="utf-8",
    )
    package = read_opf(book)
    element(package, f"{{{nav.OPF}}}manifest").insert(0, ET.Comment("manifest"))
    element(package, f"{{{nav.OPF}}}spine").insert(2, ET.Comment("spine"))
    save_opf(book, package)
    nav.regenerate(book)
    assert b"<!--spine-->" in (book / "OEBPS/content.opf").read_bytes()


def test_prefixed_xhtml_bom_svg_mathml_preserved(book: Path):
    path = book / "OEBPS/Text/cap.xhtml"
    original = (
        f'\ufeff<?xml version="1.0" encoding="utf-8"?>\n'
        f'<x:html xmlns:x="{nav.XHTML}" xmlns:svg="http://www.w3.org/2000/svg" xmlns:m="http://www.w3.org/1998/Math/MathML">'
        "<x:head><x:title>Prueba</x:title></x:head><x:body>"
        "<svg:svg><svg:title>Imagen</svg:title></svg:svg><m:math><m:mi>x</m:mi></m:math>"
        '<x:h2 title="á &gt; b" /></x:body></x:html>'
    ).encode()
    path.write_bytes(original)
    nav.regenerate(book)
    assert path.read_bytes() == original.replace(b" />", b'  id="epl-nav-1"/>')
    assert nav.regenerate(book) == 0


def test_internal_namespaces_rejected(book: Path):
    for body in (
        '<h2>Cap</h2><p xmlns="">Sin namespace</p>',
        '<h2>Cap</h2><p xmlns="urn:incorrecto">Otro</p>',
    ):
        xhtml(book, "cap", body)
        assert_rejected_unchanged(book, "namespace")


def test_xml_base_rejected(book: Path):
    xhtml(book, "cap", '<h2 xml:base="https://evil.invalid/">Cap</h2>')
    assert_rejected_unchanged(book, "xml:base")


def test_duplicate_opf_structures_rejected(book: Path):
    package = read_opf(book)
    ET.SubElement(package, f"{{{nav.OPF}}}spine")
    save_opf(book, package)
    assert_rejected_unchanged(book, "duplicado")


def test_unreferenced_symlink_rejected(book: Path):
    (book / "sin-referencia").symlink_to("no-existe")
    assert_rejected_unchanged(book, "simbólicos")


def test_symlink_directory_argument_rejected(book: Path, tmp_path: Path):
    alias = tmp_path / "alias"
    alias.symlink_to(book, target_is_directory=True)
    before = snapshot(book)
    with pytest.raises(nav.NavigationError, match="simbólicos"):
        nav.regenerate(alias)
    assert snapshot(book) == before


def test_guide_escape_rejected_even_when_not_toc(book: Path):
    package = read_opf(book)
    ET.SubElement(
        element(package, f"{{{nav.OPF}}}guide"),
        f"{{{nav.OPF}}}reference",
        {"type": "text", "href": "../../fuera.xhtml#id"},
    )
    save_opf(book, package)
    assert_rejected_unchanged(book, "escapa")


def test_missing_output_parent_is_validated_before_staging(
    book: Path, monkeypatch: pytest.MonkeyPatch
):
    package = read_opf(book)
    for item in element(package, f"{{{nav.OPF}}}manifest"):
        if item.get("id") == "TOC":
            item.set("href", "Ausente/TOC.xhtml")
    element(package, f"{{{nav.OPF}}}guide/{{{nav.OPF}}}reference").set(
        "href", "Ausente/TOC.xhtml"
    )
    save_opf(book, package)
    monkeypatch.setattr(nav.tempfile, "mkstemp", forbid_io)
    assert_rejected_unchanged(book, "directorio de destino")


def test_replace_failure_rolls_back_and_cleans_temporaries(
    book: Path, monkeypatch: pytest.MonkeyPatch
):
    original_replace = Path.replace
    calls = 0

    def replace(path, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("fallo de reemplazo")
        return original_replace(path, target)

    before = snapshot(book)
    monkeypatch.setattr(Path, "replace", replace)
    with pytest.raises(OSError, match="fallo de reemplazo"):
        nav.regenerate(book)
    assert snapshot(book) == before
    assert not list(book.rglob(".epl-nav-*"))


def test_help_is_spanish(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as result:
        nav.main(["--help"])
    assert result.value.code == 0
    output = capsys.readouterr()
    assert "muestra esta ayuda" in output.out
    assert "DIRECTORY" in output.out


def test_cli_error_is_spanish(book: Path, capsys: pytest.CaptureFixture[str]):
    write(book, "OEBPS/Text/final.xhtml", "<roto>")
    assert nav.main([str(book)]) == 1
    assert "Error de navegación:" in capsys.readouterr().err


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__)), *sys.argv[1:]]))
