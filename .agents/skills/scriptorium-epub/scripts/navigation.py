#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Regenera la navegación EPUB2 ePL sin dependencias ni acceso a la red.

Los XHTML se modifican únicamente mediante inserciones ASCII de id; se conservan
sus bytes, DTD, entidades, comentarios y prefijos. Se admite XML UTF-8. No es un
validador de esquema EPUB ni una transacción resistente a cortes de alimentación.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.entities import name2codepoint
from pathlib import Path
from typing import NoReturn
from urllib.parse import quote, unquote, urlsplit
from xml.parsers import expat

OPF = "http://www.idpf.org/2007/opf"
DC = "http://purl.org/dc/elements/1.1/"
XHTML = "http://www.w3.org/1999/xhtml"
NCX = "http://www.daisy.org/z3986/2005/ncx/"
CONTAINER = "urn:oasis:names:tc:opendocument:xmlns:container"
XML = "http://www.w3.org/XML/1998/namespace"
XHTML_DTD = (
    '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"\n'
    '  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
)
NCX_DTD = (
    '<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"\n'
    '  "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
)
DTDS = {
    "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd": (
        "html",
        "-//W3C//DTD XHTML 1.1//EN",
    ),
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd": (
        "html",
        "-//W3C//DTD XHTML 1.0 Strict//EN",
    ),
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd": (
        "html",
        "-//W3C//DTD XHTML 1.0 Transitional//EN",
    ),
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd": (
        "html",
        "-//W3C//DTD XHTML 1.0 Frameset//EN",
    ),
    "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd": (
        "ncx",
        "-//NISO//DTD ncx 2005-1//EN",
    ),
}
HEADINGS = {f"{{{XHTML}}}h{n}": n for n in range(1, 7)}
# El lexer omite regiones donde &nombre; es texto literal, no una referencia XML.
TOKENS = re.compile(
    r"<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|"
    r"<!DOCTYPE(?:[^\"'\[>]|\"[^\"]*\"|'[^']*'|\[(?:[^\]\"']|\"[^\"]*\"|'[^']*')*\])*>|"
    r"&([A-Za-z_:][\w.:-]*);"
)


class NavigationError(ValueError):
    """Entrada insegura, inválida o no compatible con EPUB2."""


def fail(message: str) -> NoReturn:
    raise NavigationError(message)


def compact(text: str) -> str:
    return " ".join(text.split())


def check_symlinks(path: Path) -> None:
    # También examinar los componentes léxicos anteriores a un posible '..'.
    for part in (path, *path.parents):
        if part.is_symlink():
            fail(f"No se permiten enlaces simbólicos: {part}")


def local_path(root: Path, base: Path, href: str) -> Path:
    if not href or any(ord(c) < 32 for c in href):
        fail(f"Referencia local inválida: {href!r}")
    try:
        uri = urlsplit(href)
    except ValueError as exc:
        raise NavigationError(f"Referencia local inválida: {href!r}") from exc
    if uri.scheme or uri.netloc or uri.query or uri.fragment:
        fail(f"Se requiere una ruta local sin consulta ni fragmento: {href!r}")
    if re.search(r"%(?![0-9a-fA-F]{2})", uri.path):
        fail(f"Escape URI inválido: {href!r}")
    try:
        name = unquote(uri.path, errors="strict")
    except UnicodeError as exc:
        raise NavigationError(f"Ruta URI no codificada en UTF-8: {href!r}") from exc
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in name
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
    ):
        fail(f"Ruta no permitida: {href!r}")
    candidate = base / name
    check_symlinks(candidate)
    path = candidate.resolve()
    if not path.is_relative_to(root):
        fail(f"La ruta escapa de DIRECTORY: {href!r}")
    if path.exists() and not path.is_file():
        fail(f"Se esperaba un archivo: {path}")
    return path


