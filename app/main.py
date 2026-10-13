"""Веб-сервис «Выдача книг в библиотеке». Запуск: uvicorn app.main:app --port 8000"""
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app import auth, repository
from app.auth import current_user
from app.db import connect, start_stats
from app.rules import LoanError
from app.schemas import IssueRequest, LoginRequest

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Библиотека: выдача книг")


@app.middleware("http")
async def add_db_stats_headers(request: Request, call_next):
    """Считает запросы к БД на каждое обращение и сообщает итог в заголовках ответа.

    X-DB-Queries: сколько запросов к базе выполнено при обработке обращения.
    X-DB-Time-Ms: сколько миллисекунд они заняли внутри базы (без открытия соединения).
    X-DB-Connect-Ms: сколько миллисекунд ушло на открытие соединения с базой.
    Заголовки нужны скрипту замеров (подраздел 2.6 методички).
    """
    stats = start_stats()
    response = await call_next(request)
    response.headers["X-DB-Queries"] = str(stats.queries)
    response.headers["X-DB-Time-Ms"] = f"{stats.seconds * 1000:.3f}"
    response.headers["X-DB-Connect-Ms"] = f"{stats.connect_seconds * 1000:.3f}"
    return response


# --- Преобразование внутренних исключений в коды ответа -------------------------

@app.exception_handler(repository.NotFound)
async def not_found_handler(request: Request, exc: repository.NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(LoanError)
async def loan_error_handler(request: Request, exc: LoanError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(repository.AlreadyReturned)
async def already_returned_handler(request: Request, exc: repository.AlreadyReturned):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# --- Клиентская страница --------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


# --- Программный интерфейс ------------------------------------------------------

@app.post("/api/login")
def login(body: LoginRequest):
    if not auth.check_credentials(body.username, body.password):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    return {"token": auth.create_token(body.username)}


@app.get("/api/loans")
def list_loans(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Literal["all", "on_hands", "overdue", "returned"] = "all",
    reader_id: int | None = Query(None, ge=1),
    user: str = Depends(current_user),
):
    with connect() as conn:
        return repository.list_loans(conn, page, size, status, reader_id)


@app.get("/api/loans/{loan_id}")
def get_loan(loan_id: int, user: str = Depends(current_user)):
    with connect() as conn:
        loan = repository.get_loan(conn, loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="выдача не найдена")
    return loan


@app.post("/api/loans", status_code=201)
def issue_loan(body: IssueRequest, user: str = Depends(current_user)):
    with connect() as conn:
        return repository.issue_loan(conn, body.reader_id, body.copy_id)


@app.post("/api/loans/{loan_id}/return")
def return_loan(loan_id: int, user: str = Depends(current_user)):
    with connect() as conn:
        return repository.return_loan(conn, loan_id)


@app.get("/api/summary")
def summary(user: str = Depends(current_user)):
    with connect() as conn:
        return repository.get_summary(conn)
