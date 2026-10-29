#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# dependencies = ["pytest", "httpx>=0.28,<1", "beautifulsoup4>=4.14,<5", "python-dotenv>=1.1,<2", "markdownify>=1.2,<2"]
# ///
"""Credenciales, Markdown, adjuntos y publicación simulada: ninguna cuenta real."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from urllib.parse import parse_qsl

import forum
import forum_ops as ops
import httpx
import pytest
from bs4 import BeautifulSoup
from forum_content import html_markdown

AUTH = '<a href="./ucp.php?mode=logout&amp;sid=secret-session">Salir</a>'
TARGET = forum.ORIGIN + "/foro/posting.php?mode=reply&f=2&t=3"
FORM = (
    AUTH
    + """<form method="post" action="./posting.php?mode=reply&amp;f=2&amp;t=3&amp;sid=secret-session">
<input type="hidden" name="form_token" value="secret-form-token">
<input type="hidden" name="creation_time" value="1000">
<input name="subject" value="Re: Tema"><textarea name="message"></textarea>
<input type="submit" name="preview" value="Vista previa"><input type="submit" name="save" value="Guardar borrador">
<input type="submit" name="post" value="Enviar"></form>"""
)


def response(text=FORM, status=200, headers=None):
    return httpx.Response(
        status, text=text, headers={"content-type": "text/html", **(headers or {})}
    )


@pytest.fixture
def app_factory(tmp_path):
    apps = []

    def make(handler):
        app = forum.Forum(
            tmp_path / "private" / "session.json",
            transport=httpx.MockTransport(handler),
            delay=0,
        )
        apps.append(app)
        return app

    yield make
    for app in apps:
        app.close()


@pytest.fixture
def message_file(tmp_path):
    path = tmp_path / "message.txt"
    path.write_text("Hola, mensaje revisado por el usuario.", encoding="utf-8")
    return path


def test_environment_pair_wins_without_even_reading_dotenv(monkeypatch, tmp_path):
    monkeypatch.setenv("EPL_USER", "env-user")
    monkeypatch.setenv("EPL_PASS", "env-pass")
    monkeypatch.setattr(
        forum, "dotenv_values", lambda *a, **k: pytest.fail("dotenv must not be read")
    )
    assert forum.credentials(tmp_path / "absent", "USER", "PASS") == (
        "env-user", "env-pass"
    )


@pytest.mark.parametrize(
    "key,value", [("EPL_USER", "user"), ("EPL_PASS", "pass"), ("EPL_USER", "")]
)
def test_partial_environment_never_mixes_with_a_file(monkeypatch, tmp_path, key, value):
    monkeypatch.setenv(key, value)
    path = tmp_path / ".env"
    path.write_text("EPL_USER=file-user\nEPL_PASS=file-pass\n")
    with pytest.raises(forum.ForumError, match="incompletas"):
        forum.credentials(path)


def test_cwd_then_skill_env_fallback_without_interpolation(tmp_path):
    cwd, skill = tmp_path / "cwd", tmp_path / "skill"
    cwd.mkdir()
    skill.mkdir()
    (skill / ".env").write_text("EPL_USER=skill-user\nEPL_PASS='literal${SECRET}'\n")
    assert forum.credentials(cwd=cwd, skill_dir=skill) == (
        "skill-user",
        "literal${SECRET}",
    )
    (cwd / ".env").write_text("EPL_USER=cwd-user\nEPL_PASS=cwd-pass\n")
    assert forum.credentials(cwd=cwd, skill_dir=skill) == ("cwd-user", "cwd-pass")


def test_incomplete_cwd_env_is_not_mixed_with_skill_env(tmp_path):
    cwd, skill = tmp_path / "cwd", tmp_path / "skill"
    cwd.mkdir()
    skill.mkdir()
    (cwd / ".env").write_text("EPL_USER=partial\n")
    (skill / ".env").write_text("EPL_USER=other\nEPL_PASS=other\n")
    with pytest.raises(forum.ForumError, match="primer .env"):
        forum.credentials(cwd=cwd, skill_dir=skill)


def test_markdown_preserves_format_and_sanitizes_links_and_scripts():
    source = """<div><p>Texto <strong>fuerte</strong> y <em>énfasis</em>.</p>
