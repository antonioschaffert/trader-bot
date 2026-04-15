import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from api.routes import status as status_route, market, rejections, trades, iv_history, settings
from api.routes import regime, analytics, wheel, accounts, balance

app = FastAPI(title="Auto-Trader Dashboard API")

_raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
origins = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Basic auth -- set API_USERNAME and API_PASSWORD env vars to enable
_auth_user = os.environ.get("API_USERNAME", "")
_auth_pass = os.environ.get("API_PASSWORD", "")
security = HTTPBasic(auto_error=False)


async def check_auth(credentials: HTTPBasicCredentials | None = Depends(security)):
    if not _auth_user:
        return  # auth disabled when no username set
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})
    user_ok = secrets.compare_digest(credentials.username.encode(), _auth_user.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), _auth_pass.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})


app.include_router(status_route.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(market.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(rejections.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(trades.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(iv_history.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(settings.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(regime.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(analytics.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(wheel.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(accounts.router, prefix="/api", dependencies=[Depends(check_auth)])
app.include_router(balance.router, prefix="/api", dependencies=[Depends(check_auth)])
