import asyncio
from typing import List, Dict

async def get_premium_matches_for_symbols(db, user_id: str, symbols: List[str], range_size: int = 10, max_diff: float = 5.0):
    from routers.analytics_routes import get_cached_or_build
    from services.market_data import tick_engine
    
    tasks = []
    for sym in symbols:
        tasks.append(get_cached_or_build(sym, user_id))
        
    # Gather chunks of 5 to prevent extreme event loop blocking
    results = []
    chunk_size = 5
    for i in range(0, len(tasks), chunk_size):
        chunk = await asyncio.gather(*tasks[i:i+chunk_size], return_exceptions=True)
        results.extend(chunk)
        await asyncio.sleep(0.01)
    
    all_matches = []
    
    for idx, chain in enumerate(results):
        if isinstance(chain, Exception) or chain is None:
            continue
            
        rows = chain.get('rows', [])
        atm = chain.get('atm')
        symbol = symbols[idx]
        
        spot = chain.get('spot', 0)
        
        if not rows or spot == 0 or atm is None:
            continue
            
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
                
                ce_ltp = call_row.get('ce_ltp', 0)
                pe_ltp = put_row.get('pe_ltp', 0)
                
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
