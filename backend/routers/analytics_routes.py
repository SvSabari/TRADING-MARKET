"""Option-chain analytics endpoints (live Kite when connected, synthetic fallback)."""
from fastapi import APIRouter, Depends

from auth import get_current_user
from db import db
from models import User
from services.options_analytics import (
    build_option_chain, iv_smile, max_pain, oi_heatmap, pcr,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/option-chain")
async def option_chain(symbol: str = "NIFTY", user: User = Depends(get_current_user)):
    chain = await build_option_chain(db, user.id, symbol)
    return {
        "spot": chain["spot"],
        "atm": chain["atm"],
        "rows": chain["rows"],
        "pcr": pcr(chain),
        "max_pain": max_pain(chain),
        "source": chain.get("source", "synthetic"),
        "expiry": chain.get("expiry", ""),
    }


@router.get("/greeks/{strike}")
async def strike_greeks(strike: int, symbol: str = "NIFTY", user: User = Depends(get_current_user)):
    chain = await build_option_chain(db, user.id, symbol)
    for r in chain["rows"]:
        if int(r["strike"]) == int(strike):
            return {
                "strike": strike, "spot": chain["spot"],
                "ce": {
                    "iv": r.get("ce_iv"), "ltp": r.get("ce_ltp"),
                    "greeks": r.get("ce_greeks"),
                },
                "pe": {
                    "iv": r.get("pe_iv"), "ltp": r.get("pe_ltp"),
                    "greeks": r.get("pe_greeks"),
                },
            }
    return {"error": "strike not found"}


@router.get("/oi-heatmap")
async def oi_heatmap_endpoint(symbol: str = "NIFTY", user: User = Depends(get_current_user)):
    chain = await build_option_chain(db, user.id, symbol)
    return {"spot": chain["spot"], "atm": chain["atm"], "data": oi_heatmap(chain), "source": chain.get("source", "synthetic")}


@router.get("/iv-smile")
async def iv_smile_endpoint(symbol: str = "NIFTY", user: User = Depends(get_current_user)):
    chain = await build_option_chain(db, user.id, symbol)
    return {"spot": chain["spot"], "atm": chain["atm"], "data": iv_smile(chain), "source": chain.get("source", "synthetic")}
