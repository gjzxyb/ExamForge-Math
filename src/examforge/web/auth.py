"""Web 登录、密码哈希与全局访问控制。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from urllib.parse import urlsplit

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config.settings import get_settings, get_settings_store
from .app import templates


PBKDF2_ITERATIONS = 600_000
router = APIRouter()


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode().rstrip("="),
        base64.urlsafe_b64encode(digest).decode().rstrip("="),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(raw_salt + "=" * (-len(raw_salt) % 4))
        expected = base64.urlsafe_b64decode(raw_digest + "=" * (-len(raw_digest) % 4))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, int(raw_iterations),
        )
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def is_authenticated(request: Request) -> bool:
    auth = get_settings().auth
    return not auth.enabled or (
        request.session.get("authenticated") is True
        and request.session.get("username") == auth.username
    )


def safe_next_url(value: str) -> str:
    parsed = urlsplit(value or "")
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return "/"
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    if is_authenticated(request):
        return RedirectResponse(safe_next_url(next), status_code=303)
    auth = get_settings().auth
    return templates.TemplateResponse(request, "login.html", {
        "error": "",
        "next_url": safe_next_url(next),
        "needs_setup": not bool(auth.password_hash),
        "username": auth.username,
    })


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
):
    auth = get_settings().auth
    valid = bool(auth.password_hash) and secrets.compare_digest(username, auth.username)
    valid = valid and verify_password(password, auth.password_hash)
    if valid:
        request.session.clear()
        request.session["authenticated"] = True
        request.session["username"] = auth.username
        return RedirectResponse(safe_next_url(next), status_code=303)
    return templates.TemplateResponse(request, "login.html", {
        "error": "用户名或密码错误。" if auth.password_hash else "系统尚未设置管理员密码。",
        "next_url": safe_next_url(next),
        "needs_setup": not bool(auth.password_hash),
        "username": auth.username,
    }, status_code=401)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    auth = get_settings().auth
    if auth.password_hash:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "setup.html", {
        "error": "",
        "username": auth.username,
    })


@router.post("/setup", response_class=HTMLResponse)
async def setup_submit(
    request: Request,
    username: str = Form("admin"),
    password: str = Form(""),
    confirm_password: str = Form(""),
):
    auth = get_settings().auth
    if auth.password_hash:
        return RedirectResponse("/login", status_code=303)
    username = username.strip()
    error = ""
    if len(username) < 3:
        error = "用户名至少需要 3 个字符。"
    elif len(password) < 10:
        error = "密码至少需要 10 个字符。"
    elif password != confirm_password:
        error = "两次输入的密码不一致。"
    if error:
        return templates.TemplateResponse(request, "setup.html", {
            "error": error,
            "username": username or "admin",
        }, status_code=400)
    get_settings_store().update(auth={
        "username": username,
        "password_hash": hash_password(password),
        "enabled": True,
    })
    request.session.clear()
    request.session["authenticated"] = True
    request.session["username"] = username
    return RedirectResponse("/", status_code=303)
