"""Авторизация: вход по логину и паролю, дальше токен доступа.

Токен имеет вид  имя:время_истечения:подпись. Подпись считается по секретному
ключу сервиса (HMAC-SHA256), поэтому подделать токен без ключа нельзя,
а хранить токены в базе или памяти не нужно.
Клиент присылает токен в заголовке  Authorization: Bearer <токен>.
"""
import hashlib
import hmac
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import config

bearer = HTTPBearer(auto_error=False)


def _sign(payload: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def check_credentials(username: str, password: str) -> bool:
    ok_user = hmac.compare_digest(username.encode(), config.APP_USER.encode())
    ok_pass = hmac.compare_digest(password.encode(), config.APP_PASSWORD.encode())
    return ok_user and ok_pass


def create_token(username: str) -> str:
    expires = int(time.time()) + config.TOKEN_TTL_SECONDS
    payload = f"{username}:{expires}"
    return f"{payload}:{_sign(payload)}"


def verify_token(token: str):
    """Возвращает имя пользователя или None, если токен неверный или просрочен."""
    parts = token.rsplit(":", 2)
    if len(parts) != 3:
        return None
    username, expires, signature = parts
    if not hmac.compare_digest(signature, _sign(f"{username}:{expires}")):
        return None
    if not expires.isdigit() or int(expires) < time.time():
        return None
    return username


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    """Зависимость маршрутов: пускает только с верным токеном, иначе 401."""
    username = verify_token(credentials.credentials) if credentials else None
    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Требуется авторизация",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username
