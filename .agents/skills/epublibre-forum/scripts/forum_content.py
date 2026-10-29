#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["beautifulsoup4>=4.14,<5", "markdownify>=1.2,<2"]
# ///
"""Normaliza contenido phpBB como Markdown; nunca ejecuta ni descarga recursos."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from markdownify import markdownify

SENSITIVE = {
    "sid",
    "token",
    "form_token",
    "csrf_test_name",
    "password",
    "pass",
    "auth",
    "access_token",
    "api_key",
}


def safe_link(value: str, base: str) -> str | None:
    try:
        url = urlsplit(urljoin(base, value))
        if (
            url.scheme not in ("http", "https")
            or url.username
            or url.password
            or not url.hostname
        ):
            return None
        host = url.hostname.casefold()
        query = [
            (k, v)
            for k, v in parse_qsl(url.query, keep_blank_values=True)
            if k.casefold() not in SENSITIVE and not k.casefold().startswith("csrf")
        ]
        local = host in {"www.epublibre.org", "epublibre.org"}
        return urlunsplit(
            (
                "https" if local else url.scheme,
                "www.epublibre.org" if local else url.netloc,
                url.path,
                urlencode(query),
                url.fragment,
            )
        )
    except ValueError:
        return None


def html_markdown(content, base: str) -> str:
    document = BeautifulSoup(str(content), "html.parser")
    for node in document.select(
        "script,style,iframe,object,embed,form,input,button,.back2top,.signature"
    ):
        node.decompose()
    for box in document.select("dl.codebox"):
        code = box.select_one("code")
        if code is not None:
            pre = document.new_tag("pre")
            pre.append(document.new_tag("code"))
            pre.code.string = code.get_text()
            box.replace_with(pre)
    for anchor in document.select("a[href]"):
        target = safe_link(str(anchor["href"]), base)
        if target:
            anchor["href"] = target
        else:
            anchor.unwrap()
    # Un lector/renderer no debe cargar imágenes de seguimiento automáticamente.
    for image in document.select("img"):
        target = safe_link(str(image.get("src", "")), base)
        label = image.get("alt", "Imagen") or "Imagen"
        link = document.new_tag("a")
        link.string = "Imagen: " + str(label)
        if target:
            link["href"] = target
        image.replace_with(link)
    text = markdownify(
        str(document), heading_style="ATX", bullets="-", newline_style="BACKSLASH"
    )
    # No normalizar dentro de bloques de código: espacios y líneas son contenido.
    pieces = re.split(r"(```[\s\S]*?```)", text)
    for index in range(0, len(pieces), 2):
        pieces[index] = re.sub(r"\n{3,}", "\n\n", pieces[index])
    return "".join(pieces).strip()


def page_markdown(result: dict) -> str:
    lines = ["# " + result.get("title", "Foro"), "", "Fuente: " + result["url"], ""]
    if not result.get("authenticated"):
        lines += ["> Sesión no verificada; contenido público o acceso limitado.", ""]
    for post in result.get("posts", []):
        body = post.get("markdown", post.get("text", ""))
        if post.get("truncated") and len(re.findall(r"^```", body, re.MULTILINE)) % 2:
            body += "\n```"
        author = post.get("author") or "Mensaje"
        if post.get("author_profile"):
            author = f"[{author}](<{post['author_profile']}>)"
        lines += [
            "## " + author + (" · " + post["id"] if post.get("id") else ""),
            "",
            body,
            "",
        ]
        if post.get("truncated"):
            lines += ["> Contenido truncado; consultar el mensaje original.", ""]
    links = result.get("links", [])
    if links:
        lines += ["## Navegación", ""]
        for link in links:
            label = link["label"].replace("[", "\\[").replace("]", "\\]")
            lines.append(f"- [{label}](<{link['url']}>)")
        lines.append("")
    attachments = result.get("attachments", [])
    if attachments:
        lines += ["## Adjuntos (no descargados)", ""]
        for item in attachments:
            lines.append(f"- [{item['label']}](<{item['url']}>)")
        lines.append("")
    actions = result.get("actions", [])
    if actions:
        lines += ["## Acciones disponibles (no ejecutadas)", ""]
        for item in actions:
            lines.append(f"- {item['label']}: <{item['url']}>")
        lines.append("")
    if result.get("posts_may_be_truncated"):
        lines += [
            "> La página excede el límite de mensajes; este resultado no es el hilo completo.",
            "",
        ]
    return "\n".join(lines).strip() + "\n"
