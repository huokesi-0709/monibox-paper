"""FastAPI application entrypoint for MoniBox."""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, protocol, rag, status


def create_app() -> FastAPI:
    app = FastAPI(
        title="MoniBox API",
        version="0.1.0",
        description="API layer for the MoniBox React frontend.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(status.router)
    app.include_router(chat.router)
    app.include_router(rag.router)
    app.include_router(protocol.router)

    @app.get("/", tags=["meta"])
    def root() -> dict[str, str]:
        return {"name": "MoniBox API", "docs": "/docs", "health": "/api/status/health"}

    return app


app = create_app()


def main() -> None:
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=False)
