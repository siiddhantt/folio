from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request

from .models import Update
from .store import describe, save_controls

LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def local_request(request: Request):
    if request.url.hostname not in LOOPBACK:
        raise HTTPException(403, "Development settings require a local host.")
    origin = request.headers.get("origin")
    if origin is not None:
        try:
            parsed = urlsplit(origin)
            _ = parsed.port
        except ValueError:
            raise HTTPException(403, "Development settings require a local origin.") from None
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in LOOPBACK
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise HTTPException(403, "Development settings require a local origin.")
    if request.method == "PUT" and (
        request.headers.get("x-folio-development") != "1"
        or request.headers.get("content-type", "").split(";", 1)[0] != "application/json"
    ):
        raise HTTPException(403, "Use the development console or an explicit JSON request.")


def create_router(database, settings):
    router = APIRouter(dependencies=[Depends(local_request)])

    @router.get("/development/settings")
    def read():
        return describe(database, settings)

    @router.put("/development/settings")
    def update(value: Update):
        try:
            saved = save_controls(database, settings, value)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        if not saved:
            raise HTTPException(409, "Settings changed in another tab. Reload before saving.")
        return describe(database, settings, current=saved)

    return router
