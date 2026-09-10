"""Option-chain analytics endpoints (live Kite when connected, synthetic fallback)."""
from fastapi import APIRouter, Depends

from auth import get_current_user
from db import db
from models import User
from services.options_analytics import (
    build_option_chain, iv_smile, max_pain, oi_heatmap, pcr,
)
from services.options_sweeper import options_sweeper

async def get_cached_or_build(symbol: str, user_id: str, expiry: str = None):
    from datetime import datetime, timezone
    from services.live_feed_manager import live_feed_manager
    
    cache_key = f"{symbol}_{expiry}" if expiry else symbol
    
    # Use extreme TTL for AliceBlue since we will manually update prices via tokens
    active_name = getattr(live_feed_manager._active, "name", "") if live_feed_manager._active else ""
    cache_ttl = 86400 if active_name == "aliceblue" else (60 if active_name == "breeze" else 5)

    if cache_key in options_sweeper.cache:
        now = datetime.now(timezone.utc).timestamp()
        if now - options_sweeper.last_update.get(cache_key, 0) < cache_ttl:
            chain = options_sweeper.cache[cache_key]
            # Inject live prices from tick_engine before returning so Option Chain UI is live
            from services.market_data import tick_engine
            if chain and chain.get("rows"):
                # Also update spot price
                live_spot = tick_engine.prices.get(symbol, 0)
                if live_spot > 0:
                    chain["spot"] = live_spot
                for row in chain["rows"]:
                    ce_tok = row.get("ce_token", "")
                    pe_tok = row.get("pe_token", "")
                    if ce_tok and ce_tok in tick_engine.prices:
                        row["ce_ltp"] = tick_engine.prices[ce_tok]
                        row["ce_oi"] = tick_engine.oi_cache.get(ce_tok, row.get("ce_oi", 0))
                        row["ce_change_ltp"] = tick_engine.change_pcts.get(ce_tok, row.get("ce_change_ltp", 0.0))
                    if pe_tok and pe_tok in tick_engine.prices:
                        row["pe_ltp"] = tick_engine.prices[pe_tok]
                        row["pe_oi"] = tick_engine.oi_cache.get(pe_tok, row.get("pe_oi", 0))
                        row["pe_change_ltp"] = tick_engine.change_pcts.get(pe_tok, row.get("pe_change_ltp", 0.0))
            return chain

    chain = await build_option_chain(db, user_id, symbol, expiry)
    if chain and chain.get("rows") and len(chain["rows"]) > 0:
        options_sweeper.cache[cache_key] = chain
        options_sweeper.last_update[cache_key] = datetime.now(timezone.utc).timestamp()
        return chain
        
    # If fetch failed (e.g. rate limit), fallback to stale cache if available
    if cache_key in options_sweeper.cache:
        return options_sweeper.cache[cache_key]
        
    return chain


router = APIRouter(prefix="/analytics", tags=["analytics"])



@router.get("/premium-matcher")
async def premium_matcher_api(preset: str = "indices", range_size: int = 10, max_diff: float = 5.0, tracked: str = "", user: User = Depends(get_current_user)):
    from services.premium_matcher import get_premium_matches_for_symbols
    from routers.market_routes import NIFTY_50
    from services.market_data import tick_engine
    
    symbols = []
    INDICES = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYNXT50"]
    
    if preset == "indices":
        symbols = INDICES
    elif preset == "all":
        symbols = INDICES + NIFTY_50
    else:
        symbols = [preset]
        
    matches = await get_premium_matches_for_symbols(db, user.id, symbols, range_size, max_diff)
    
    tracked_prices = {}
    if tracked:
        for t in tracked.split(','):
            t = t.strip()
            if t:
                tracked_prices[t] = tick_engine.prices.get(t, 0.0)
                
    return {"matches": matches, "tracked_prices": tracked_prices}

@router.get("/option-chain")

async def option_chain(symbol: str = "NIFTY", expiry: str = None, user: User = Depends(get_current_user)):
    chain = await get_cached_or_build(symbol, user.id, expiry)
    return {
        "spot": chain["spot"],
        "atm": chain["atm"],
        "rows": chain["rows"],
        "pcr": pcr(chain),
        "max_pain": max_pain(chain),
        "source": chain.get("source", "offline"),
        "expiry": chain.get("expiry", ""),
        "available_expiries": chain.get("available_expiries", []),
    }


@router.get("/greeks/{strike}")
async def strike_greeks(strike: int, symbol: str = "NIFTY", user: User = Depends(get_current_user)):
    chain = await get_cached_or_build(symbol, user.id)
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
async def oi_heatmap_endpoint(symbol: str = "NIFTY", expiry: str = None, user: User = Depends(get_current_user)):
    chain = await get_cached_or_build(symbol, user.id, expiry)
    return {"spot": chain["spot"], "atm": chain["atm"], "data": oi_heatmap(chain), "source": chain.get("source", "offline"), "expiry": chain.get("expiry")}


@router.get("/iv-smile")
async def iv_smile_endpoint(symbol: str = "NIFTY", user: User = Depends(get_current_user)):
    chain = await get_cached_or_build(symbol, user.id)
    return {"spot": chain["spot"], "atm": chain["atm"], "data": iv_smile(chain), "source": chain.get("source", "offline")}