def relative(source: Path, target: Path, fragment: str | None = None) -> str:
    # Path.relative_to no admite walk_up en Python 3.11.
    parent = source.parent
    common = next(
        base for base in (parent, *parent.parents) if target.is_relative_to(base)
    )
    path = Path(*([".."] * len(parent.relative_to(common).parts))) / target.relative_to(
        common
    )
    href = quote(path.as_posix(), safe="/-._~")
    return href + ("#" + quote(fragment, safe="-._~") if fragment is not None else "")


@dataclass
class Document:
    path: Path
    data: bytes
    tree: ET.Element
    starts: dict[ET.Element, int]


def parse_xml(path: Path, data: bytes) -> Document:
    """Expat controla las declaraciones antes de que ElementTree lea entidades.

    Nunca se carga el subconjunto externo. Las entidades XHTML1 requieren una
    DTD pública estándar o una declaración interna explícita de valor seguro.
    Se sustituyen solo en la copia de análisis, incluso en atributos (Expat
    omitiría allí referencias a entidades de un subconjunto externo no leído).
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NavigationError(f"{path}: se requiere XML UTF-8: {exc}") from exc
    parser = expat.ParserCreate(namespace_separator="}")
    starts: list[int] = []
    dtd_name = None
    root_name = None
    public_xhtml_dtd = False
    declared_entities: set[str] = set()

    def declaration(version, encoding, standalone):
        if encoding and encoding.lower().replace("_", "-") not in (
            "utf-8",
            "utf8",
            "us-ascii",
            "ascii",
        ):
            fail(f"{path}: codificación no compatible: {encoding}; use UTF-8")

    def doctype(name, system, public, internal):
        nonlocal dtd_name, public_xhtml_dtd
        dtd_name = name
        if system is not None or public is not None:
            if DTDS.get(system) != (name, public) and not (
                public is None and system in DTDS and DTDS[system][0] == name
            ):
                fail(f"{path}: DTD externa personalizada no permitida")
        elif name != "html":
            fail(f"{path}: DTD no permitida")
        public_xhtml_dtd = (
            name == "html" and public is not None and DTDS.get(system) == (name, public)
        )

    def entity(name, parameter, value, base, system, public, notation):
        expected = chr(name2codepoint[name]) if name in name2codepoint else None
        if (
            parameter
            or system
            or public
            or notation
            or expected is None
            or value != expected
        ):
            fail(f"{path}: declaración de entidad no permitida: {name}")
        declared_entities.add(name)

    def forbidden(*args):
        fail(f"{path}: declaración DTD personalizada no permitida")

    parser.XmlDeclHandler = declaration
    parser.StartDoctypeDeclHandler = doctype
    parser.EntityDeclHandler = entity
    parser.ElementDeclHandler = forbidden
    parser.AttlistDeclHandler = forbidden
    parser.NotationDeclHandler = forbidden
    parser.ExternalEntityRefHandler = forbidden
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)

    def start(name, attrs):
        nonlocal root_name
        if root_name is None:
            root_name = name
        starts.append(parser.CurrentByteIndex)

    parser.StartElementHandler = start

    def substitute(match):
        name = match.group(1)
        if name is None or name in ("amp", "lt", "gt", "quot", "apos"):
            return match.group()
        if (
            root_name != f"{XHTML}}}html"
            or name not in name2codepoint
            or not (public_xhtml_dtd or name in declared_entities)
        ):
            fail(f"{path}: entidad no declarada o no estándar: &{name};")
        return f"&#{name2codepoint[name]};"

    try:
        parser.Parse(data, True)
        safe = TOKENS.sub(substitute, text)
        tree = ET.fromstring(
            safe,
            parser=ET.XMLParser(
                target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
            ),
        )
    except (expat.ExpatError, ET.ParseError) as exc:
        raise NavigationError(f"{path}: XML inválido: {exc}") from exc
    root_name = tree.tag.rsplit("}", 1)[-1]
    if dtd_name is not None and (
        root_name != dtd_name
        or (dtd_name == "html" and tree.tag != f"{{{XHTML}}}html")
        or (dtd_name == "ncx" and tree.tag != f"{{{NCX}}}ncx")
    ):
        fail(f"{path}: namespace o raíz incompatible con la DTD")
    elements = [element for element in tree.iter() if isinstance(element.tag, str)]
    if len(elements) != len(starts):
        fail(f"{path}: declaraciones XML no compatibles")
    return Document(path, data, tree, dict(zip(elements, starts)))


def read_xml(path: Path, expected: str) -> Document:
    document = parse_xml(path, path.read_bytes())
    if document.tree.tag != expected:
        fail(f"{path}: raíz/namespace inválido; se esperaba {expected}")
    namespace = expected[1:].split("}", 1)[0]
    allowed = {namespace}
    if namespace == XHTML:
        allowed.update(
            {"http://www.w3.org/2000/svg", "http://www.w3.org/1998/Math/MathML"}
        )
    elif namespace == OPF:
        allowed.add(DC)
    for element in document.tree.iter():
        if not isinstance(element.tag, str):
            continue
        if (
            not element.tag.startswith("{")
            or element.tag[1:].split("}", 1)[0] not in allowed
        ):
            fail(f"{path}: elemento con namespace inválido: {element.tag}")
        # Ignorarlo produciría enlaces con un destino distinto al declarado.
        if f"{{{XML}}}base" in element.attrib:
            fail(f"{path}: xml:base no está soportado")
    return document


def dedicated_toc(path: Path) -> bool:
    """Una referencia guide no autoriza a reemplazar un capítulo completo."""
    if path.name.lower() == "toc.xhtml":
        return True
    if not path.is_file():
        return False
    body = read_xml(path, f"{{{XHTML}}}html").tree.find(f"{{{XHTML}}}body")
    if body is None or compact(body.text or ""):
        return False
    title = False
    links = 0
    for child in body:
        if compact(child.tail or ""):
            return False
        if not isinstance(child.tag, str):
            continue
        if child.tag != f"{{{XHTML}}}div":
            return False
        classes = child.get("class", "").split()
        content = [node for node in child if isinstance(node.tag, str)]
        if "sgc-toc-title" in classes:
            if title or content or not compact(child.text or ""):
                return False
            title = True
        elif any(re.fullmatch(r"sgc-toc-level-[1-6]", name) for name in classes):
            if compact(child.text or "") or len(content) != 1:
                return False
            anchor = content[0]
            if (
                anchor.tag != f"{{{XHTML}}}a"
                or not anchor.get("href")
                or any(isinstance(node.tag, str) for node in anchor)
                or any(compact(node.tail or "") for node in child)
            ):
                return False
            links += 1
        else:
            return False
    return title and links > 0


def identifiers(tree: ET.Element, path: Path) -> set[str]:
    seen: set[str] = set()
    for element in tree.iter():
        values = {element.get("id"), element.get(f"{{{XML}}}id")} - {None}
        for value in values:
            if not value or any(char.isspace() for char in value):
                fail(f"{path}: id vacío o con espacios")
            if value in seen:
                fail(f"{path}: id duplicado: {value}")
            seen.add(value)
    return seen


def heading_label(element: ET.Element) -> str:
    if compact(element.get("title", "")):
        return compact(element.get("title", ""))

    def text(node):
        chunks = [node.text or ""]
        for child in node:
            # Las llamadas a notas de ePL usan <a><sup>[n]</sup></a>.
            if isinstance(child.tag, str) and child.tag != f"{{{XHTML}}}sup":
                chunks.append(text(child))
            chunks.append(child.tail or "")
        return "".join(chunks)

    return compact(text(element))


def insert_ids(document: Document, additions: list[tuple[ET.Element, str]]) -> bytes:
    data = document.data
    insertions = []
    for element, identifier in additions:
        start = document.starts[element]
        # Buscar el cierre real del tag, no un '>' dentro de un atributo.
        token = re.match(rb"<(?:[^\"'>]|\"[^\"]*\"|'[^']*')*>", data[start:])
        if token is None:
            fail(f"{document.path}: no se pudo localizar el encabezado")
        end = start + token.end() - 1
        if data[end - 1 : end] == b"/":
            end -= 1
        insertions.append((end, f' id="{identifier}"'.encode("ascii")))
    for offset, value in sorted(insertions, reverse=True):
        data = data[:offset] + value + data[offset:]
    return data


@dataclass
class Entry:
    level: int
    label: str
    path: Path
    identifier: str


def serialize(tree: ET.Element, namespace: str, doctype: str = "") -> bytes:
    # OPF usa prefijo también en los atributos: el namespace por defecto no
    # se aplica a atributos como opf:role / opf:scheme.
    if namespace != OPF:
        ET.register_namespace("", namespace)
    ET.register_namespace("dc", DC)
    ET.register_namespace("opf", OPF)
    body = ET.tostring(tree, encoding="unicode", short_empty_elements=False)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        + (doctype + "\n" if doctype else "")
        + body
        + "\n"
    ).encode("utf-8")


def navigation(
    entries: list[Entry],
    ncx_path: Path,
    toc_path: Path,
    title: str,
    uid: str,
    language: str,
    css: list[Path],
) -> tuple[bytes, bytes]:
    ncx = ET.Element(f"{{{NCX}}}ncx", {"version": "2005-1"})
    head = ET.SubElement(ncx, f"{{{NCX}}}head")
    for name, value in (
        ("uid", uid),
        ("depth", str(max(e.level for e in entries))),
        ("totalPageCount", "0"),
        ("maxPageNumber", "0"),
    ):
        ET.SubElement(head, f"{{{NCX}}}meta", {"name": f"dtb:{name}", "content": value})
    ET.SubElement(
        ET.SubElement(ncx, f"{{{NCX}}}docTitle"), f"{{{NCX}}}text"
    ).text = title
    navmap = ET.SubElement(ncx, f"{{{NCX}}}navMap")
    parents = [navmap]
    html = ET.Element(f"{{{XHTML}}}html", {f"{{{XML}}}lang": language})
    head = ET.SubElement(html, f"{{{XHTML}}}head")
    ET.SubElement(head, f"{{{XHTML}}}title").text = "Índice de contenido"
    for path in css:
        ET.SubElement(
            head,
            f"{{{XHTML}}}link",
            {"href": relative(toc_path, path), "rel": "stylesheet", "type": "text/css"},
        )
    body = ET.SubElement(html, f"{{{XHTML}}}body")
    # No es h1: el índice nunca participa en su propia generación.
    ET.SubElement(
        body, f"{{{XHTML}}}div", {"class": "oculto sgc-toc-title"}
    ).text = "Índice de contenido"
    for number, entry in enumerate(entries, 1):
        parents = parents[: entry.level]
        point = ET.SubElement(
            parents[-1],
            f"{{{NCX}}}navPoint",
            {"id": f"navPoint-{number}", "playOrder": str(number)},
        )
        ET.SubElement(
            ET.SubElement(point, f"{{{NCX}}}navLabel"), f"{{{NCX}}}text"
        ).text = entry.label
        ET.SubElement(
            point,
            f"{{{NCX}}}content",
            {"src": relative(ncx_path, entry.path, entry.identifier)},
        )
        parents.append(point)
        div = ET.SubElement(
            body, f"{{{XHTML}}}div", {"class": f"sgc-toc-level-{entry.level}"}
        )
        ET.SubElement(
            div,
            f"{{{XHTML}}}a",
            {"href": relative(toc_path, entry.path, entry.identifier)},
        ).text = entry.label
    return serialize(ncx, NCX, NCX_DTD), serialize(html, XHTML, XHTML_DTD)


def plan(directory: Path) -> dict[Path, bytes]:
    check_symlinks(directory.absolute())
    root = directory.resolve()
    if not root.is_dir():
        fail(f"DIRECTORY no es un directorio: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            fail(f"No se permiten enlaces simbólicos: {path}")
    container_path = local_path(root, root, "META-INF/container.xml")
    container = read_xml(container_path, f"{{{CONTAINER}}}container").tree
    rootfiles = container.findall(f"{{{CONTAINER}}}rootfiles/{{{CONTAINER}}}rootfile")
    children = [child for child in container if isinstance(child.tag, str)]
    if (
        len(children) != 1
        or children[0].tag != f"{{{CONTAINER}}}rootfiles"
        or len([child for child in children[0] if isinstance(child.tag, str)]) != 1
        or len(rootfiles) != 1
        or rootfiles[0].get("media-type") != "application/oebps-package+xml"
    ):
        fail("container.xml debe declarar un único rootfile OPF")
    opf_path = local_path(root, root, rootfiles[0].get("full-path", ""))
    package = read_xml(opf_path, f"{{{OPF}}}package").tree
    if package.get("version") != "2.0":
        fail("Solo se admite EPUB2 (package version=2.0); EPUB3 no se convierte")
    identifiers(package, opf_path)
    metadata = package.find(f"{{{OPF}}}metadata")
    manifest = package.find(f"{{{OPF}}}manifest")
    spine = package.find(f"{{{OPF}}}spine")
    if metadata is None or manifest is None or spine is None:
        fail("OPF incompleto: faltan metadata, manifest o spine")
    for name in ("metadata", "manifest", "spine", "guide"):
        if len(package.findall(f"{{{OPF}}}{name}")) > 1:
            fail(f"OPF con elemento duplicado: {name}")
    if any(
        isinstance(child.tag, str) and not child.tag.startswith(f"{{{OPF}}}")
        for child in package
    ):
        fail("OPF con namespace inválido en su estructura")
    title = compact(metadata.findtext(f"{{{DC}}}title", ""))
    uid_ref = package.get("unique-identifier")
    uid = next(
        (
            compact(e.text or "")
            for e in metadata.findall(f"{{{DC}}}identifier")
            if uid_ref and e.get("id") == uid_ref
        ),
        "",
    )
    if not title or not uid:
        fail("OPF sin dc:title o unique-identifier resoluble y no vacío")
    language = compact(metadata.findtext(f"{{{DC}}}language", "es")) or "es"
    items: dict[str, tuple[ET.Element, Path]] = {}
    paths: dict[Path, ET.Element] = {}
    for item in manifest:
        if not isinstance(item.tag, str):
            continue
        if item.tag != f"{{{OPF}}}item" or not item.get("id"):
            fail("Entrada inválida en manifest")
        path = local_path(root, opf_path.parent, item.get("href", ""))
        if path in paths or item.get("id") in items:
            fail(f"Entrada duplicada en manifest: {path}")
        items[item.attrib["id"]] = (item, path)
        paths[path] = item
    used_ids = identifiers(package, opf_path)

    def register(path, media_type, preferred_id):
        if path in paths:
            item = paths[path]
            if item.get("media-type") != media_type:
                fail(f"Tipo de medio incorrecto: {path}")
            return item
        identifier = preferred_id
        number = 2
        while identifier in used_ids:
            identifier = f"{preferred_id}-{number}"
            number += 1
        used_ids.add(identifier)
        item = ET.SubElement(
            manifest,
            f"{{{OPF}}}item",
            {
                "id": identifier,
                "href": relative(opf_path, path),
                "media-type": media_type,
            },
        )
        paths[path] = item
        items[identifier] = (item, path)
        return item

    ncx_candidates = [
        (item, path)
        for item, path in items.values()
        if item.get("media-type") == "application/x-dtbncx+xml"
    ]
    if len(ncx_candidates) > 1:
        fail("Hay varios NCX en manifest")
    if ncx_candidates:
        ncx_item, ncx_path = ncx_candidates[0]
    else:
        ncx_path = local_path(root, opf_path.parent, "toc.ncx")
        ncx_item = register(ncx_path, "application/x-dtbncx+xml", "ncx")
    guide = package.find(f"{{{OPF}}}guide")
    toc_refs = []
    if guide is not None:
        for reference in guide:
            if not isinstance(reference.tag, str):
                continue
            if reference.tag != f"{{{OPF}}}reference":
                fail("Entrada inválida en guide")
            local_path(
                root, opf_path.parent, reference.get("href", "").split("#", 1)[0]
            )
            if reference.get("type") == "toc":
                toc_refs.append(reference)
    template_toc = local_path(root, opf_path.parent, "Text/TOC.xhtml")
    toc_candidates = {
        path for item, path in items.values() if path.name.lower() == "toc.xhtml"
    }
    for ref in toc_refs:
        href = ref.get("href", "")
        path = local_path(root, opf_path.parent, href.split("#", 1)[0])
        # Un fragmento puede señalar un índice incrustado en un capítulo. Solo
        # normalizarlo al archivo completo si el destino es un índice dedicado.
        if not dedicated_toc(path):
            fail(f"guide toc no apunta a un documento dedicado al índice: {href!r}")
        toc_candidates.add(path)
    if len(toc_candidates) > 1:
        fail("Referencias contradictorias a TOC.xhtml en manifest/guide")
    toc_path = next(iter(toc_candidates), template_toc)
    if toc_path == ncx_path or toc_path == opf_path:
        fail("Las rutas OPF, NCX y TOC deben ser distintas")
    toc_item = register(toc_path, "application/xhtml+xml", "TOC.xhtml")
    css = []
    for name in ("epl.css", "sgc-toc.css"):
        candidates = [path for path in paths if path.name == name]
        if len(candidates) > 1:
            fail(f"Hoja de estilos ambigua: {name}")
        path = (
            candidates[0]
            if candidates
            else local_path(root, opf_path.parent, f"Styles/{name}")
        )
        if not path.is_file():
            fail(f"Falta la hoja de estilos de la plantilla: {path}")
        register(path, "text/css", name)
        css.append(path)
    # No ocultar XML roto simplemente porque sus índices van a regenerarse.
    for path, expected in ((toc_path, f"{{{XHTML}}}html"), (ncx_path, f"{{{NCX}}}ncx")):
        if path.exists():
            read_xml(path, expected)
    refs = [ref for ref in spine if isinstance(ref.tag, str)]
    spine_paths = []
    seen = set()
    for ref in refs:
        if ref.tag != f"{{{OPF}}}itemref" or ref.get("idref") not in items:
            fail("itemref de spine no resoluble")
        item, path = items[ref.attrib["idref"]]
        if path in seen or item.get("media-type") != "application/xhtml+xml":
            fail(f"Spine duplicado o no XHTML: {path}")
        seen.add(path)
        spine_paths.append(path)
    fixed = ["cubierta.xhtml", "sinopsis.xhtml", "titulo.xhtml", "info.xhtml"]
    if [path.name for path in spine_paths[:4]] != fixed:
        fail(
            "Las primeras cuatro entradas de spine deben ser cubierta, sinopsis, titulo e info"
        )
    if toc_path not in seen:
        # Los comentarios no cuentan como entradas del orden de lectura.
        position = list(spine).index(refs[3]) + 1
        spine.insert(
            position, ET.Element(f"{{{OPF}}}itemref", {"idref": toc_item.get("id")})
        )
    elif spine_paths.index(toc_path) not in (4, len(spine_paths) - 1):
        fail("TOC.xhtml debe estar tras info.xhtml o al final de spine")
    spine.set("toc", ncx_item.attrib["id"])
    if guide is None:
        guide = ET.SubElement(package, f"{{{OPF}}}guide")
    if toc_refs:
        reference = toc_refs[0]
        for duplicate in toc_refs[1:]:
            guide.remove(duplicate)
    else:
        reference = ET.SubElement(guide, f"{{{OPF}}}reference")
    reference.attrib.update(
        {
            "type": "toc",
            "title": "Índice de contenido",
            "href": relative(opf_path, toc_path),
        }
    )

    entries: list[Entry] = []
    changes: dict[Path, bytes] = {}
    previous = 0
    for path in spine_paths:
        if path == toc_path:
            continue
        document = read_xml(path, f"{{{XHTML}}}html")
        ids = identifiers(document.tree, path)
        body = document.tree.find(f"{{{XHTML}}}body")
        if body is None:
            fail(f"{path}: falta body XHTML")
        additions = []
        number = 1
        for element in document.tree.iter():
            if (
                isinstance(element.tag, str)
                and re.fullmatch(r"h[1-6]", element.tag.rsplit("}", 1)[-1])
                and element.tag not in HEADINGS
            ):
                fail(f"{path}: heading con namespace inválido")
        for element in body.iter():
            if element.tag not in HEADINGS:
                continue
            label = heading_label(element)
            if not label:
                fail(f"{path}: encabezado sin texto ni title válido")
            level = HEADINGS[element.tag]
            if level > previous + 1:
                fail(f"{path}: salto de jerarquía h{previous} → h{level} ({label})")
            previous = level
            identifier = element.get("id") or element.get(f"{{{XML}}}id")
            if identifier is None:
                while f"epl-nav-{number}" in ids:
                    number += 1
                identifier = f"epl-nav-{number}"
                ids.add(identifier)
                additions.append((element, identifier))
            entries.append(Entry(level, label, path, identifier))
        if additions:
            changes[path] = insert_ids(document, additions)
    if not entries:
        fail("No hay encabezados para generar navegación")
    ncx_data, toc_data = navigation(
        entries, ncx_path, toc_path, title, uid, language, css
    )
    changes.update(
        {ncx_path: ncx_data, toc_path: toc_data, opf_path: serialize(package, OPF)}
    )
    # Validar incluso las inserciones quirúrgicas antes de abrir ningún destino.
    for path, data in changes.items():
        if not path.parent.is_dir():
            fail(f"No existe el directorio de destino de la plantilla: {path.parent}")
        result = parse_xml(path, data)
        identifiers(result.tree, path)
    return {
        path: data
        for path, data in changes.items()
        if not path.exists() or path.read_bytes() != data
    }


def commit(changes: dict[Path, bytes]) -> None:
    """Preparar todos los temporales antes de reemplazar el primer archivo.

    Cada reemplazo es atómico; el conjunto no es una transacción del filesystem.
    Un fallo de E/S durante los reemplazos intenta restaurar los originales.
    """
    staged = {}
    originals = {}
    replaced = []
    try:
        for path, data in changes.items():
            check_symlinks(path)
            originals[path] = path.read_bytes() if path.exists() else None
            if not path.parent.is_dir():
                fail(
                    f"No existe el directorio de destino de la plantilla: {path.parent}"
                )
            fd, name = tempfile.mkstemp(prefix=".epl-nav-", dir=path.parent)
            temporary = Path(name)
            staged[path] = temporary
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists():
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
        for path, temporary in staged.items():
            temporary.replace(path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def regenerate(directory: Path) -> int:
    changes = plan(directory)
    commit(changes)
    return len(changes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenera toc.ncx y TOC.xhtml desde los encabezados del spine EPUB2 ePL.",
        epilog="Valida todo antes de escribir. No descarga DTD ni convierte EPUB3. XML UTF-8.",
        add_help=False,
    )
    parser._positionals.title = "argumentos posicionales"
    parser._optionals.title = "opciones"
    parser.add_argument(
        "-h", "--help", action="help", help="muestra esta ayuda y termina"
    )
    parser.add_argument(
        "directory",
        metavar="DIRECTORY",
        type=Path,
        help="directorio raíz del EPUB descomprimido (con META-INF/container.xml)",
    )
    args = parser.parse_args(argv)
    try:
        count = regenerate(args.directory)
    except (NavigationError, OSError, UnicodeError, ValueError) as exc:
        print(f"Error de navegación: {exc}", file=sys.stderr)
        return 1
    print(f"Navegación EPUB2 regenerada: {count} archivo(s) actualizado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
