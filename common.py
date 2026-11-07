"""Small infrastructure helpers; copied per repository, no shared domain/database access."""
import os
import time
from contextlib import contextmanager
from uuid import UUID, uuid4
import jwt
import psycopg
from psycopg.rows import dict_row
from fastapi import Header, HTTPException, Request
from fastapi.responses import JSONResponse

ISSUER = "cant-run-alone-local"
AUDIENCE = "cant-run-alone-services"

def token_key():
    return os.environ["JWT_SECRET"]

def issue(user_id, verified=True):
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "phoneVerified": verified, "iss": ISSUER,
                       "aud": AUDIENCE, "iat": now, "exp": now + 900}, token_key(), algorithm="HS256")

def user(authorization: str = Header(default="")):
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            raise ValueError()
        claims = jwt.decode(token, token_key(), algorithms=["HS256"], issuer=ISSUER,
                            audience=AUDIENCE, options={"require": ["sub", "exp", "iat", "iss", "aud"]})
        UUID(claims["sub"])
        return claims
    except (ValueError, jwt.PyJWTError):
        raise HTTPException(401, "Valid access token required")

@contextmanager
def db():
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        yield connection

def migrate():
    from pathlib import Path
    with db() as connection:
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('cra_schema_migrations'))")
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY)")
        for path in sorted(Path("migrations").glob("*.sql")):
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE version=%s", (path.name,)).fetchone():
                connection.execute(path.read_text())
                connection.execute("INSERT INTO schema_migrations VALUES (%s)", (path.name,))

def setup(app):
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc):
        return JSONResponse(status_code=exc.status_code, content={"code": str(exc.status_code),
            "message": str(exc.detail), "correlationId": request.headers.get("x-correlation-id", str(uuid4()))})

    @app.exception_handler(psycopg.errors.UniqueViolation)
    async def duplicate(request: Request, exc):
        return JSONResponse(status_code=409, content={"code": "conflict", "message": "Record already exists"})

    @app.get("/up")
    def health():
        if os.getenv("DATABASE_URL"):
            with db() as connection:
                connection.execute("SELECT 1")
        return {"status": "ok"}
