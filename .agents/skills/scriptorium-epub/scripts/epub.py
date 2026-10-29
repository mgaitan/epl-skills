#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Preparación, empaquetado y auditoría local del perfil EPUB2 ePL r2.1.

No modifica libros al comprobarlos, no autocorrige y no certifica conformidad.
El parser XML seguro se comparte con navigation.py, incluido en esta skill.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import stat
import struct
import subprocess
import sys
import uuid
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

import navigation as nav

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "resources" / "epub-base-epl-r2.1.epub"
MIMETYPE = b"application/epub+zip"
MAX_MEMBER = 32 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILES = 10000
DEFAULT_EPUBCHECK_IMAGE = (
    "yamamotoatshoeisha/epubcheck:epub5.4.0_jdk27"
    "@sha256:c69bb8ea600157e774b7682b15f9a3d49f7d6b45c187966ca95fa4d04c3dc503"
)
OPF, DC, XHTML, NCX, XML = nav.OPF, nav.DC, nav.XHTML, nav.NCX, nav.XML
SVG = "http://www.w3.org/2000/svg"
MEDIA = {
    ".xhtml": "application/xhtml+xml",
    ".html": "application/xhtml+xml",
    ".css": "text/css",
    ".ncx": "application/x-dtbncx+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}


def member_name(name: str) -> str:
    path = Path(name)
    if (
        not name
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
        or any(p in ("", ".", "..") for p in name.rstrip("/").split("/"))
    ):
        raise ValueError(f"Ruta ZIP no permitida: {name!r}")
    return path.as_posix()


def uri_target(source: str, value: str) -> tuple[str | None, str]:
    """Resuelve URI internas como rutas ZIP, sin consultar el sistema de archivos."""
    if any(ord(c) < 32 for c in value):
        raise ValueError(f"URI con caracteres de control: {value!r}")
    uri = urlsplit(value)
    if uri.scheme or uri.netloc:
        return None, ""
    if uri.query or re.search(r"%(?![0-9A-Fa-f]{2})", value):
        raise ValueError(f"URI local no soportada: {value!r}")
    name = unquote(uri.path, errors="strict")
    if "\\" in name or ":" in name or name.startswith("/"):
        raise ValueError(f"Ruta URI no permitida: {value!r}")
    path = Path(source).parent / name if name else Path(source)
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if not parts:
                raise ValueError(f"La URI escapa del EPUB: {value!r}")
            parts.pop()
        elif part != ".":
            parts.append(part)
    target = member_name(Path(*parts).as_posix())
    return target, unquote(uri.fragment, errors="strict")


def read_zip(path: Path) -> tuple[dict[str, bytes], list[zipfile.ZipInfo]]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_TOTAL:
            raise ValueError(
                "ZIP excede límites de seguridad (10000 entradas / 256 MiB)"
            )
        files: dict[str, bytes] = {}
        seen: set[str] = set()
        for info in infos:
            name = member_name(info.filename)
            if name in seen:
                raise ValueError(f"Entrada ZIP duplicada: {name}")
            seen.add(name)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (
                stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
            ):
                raise ValueError(f"Entrada ZIP especial no permitida: {name}")
            if info.file_size > MAX_MEMBER or info.flag_bits & 1:
                raise ValueError(f"Entrada cifrada o mayor de 32 MiB: {name}")
            if not info.is_dir():
                files[name] = archive.read(info)
        return files, infos


def read_directory(root: Path) -> dict[str, bytes]:
    nav.check_symlinks(root)
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"No es un directorio: {root}")
    files: dict[str, bytes] = {}
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            raise ValueError(f"Archivo especial no permitido: {path}")
        if path.is_file():
            name = member_name(path.relative_to(root).as_posix())
            size = path.stat().st_size
            total += size
            if size > MAX_MEMBER or total > MAX_TOTAL or len(files) >= MAX_FILES:
                raise ValueError("Directorio excede límites de seguridad")
            files[name] = path.read_bytes()
    return files


def image_size(data: bytes) -> tuple[int, int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if not data.startswith(b"\xff\xd8"):
        return None
    pos = 2
    while pos + 3 < len(data):
        if data[pos] != 255:
            return None
        while pos < len(data) and data[pos] == 255:
            pos += 1
        if pos >= len(data):
            return None
        marker = data[pos]
        pos += 1
        if marker in (0xD9, 0xDA):
            return None
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        if pos + 2 > len(data):
            return None
        size = int.from_bytes(data[pos : pos + 2], "big")
        if size < 2 or pos + size > len(data):
            return None
        if (
            marker
            in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            )
            and size >= 7
        ):
            height, width = struct.unpack(">HH", data[pos + 3 : pos + 7])
            return width, height
        pos += size
    return None


def text_of(node) -> str:
    if node is None:
        return ""
    return "".join(node.itertext())


def compact(value: str) -> str:
    return " ".join(value.split())


