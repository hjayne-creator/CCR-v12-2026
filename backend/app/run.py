"""uvicorn entry: python -m app.run"""
from __future__ import annotations

import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    # Reload for local dev; disable on Railway / when UVICORN_RELOAD=0
    on_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT"))
    reload = os.environ.get("UVICORN_RELOAD", "0" if on_railway else "1") == "1"
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    main()
