#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["beautifulsoup4>=4.14,<5"]
# ///
"""Adjuntos y envíos phpBB preparados y confirmados; sin reintentos de escritura."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

ORIGIN = "https://www.epublibre.org"
INDEX = ORIGIN + "/foro/index.php"


class OperationError(ValueError):
    """Error de operación, sin volcar formularios privados ni tokens."""


def local_url(value: str, base: str = INDEX) -> str:
    try:
        u = urlsplit(urljoin(base, value))
        if (
            u.scheme != "https"
            or u.hostname != "www.epublibre.org"
            or u.port not in (None, 443)
            or u.username
            or u.password
            or "\\" in u.path
            or any(ord(c) < 32 for c in value)
        ):
            raise ValueError
        return urlunsplit(("https", "www.epublibre.org", u.path, u.query, ""))
    except ValueError:
        raise OperationError("Destino de operación no permitido") from None


def operation_url(value: str, base: str = INDEX) -> str:
    url = local_url(value, base)
    u = urlsplit(url)
    pairs = parse_qsl(u.query, keep_blank_values=True)
    params = dict(pairs)
    if len(params) != len(pairs):
        raise OperationError("Parámetros de acción duplicados")
    if u.path == "/foro/posting.php":
        allowed = {"mode", "f", "t", "p", "sid"}
        valid = params.get("mode") in {"post", "reply"}
    elif u.path == "/foro/ucp.php":
        allowed = {"i", "mode", "action", "u", "p", "sid"}
        valid = (
            params.get("i") in {"pm", "privmsgs"}
            and params.get("mode") == "compose"
            and params.get("action", "post") in {"post", "reply", "quotepost"}
        )
    else:
        allowed, valid = set(), False
    if not valid or not set(params) <= allowed:
        raise OperationError(
            "Solo se permite componer un tema, respuesta o MP; no editar, borrar ni moderar"
        )
    if any(
        not v.isdecimal() or int(v) <= 0 for k, v in pairs if k in {"f", "t", "p", "u"}
    ):
        raise OperationError("Identificador de destino inválido")
    return url


def download_url(value: str, base: str = INDEX) -> str:
    url = local_url(value, base)
    u = urlsplit(url)
    params = parse_qsl(u.query, keep_blank_values=True)
    data = dict(params)
    if (
        u.path != "/foro/download/file.php"
        or len(data) != len(params)
        or not set(data) <= {"id", "sid", "mode", "t"}
        or not data.get("id", "").isdecimal()
        or int(data["id"]) <= 0
        or ("mode" in data and data["mode"] != "view")
        or ("t" in data and data["t"] != "1")
    ):
        raise OperationError(
            "Se requiere un enlace de adjunto phpBB observado, no una URL arbitraria"
        )
    return url


def clean_url(value: str) -> str:
    u = urlsplit(value)
    from urllib.parse import urlencode

    return urlunsplit(
        (
            u.scheme,
            u.netloc,
            u.path,
            urlencode([(k, v) for k, v in parse_qsl(u.query) if k != "sid"]),
            "",
        )
    )


def private_path(path: Path):
    if any(p.is_symlink() for p in (path, *path.absolute().parents)):
        raise OperationError("No se permiten symlinks en borradores/adjuntos")


def digest(plan: dict) -> str:
    payload = {k: v for k, v in plan.items() if k != "confirmation"}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def plan_summary(plan: dict) -> dict:
    return {
        "kind": plan["kind"],
        "destination": clean_url(plan["action"]),
        "source": clean_url(plan["referer"]),
        "subject": dict(plan["fields"]).get("subject", ""),
        "message": dict(plan["fields"])["message"],
        "recipients": plan["recipients"],
        "recipient_details": plan.get("recipient_details", []),
        "confirmation": plan["confirmation"],
        "submitted": False,
        "authenticated": True,
    }


def prepare(
    app, url: str, message_file: Path, subject: str | None, *, is_authenticated
) -> dict:
    url = operation_url(url)
    private_path(message_file)
    if message_file.name.startswith(".env") or message_file.name in {
        "session.json",
        "cookies.json",
    }:
        raise OperationError("Un archivo de secretos no puede usarse como mensaje")
    if not message_file.is_file() or message_file.stat().st_size > 100000:
        raise OperationError(
            "El mensaje debe ser un archivo UTF-8 de hasta 100000 bytes"
        )
    try:
        message = message_file.read_text(encoding="utf-8")
    except UnicodeError:
        raise OperationError("El mensaje debe ser UTF-8") from None
    if not message.strip():
        raise OperationError("El mensaje está vacío")
    response = app.request(url, operation=True)
    soup = BeautifulSoup(response.text, "html.parser")
    if not is_authenticated(soup):
        raise OperationError(
            "No se verificó sesión del foro; no preparar ni enviar como invitado"
        )
    if soup.select_one(
        '[name="confirm_code"],.g-recaptcha,.h-captcha,[name="otp"],[name="totp"]'
    ):
        raise OperationError("Intervención CAPTCHA/2FA requerida; no eludirla")
    forms = [f for f in soup.select("form") if f.select_one('textarea[name="message"]')]
    if len(forms) != 1:
        raise OperationError("No se encontró un único formulario phpBB de composición")
    form = forms[0]
    action = operation_url(str(form.get("action", "")), str(response.url))
    if str(form.get("method", "get")).lower() != "post":
        raise OperationError("Cambió el método del formulario")
    requested, target = (
        dict(parse_qsl(urlsplit(url).query)),
        dict(parse_qsl(urlsplit(action).query)),
    )
    quote_to_pm = (
        urlsplit(action).path == "/foro/ucp.php"
        and requested.get("action") == "quotepost"
        and target.get("action") == "post"
    )
    bound_keys = {"mode", "f", "t", "p", "u", "i", "action"} - (
        {"action", "p"} if quote_to_pm else set()
    )
    if urlsplit(action).path != urlsplit(url).path or any(
        target.get(k) != v for k, v in requested.items() if k in bound_keys
    ):
        raise OperationError(
            "El formulario cambió el destino solicitado; no adivinar destinatarios"
        )
    fields, submit = [], None
    for item in form.select("input[name],textarea[name],select[name],button[name]"):
        if item.has_attr("disabled"):
            continue
        name, kind = (
            str(item["name"]),
            str(
                item.get("type", "submit" if item.name == "button" else "text")
            ).lower(),
        )
        if kind in {"submit", "image"}:
            if name == "post":
                submit = (name, str(item.get("value", "")))
            continue
        if kind in {"file", "button", "reset"} or (
            kind in {"checkbox", "radio"} and not item.has_attr("checked")
        ):
            continue
        if item.name == "textarea":
            value = item.get_text()
        elif item.name == "select":
            selected = item.select_one("option[selected]") or item.select_one("option")
            value = selected.get("value", selected.get_text()) if selected else ""
        else:
            value = item.get("value", "")
        if name == "message":
            value = message
        if name == "subject" and subject is not None:
            value = subject
        if name in {"delete", "delete_post", "delete_message", "cancel"}:
            raise OperationError(
                "El formulario incluye una acción secundaria destructiva; no enviar"
            )
        fields.append((name, str(value)))
    values = dict(fields)
    if (
        not values.get("form_token")
        or not values.get("creation_time")
        or submit is None
    ):
        raise OperationError(
            "Faltan tokens o botón post del formulario observado; no enviar"
        )
    if (
        len({n for n, v in fields if n == "message"}) != 1
        or sum(n == "message" for n, v in fields) != 1
    ):
        raise OperationError("Campo message ambiguo")
    kind = (
        "pm"
        if urlsplit(action).path.endswith("ucp.php")
        else ("reply" if target.get("mode") == "reply" else "topic")
    )
    if kind in {"topic", "pm"} and not values.get("subject", "").strip():
        raise OperationError("Un tema nuevo o MP requiere asunto explícito")
    recipients = [
        n for n, v in fields if re.fullmatch(r"address_list\[\d+\]\[(?:to|bcc)\]", n)
    ]
    if kind == "pm" and not recipients:
        raise OperationError(
            "El formulario no confirma destinatarios del MP; obtener un enlace de composición dirigido"
        )
    details = []
    for field in recipients:
        match = re.fullmatch(r"address_list\[(\d+)\]\[(to|bcc)\]", field)
        member_id, delivery = match.groups()
        name = None
        for anchor in form.select("a[href]"):
            parts = urlsplit(urljoin(str(response.url), str(anchor["href"])))
            if (
                parts.path.endswith("memberlist.php")
                and dict(parse_qsl(parts.query)).get("u") == member_id
            ):
                name = anchor.get_text(" ", strip=True) or None
                break
        details.append({"id": member_id, "delivery": delivery, "name": name})
    plan = {
        "version": 1,
        "kind": kind,
        "action": action,
        "referer": str(response.url),
        "fields": fields,
        "submit": submit,
        "recipients": recipients,
        "recipient_details": details,
        "created": time.time(),
    }
    plan["confirmation"] = digest(plan)
    directory = app.state.parent / "plans"
    private_path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (uuid.uuid4().hex + ".json")
    with path.open("x", encoding="utf-8") as stream:
        path.chmod(0o600)
        json.dump(plan, stream, ensure_ascii=False)
    return {**plan_summary(plan), "plan": str(path)}


def send(app, path: Path, confirmation: str, *, is_authenticated) -> dict:
    private_path(path)
    if (
        not path.is_file()
        or path.stat().st_size > 262144
        or stat.S_IMODE(path.stat().st_mode) & 0o077
    ):
        raise OperationError("Plan inexistente, inválido o no privado (0600)")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
        if (
            plan["version"] != 1
            or confirmation != plan["confirmation"]
            or digest(plan) != confirmation
        ):
            raise ValueError
        if not 0 <= time.time() - plan["created"] <= 1800:
            raise OperationError(
                "El plan expiró; preparar uno nuevo y volver a confirmar"
            )
        operation_url(plan["action"])
        operation_url(plan["referer"])
        if plan["submit"][0] != "post":
            raise ValueError
    except (ValueError, TypeError, KeyError) as exc:
        if isinstance(exc, OperationError):
            raise
        raise OperationError(
            "La confirmación no coincide con el plan completo o el plan fue modificado"
        ) from None
    if not is_authenticated(
        BeautifulSoup(app.request(INDEX, reading=True).text, "html.parser")
    ):
        raise OperationError("La sesión del foro expiró; no se envió el mensaje")
    claim = path.with_suffix(".attempted")
    private_path(claim)
    try:
        with claim.open("x", encoding="utf-8") as stream:
            claim.chmod(0o600)
            stream.write(confirmation)
    except FileExistsError:
        raise OperationError(
            "Este plan ya tuvo un intento: comprobar el foro antes de preparar otro, no reenviar"
        ) from None
    # La marca se conserva incluso con timeout: el resultado podría ser desconocido.
    response = app.request(
        plan["action"],
        form=[*(tuple(pair) for pair in plan["fields"]), tuple(plan["submit"])],
        operation=True,
        referer=plan["referer"],
    )
    if response.status_code in {301, 302, 303}:
        location = response.headers.get("location", "")
        return {
            "submitted": True,
            "publication_verified": False,
            "result_url": clean_url(local_url(location, plan["action"])),
            "retry_safe": False,
            "authenticated": True,
        }
    soup = BeautifulSoup(response.text, "html.parser")
    if soup.select_one('.error, .errorbox, textarea[name="message"]'):
        raise OperationError(
            "El foro devolvió el formulario/error; no reintentar automáticamente. Revisar antes de preparar otro plan"
        )
    acknowledgement = soup.select_one("#message, .message, .panel")
    text = acknowledgement.get_text(" ", strip=True) if acknowledgement else ""
    verified = bool(
        re.search(
            r"(?:mensaje|message).*?(?:enviado|publicado|sent|posted)",
            text,
            re.IGNORECASE,
        )
    )
    return {
        "submitted": True,
        "publication_verified": verified,
        "retry_safe": False,
        "authenticated": True,
    }


def download(app, url: str, output: Path) -> dict:
    url = download_url(url)
    private_path(output)
    if output.name.startswith(".env") or output.resolve() == app.state.resolve():
        raise OperationError(
            "No se permite descargar sobre credenciales o estado de sesión"
        )
    if output.exists() or not output.parent.is_dir():
        raise OperationError("El destino debe ser nuevo y su directorio debe existir")
    response = app.request(url, attachment=True)
    mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime in {
        "text/html",
        "application/xhtml+xml",
        "application/javascript",
        "text/javascript",
    }:
        raise OperationError(
            "El servidor devolvió HTML/script, no un adjunto descargable"
        )
    if not response.content:
        raise OperationError("Adjunto vacío")
    with output.open("xb") as stream:
        output.chmod(0o600)
        try:
            stream.write(response.content)
        except BaseException:
            stream.close()
            output.unlink(missing_ok=True)
            raise
    return {
        "output": str(output),
        "bytes": len(response.content),
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "content_type": mime,
        "source": clean_url(url),
        "executed": False,
    }