class Audit:
    def __init__(self, files: dict[str, bytes], infos=None):
        self.files = files
        self.infos = infos
        self.findings: list[dict] = []
        self.documents: dict[str, nav.Document] = {}
        self.ids: dict[str, dict] = {}
        self.edges: dict[tuple[str, str], list[tuple[str, str]]] = {}
        self.referenced: set[str] = set()
        self.skipped: list[dict] = []
        self.spine: list[str] = []
        self.package = ""
        self.parsed: set[str] = set()

    def add(self, level: str, code: str, file: str, message: str, **extra):
        self.findings.append(
            dict(level=level, code=code, file=file, message=message, **extra)
        )

    def error(self, code, file, message, **extra):
        self.add("error", code, file, message, **extra)

    def warn(self, code, file, message, **extra):
        self.add("warning", code, file, message, **extra)

    def link(self, source: str, value: str, *, resource=False):
        try:
            target, fragment = uri_target(source, value)
        except (ValueError, UnicodeError) as exc:
            self.error("URI", source, str(exc))
            return None
        if target is None:
            if resource:
                self.warn(
                    "REMOTE_RESOURCE", source, f"Recurso externo/no local: {value}"
                )
            return None
        if target not in self.files:
            self.error("MISSING_TARGET", source, f"No existe destino: {value}")
        else:
            self.referenced.add(target)
            if fragment:
                if target not in self.documents:
                    self.warn(
                        "UNCHECKED_FRAGMENT",
                        source,
                        f"Fragmento no comprobable: {value}",
                    )
                elif fragment not in self.ids.get(target, {}):
                    self.error(
                        "MISSING_FRAGMENT", source, f"No existe fragmento: {value}"
                    )
        return target, fragment

    def parse(self, required=None):
        for name, data in self.files.items():
            if name in self.parsed:
                continue
            if required is not None and name not in required:
                continue
            if required is None and Path(name).suffix.lower() not in (
                ".xml",
                ".opf",
                ".ncx",
                ".xhtml",
                ".html",
                ".svg",
            ):
                continue
            self.parsed.add(name)
            try:
                doc = nav.parse_xml(Path(name), data)
            except (nav.NavigationError, ValueError) as exc:
                self.error("XML", name, str(exc))
                continue
            self.documents[name] = doc
            ids = {}
            for element in doc.tree.iter():
                if not isinstance(element.tag, str):
                    continue
                if element.get(f"{{{XML}}}base") is not None:
                    self.error(
                        "XML_BASE", name, "xml:base no soportado por este perfil"
                    )
                values = {element.get("id"), element.get(f"{{{XML}}}id")} - {None}
                for value in values:
                    if value in ids:
                        self.error("DUPLICATE_ID", name, f"ID duplicado: {value}")
                    if not value or re.search(r"\s", value):
                        self.error(
                            "INVALID_ID", name, f"ID vacío/con espacios: {value!r}"
                        )
                    ids[value] = element
            self.ids[name] = ids

    def container(self):
        if self.files.get("mimetype") != MIMETYPE:
            self.error(
                "MIMETYPE",
                "mimetype",
                "Contenido exacto requerido: application/epub+zip",
            )
        if self.infos is not None:
            if not self.infos or self.infos[0].filename != "mimetype":
                self.error(
                    "MIMETYPE_FIRST", "mimetype", "Debe ser la primera entrada ZIP"
                )
            info = next((i for i in self.infos if i.filename == "mimetype"), None)
            if info and (
                info.compress_type != zipfile.ZIP_STORED
                or info.extra
                or info.header_offset != 0
            ):
                self.error(
                    "MIMETYPE_ZIP",
                    "mimetype",
                    "Sin compresión, datos extra ni prefijo ZIP",
                )
        doc = self.documents.get("META-INF/container.xml")
        if doc is None:
            self.error(
                "CONTAINER", "META-INF/container.xml", "Contenedor ausente o ilegible"
            )
            return None
        if doc.tree.tag != f"{{{nav.CONTAINER}}}container":
            self.error(
                "CONTAINER_NAMESPACE",
                "META-INF/container.xml",
                "Namespace/raíz inválidos",
            )
            return None
        roots = doc.tree.findall(f".//{{{nav.CONTAINER}}}rootfile")
        if len(roots) != 1:
            self.error(
                "ROOTFILE",
                "META-INF/container.xml",
                "Perfil soportado: un único rootfile",
            )
            return None
        self.package = roots[0].get("full-path", "")
        try:
            self.package = member_name(self.package)
        except ValueError as exc:
            self.error("ROOTFILE", "META-INF/container.xml", str(exc))
            return None
        if roots[0].get("media-type") != "application/oebps-package+xml":
            self.error(
                "ROOTFILE_MEDIA", "META-INF/container.xml", "media-type OPF incorrecto"
            )
        self.parse([self.package])
        package = self.documents.get(self.package)
        if package is None:
            self.error("OPF", self.package, "Paquete ausente o ilegible")
            return None
        if (
            package.tree.tag != f"{{{OPF}}}package"
            or package.tree.get("version") != "2.0"
        ):
            self.error(
                "PROFILE",
                self.package,
                "Esta skill comprueba EPUB2 ePL, no convierte EPUB3",
            )
            return None
        return package.tree

    def manifest(self, package):
        entries = {}
        targets = set()
        for item in package.findall(f"{{{OPF}}}manifest/{{{OPF}}}item"):
            ident = item.get("id", "")
            if not ident or ident in entries:
                self.error(
                    "MANIFEST_ID",
                    self.package,
                    f"ID de manifiesto vacío/duplicado: {ident}",
                )
            result = self.link(self.package, item.get("href", ""), resource=True)
            if result is None:
                self.error(
                    "MANIFEST_URI", self.package, "Recurso de manifiesto no local"
                )
                continue
            target, fragment = result
            if fragment or target == self.package:
                self.error(
                    "MANIFEST_URI",
                    self.package,
                    f"URI de manifiesto inválida: {target}#{fragment}",
                )
            if target in targets:
                self.error(
                    "MANIFEST_DUPLICATE",
                    self.package,
                    f"Recurso declarado más de una vez: {target}",
                )
            targets.add(target)
            media_type = item.get("media-type", "")
            entries[ident] = (target, media_type)
            if media_type.endswith("+xml") or media_type in (
                "application/xml",
                "text/xml",
            ):
                self.parse([target])
            expected = MEDIA.get(Path(target).suffix.lower())
            if expected and item.get("media-type") != expected:
                self.error("MEDIA_TYPE", target, f"media-type esperado: {expected}")
            if not item.get("media-type"):
                self.error("MEDIA_TYPE", target, "Falta media-type")
        for name in self.files:
            if (
                name not in targets
                and name not in ("mimetype", self.package)
                and not name.startswith("META-INF/")
            ):
                self.error("UNMANIFESTED", name, "Archivo no declarado en manifest")
        spine = package.find(f"{{{OPF}}}spine")
        if spine is None:
            self.error("SPINE", self.package, "Falta spine")
            return entries, None
        for item in spine.findall(f"{{{OPF}}}itemref"):
            target = entries.get(item.get("idref"))
            if target is None or target[1] != "application/xhtml+xml":
                self.error(
                    "SPINE_REF",
                    self.package,
                    f"idref ausente/no XHTML: {item.get('idref')}",
                )
            else:
                self.spine.append(target[0])
        if not self.spine or len(set(self.spine)) != len(self.spine):
            self.error("SPINE", self.package, "Spine vacío o con entradas repetidas")
        expected = ["cubierta.xhtml", "sinopsis.xhtml", "titulo.xhtml", "info.xhtml"]
        if [Path(n).name for n in self.spine[:4]] != expected:
            self.error(
                "EPL_ORDER",
                self.package,
                "Primeras cuatro secciones: " + ", ".join(expected),
            )
        for ref in package.findall(f"{{{OPF}}}guide/{{{OPF}}}reference"):
            self.link(self.package, ref.get("href", ""))
        toc = entries.get(spine.get("toc"))
        if toc is None or toc[1] != "application/x-dtbncx+xml":
            self.error("NCX", self.package, "spine@toc debe apuntar al NCX declarado")
            return entries, None
        return entries, toc[0]

    def metadata(self, package, entries, ncx_name):
        metadata = package.find(f"{{{OPF}}}metadata")
        if metadata is None:
            self.error("METADATA", self.package, "Faltan metadatos")
            return
        fields = {}
        for key in (
            "title",
            "creator",
            "language",
            "description",
            "subject",
            "publisher",
        ):
            values = metadata.findall(f"{{{DC}}}{key}")
            fields[key] = compact(" ".join(text_of(v) for v in values))
            if not fields[key]:
                self.error("METADATA_REQUIRED", self.package, f"Falta dc:{key}")
        if fields["publisher"] != "ePubLibre":
            self.error("EPL_PUBLISHER", self.package, "Editorial del perfil: ePubLibre")
        for person in metadata.findall(f"{{{DC}}}creator") + metadata.findall(
            f"{{{DC}}}contributor"
        ):
            if not compact(person.get(f"{{{OPF}}}file-as", "")):
                self.error(
                    "FILE_AS", self.package, f"Falta ordenar-como: {text_of(person)}"
                )
        dates = metadata.findall(f"{{{DC}}}date")
        if not any(
            d.get(f"{{{OPF}}}event") == "publication" and compact(text_of(d))
            for d in dates
        ):
            self.error(
                "PUBLICATION_DATE", self.package, "Falta fecha de publicación original"
            )
        for date in dates:
            if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", text_of(date).strip()):
                self.warn(
                    "DATE_REVIEW", self.package, f"Revisar fecha/era: {text_of(date)}"
                )
        identifiers = metadata.findall(f"{{{DC}}}identifier")
        uid_node = next(
            (n for n in identifiers if n.get("id") == package.get("unique-identifier")),
            None,
        )
        uid = text_of(uid_node).strip()
        try:
            book_uuid = uuid.UUID(uid.removeprefix("urn:uuid:"))
            if not book_uuid.int:
                raise ValueError("UUID de ceros")
        except ValueError:
            self.error(
                "BOOK_UUID",
                self.package,
                "BookId debe ser UUID propio distinto del de ceros",
            )
        epl_id = next(
            (
                text_of(n).strip()
                for n in identifiers
                if n.get(f"{{{OPF}}}scheme") == "EPL"
            ),
            "",
        )
        if not epl_id.isascii() or not epl_id.isdigit() or int(epl_id) == 0:
            self.warn(
                "EPL_ID_PENDING",
                self.package,
                "Falta EPL-ID real: no inventar uno; pendiente de ficha",
            )
        revision = next(
            (
                text_of(n).strip()
                for n in identifiers
                if n.get(f"{{{OPF}}}scheme") == "revision"
            ),
            "",
        )
        if not re.fullmatch(r"(?:[1-9]\d*\.\d|0\.\d+)(?:a)?", revision):
            self.error(
                "REVISION", self.package, f"Revisión no reconocida: {revision!r}"
            )
        ncx = self.documents.get(ncx_name)
        if ncx is not None:
            root = ncx.tree
            if root.tag != f"{{{NCX}}}ncx":
                self.error("NCX_NAMESPACE", ncx_name, "Raíz/namespace NCX incorrecto")
            metas = root.findall(f"{{{NCX}}}head/{{{NCX}}}meta")
            if not any(
                n.get("name") == "dtb:uid" and n.get("content") == uid for n in metas
            ):
                self.error("NCX_UID", ncx_name, "dtb:uid distinto de BookId")
            if compact(text_of(root.find(f"{{{NCX}}}docTitle"))) != fields["title"]:
                self.error("NCX_TITLE", ncx_name, "docTitle distinto del título OPF")
            if not root.findall(f".//{{{NCX}}}navPoint"):
                self.error("NCX_EMPTY", ncx_name, "NCX sin navPoint")
        elif ncx_name:
            self.error("NCX", ncx_name, "NCX ilegible")
        self.taxonomy(fields["subject"])
        self.fixed_pages(fields, revision)
        covers = [
            n.get("content")
            for n in metadata.findall(f"{{{OPF}}}meta")
            if n.get("name") == "cover"
        ]
        cover = entries.get(covers[0]) if len(covers) == 1 else None
        if (
            cover is None
            or cover[1] != "image/jpeg"
            or Path(cover[0]).name != "cover.jpg"
        ):
            self.error(
                "COVER_META",
                self.package,
                "meta cover debe identificar cover.jpg JPEG en manifest",
            )
        else:
            data = self.files.get(cover[0], b"")
            size = image_size(data)
            if not data.startswith(b"\xff\xd8") or not size:
                self.error("COVER_JPEG", cover[0], "Cubierta JPEG no reconocida")
            elif not (
                600 <= size[0] <= 1200
                and 900 <= size[1] <= 1800
                and size[0] * 3 == size[1] * 2
            ):
                self.error(
                    "COVER_SIZE",
                    cover[0],
                    f"Dimensiones {size}; perfil 2:3, 600×900 a 1200×1800",
                )
            else:
                self.cover_svg(size)

    def taxonomy(self, subject):
        catalog = json.loads(
            (SKILL / "resources" / "genres.json").read_text(encoding="utf-8")
        )
        terms = [t.strip() for t in subject.split(",") if t.strip()]
        valid = False
        for kind in catalog["tipos"]:
            genres = {g["nombre"] for g in kind["generos"]}
            subs = {g["nombre"] for g in kind["subgeneros"]}
            valid |= (
                len(terms) == len(set(terms))
                and len(set(terms) & genres) == 1
                and 1 <= len(set(terms) & subs) <= 5
                and set(terms) <= genres | subs
            )
        if not valid:
            self.error(
                "GENRES",
                self.package,
                "Usar un género y 1–5 subgéneros del mismo tipo en resources/genres.json, sin incluir el tipo",
            )

    def fixed_pages(self, fields, revision):
        for name in self.spine:
            doc = self.documents.get(name)
            if doc is None:
                continue
            base = Path(name).name
            if base == "sinopsis.xhtml":
                container = next(
                    (
                        e
                        for e in doc.tree.iter()
                        if "sinopsis" in e.get("class", "").split()
                    ),
                    None,
                )
                # Las fronteras entre párrafos son espacios; los inline no separan palabras.
                synopsis = (
                    compact(
                        " ".join(text_of(p) for p in container.findall(f"{{{XHTML}}}p"))
                    )
                    if container is not None
                    else ""
                )
                # OPF no admite cursiva: la convención ePL la convierte en comillas.
                if synopsis != fields["description"]:
                    self.warn(
                        "SYNOPSIS",
                        name,
                        "Sinopsis y dc:description difieren; revisar también títulos en cursiva→comillas",
                    )
            if base == "titulo.xhtml":
                for cls, expected in (
                    ("ttitulo", fields["title"]),
                    ("tautor", fields["creator"]),
                    ("trevision", f"ePub r{revision}"),
                ):
                    node = next(
                        (
                            e
                            for e in doc.tree.iter()
                            if cls in e.get("class", "").split()
                        ),
                        None,
                    )
                    if compact(text_of(node)) != expected:
                        self.error(
                            "TITLE_PAGE",
                            name,
                            f"{cls} no concuerda con OPF: {expected!r}",
                        )

    def cover_svg(self, size):
        for name in self.spine:
            if Path(name).name != "cubierta.xhtml" or name not in self.documents:
                continue
            root = self.documents[name].tree
            svg = root.find(f".//{{{SVG}}}svg")
            image = root.find(f".//{{{SVG}}}image")
            try:
                box = (
                    [float(x) for x in svg.get("viewBox", "").replace(",", " ").split()]
                    if svg is not None
                    else []
                )
                dims = (
                    (float(image.get("width", "")), float(image.get("height", "")))
                    if image is not None
                    else ()
                )
            except ValueError:
                box, dims = [], ()
            if box != [0, 0, *size] or dims != size:
                self.error(
                    "COVER_SVG",
                    name,
                    f"viewBox y SVG image width/height deben concordar con {size}",
                )

    def content(self):
        previous_heading = 0
        for name in self.spine:
            doc = self.documents.get(name)
            if doc is None:
                self.error(
                    "SPINE_XML", name, "Documento del spine ausente o XML no analizable"
                )
                continue
            root = doc.tree
            if root.tag != f"{{{XHTML}}}html":
                self.error("XHTML_NAMESPACE", name, "Raíz XHTML incorrecta")
                continue
            if not root.get(f"{{{XML}}}lang"):
                self.error("LANG", name, "Falta xml:lang en html")
            if not compact(text_of(root.find(f"{{{XHTML}}}head/{{{XHTML}}}title"))):
                self.error("HTML_TITLE", name, "Falta título descriptivo en head")
            body = root.find(f"{{{XHTML}}}body")
            if body is None:
                self.error("BODY", name, "Falta body XHTML")
                continue

            def visible(node):
                if "oculto" in node.get("class", "").split():
                    return False
                return (
                    bool(compact(node.text or ""))
                    or node.tag in (f"{{{XHTML}}}img", f"{{{SVG}}}svg")
                    or any(
                        visible(c) or bool(compact(c.tail or ""))
                        for c in node
                        if isinstance(c.tag, str)
                    )
                )

            if not visible(body):
                self.error(
                    "EMPTY_BODY",
                    name,
                    "Body vacío o solo oculto (detección básica, no evalúa CSS)",
                )
            links = root.findall(f"{{{XHTML}}}head/{{{XHTML}}}link")
            sheets = [e.get("href", "") for e in links if e.get("rel") == "stylesheet"]
            if Path(name).name != "TOC.xhtml" and (
                not sheets or Path(sheets[0]).name != "epl.css"
            ):
                self.error(
                    "EPL_CSS_FIRST", name, "epl.css debe ser la primera hoja de estilos"
                )
            if Path(name).name == "TOC.xhtml":
                continue
            for element in root.iter():
                if element.tag in nav.HEADINGS:
                    rank = nav.HEADINGS[element.tag]
                    if rank > previous_heading + 1:
                        self.error(
                            "HEADING_JUMP",
                            name,
                            f"Salto de h{previous_heading} a h{rank}",
                        )
                    previous_heading = rank

    def resources(self):
        for name, doc in self.documents.items():
            for element in doc.tree.iter():
                if not isinstance(element.tag, str):
                    continue
                for key in ("href", "src", "{http://www.w3.org/1999/xlink}href"):
                    if key not in element.attrib:
                        continue
                    value = element.get(key)
                    # Manifiesto/guide ya se comprueban con contexto propio.
                    if name == self.package:
                        continue
                    resource = element.tag not in (f"{{{XHTML}}}a",)
                    result = self.link(name, value, resource=resource)
                    if element.tag == f"{{{XHTML}}}a" and result:
                        ident = element.get("id", "")
                        self.edges.setdefault((name, ident), []).append(result)

                if element.tag == f"{{{XHTML}}}img" and "alt" not in element.attrib:
                    self.warn("IMAGE_ALT", name, "Imagen sin atributo alt")
                if element.tag.startswith(f"{{{XHTML}}}") and (
                    "style" in element.attrib or element.tag == f"{{{XHTML}}}style"
                ):
                    self.error(
                        "INLINE_STYLE",
                        name,
                        "Estilo XHTML inline/interno: trasladar a hoja externa",
                    )
                if element.tag == f"{{{XHTML}}}script":
                    self.error("SCRIPT", name, "JavaScript fuera del perfil EPUB2 ePL")
                # @font-face en SVG puede contener URL de fuente externa al gráfico.
                if element.tag == f"{{{SVG}}}style":
                    self.css_links(name, text_of(element))
        for name, data in self.files.items():
            if Path(name).suffix.lower() == ".css":
                try:
                    css = data.decode("utf-8-sig")
                except UnicodeError as exc:
                    self.error("CSS_ENCODING", name, str(exc))
                    continue
                self.css_links(name, css)
                if Path(name).name == "style.css":
                    clean = re.sub(r"/\*[\s\S]*?\*/", "", css)
                    if re.search(
                        r"(?:font-variant\s*:\s*small-caps|!important|:(?:first-letter|first-line|before|after|nth-child)\b)",
                        clean,
                    ):
                        self.warn(
                            "CSS_LEGACY",
                            name,
                            "CSS de compatibilidad heredada: revisar references/advanced.md",
                        )
                    if re.search(
                        r"(?:^|})\s*(?:body|p)\s*\{[^}]*font-(?:size|family)\s*:", clean
                    ):
                        self.warn(
                            "BODY_FONT",
                            name,
                            "Revisar fuente/tamaño impuestos al cuerpo: preservar controles del lector",
                        )
        for name, data in self.files.items():
            if len(data) > 300000:
                self.warn(
                    "RESOURCE_SIZE",
                    name,
                    f"{len(data)} bytes; manuales citan 300 kB sin base inequívoca: alerta conservadora, no límite EPUB",
                )

    def css_links(self, name, css):
        css = re.sub(r"/\*[\s\S]*?\*/", "", css)
        # Escapes CSS complejos y cadenas con ')' requieren EPUBCheck/revisión.
        for match in re.finditer(
            r"url\(\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s)]+))\s*\)|@import\s+[\"']([^\"']+)[\"']",
            css,
        ):
            value = next(v for v in match.groups() if v is not None)
            self.link(name, value, resource=True)
        if "\\" in css:
            self.skipped.append(
                {
                    "code": "CSS_ESCAPES",
                    "file": name,
                    "reason": "URLs/selectores con escapes CSS no analizados completamente",
                }
            )

    def notes(self):
        consumed = set()
        for name, ids in self.ids.items():
            for ident, anchor in ids.items():
                match = re.fullmatch(r"rf(\d+)", ident)
                if not match:
                    continue
                number = match[1]
                targets = self.edges.get((name, ident), [])
                if len(targets) != 1 or targets[0][1] != f"nt{number}":
                    self.error(
                        "NOTE_FORWARD",
                        name,
                        f"{ident}: llamada debe enlazar a nt{number}",
                    )
                    continue
                target_name, target_id = targets[0]
                target = self.ids.get(target_name, {}).get(target_id)
                if target is None:
                    continue
                consumed.add((target_name, target_id))
                if (
                    compact(text_of(anchor)) != f"[{number}]"
                    or anchor.find(f"{{{XHTML}}}sup") is None
                ):
                    self.error(
                        "NOTE_LABEL", name, f"{ident}: usar <sup>[{number}]</sup>"
                    )
                # La plantilla coloca ntN en p; aceptar contenedor de varios párrafos.
                returns = []
                for link in target.iter(f"{{{XHTML}}}a"):
                    try:
                        returns.append(uri_target(target_name, link.get("href", "")))
                    except (ValueError, UnicodeError):
                        continue
                if (name, ident) not in returns:
                    self.error(
                        "NOTE_BACK",
                        target_name,
                        f"{target_id}: falta retorno a {name}#{ident}",
                    )
                if not compact(text_of(target)).startswith(f"[{number}]"):
                    self.error(
                        "NOTE_LABEL",
                        target_name,
                        f"{target_id}: número visible no coincide",
                    )
        for name, ids in self.ids.items():
            for ident in ids:
                if re.fullmatch(r"nt\d+", ident) and (name, ident) not in consumed:
                    self.warn(
                        "ORPHAN_NOTE", name, f"Nota sin llamada ePL reconocida: {ident}"
                    )

    def template_checks(self):
        template, _ = read_zip(TEMPLATE)
        for name, data in self.files.items():
            if (
                Path(name).name == "epl.css"
                and data != template["OEBPS/Styles/epl.css"]
            ):
                self.error(
                    "EPL_CSS_CHANGED",
                    name,
                    "epl.css difiere de la base r2.1 distribuida",
                )
            if Path(name).name in ("cover.jpg", "autor.jpg") and data == template.get(
                "OEBPS/Images/" + Path(name).name
            ):
                self.warn(
                    "SAMPLE_IMAGE",
                    name,
                    "Imagen idéntica al ejemplo del ePub Base: sustituir o retirar si es opcional",
                )
            if Path(name).suffix.lower() in (".xhtml", ".html", ".opf"):
                text = data.decode("utf-8", errors="replace")
                if re.search(
                    r"Lorem ipsum|Nombres Apellidos|NOMBRE DEL AUTOR|Saga: Serie Volumen|>Subtitulo<|>Título<",
                    text,
                    re.IGNORECASE,
                ):
                    self.warn(
                        "PLACEHOLDER", name, "Posible contenido residual de plantilla"
                    )
        # El manifiesto declara, pero no demuestra uso; analizar referencias reales.
        for name in self.files:
            if name not in self.actual_references and Path(name).suffix.lower() in (
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".svg",
                ".ttf",
                ".otf",
                ".css",
            ):
                self.warn(
                    "UNUSED_RESOURCE",
                    name,
                    "Sin referencia XHTML/CSS/SVG reconocida; revisar antes de retirar, no autocorregir",
                )

    def patterns(self):
        rules = json.loads(
            (SKILL / "resources" / "manual-regex.json").read_text(encoding="utf-8")
        )
        for rule in rules:
            if not rule.get("stdlib_re_compatible", True):
                self.skipped.append(
                    {"code": rule["id"], "reason": rule["stdlib_re_skip_reason"]}
                )
                continue
            pattern = (
                re.escape(rule["pattern"])
                if rule["kind"] == "literal"
                else rule["pattern"]
            )
            try:
                compiled = re.compile(pattern)
            except re.error as exc:
                self.skipped.append({"code": rule["id"], "reason": str(exc)})
                continue
            for name, doc in self.documents.items():
                if doc.tree.tag != f"{{{XHTML}}}html":
                    continue
                if rule["scope"] == "text":
                    body = doc.tree.find(f"{{{XHTML}}}body")
                    if body is None:
                        continue

                    # Sin saltos artificiales entre spans, pero sí entre bloques.
                    def render(node):
                        if not isinstance(node.tag, str) or node.tag in (
                            f"{{{XHTML}}}script",
                            f"{{{XHTML}}}style",
                        ):
                            return ""
                        out = (node.text or "") + "".join(
                            render(c) + (c.tail or "") for c in node
                        )
                        block = node.tag.rsplit("}", 1)[-1] in {
                            "p",
                            "div",
                            "li",
                            "h1",
                            "h2",
                            "h3",
                            "h4",
                            "h5",
                            "h6",
                            "td",
                            "tr",
                            "blockquote",
                            "br",
                        }
                        return out + ("\n" if block else "")

                    text = render(body)
                    location = "body-text-offset"
                else:
                    text = doc.data.decode("utf-8-sig")
                    location = "source-offset"
                count = 0
                samples = []
                for match in compiled.finditer(text):
                    count += 1
                    if len(samples) < 5:
                        sample = {
                            "offset": match.start(),
                            "context": text[
                                max(0, match.start() - 45) : match.end() + 45
                            ],
                            "location": location,
                        }
                        if location == "source-offset":
                            sample["line"] = text.count("\n", 0, match.start()) + 1
                        samples.append(sample)
                if count:
                    self.warn(
                        rule["id"],
                        name,
                        rule["description"],
                        count=count,
                        samples=samples,
                        caveat=rule["caveat"],
                    )
        heuristics = [
            (
                "DOUBLE_SPACE",
                r"[^\S\n]{2,}",
                "Espacios repetidos en texto: revisar intención",
            ),
            (
                "PUNCTUATION_SPACE",
                r"\s+[,.!?;:]",
                "Espacio antes de puntuación: revisar",
            ),
            ("OCR_HYPHEN", r"\w-\n\w", "Posible corte OCR: cotejar antes de unir"),
        ]
        for name, doc in self.documents.items():
            if doc.tree.tag != f"{{{XHTML}}}html":
                continue
            for paragraph in doc.tree.iter(f"{{{XHTML}}}p"):
                text = text_of(paragraph)
                for code, pattern, message in heuristics:
                    match = re.search(pattern, text)
                    if match:
                        self.warn(
                            code,
                            name,
                            message + " (heurística local, no regex oficial)",
                            context=text[max(0, match.start() - 30) : match.end() + 30],
                        )
            if re.search(
                r"<br\s*/?>\s*<br\s*/?>", doc.data.decode("utf-8"), re.IGNORECASE
            ):
                self.warn(
                    "BR_SPACING",
                    name,
                    "BR consecutivos: usar CSS para espaciado (III 2.02)",
                )

    def run(self):
        self.parse()
        package = self.container()
        if package is not None:
            entries, ncx_name = self.manifest(package)
            self.metadata(package, entries, ncx_name)
            self.content()
        # Separar referencias de uso de las meras declaraciones del manifiesto.
        self.referenced.clear()
        self.resources()
        self.actual_references = set(self.referenced)
        self.notes()
        self.template_checks()
        self.patterns()
        self.skipped.extend(
            [
                {
                    "code": "EPUB_SCHEMA",
                    "reason": "Sin validación de esquema completa; ejecutar EPUBCheck",
                },
                {
                    "code": "NAVIGATION_SEMANTICS",
                    "reason": "UID, título y destinos NCX comprobados; etiquetas, orden y cobertura frente a encabezados/TOC HTML requieren regenerar con navigation.py y revisar",
                },
                {
                    "code": "EDITORIAL_VISUAL",
                    "reason": "Pendiente cotejo de integridad, ortografía, derechos, fuentes/glifos y pruebas visuales en lectores",
                },
                {
                    "code": "OFFICIAL_INI",
                    "reason": "Los manuales no incluyen el .ini oficial de búsquedas ni el programa ePLValidator",
                },
            ]
        )
        return self.report()

    def report(self):
        counts = Counter(f["level"] for f in self.findings)
        return {
            "profile": "Scriptorium EPUB2 / ePub Base r2.1 (manuales locales)",
            "counts": {"error": counts["error"], "warning": counts["warning"]},
            "findings": self.findings,
            "skipped": self.skipped,
            "compliance_certified": False,
        }


