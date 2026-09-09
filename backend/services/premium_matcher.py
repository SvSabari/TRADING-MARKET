import asyncio
from typing import List, Dict

_CHAIN_CACHE = {}

async def get_premium_matches_for_symbols(db, user_id: str, symbols: List[str], range_size: int = 10, max_diff: float = 5.0):
    from routers.analytics_routes import get_cached_or_build
    from services.market_data import tick_engine
    import time
    
    global _CHAIN_CACHE
    
    all_matches = []
    
    for symbol in symbols:
        # Get chain structure from cache or build it once
        if symbol not in _CHAIN_CACHE:
            chain = await get_cached_or_build(symbol, user_id)
            if isinstance(chain, Exception) or chain is None:
                continue
            # Keep a lightweight copy
            _CHAIN_CACHE[symbol] = {
                "rows": chain.get("rows", []),
                "atm": chain.get("atm")
            }
            
        cached_chain = _CHAIN_CACHE[symbol]
        rows = cached_chain["rows"]
        # Update spot from tick_engine to re-calculate ATM if needed, but for speed we just use the cached ATM or spot
        spot = tick_engine.prices.get(symbol, 0)
        
        if not rows or spot == 0:
            continue
            
        # Re-calculate ATM based on live spot
        closest_strike = min(rows, key=lambda r: abs(r['strike'] - spot))['strike']
        atm = closest_strike
            
        sorted_rows = sorted(rows, key=lambda r: r['strike'])
        
        atm_index = -1
        min_d = float('inf')
        for i, r in enumerate(sorted_rows):
            d = abs(r['strike'] - atm)
            if d < min_d:
                min_d = d
                atm_index = i
                
        if atm_index == -1:
            continue
            
        low = max(0, atm_index - range_size)
        high = min(len(sorted_rows) - 1, atm_index + range_size)
        
        for i in range(low, high + 1):
            call_row = sorted_rows[i]
            for j in range(low, high + 1):
                put_row = sorted_rows[j]
                
                # Fetch live prices instantly from tick_engine
                ce_sym = f"{symbol}_{call_row['strike']}_CE"
                pe_sym = f"{symbol}_{put_row['strike']}_PE"
                
                ce_ltp = tick_engine.prices.get(ce_sym, 0.0)
                pe_ltp = tick_engine.prices.get(pe_sym, 0.0)
                
                if ce_ltp > 0 and pe_ltp > 0:
                    diff = abs(ce_ltp - pe_ltp)
                    if diff <= max_diff:
                        all_matches.append({
                            "symbol": symbol,
                            "spot": spot,
                            "callStrike": call_row['strike'],
                            "callLtp": ce_ltp,
                            "putStrike": put_row['strike'],
                            "putLtp": pe_ltp,
                            "diff": round(diff, 2)
                        })
                        
    # Sort all matches globally by diff
    all_matches.sort(key=lambda x: x['diff'])
    return all_matches