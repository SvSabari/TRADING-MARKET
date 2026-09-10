import asyncio
from typing import List, Dict

async def get_premium_matches_for_symbols(db, user_id: str, symbols: List[str], range_size: int = 10, max_diff: float = 5.0):
    from routers.analytics_routes import get_cached_or_build
    from services.market_data import tick_engine
    from services.live_feed_manager import live_feed_manager
    
    tasks = []
    for sym in symbols:
        tasks.append(get_cached_or_build(sym, user_id))
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_matches = []
    tokens_to_subscribe = []
    
    for idx, chain in enumerate(results):
        if isinstance(chain, Exception) or chain is None:
            continue
            
        rows = chain.get('rows', [])
        symbol = symbols[idx]
        
        # Spot fallback logic
        spot = tick_engine.prices.get(symbol, 0)
        if spot == 0:
            spot = chain.get("spot", 0)
            if spot == 0:
                spot = chain.get("atm", 0)
        
        if not rows or spot == 0:
            continue
            
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
        
        # Subscribe to required tokens to ensure tick_engine receives them
        for i in range(low, high + 1):
            ce_tok = sorted_rows[i].get('ce_token')
            if ce_tok: tokens_to_subscribe.append(ce_tok)
            pe_tok = sorted_rows[i].get('pe_token')
            if pe_tok: tokens_to_subscribe.append(pe_tok)
        
        for i in range(low, high + 1):
            call_row = sorted_rows[i]
            for j in range(low, high + 1):
                put_row = sorted_rows[j]
                
                # Fetch live prices using real broker tokens
                ce_tok = call_row.get('ce_token', '')
                pe_tok = put_row.get('pe_token', '')
                
                ce_ltp = tick_engine.prices.get(ce_tok, 0.0)
                pe_ltp = tick_engine.prices.get(pe_tok, 0.0)
                
                # Fallback to cached close prices if off-hours
                if ce_ltp == 0.0: ce_ltp = call_row.get('ce_ltp', 0)
                if pe_ltp == 0.0: pe_ltp = put_row.get('pe_ltp', 0)
                
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
                        
    # Run subscription in background so we don't block
    if tokens_to_subscribe and live_feed_manager._active:
        asyncio.create_task(live_feed_manager.add_symbols(list(set(tokens_to_subscribe))))
        
    all_matches.sort(key=lambda x: x['diff'])
    return all_matches