def initialize(output: Path):
    files, _ = read_zip(TEMPLATE)
    nav.check_symlinks(output)
    if output.exists():
        raise ValueError(f"El destino ya existe: {output}")
    identifier = str(uuid.uuid4()).encode("ascii")
    for name in ("OEBPS/content.opf", "OEBPS/toc.ncx"):
        files[name] = files[name].replace(
            b"00000000-0000-0000-0000-000000000000", identifier
        )
    output.mkdir(parents=True)
    for name, data in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    print(
        f"Plantilla preparada en {output}; UUID nuevo sincronizado. Completar contenido/metadatos/índices."
    )


def pack(root: Path, output: Path):
    nav.check_symlinks(output)
    nav.check_symlinks(root)
    root = root.resolve(strict=True)
    if output.resolve().is_relative_to(root):
        raise ValueError(
            "El EPUB de salida debe quedar fuera del directorio empaquetado"
        )
    files = read_directory(root)
    if files.get("mimetype") != MIMETYPE or "META-INF/container.xml" not in files:
        raise ValueError("Falta mimetype exacto o META-INF/container.xml")
    # xb protege archivos existentes; la fecha fija hace reproducible el ZIP.
    with output.open("xb") as stream:
        try:
            with zipfile.ZipFile(stream, "w") as archive:
                for name in ["mimetype", *sorted(n for n in files if n != "mimetype")]:
                    info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
                    info.compress_type = (
                        zipfile.ZIP_STORED
                        if name == "mimetype"
                        else zipfile.ZIP_DEFLATED
                    )
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(info, files[name])
        except BaseException:
            # El archivo fue creado por esta ejecución, nunca un destino previo.
            stream.close()
            output.unlink(missing_ok=True)
            raise
    print(f"EPUB empaquetado: {output} (sin certificación; ejecutar check y EPUBCheck)")


