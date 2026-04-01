from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import status, market, rejections, trades, iv_history, settings

app = FastAPI(title="Auto-Trader Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(status.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(rejections.router, prefix="/api")
app.include_router(trades.router, prefix="/api")
app.include_router(iv_history.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