<blockquote><p>Cita</p></blockquote><ul><li>Uno</li><li>Dos</li></ul>
<dl class="codebox"><dt>Seleccionar todo</dt><dd><code>a = 1\n  b = 2</code></dd></dl>
<a href="./viewtopic.php?t=3&amp;sid=private&amp;form_token=secret">Hilo</a>
<a href="javascript:alert(1)">no ejecutar</a><img src="https://images.test/pixel" alt="Figura">
<script>secret-script</script></div>"""
    text = html_markdown(source, forum.INDEX)
    assert "**fuerte**" in text and "*énfasis*" in text
    assert "> Cita" in text and "- Uno" in text
    assert "```" in text and "  b = 2" in text
    assert "sid=" not in text and "form_token" not in text
    assert "javascript:" not in text and "secret-script" not in text
    assert "![" not in text and "Imagen: Figura" in text


def test_reader_includes_markdown_and_observed_actions_and_attachments(app_factory):
    body = (
        AUTH
        + f'''<a href="{TARGET}">Responder</a><a href="./download/file.php?id=9&amp;sid=private">regex.ini</a>
<div class="post" id="p4"><div class="postprofile"><dt><a>Autor</a></dt></div>
<div class="postbody"><div class="content"><p>Una <b>guía</b>.</p></div></div></div>'''
    )
    app = app_factory(lambda req: response(body))
    result = app.read(forum.INDEX)
    assert "**guía**" in result["markdown"]
    assert result["actions"][0]["url"] == TARGET
    assert result["attachments"][0]["url"].endswith("?id=9")
    assert "private" not in json.dumps(result)


def test_prepare_fetches_form_but_never_posts_and_hides_tokens(
    app_factory, message_file
):
    calls = []
    app = app_factory(lambda req: calls.append(req) or response())
    report = ops.prepare(
        app, TARGET, message_file, None, is_authenticated=forum.authenticated
    )
    assert len(calls) == 1 and calls[0].method == "GET"
    assert report["submitted"] is False
    assert report["message"] == message_file.read_text()
    assert "secret-form-token" not in json.dumps(report)
    assert "secret-session" not in json.dumps(report)
    assert stat.S_IMODE(Path(report["plan"]).stat().st_mode) == 0o600


def test_send_exact_plan_once_and_never_preview_or_save(app_factory, message_file):
    posts = []

    def handler(req):
        if req.method == "POST":
            posts.append(dict(parse_qsl(req.content.decode())))
            return response('<div id="message">Tu mensaje ha sido publicado.</div>')
        return response(AUTH if req.url.path.endswith("index.php") else FORM)

    app = app_factory(handler)
    report = ops.prepare(
        app, TARGET, message_file, None, is_authenticated=forum.authenticated
    )
    result = ops.send(
        app,
        Path(report["plan"]),
        report["confirmation"],
        is_authenticated=forum.authenticated,
    )
    assert result["publication_verified"] is True
    assert len(posts) == 1
    assert (
        posts[0]["post"] == "Enviar"
        and "preview" not in posts[0]
        and "save" not in posts[0]
    )
    assert posts[0]["message"] == message_file.read_text()
    assert posts[0]["form_token"] == "secret-form-token"
    with pytest.raises(ops.OperationError, match="ya tuvo"):
        ops.send(
            app,
            Path(report["plan"]),
            report["confirmation"],
            is_authenticated=forum.authenticated,
        )
    assert len(posts) == 1


def test_confirmation_binds_content_destination_and_subject(app_factory, message_file):
    app = app_factory(lambda req: response())
    report = ops.prepare(
        app, TARGET, message_file, "Re: otro", is_authenticated=forum.authenticated
    )
    path = Path(report["plan"])
    with pytest.raises(ops.OperationError, match="confirmación"):
        ops.send(app, path, "wrong", is_authenticated=forum.authenticated)
    data = json.loads(path.read_text())
    data["fields"] = [
        [n, "changed" if n == "message" else v] for n, v in data["fields"]
    ]
    path.write_text(json.dumps(data))
    with pytest.raises(ops.OperationError, match="confirmación"):
        ops.send(
            app, path, report["confirmation"], is_authenticated=forum.authenticated
        )
    assert not path.with_suffix(".attempted").exists()


def test_timeout_claim_prevents_duplicate_send(app_factory, message_file):
    calls = []

    def handler(req):
        if req.method == "POST":
            calls.append(req)
            raise httpx.ReadTimeout("unknown delivery", request=req)
        return response(AUTH if req.url.path.endswith("index.php") else FORM)

    app = app_factory(handler)
    plan = ops.prepare(
        app, TARGET, message_file, None, is_authenticated=forum.authenticated
    )
    path = Path(plan["plan"])
    with pytest.raises(forum.ForumError):
        ops.send(app, path, plan["confirmation"], is_authenticated=forum.authenticated)
    with pytest.raises(ops.OperationError, match="ya tuvo"):
        ops.send(app, path, plan["confirmation"], is_authenticated=forum.authenticated)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        FORM.replace('value="secret-form-token"', 'value=""'),
        FORM.replace(AUTH, ""),
        FORM.replace('name="post"', 'name="save"'),
        FORM.replace("mode=reply", "mode=post"),
        FORM + '<input name="confirm_code">',
    ],
)
def test_missing_auth_tokens_or_changed_target_never_prepare(
    app_factory, message_file, body
):
    app = app_factory(lambda req: response(body))
    with pytest.raises(ops.OperationError):
        ops.prepare(
            app, TARGET, message_file, None, is_authenticated=forum.authenticated
        )
    assert not (app.state.parent / "plans").exists()


def test_pm_requires_observed_recipients(app_factory, message_file):
    url = forum.ORIGIN + "/foro/ucp.php?i=pm&mode=compose&action=post&u=7"
    body = FORM.replace(
        "./posting.php?mode=reply&amp;f=2&amp;t=3&amp;sid=secret-session",
        url.replace("&", "&amp;"),
    )
    app = app_factory(lambda req: response(body))
    with pytest.raises(ops.OperationError, match="destinatarios"):
        ops.prepare(app, url, message_file, None, is_authenticated=forum.authenticated)
    body = body.replace(
        "</form>", '<input type="hidden" name="address_list[7][to]" value="to"></form>'
    )
    app = app_factory(lambda req: response(body))
    report = ops.prepare(
        app, url, message_file, None, is_authenticated=forum.authenticated
    )
    assert report["kind"] == "pm" and report["recipients"] == ["address_list[7][to]"]


def test_download_is_bounded_data_and_never_overwrites(app_factory, tmp_path):
    data = b"[regex]\npattern=example\n"
    app = app_factory(
        lambda req: httpx.Response(
            200,
            content=data,
            headers={
                "content-type": "application/octet-stream",
                "content-disposition": 'attachment; filename="../../not-trusted.ini"',
            },
        )
    )
    output = tmp_path / "regex.ini"
    report = ops.download(app, forum.ORIGIN + "/foro/download/file.php?id=9", output)
    assert output.read_bytes() == data and report["executed"] is False
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(ops.OperationError):
        ops.download(app, forum.ORIGIN + "/foro/download/file.php?id=9", output)
    assert output.read_bytes() == data


def test_download_rejects_html_and_protected_outputs(app_factory, tmp_path):
    app = app_factory(lambda req: response("<form>Login</form>"))
    output = tmp_path / "regex.ini"
    with pytest.raises(ops.OperationError, match="HTML"):
        ops.download(app, forum.ORIGIN + "/foro/download/file.php?id=9", output)
    assert not output.exists()
    with pytest.raises(ops.OperationError, match="credenciales"):
        ops.download(
            app, forum.ORIGIN + "/foro/download/file.php?id=9", tmp_path / ".env"
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/file",
        "./download/file.php?id=9&delete=1",
        "./posting.php?mode=delete&p=1",
        "./ucp.php?i=pm&mode=compose&action=delete",
        "./posting.php?mode=reply&mode=delete&t=1",
    ],
)
def test_operation_allowlists_reject_other_actions(url):
    with pytest.raises(ops.OperationError):
        if "download" in url:
            ops.download_url(url)
        else:
            ops.operation_url(url)


UCP = '<a href="./ucp.php">Panel de control</a>'
INBOX = '<a href="./ucp.php?i=pm&amp;folder=inbox">Bandeja de entrada</a>'


@pytest.mark.parametrize(
    "body,expected",
    [
        (UCP + INBOX, True),
        (UCP, False),
        (INBOX, False),
        ('<div class="post">' + UCP + INBOX + '</div>', False),
        (UCP + '<div class="postbody">' + INBOX + '</div>', False),
    ],
)
def test_integrated_menu_requires_both_links_outside_posts(body, expected):
    assert forum.authenticated(BeautifulSoup(body, "html.parser")) is expected


def test_status_checks_account_and_index_without_login(app_factory):
    calls = []
    app = app_factory(lambda req: calls.append(str(req.url)) or response(UCP + INBOX))
    assert app.status() == {
        "site_authenticated": True, "forum_authenticated": True
    }
    assert calls == [forum.ORIGIN + "/usuario/cuenta", forum.INDEX]


def test_quotepost_prepares_pm_with_resolved_recipient_and_explicit_body(
    app_factory, message_file
):
    source = forum.ORIGIN + "/foro/ucp.php?i=pm&mode=compose&action=quotepost&p=4"
    target = "./ucp.php?i=pm&amp;mode=compose&amp;action=post"
    body = FORM.replace(
        "./posting.php?mode=reply&amp;f=2&amp;t=3&amp;sid=secret-session", target
    ).replace(
        '<textarea name="message"></textarea>',
        '<textarea name="message">[quote]Original privado[/quote]</textarea>'
    ).replace(
        '</form>',
        '<input type="hidden" name="address_list[7][to]" value="to">'
        '<a href="./memberlist.php?mode=viewprofile&amp;u=7">Revisor</a></form>'
    )
    calls = []
    app = app_factory(lambda req: calls.append(req) or response(body))
    report = ops.prepare(
        app, source, message_file, None, is_authenticated=forum.authenticated
    )
    assert [req.method for req in calls] == ["GET"]
    assert report["kind"] == "pm"
    assert report["source"] == source
    assert report["destination"].endswith("action=post")
    assert report["message"] == message_file.read_text()
    assert report["recipient_details"] == [
        {"id": "7", "delivery": "to", "name": "Revisor"}
    ]
    fields = dict(json.loads(Path(report["plan"]).read_text())["fields"])
    assert fields["message"] == message_file.read_text()
    assert fields["address_list[7][to]"] == "to"


def test_expired_plan_never_makes_a_request(app_factory, message_file, monkeypatch):
    calls = []
    app = app_factory(lambda req: calls.append(req) or response())
    report = ops.prepare(
        app, TARGET, message_file, None, is_authenticated=forum.authenticated
    )
    path = Path(report["plan"])
    created = json.loads(path.read_text())["created"]
    monkeypatch.setattr(ops.time, "time", lambda: created + 1801)
    with pytest.raises(ops.OperationError, match="expiró"):
        ops.send(app, path, report["confirmation"], is_authenticated=forum.authenticated)
    assert len(calls) == 1
    assert not path.with_suffix(".attempted").exists()


@pytest.mark.parametrize("case", ["external", "too-large"])
def test_rejected_download_leaves_no_file(app_factory, tmp_path, monkeypatch, case):
    monkeypatch.setattr(forum, "MAX_ATTACHMENT", 8)
    calls = []

    def handler(req):
        calls.append(req)
        if case == "external":
            return httpx.Response(302, headers={"location": "https://evil.test/file"})
        return httpx.Response(200, content=b"123456789")

    app = app_factory(handler)
    output = tmp_path / "attachment.ini"
    with pytest.raises((forum.ForumError, ops.OperationError)):
        ops.download(app, forum.ORIGIN + "/foro/download/file.php?id=9", output)
    assert not output.exists()
    assert len(calls) == 1


@pytest.mark.parametrize("args", [[], ["--format", "json"]])
def test_cli_read_markdown_default_and_json_option(
    app_factory, monkeypatch, capsys, args
):
    app = app_factory(lambda req: response('<title>Foro</title>'))
    monkeypatch.setattr(forum, "Forum", lambda *a, **kw: app)
    assert forum.main(["read", *args]) == 0
    output = capsys.readouterr().out
    if args:
        assert "markdown" in json.loads(output)
    else:
        assert output.startswith("# Foro")