def _run_epubcheck_command(command: list[str], timeout: int) -> dict:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        # TimeoutExpired puede conservar bytes incluso con text=True.
        def output(value):
            return (
                value.decode("utf-8", errors="replace")
                if isinstance(value, bytes)
                else value or ""
            )

        return {
            "command": command,
            "returncode": None,
            "stdout": output(getattr(exc, "stdout", None)),
            "stderr": output(getattr(exc, "stderr", None)),
            "completed": False,
            "error": str(exc),
        }
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "completed": True,
    }


def run_epubcheck(book: Path, jar: Path) -> dict:
    if not jar.is_file():
        raise ValueError(f"No existe JAR de EPUBCheck: {jar}")
    return _run_epubcheck_command(
        ["java", "-jar", str(jar.resolve()), str(book.resolve())], timeout=120
    )


def run_epubcheck_docker(book: Path, image: str = DEFAULT_EPUBCHECK_IMAGE) -> dict:
    if not image or image.startswith("-"):
        raise ValueError(
            "La imagen Docker debe ser una referencia no vacía, no una opción"
        )
    book = book.resolve(strict=True)
    if not book.is_file():
        raise ValueError(f"No es un archivo EPUB: {book}")
    # --mount usa CSV: citar campos completos preserva comas y comillas del path.
    mount = io.StringIO(newline="")
    csv.writer(mount).writerow(
        ["type=bind", f"source={book}", "target=/data/book.epub", "readonly"]
    )
    command = [
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
        mount.getvalue()[:-2],
        "--",
        image,
        "/data/book.epub",
    ]
    return _run_epubcheck_command(command, timeout=300)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser(
        "init", help="Extraer plantilla en directorio NUEVO y asignar UUID"
    )
    init.add_argument("directory", type=Path)
    archive = sub.add_parser(
        "pack", help="Empaquetar directorio a EPUB NUEVO (no valida contenido)"
    )
    archive.add_argument("directory", type=Path)
    archive.add_argument("output", type=Path)
    check = sub.add_parser(
        "check", help="Auditoría de solo lectura; no sustituye EPUBCheck"
    )
    check.add_argument("book", type=Path)
    check.add_argument("--json", action="store_true", help="Informe JSON por stdout")
    check.add_argument(
        "--strict", action="store_true", help="Salir con 1 también si hay alertas"
    )
    validator = check.add_mutually_exclusive_group()
    validator.add_argument(
        "--epubcheck",
        type=Path,
        metavar="JAR",
        help="Ejecutar JAR local, sin descargarlo (requiere Java)",
    )
    validator.add_argument(
        "--epubcheck-docker",
        nargs="?",
        const=DEFAULT_EPUBCHECK_IMAGE,
        metavar="IMAGE",
        help="Ejecutar EPUBCheck con Docker; imagen de terceros fijada por digest por defecto (puede descargarla)",
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.directory)
        elif args.command == "pack":
            pack(args.directory, args.output)
        else:
            try:
                files, infos = read_zip(args.book)
                audit = Audit(files, infos)
                report: dict = audit.run()
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                report = {
                    "counts": {"error": 1, "warning": 0},
                    "findings": [
                        {
                            "level": "error",
                            "code": "INPUT",
                            "file": str(args.book),
                            "message": str(exc),
                        }
                    ],
                    "skipped": [
                        {
                            "code": "ALL_CHECKS",
                            "reason": "Entrada ilegible/insegura: comprobaciones pendientes",
                        }
                    ],
                    "compliance_certified": False,
                }
            if args.epubcheck is not None or args.epubcheck_docker is not None:
                if any(s["code"] == "ALL_CHECKS" for s in report["skipped"]):
                    report["epubcheck"] = {
                        "completed": False,
                        "error": "EPUBCheck no ejecutado: entrada ilegible/insegura (ALL_CHECKS)",
                    }
                else:
                    try:
                        report["epubcheck"] = (
                            run_epubcheck(args.book, args.epubcheck)
                            if args.epubcheck is not None
                            else run_epubcheck_docker(args.book, args.epubcheck_docker)
                        )
                    except (OSError, ValueError) as exc:
                        report["epubcheck"] = {"error": str(exc), "completed": False}
                    external: dict = report["epubcheck"]
                    if external.get("completed") and external.get("returncode") == 0:
                        report["skipped"] = [
                            s for s in report["skipped"] if s["code"] != "EPUB_SCHEMA"
                        ]
                    else:
                        report["findings"].append(
                            {
                                "level": "error",
                                "code": "EPUBCHECK",
                                "file": str(args.book),
                                "message": external.get("error")
                                or (
                                    f"EPUBCheck/ejecutor terminó con código {external.get('returncode')}; "
                                    "consultar stdout/stderr en epubcheck"
                                ),
                            }
                        )
                        report["counts"]["error"] += 1
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                for finding in report["findings"]:
                    print(
                        f"{finding['level'].upper()} {finding['code']} {finding['file']}: {finding['message']}"
                    )
                for skipped in report["skipped"]:
                    print(f"PENDIENTE {skipped['code']}: {skipped['reason']}")
                if "epubcheck" in report:
                    print(
                        "EPUBCheck:",
                        json.dumps(report["epubcheck"], ensure_ascii=False),
                    )
                print("Resumen:", report["counts"], "— no certifica conformidad ePL")
            return int(
                bool(
                    report["counts"]["error"]
                    or (args.strict and report["counts"]["warning"])
                )
            )
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
