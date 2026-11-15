from __future__ import annotations

import hmac
import json
import os
import sqlite3
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DB_PATH = Path(os.getenv("DB_PATH", "/data/booknest.db"))
CONFIG_FILE = Path(os.getenv("CONFIG_FILE", "/etc/booknest/config/config.json"))
SECRET_FILE = Path(os.getenv("SECRET_FILE", "/etc/booknest/secrets/credentials.json"))
SESSION_COOKIE_NAME = "booknest_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60

app = FastAPI(
    title="BookNest Library API",
    description="A demonstration library application configured with Kubernetes ConfigMaps and Secrets.",
    version="2.0.0",
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class BookCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    author: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=50)
    isbn: str = Field(min_length=5, max_length=30)
    copies: int = Field(default=1, ge=1, le=100)


class IssueRequest(BaseModel):
    book_id: int
    student_name: str = Field(min_length=2, max_length=100)
    student_id: str = Field(min_length=2, max_length=40)


class ReturnRequest(BaseModel):
    loan_id: int


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


SEED_BOOKS = [
    ("Atomic Habits", "James Clear", "Personal Growth", "9780735211292", 5),
    ("The Psychology of Money", "Morgan Housel", "Finance", "9780857197689", 4),
    ("Clean Code", "Robert C. Martin", "Technology", "9780132350884", 3),
    ("Deep Work", "Cal Newport", "Productivity", "9781455586691", 3),
    ("The Alchemist", "Paulo Coelho", "Fiction", "9780062315007", 4),
    ("Design of Everyday Things", "Don Norman", "Design", "9780465050659", 2),
    ("Python Crash Course", "Eric Matthes", "Technology", "9781718502703", 4),
    ("Sapiens", "Yuval Noah Harari", "History", "9780062316097", 3),
    ("Ikigai", "Héctor García & Francesc Miralles", "Lifestyle", "9780143130727", 4),
    ("The Pragmatic Programmer", "David Thomas & Andrew Hunt", "Technology", "9780135957059", 2),
    ("Start With Why", "Simon Sinek", "Business", "9781591846444", 2),
    ("The Midnight Library", "Matt Haig", "Fiction", "9780525559474", 3),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def db_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database() -> None:
    with db_connection() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                category TEXT NOT NULL,
                isbn TEXT NOT NULL UNIQUE,
                total_copies INTEGER NOT NULL,
                available_copies INTEGER NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                student_id TEXT NOT NULL,
                issued_on TEXT NOT NULL,
                returned_on TEXT,
                FOREIGN KEY(book_id) REFERENCES books(id)
            )"""
        )
        for title, author, category, isbn, copies in SEED_BOOKS:
            connection.execute(
                "INSERT OR IGNORE INTO books (title, author, category, isbn, total_copies, available_copies) VALUES (?, ?, ?, ?, ?, ?)",
                (title, author, category, isbn, copies, copies),
            )


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def read_config() -> dict[str, str]:
    """Read the projected ConfigMap file on every request so updates can appear live."""
    file_values = read_json_file(CONFIG_FILE)
    keys = [
        "LIBRARY_NAME",
        "LIBRARY_HOURS",
        "MAX_BOOKS_PER_STUDENT",
        "LATE_RETURN_FEE",
        "ANNOUNCEMENT",
        "LIBRARY_THEME",
    ]
    result: dict[str, str] = {}
    for key in keys:
        env_value = os.getenv(key)
        file_value = file_values.get(key)
        # Mounted ConfigMap file is the live source. Environment values show the
        # pod-start snapshot and are updated when the Deployment rolls out.
        value = file_value if file_value not in (None, "") else env_value
        result[key] = str(value if value not in (None, "") else "Not configured")
    return result


def read_secret_file() -> dict[str, Any]:
    return read_json_file(SECRET_FILE)


def expected_credentials() -> tuple[str, str]:
    return os.getenv("ADMIN_USERNAME", "librarian"), os.getenv("ADMIN_PASSWORD", "")


def credentials_match(username: str, password: str) -> bool:
    configured_username, configured_password = expected_credentials()
    return hmac.compare_digest(username, configured_username) and hmac.compare_digest(password, configured_password)


def _session_key() -> bytes:
    key = os.getenv("SESSION_SECRET_KEY") or os.getenv("ADMIN_PASSWORD", "")
    if not key:
        raise HTTPException(status_code=503, detail="Session signing key is not configured.")
    return key.encode("utf-8")


def _create_session_token(username: str) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    payload = f"{username}|{issued_at}|{nonce}"
    signature = hmac.new(_session_key(), payload.encode("utf-8"), digestmod="sha256").hexdigest()
    return f"{issued_at}.{nonce}.{signature}"


def _valid_session(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    parts = token.split(".")
    if len(parts) != 3:
        return False
    issued_at, nonce, signature = parts
    try:
        age = int(time.time()) - int(issued_at)
    except ValueError:
        return False
    if age < 0 or age > SESSION_MAX_AGE_SECONDS:
        return False
    username, _ = expected_credentials()
    payload = f"{username}|{issued_at}|{nonce}"
    expected = hmac.new(_session_key(), payload.encode("utf-8"), digestmod="sha256").hexdigest()
    return hmac.compare_digest(signature, expected)


def _create_tab_proof(session_token: str) -> str:
    message = f"booknest-tab|{session_token}"
    return hmac.new(_session_key(), message.encode("utf-8"), digestmod="sha256").hexdigest()


def require_admin(request: Request) -> None:
    session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    supplied_tab_proof = request.headers.get("X-BookNest-Tab", "")
    if not _valid_session(request) or not supplied_tab_proof:
        raise HTTPException(status_code=401, detail="Your librarian session has ended. Please sign in again.")
    expected_tab_proof = _create_tab_proof(session_token)
    if not hmac.compare_digest(supplied_tab_proof, expected_tab_proof):
        raise HTTPException(status_code=401, detail="This browser tab is not authenticated. Please sign in again.")


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/", include_in_schema=False)
def homepage(request: Request):
    if not _valid_session(request):
        return RedirectResponse(url="/login", status_code=303)
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"status": "healthy", "service": "booknest", "pod": os.getenv("HOSTNAME", "local")}


@app.get("/api/status")
def runtime_status(request: Request):
    require_admin(request)
    config = read_config()
    env_keys = ["LIBRARY_NAME", "LIBRARY_HOURS", "MAX_BOOKS_PER_STUDENT", "LATE_RETURN_FEE", "ANNOUNCEMENT", "LIBRARY_THEME"]
    env_snapshot = {key: os.getenv(key, "Not configured") for key in env_keys}
    secret_file = read_secret_file()
    secret_user, secret_password = expected_credentials()
    secret_file_user = str(secret_file.get("ADMIN_USERNAME", ""))
    secret_file_password = str(secret_file.get("ADMIN_PASSWORD", ""))
    return {
        "application": "BookNest",
        "pod": os.getenv("HOSTNAME", "local"),
        "config": config,
        "environment_snapshot": env_snapshot,
        "config_file_mounted": CONFIG_FILE.is_file(),
        "secret_file_mounted": SECRET_FILE.is_file(),
        "secret_env_loaded": bool(secret_user and secret_password),
        "secret_file_keys": sorted(secret_file.keys()),
        "secret_sources_match": bool(secret_file_user and secret_file_password) and hmac.compare_digest(secret_user, secret_file_user) and hmac.compare_digest(secret_password, secret_file_password),
        "secret_values_exposed": False,
    }


@app.get("/api/books")
def list_books(request: Request, search: str = ""):
    require_admin(request)
    search_value = f"%{search.strip()}%"
    with db_connection() as connection:
        rows = connection.execute(
            """SELECT id, title, author, category, isbn, total_copies, available_copies
               FROM books WHERE title LIKE ? OR author LIKE ? OR category LIKE ? ORDER BY title""",
            (search_value, search_value, search_value),
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/loans")
def list_loans(request: Request):
    require_admin(request)
    with db_connection() as connection:
        rows = connection.execute(
            """SELECT loans.id, loans.book_id, books.title AS book_title, loans.student_name,
                      loans.student_id, loans.issued_on, loans.returned_on
               FROM loans JOIN books ON books.id = loans.book_id
               ORDER BY loans.id DESC LIMIT 100"""
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/stats")
def stats(request: Request):
    require_admin(request)
    with db_connection() as connection:
        books = connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(total_copies), 0) AS total FROM books").fetchone()
        available = connection.execute("SELECT COALESCE(SUM(available_copies), 0) AS total FROM books").fetchone()
        issued = connection.execute("SELECT COUNT(*) AS total FROM loans WHERE returned_on IS NULL").fetchone()
        students = connection.execute("SELECT COUNT(DISTINCT student_id) AS total FROM loans WHERE returned_on IS NULL").fetchone()
    return {
        "book_titles": books["count"],
        "total_copies": books["total"],
        "available_copies": available["total"],
        "active_loans": issued["total"],
        "active_students": students["total"],
    }


@app.post("/api/admin/login")
def admin_login(payload: LoginRequest):
    if not credentials_match(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")
    session_token = _create_session_token(payload.username)
    response = JSONResponse({
        "ok": True,
        "message": "Welcome to BookNest.",
        "tab_token": _create_tab_proof(session_token),
    })
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="strict",
        path="/",
        # No max-age/expires: this is a browser-session cookie.
    )
    return response


@app.post("/api/admin/logout")
def admin_logout():
    response = JSONResponse({"ok": True, "message": "You have been signed out."})
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", httponly=True, samesite="strict")
    return response


@app.post("/api/books", status_code=201)
def create_book(payload: BookCreate, request: Request):
    require_admin(request)
    try:
        with db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO books (title, author, category, isbn, total_copies, available_copies) VALUES (?, ?, ?, ?, ?, ?)",
                (payload.title.strip(), payload.author.strip(), payload.category.strip(), payload.isbn.strip(), payload.copies, payload.copies),
            )
            book_id = cursor.lastrowid
            row = connection.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A book with this ISBN already exists.")
    return dict(row)


@app.post("/api/loans", status_code=201)
def issue_book(payload: IssueRequest, request: Request):
    require_admin(request)
    config = read_config()
    try:
        max_books = max(1, int(config.get("MAX_BOOKS_PER_STUDENT", "3")))
    except ValueError:
        max_books = 3
    with db_connection() as connection:
        active = connection.execute("SELECT COUNT(*) FROM loans WHERE student_id = ? AND returned_on IS NULL", (payload.student_id.strip(),)).fetchone()[0]
        if active >= max_books:
            raise HTTPException(status_code=400, detail=f"This student has reached the current limit of {max_books} active books.")
        book = connection.execute("SELECT * FROM books WHERE id = ?", (payload.book_id,)).fetchone()
        if book is None:
            raise HTTPException(status_code=404, detail="Book not found.")
        if book["available_copies"] < 1:
            raise HTTPException(status_code=400, detail="No copies of this book are currently available.")
        connection.execute("UPDATE books SET available_copies = available_copies - 1 WHERE id = ?", (payload.book_id,))
        cursor = connection.execute(
            "INSERT INTO loans (book_id, student_name, student_id, issued_on) VALUES (?, ?, ?, ?)",
            (payload.book_id, payload.student_name.strip(), payload.student_id.strip(), utc_now()),
        )
        loan_id = cursor.lastrowid
    return {"ok": True, "loan_id": loan_id, "message": f"{book['title']} issued successfully."}


@app.post("/api/returns")
def return_book(payload: ReturnRequest, request: Request):
    require_admin(request)
    with db_connection() as connection:
        loan = connection.execute("SELECT * FROM loans WHERE id = ?", (payload.loan_id,)).fetchone()
        if loan is None:
            raise HTTPException(status_code=404, detail="Loan record not found.")
        if loan["returned_on"] is not None:
            raise HTTPException(status_code=400, detail="This book has already been returned.")
        connection.execute("UPDATE loans SET returned_on = ? WHERE id = ?", (utc_now(), payload.loan_id))
        connection.execute("UPDATE books SET available_copies = available_copies + 1 WHERE id = ?", (loan["book_id"],))
    return {"ok": True, "message": "Book returned successfully."}
