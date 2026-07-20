from fastapi import FastAPI

from darwin.api.routes import health, markets, metrics, orders, positions


def create_app() -> FastAPI:
    app = FastAPI(title="Darwin", version="0.1.0")
    app.include_router(health.router)
    app.include_router(markets.router)
    app.include_router(orders.router)
    app.include_router(positions.router)
    app.include_router(metrics.router)
    return app
