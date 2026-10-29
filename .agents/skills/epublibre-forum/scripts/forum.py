#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["httpx>=0.28,<1", "beautifulsoup4>=4.14,<5", "python-dotenv>=1.1,<2", "markdownify>=1.2,<2"]
# ///
"""Foro ePubLibre por HTTP: Markdown, adjuntos y envíos preparados/confirmados."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import stat
import sys
import tempfile
import time
from http.cookiejar import Cookie
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from dotenv import dotenv_values
from forum_content import html_markdown, page_markdown
from forum_ops import (
    OperationError,
    download,
    download_url,
    operation_url,
    prepare,
    send,
)

ORIGIN = "https://www.epublibre.org"
LOGIN = ORIGIN + "/acceso/entrar"
INDEX = ORIGIN + "/foro/index.php"
SKILL = Path(__file__).resolve().parent.parent
STATE = Path.home() / ".local" / "state" / "epublibre-forum" / "session.json"
MAX_BODY = 4 * 1024 * 1024
MAX_ATTACHMENT = 32 * 1024 * 1024
READ_QUERIES = {
    "/foro/": {"sid"},
    "/foro/index.php": {"sid"},
    "/foro/viewforum.php": {"sid", "f", "start", "st", "sk", "sd"},
    "/foro/viewtopic.php": {
        "sid",
        "f",
        "t",
        "p",
        "start",
        "st",
        "sk",
        "sd",
        "hilit",
        "view",
    },
    "/foro/search.php": {
        "sid",
        "keywords",
        "terms",
        "author",
        "fid[]",
        "sc",
        "sf",
        "sr",
        "sk",
        "sd",
        "st",
        "ch",
        "search_id",
        "start",
        "submit",
    },
}
COOKIE_KEYS = {
    "version",
    "name",
    "value",
    "port",
    "port_specified",
    "domain",
    "domain_specified",
    "domain_initial_dot",
    "path",
    "path_specified",
    "secure",
    "expires",
    "discard",
    "comment",
    "comment_url",
    "rest",
    "rfc2109",
}


class ForumError(ValueError):
    """Fallo seguro, sin volcar credenciales, cookies, HTML ni tokens."""


def trusted_url(value: str, base: str = ORIGIN) -> str:
    try:
        url = urlsplit(urljoin(base, value))
        if (
            url.scheme != "https"
            or url.hostname != "www.epublibre.org"
            or url.port not in (None, 443)
            or url.username is not None
            or url.password is not None
            or "\\" in url.path
            or any(ord(c) < 32 for c in value)
        ):
            raise ForumError("Solo se permite HTTPS en www.epublibre.org")
        return urlunsplit(
            ("https", "www.epublibre.org", url.path or "/", url.query, "")
        )
    except ValueError:
        raise ForumError("URL no permitida; no se siguió el enlace") from None


def read_url(value: str, base: str = INDEX) -> str:
    url = trusted_url(value, base)
    parts = urlsplit(url)
    allowed = READ_QUERIES.get(parts.path)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if allowed is None or any(key not in allowed for key, _ in query):
        raise ForumError(
            "Ruta/parámetros fuera de lectura: no se permiten publicar, marcar, votar, suscribir, borrar o cerrar sesión"
        )
    if any(
        key == "view" and val not in ("unread", "print", "next", "previous")
        for key, val in query
    ):
        raise ForumError("Acción view no permitida")
    if any(
        key == "search_id"
        and val
        not in ("active_topics", "unanswered", "unreadposts", "newposts", "egosearch")
        for key, val in query
    ):
        raise ForumError("Tipo de búsqueda no permitido")
    return url


def access_url(value: str, base: str = ORIGIN) -> str:
    url = trusted_url(value, base)
    parts = urlsplit(url)
    if parts.path in READ_QUERIES:
        return read_url(url)
    if (
        parts.path
        not in {
            "/",
            "/acceso/entrar",
            "/acceso/login",
            "/catalogo/index",
            "/catalogo/novedades",
            "/inicio/index",
            "/usuario/cuenta",
        }
        or parts.query
    ):
        raise ForumError(
            "Redirección/ruta del portal no reconocida como lectura; revisar SSO antes de continuar"
        )
    return url


def public_url(value: str) -> str:
    """No incluir SID ni otros tokens en informes para el agente."""
    parts = urlsplit(value)
    keep = {
        "f",
        "t",
        "p",
        "u",
        "id",
        "i",
        "mode",
        "action",
        "start",
        "keywords",
        "search_id",
    }
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in keep]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def no_symlinks(path: Path):
    if any(p.is_symlink() for p in (path, *path.absolute().parents)):
        raise ForumError(
            "No se permiten enlaces simbólicos en rutas de secretos/estado"
        )


def credentials(
    path: Path | None = None,
    user_key: str = "EPL_USER",
    password_key: str = "EPL_PASS",
    *,
    cwd: Path | None = None,
    skill_dir: Path | None = None,
) -> tuple[str, str]:
    # Una pareja completa de entorno prevalece incluso sobre --env-file.
    # No mezclar una cuenta del entorno con una contraseña de otro archivo.
    if "EPL_USER" in os.environ or "EPL_PASS" in os.environ:
        username, password = os.environ.get("EPL_USER"), os.environ.get("EPL_PASS")
        if not username or not password:
            raise ForumError(
                "Credenciales de entorno incompletas/vacías; no se mezclarán con archivos"
            )
        return username, password
    candidates = (
        [path]
        if path is not None
        else [(cwd or Path.cwd()) / ".env", (skill_dir or SKILL) / ".env"]
    )
    for candidate in candidates:
        no_symlinks(candidate)
        if not candidate.exists():
            continue
        if not candidate.is_file() or candidate.stat().st_size > 65536:
            raise ForumError("Archivo de credenciales inválido o demasiado grande")
        # Solo este proceso recibe los valores; no exportar, registrar ni expandir.
        values = dotenv_values(candidate, interpolate=False)
        username, password = values.get(user_key), values.get(password_key)
        if not username or not password:
            raise ForumError(
                "El primer .env encontrado no contiene la pareja de claves requerida; revisar nombres sin mostrar valores"
            )
        return username, password
    raise ForumError(
        "No hay credenciales en el entorno ni .env en el directorio de trabajo o la skill"
    )


def cookie_record(cookie: Cookie) -> dict:
    return {
        name: getattr(cookie, "_rest" if name == "rest" else name)
        for name in COOKIE_KEYS
    }


def load_state(path: Path, client: httpx.Client):
    no_symlinks(path)
    if not path.exists():
        return
    if not path.is_file() or path.stat().st_size > 262144:
        raise ForumError("Estado de sesión inválido")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ForumError("El archivo de sesión debe ser privado (permisos 0600)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (
            data.get("version") != 1
            or not isinstance(data.get("cookies"), list)
            or len(data["cookies"]) > 128
        ):
            raise ValueError
        for record in data["cookies"]:
            if (
                set(record) != COOKIE_KEYS
                or record["domain"].lstrip(".")
                not in ("epublibre.org", "www.epublibre.org")
                or not isinstance(record["name"], str)
                or not isinstance(record["value"], str)
            ):
                raise ValueError
            client.cookies.jar.set_cookie(Cookie(**record))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ForumError(
            "Estado de sesión ilegible; no se ejecutó ni deserializó código"
        ) from None


def save_state(path: Path, client: httpx.Client):
    no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "version": 1,
        "cookies": [
            cookie_record(c)
            for c in client.cookies.jar
            if c.domain.lstrip(".") in ("epublibre.org", "www.epublibre.org")
        ],
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, delete=False, mode="w", encoding="utf-8"
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False)
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def controls(form) -> list[tuple[str, str]]:
    result = []
    for field in form.select("input[name],button[name],textarea[name],select[name]"):
        if field.has_attr("disabled"):
            continue
        kind = str(field.get("type", "text")).lower()
        if kind in ("file", "reset", "button") or (
            kind in ("checkbox", "radio") and not field.has_attr("checked")
        ):
            continue
        if field.name == "textarea":
            value = field.get_text()
        elif field.name == "select":
            option = field.select_one("option[selected]") or field.select_one("option")
            value = option.get("value", option.get_text()) if option else ""
        else:
            value = field.get("value", "")
        result.append((str(field["name"]), str(value)))
    return result


def html(response: httpx.Response) -> BeautifulSoup:
    soup = BeautifulSoup(response.text, "html.parser")
    if soup.select_one(
        '.g-recaptcha, .h-captcha, iframe[src*="captcha"], input[name="otp"], input[name="totp"], input[name="confirm_code"]'
    ):
        raise ForumError(
            "Se requiere CAPTCHA/2FA u otra intervención manual; detener sin eludirla"
        )
    if soup.title and soup.title.get_text(strip=True).lower() in (
        "just a moment...",
        "attention required! | cloudflare",
    ):
        raise ForumError(
            "Intervención de acceso requerida; no eludir ni reintentar automáticamente"
        )
    return soup


def authenticated(soup: BeautifulSoup) -> bool:
    control_panel = private_inbox = False
    for anchor in soup.select("a[href]"):
        # Un enlace escrito por un usuario dentro de un post no prueba sesión.
        if any(
            set(parent.get("class", [])) & {"post", "postbody", "content", "signature"}
            for parent in anchor.parents
        ):
            continue
        try:
            url = urlsplit(trusted_url(str(anchor["href"]), INDEX))
        except ForumError:
            continue
        label = anchor.get_text(" ", strip=True).casefold()
        if url.path.startswith("/acceso/") and any(
            word in label
            for word in ("cerrar sesión", "desconectar", "salir", "logout")
        ):
            return True
        if url.path == "/foro/ucp.php":
            params = dict(parse_qsl(url.query))
            if params.get("mode") == "logout":
                return True
            if not params or set(params) <= {"sid"}:
                control_panel = True
            if (
                params.get("i") in {"pm", "privmsgs"}
                and params.get("folder") == "inbox"
            ):
                private_inbox = True
    # La integración ePL oculta logout de phpBB: el menú propio muestra ambos.
    return control_panel and private_inbox


def login_data(
    soup: BeautifulSoup, url: str, username: str, password: str
) -> tuple[str, list[tuple[str, str]]]:
    forms = [f for f in soup.select("form") if f.select_one('input[type="password"]')]
    if len(forms) != 1:
        raise ForumError(
            "No se encontró un único formulario de login; revisar el protocolo"
        )
    form = forms[0]
    action = trusted_url(str(form.get("action", "")), url)
    if action != LOGIN or str(form.get("method", "get")).lower() != "post":
        raise ForumError("El formulario de login cambió de destino o método")
    pairs = controls(form)
    names = {key for key, _ in pairs}
    if not {"user", "pass", "csrf_test_name", "tkSrv"} <= names:
        raise ForumError("Cambió el formulario de acceso; no enviar credenciales")
    values = dict(pairs)
    if not values["csrf_test_name"]:
        raise ForumError("Falta el token CSRF de la sesión actual")
    if not values["tkSrv"]:
        # Traducción acotada del algoritmo público observado; no ejecutar JS remoto.
        script = "".join(s.get_text() for s in soup.select("script:not([src])"))
        compact_script = "".join(script.split())
        expected = "document.getElementById('b64_tkSrv').value=btoa(Math.floor(Math.random()*100000)+location.hostname);"
        if expected not in compact_script or not form.select_one(
            'input[name="tkSrv"][id="b64_tkSrv"]'
        ):
            raise ForumError(
                "No se reconoce la generación de tkSrv; detener sin adivinar tokens"
            )
        values["tkSrv"] = base64.b64encode(
            f"{secrets.randbelow(100000)}www.epublibre.org".encode("ascii")
        ).decode("ascii")
    values.update(user=username, **{"pass": password})
    # No activar 'recuérdame' automáticamente ni permitir varios botones de envío.
    return action, [(key, values[key]) for key, _ in pairs if key != "recuerdame"]


class Forum:
    def __init__(
        self, state: Path = STATE, *, transport=None, delay: float = 1.0, restore=True
    ):
        self.state = state
        self.delay = delay
        self.last_request = 0.0
        self.client = httpx.Client(
            timeout=30,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": "epl-skills/epublibre-forum (user-directed; no crawler)"
            },
            transport=transport,
        )
        if restore:
            try:
                load_state(state, self.client)
            except Exception:
                self.client.close()
                raise

    def close(self):
        self.client.close()

    def request(
        self,
        url: str,
        *,
        form=None,
        reading=False,
        operation=False,
        attachment=False,
        referer=None,
    ) -> httpx.Response:
        if operation and attachment:
            raise ForumError("Modos de petición incompatibles")
        url = (
            operation_url(url)
            if operation
            else download_url(url)
            if attachment
            else read_url(url)
            if reading
            else access_url(url)
        )
        method = "POST" if form is not None else "GET"
        if attachment and method != "GET":
            raise ForumError("Los adjuntos solo se descargan mediante GET")
        if method == "POST" and url != LOGIN and not operation:
            raise ForumError(
                "Solo se permite POST al formulario de login; no hay publicaciones"
            )
        for _ in range(7):
            remaining = self.delay - (time.monotonic() - self.last_request)
            if remaining > 0:
                time.sleep(remaining)
            try:
                request = self.client.build_request(
                    method,
                    url,
                    content=urlencode(form).encode("utf-8")
                    if form is not None
                    else None,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Referer": trusted_url(referer) if referer else LOGIN,
                        "Origin": ORIGIN,
                    }
                    if form is not None
                    else None,
                )
                streamed = self.client.send(request, stream=True)
                self.last_request = time.monotonic()
                try:
                    chunks, size = [], 0
                    for chunk in streamed.iter_bytes():
                        size += len(chunk)
                        if size > (MAX_ATTACHMENT if attachment else MAX_BODY):
                            raise ForumError(
                                "Respuesta demasiado grande; no se realizará rastreo/descarga masiva"
                            )
                        chunks.append(chunk)
                    # iter_bytes ya descomprimió el cuerpo: no decodificar gzip dos veces.
                    decoded_headers = [
                        (k, v)
                        for k, v in streamed.headers.multi_items()
                        if k.lower()
                        not in {
                            "content-encoding",
                            "content-length",
                            "transfer-encoding",
                        }
                    ]
                    response = httpx.Response(
                        streamed.status_code,
                        headers=decoded_headers,
                        content=b"".join(chunks),
                        request=request,
                    )
                finally:
                    streamed.close()
            except httpx.HTTPError:
                raise ForumError(
                    "Fallo de transporte HTTP/TLS; sin reintentos ni volcados de solicitudes"
                ) from None
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise ForumError("Redirección sin destino")
                if operation and method == "POST":
                    if response.status_code in (307, 308):
                        raise ForumError(
                            "Resultado de envío desconocido; no se reenviará el POST"
                        )
                    trusted_url(location, url)
                    return response
                destination = (
                    operation_url(location, url)
                    if operation
                    else download_url(location, url)
                    if attachment
                    else read_url(location, url)
                    if reading
                    else access_url(location, url)
                )
                if method == "POST":
                    if response.status_code in (307, 308):
                        raise ForumError(
                            "No se reenviarán credenciales mediante redirección POST"
                        )
                    method, form = "GET", None
                url = destination
                continue
            if response.status_code in (401, 403, 429):
                raise ForumError(
                    f"Acceso detenido (HTTP {response.status_code}); no reintentar ni eludir controles"
                )
            if response.status_code >= 400:
                raise ForumError(
                    f"Respuesta HTTP {response.status_code}; revisar el acceso sin repetir envíos"
                )
            if (
                not attachment
                and "html" not in response.headers.get("content-type", "").lower()
            ):
                raise ForumError(
                    "Se esperaba HTML; no descargar ni ejecutar contenido inesperado"
                )
            return response
        raise ForumError("Demasiadas redirecciones; revisar SSO manualmente")

    def probe(self):
        response = self.request(LOGIN)
        soup = html(response)
        forms = []
        for form in soup.select("form"):
            if form.select_one('input[type="password"]'):
                forms.append(
                    {
                        "action": public_url(
                            trusted_url(str(form.get("action", "")), str(response.url))
                        ),
                        "method": str(form.get("method", "get")).upper(),
                        "fields": [str(x["name"]) for x in form.select("[name]")],
                    }
                )
        forum = self.request(INDEX, reading=True)
        return {
            "login_forms": forms,
            "forum_title": html(forum).title.get_text(strip=True)
            if html(forum).title
            else "",
            "credentials_used": False,
        }

    def status(self):
        site_response = self.request(ORIGIN + "/usuario/cuenta")
        site = html(site_response)
        forum = html(self.request(INDEX, reading=True))
        return {
            "site_authenticated": authenticated(site),
            "forum_authenticated": authenticated(forum),
        }

    def login(
        self,
        env_file: Path | None = None,
        username_key: str = "EPL_USER",
        password_key: str = "EPL_PASS",
    ):
        username, password = credentials(env_file, username_key, password_key)
        response = self.request(LOGIN)
        soup = html(response)
        if not authenticated(soup):
            action, data = login_data(soup, str(response.url), username, password)
            html(self.request(action, form=data))
        result = self.status()
        if result["site_authenticated"] or result["forum_authenticated"]:
            save_state(self.state, self.client)
        else:
            raise ForumError(
                "Login no verificado; no se guardó la sesión ni se reintentará la contraseña"
            )
        return result

    def read(self, url: str):
        response = self.request(read_url(url), reading=True)
        soup = html(response)
        result = {
            "url": public_url(str(response.url)),
            "title": soup.title.get_text(" ", strip=True) if soup.title else "",
            "authenticated": authenticated(soup),
            "links": [],
            "posts": [],
            "actions": [],
            "attachments": [],
        }
        for anchor in soup.select("a[href]"):
            label = anchor.get_text(" ", strip=True)
            for validator, collection in (
                (operation_url, "actions"),
                (download_url, "attachments"),
            ):
                try:
                    target = validator(str(anchor["href"]), str(response.url))
                    item = {
                        "label": label[:300] or collection,
                        "url": public_url(target),
                    }
                    if item not in result[collection]:
                        result[collection].append(item)
                except OperationError:
                    pass
            try:
                target = read_url(str(anchor["href"]), str(response.url))
            except ForumError:
                continue
            label = anchor.get_text(" ", strip=True)
            item = {"label": label[:300], "url": public_url(target)}
            if label and item not in result["links"]:
                result["links"].append(item)
        for post in soup.select("div.post")[:50]:
            content = post.select_one(".postbody .content, .content")
            if content is None:
                continue
            author = post.select_one(
                ".postprofile a.username, .postprofile a.username-coloured"
            )
            if author is None:
                author = next(
                    (
                        a
                        for a in post.select(".postprofile dt a")
                        if a.get_text(strip=True)
                    ),
                    None,
                )
            if author is None:
                author = post.select_one(".author")
            profile = None
            if author is not None and author.get("href"):
                try:
                    candidate = trusted_url(str(author["href"]), str(response.url))
                    if urlsplit(candidate).path == "/foro/memberlist.php":
                        profile = public_url(candidate)
                except ForumError:
                    pass
            text = content.get_text("\n", strip=True)
            markdown = html_markdown(content, str(response.url))
            result["posts"].append(
                {
                    "id": post.get("id", ""),
                    "author": author.get_text(" ", strip=True) if author else "",
                    "author_profile": profile,
                    "text": text[:20000],
                    "markdown": markdown[:20000],
                    "truncated": len(text) > 20000 or len(markdown) > 20000,
                }
            )
        result["links"] = result["links"][:200]
        result["posts_may_be_truncated"] = len(soup.select("div.post")) > 50
        result["actions"] = result["actions"][:100]
        result["attachments"] = result["attachments"][:100]
        result["markdown"] = page_markdown(result)
        return result

    def search(self, keywords: str):
        response = self.request(INDEX, reading=True)
        soup = html(response)
        forms = [f for f in soup.select("form") if f.select_one('[name="keywords"]')]
        if not forms:
            raise ForumError(
                "No se encontró un buscador accesible; verificar login/permisos, no adivinar endpoints"
            )
        form = forms[0]
        if str(form.get("method", "get")).lower() != "get":
            raise ForumError(
                "El buscador requiere POST; este prototipo solo admite búsquedas GET observadas"
            )
        action = read_url(str(form.get("action", "")), str(response.url))
        parts = urlsplit(action)
        pairs = [(k, v) for k, v in controls(form) if k != "keywords"]
        pairs.append(("keywords", keywords))
        query = parse_qsl(parts.query, keep_blank_values=True) + pairs
        target = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), "")
        )
        return self.read(read_url(target))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=STATE,
        help="Cookies privadas fuera del repositorio (0600)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "probe", help="Inspección pública, sin credenciales ni estado persistido"
    )
    login = sub.add_parser("login", help="Un intento de acceso; no publica contenido")
    login.add_argument(
        "--env-file",
        type=Path,
        help="Fallback explícito, solo si no hay variables de entorno",
    )
    login.add_argument("--username-key", default="EPL_USER")
    login.add_argument("--password-key", default="EPL_PASS")
    sub.add_parser("status", help="Comprobar sesión web y foro sin mostrar cookies")
    read = sub.add_parser(
        "read", help="Leer una página/tema por URL, sin rastreo recursivo"
    )
    read.add_argument("url", nargs="?", default=INDEX)
    read.add_argument("--format", choices=("markdown", "json"), default="markdown")
    search = sub.add_parser(
        "search", help="Usar un formulario GET observado en el foro"
    )
    search.add_argument("keywords")
    search.add_argument("--format", choices=("markdown", "json"), default="markdown")
    attachment = sub.add_parser(
        "download", help="Descargar un adjunto observado sin ejecutarlo ni sobrescribir"
    )
    attachment.add_argument("url")
    attachment.add_argument("output", type=Path)
    draft = sub.add_parser(
        "prepare", help="Observar formulario y preparar tema/respuesta/MP, sin enviar"
    )
    draft.add_argument("url")
    draft.add_argument("--message-file", type=Path, required=True)
    draft.add_argument("--subject")
    submit = sub.add_parser(
        "send",
        help="Un solo intento de envío del plan exacto confirmado por el usuario",
    )
    submit.add_argument("plan", type=Path)
    submit.add_argument(
        "--confirm",
        required=True,
        help="Hash devuelto por prepare tras revisar texto y destinatario",
    )
    sub.add_parser("forget", help="Borrar solo la sesión local, sin logout remoto")
    args = parser.parse_args(argv)
    app = None
    try:
        if args.command == "forget":
            no_symlinks(args.state)
            args.state.unlink(missing_ok=True)
            result = {"local_session_removed": True, "remote_logout": False}
        else:
            app = Forum(args.state, restore=args.command != "probe")
            if args.command == "probe":
                result = app.probe()
            elif args.command == "login":
                result = app.login(args.env_file, args.username_key, args.password_key)
            elif args.command == "status":
                result = app.status()
            elif args.command == "read":
                result = app.read(args.url)
            elif args.command == "search":
                result = app.search(args.keywords)
            elif args.command == "download":
                result = download(app, args.url, args.output)
            elif args.command == "prepare":
                result = prepare(
                    app,
                    args.url,
                    args.message_file,
                    args.subject,
                    is_authenticated=authenticated,
                )
            else:
                result = send(
                    app, args.plan, args.confirm, is_authenticated=authenticated
                )
            if args.command in ("status", "read", "search", "prepare", "send") and (
                result.get("authenticated")
                or result.get("site_authenticated")
                or result.get("forum_authenticated")
            ):
                save_state(app.state, app.client)
        if args.command in ("read", "search") and args.format == "markdown":
            print(result["markdown"], end="")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command in ("login", "status") and not result.get(
            "forum_authenticated"
        ):
            return 1
        return 0
    except (ForumError, OperationError, OSError):
        # No volcar excepciones de librerías que puedan incluir requests o cookies.
        error = sys.exception()
        message = (
            str(error)
            if isinstance(error, (ForumError, OperationError))
            else "No se pudo acceder al archivo privado/local; revisar ruta y permisos"
        )
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if app is not None:
            app.close()


if __name__ == "__main__":
    sys.exit(main())
