"""Premium Matcher — finds CE/PE pairs with similar premiums within a strike range.

Logic:
- For each symbol, get the ATM strike
- Scan +/- range_size strikes around ATM
- For EACH strike, compare its CE LTP vs PE LTP (same-strike comparison)
- Also compare CE of strike i vs PE of strike j (cross-strike, for strangle/straddle)
- Filter pairs where abs(ce_ltp - pe_ltp) <= max_diff
- The max_diff is treated as a PERCENTAGE of spot for index options (makes it scale-independent)
"""
import asyncio
from typing import List

async def get_premium_matches_for_symbols(db, user_id: str, symbols: List[str], range_size: int = 10, max_diff: float = 5.0):
    from routers.analytics_routes import get_cached_or_build
    from services.market_data import tick_engine
    from services.live_feed_manager import live_feed_manager
    
    tasks = [get_cached_or_build(db, sym, user_id) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_matches = []
    tokens_to_subscribe = []
    
    for idx, chain in enumerate(results):
        if isinstance(chain, Exception) or chain is None:
            continue
            
        rows = chain.get('rows', [])
        symbol = symbols[idx]
        
        # Spot: prefer live tick, fallback to chain spot
        spot = tick_engine.prices.get(symbol, 0)
        if not spot:
            spot = chain.get("spot", 0)
        if not spot:
            continue
            
        if not rows:
            continue
            
        sorted_rows = sorted(rows, key=lambda r: r['strike'])
        
        # Find ATM index
        atm_index = min(range(len(sorted_rows)), key=lambda i: abs(sorted_rows[i]['strike'] - spot))
        
        low = max(0, atm_index - range_size)
        high = min(len(sorted_rows) - 1, atm_index + range_size)
        
        # Collect tokens for subscription
        for i in range(low, high + 1):
            ce_tok = sorted_rows[i].get('ce_token')
            if ce_tok: tokens_to_subscribe.append(ce_tok)
            pe_tok = sorted_rows[i].get('pe_token')
            if pe_tok: tokens_to_subscribe.append(pe_tok)
        
        # Compare SAME-STRIKE CE vs PE (straddle premium matching)
        for i in range(low, high + 1):
            row = sorted_rows[i]
            strike = row['strike']
            
            ce_tok = row.get('ce_token', '')
            pe_tok = row.get('pe_token', '')
            
            # Live price from tick_engine, fallback to chain's cached value
            ce_ltp = tick_engine.prices.get(ce_tok, 0.0) if ce_tok else 0.0
            pe_ltp = tick_engine.prices.get(pe_tok, 0.0) if pe_tok else 0.0
            if ce_ltp == 0.0: ce_ltp = float(row.get('ce_ltp') or 0)
            if pe_ltp == 0.0: pe_ltp = float(row.get('pe_ltp') or 0)
            
            if ce_ltp > 0 and pe_ltp > 0:
                diff = abs(ce_ltp - pe_ltp)
                if diff <= max_diff:
                    all_matches.append({
                        "symbol": symbol,
                        "spot": spot,
                        "callStrike": strike,
                        "callLtp": round(ce_ltp, 2),
                        "putStrike": strike,
                        "putLtp": round(pe_ltp, 2),
                        "diff": round(diff, 2),
                        "type": "straddle"
                    })
        
        # Also compare CROSS-STRIKE CE vs PE (strangle matching — within ±3 strikes of ATM)
        cross_low = max(0, atm_index - 3)
        cross_high = min(len(sorted_rows) - 1, atm_index + 3)
        for i in range(cross_low, cross_high + 1):
            for j in range(cross_low, cross_high + 1):
                if i == j:
                    continue  # already covered in straddle loop
                call_row = sorted_rows[i]
                put_row = sorted_rows[j]
                
                ce_tok = call_row.get('ce_token', '')
                pe_tok = put_row.get('pe_token', '')
                
                ce_ltp = tick_engine.prices.get(ce_tok, 0.0) if ce_tok else 0.0
                pe_ltp = tick_engine.prices.get(pe_tok, 0.0) if pe_tok else 0.0
                if ce_ltp == 0.0: ce_ltp = float(call_row.get('ce_ltp') or 0)
                if pe_ltp == 0.0: pe_ltp = float(put_row.get('pe_ltp') or 0)
                
                if ce_ltp > 0 and pe_ltp > 0:
                    diff = abs(ce_ltp - pe_ltp)
                    if diff <= max_diff:
                        all_matches.append({
                            "symbol": symbol,
                            "spot": spot,
                            "callStrike": call_row['strike'],
                            "callLtp": round(ce_ltp, 2),
                            "putStrike": put_row['strike'],
                            "putLtp": round(pe_ltp, 2),
                            "diff": round(diff, 2),
                            "type": "strangle"
                        })

    # Subscribe tokens in background
    if tokens_to_subscribe and live_feed_manager._active:
        asyncio.create_task(live_feed_manager.add_symbols(list(set(tokens_to_subscribe))))
        
    all_matches.sort(key=lambda x: x['diff'])
    return all_matches
