import pandas as pd
from datetime import datetime, timezone
import traceback
import os

_NFO_DF = None
_BFO_DF = None

async def build_aliceblue_chain(alice, symbol: str = "NIFTY", expiry: str = None) -> dict | None:
    global _NFO_DF, _BFO_DF
    from services.market_data import tick_engine
    from services.live_feed_manager import live_feed_manager
    from services.options_analytics import INDEX_CONFIG
    from services.poi_snapshot import initialize_poi_from_first_ticks
    import asyncio
    try:
        if _NFO_DF is None:
            csv_path = os.path.join(os.path.dirname(__file__), "NFO.csv")
            _NFO_DF = pd.read_csv(csv_path, low_memory=False)
            _NFO_DF["Strike"] = pd.to_numeric(_NFO_DF["Strike Price"], errors="coerce")
            _NFO_DF["ExpiryDate"] = pd.to_datetime(_NFO_DF["Expiry Date"]).dt.date
            
        if _BFO_DF is None:
            csv_path = os.path.join(os.path.dirname(__file__), "BFO.csv")
            if os.path.exists(csv_path):
                _BFO_DF = pd.read_csv(csv_path, low_memory=False)
                _BFO_DF["Strike"] = pd.to_numeric(_BFO_DF["Strike Price"], errors="coerce")
                _BFO_DF["ExpiryDate"] = pd.to_datetime(_BFO_DF["Expiry Date"]).dt.date
            else:
                _BFO_DF = pd.DataFrame(columns=["Symbol", "Instrument Type", "Token", "Strike", "Option Type", "ExpiryDate", "Expiry Date"])

        if symbol in ["SENSEX", "BANKEX"]:
            df_source = _BFO_DF
            segment_prefix = "BFO|"
        else:
            df_source = _NFO_DF
            segment_prefix = "NFO|"
            
        df = df_source[df_source["Symbol"] == symbol].copy()
        df = df[df["Instrument Type"].isin(["OPTIDX", "OPTSTK", "IO", "SO"])]
        if df.empty:
            with open("alice_debug.txt", "w") as f: f.write("Aliceblue chain returning None: df empty after Instrument Type filter\n")
            return None
        
        today_date = datetime.now(timezone.utc).date()
        df = df[df["ExpiryDate"] >= today_date]
        if df.empty:
            with open("alice_debug.txt", "w") as f: f.write("Aliceblue chain returning None: df empty after Expiry filter\n")
            return None
        
        available_expiries = sorted(df["ExpiryDate"].unique())
        
        target_expiry = None
        if expiry:
            target_expiry = datetime.strptime(expiry, "%Y-%m-%d").date()
        
        if target_expiry and target_expiry in available_expiries:
            df = df[df["ExpiryDate"] == target_expiry]
            expiry_val = target_expiry
        else:
            nearest_expiry = available_expiries[0]
            df = df[df["ExpiryDate"] == nearest_expiry]
            expiry_val = nearest_expiry
            
        expiry_str = expiry_val.strftime("%Y-%m-%d")
        
        lot_size = int(df.iloc[0]["Lot Size"]) if "Lot Size" in df.columns else 1
            
        unique_strikes = sorted(df["Strike"].unique())
        
        # fallback step computation
        if len(unique_strikes) > 1:
            diffs = pd.Series(unique_strikes).diff().dropna()
            step = float(diffs.mode()[0])
        else:
            step = 50.0

        spot = tick_engine.prices.get(symbol, 0.0)
        if not spot:
            token_str = ""
            if symbol == "SENSEX": token_str = "BSE|1"
            elif symbol == "NIFTY": token_str = "NSE|26000"
            elif symbol == "BANKNIFTY": token_str = "NSE|26009"
            elif symbol == "FINNIFTY": token_str = "NSE|26037"
            
            if token_str:
                try:
                    res = alice.ltp(token_str)
                    if res and hasattr(res, 'get') and 'LTP' in res:
                        spot = float(res['LTP'])
                        tick_engine.prices[symbol] = spot
                    elif isinstance(res, (int, float)):
                        spot = float(res)
                        tick_engine.prices[symbol] = spot
                except Exception:
                    pass
                    
        # If Alice Blue rate limited the ltp call, spot might still be 0.
        # Fallback to the seed price so we can at least build the real strikes!
        if not spot:
            spot = tick_engine.prices.get(symbol)

        if not spot:
            with open("alice_debug.txt", "w") as f: f.write(f"Aliceblue chain returning None: spot is {spot}\n")
            return None
            
        atm = round(spot / step) * step
        
        # Select +-15 strikes (approx 31 rows)
        if atm in unique_strikes:
            atm_idx = unique_strikes.index(atm)
        else:
            # Find closest strike
            atm_idx = min(range(len(unique_strikes)), key=lambda i: abs(unique_strikes[i] - atm))
            
        start_index = max(0, atm_idx - 15)
        end_index = start_index + 31
        strikes = unique_strikes[start_index:end_index]
        
        rows = []
        tokens_to_subscribe = []
        
        def get_trend(coi, cltp):
            if coi > 0 and cltp > 0: return "Long Buildup"
            if coi > 0 and cltp < 0: return "Short Buildup"
            if coi < 0 and cltp < 0: return "Long Unwinding"
            if coi < 0 and cltp > 0: return "Short Covering"
            if cltp > 0: return "Bullish"
            if cltp < 0: return "Bearish"
            return "Neutral"

        # 1. Collect all required tokens
        for k in strikes:
            ce_row = df[(df["Strike"] == k) & (df["Option Type"] == "CE")]
            pe_row = df[(df["Strike"] == k) & (df["Option Type"] == "PE")]
            if not ce_row.empty:
                tokens_to_subscribe.append(segment_prefix + str(int(ce_row.iloc[0]["Token"])))
            if not pe_row.empty:
                tokens_to_subscribe.append(segment_prefix + str(int(pe_row.iloc[0]["Token"])))

        # 2. Check if this is a fresh subscription requiring a tiny delay to wait for AliceBlue ticks
        needs_wait = False
        if tokens_to_subscribe:
            needs_wait = any(t not in tick_engine.prices for t in tokens_to_subscribe)
            
        # 3. Actually send the subscription to the broker
        await live_feed_manager.add_symbols(tokens_to_subscribe)
        
        # 4. If new, wait 1.5 seconds to let the live WebSocket stream populate the tick engine
        if needs_wait:
            await asyncio.sleep(1.5)
            # After new tokens arrive, seed any missing POI from these first ticks
            await initialize_poi_from_first_ticks()
        
        # Subscribe to the spot token as well so we get live spot price updates!
        token_str = ""
        if symbol == "SENSEX": token_str = "BSE|1"
        elif symbol == "NIFTY": token_str = "NSE|26000"
        elif symbol == "BANKNIFTY": token_str = "NSE|26009"
        elif symbol == "FINNIFTY": token_str = "NSE|26037"
        if token_str:
            if live_feed_manager._active:
                live_feed_manager._active.symbol_map[token_str] = symbol
                live_feed_manager._active.symbol_map[token_str.split('|')[1]] = symbol
            await live_feed_manager.add_symbols([token_str])

        # 5. Build the final response rows using the fresh tick engine data
        for k in strikes:
            ce_row = df[(df["Strike"] == k) & (df["Option Type"] == "CE")]
            pe_row = df[(df["Strike"] == k) & (df["Option Type"] == "PE")]

            if ce_row.empty and pe_row.empty:
                continue

            ce_ltp, pe_ltp, ce_oi, pe_oi = 0.0, 0.0, 0, 0
            ce_change_oi, pe_change_oi = 0, 0
            ce_change_ltp, pe_change_ltp = 0.0, 0.0

            if not ce_row.empty:
                ce_token = segment_prefix + str(int(ce_row.iloc[0]["Token"]))
                if ce_token in tick_engine.prices:
                    ce_ltp = tick_engine.prices[ce_token]
                ce_oi = tick_engine.oi_cache.get(ce_token, 0) // lot_size
                ce_poi = tick_engine.poi_cache.get(ce_token, 0) // lot_size
                # Show change vs POI; if POI not available yet show 0 (not raw OI)
                ce_change_oi = ce_oi - ce_poi if (ce_poi and ce_poi != ce_oi) else 0
                ce_change_ltp = tick_engine.change_pcts.get(ce_token, 0.0)

            if not pe_row.empty:
                pe_token = segment_prefix + str(int(pe_row.iloc[0]["Token"]))
                if pe_token in tick_engine.prices:
                    pe_ltp = tick_engine.prices[pe_token]
                pe_oi = tick_engine.oi_cache.get(pe_token, 0) // lot_size
                pe_poi = tick_engine.poi_cache.get(pe_token, 0) // lot_size
                # Show change vs POI; if POI not available yet show 0
                pe_change_oi = pe_oi - pe_poi if (pe_poi and pe_poi != pe_oi) else 0
                pe_change_ltp = tick_engine.change_pcts.get(pe_token, 0.0)

            rows.append({
                "strike": k,
                "ce_oi": ce_oi, "ce_iv": 0.0, "ce_ltp": ce_ltp, "ce_change_ltp": ce_change_ltp, "ce_change_oi": ce_change_oi,
                "ce_trend": get_trend(ce_change_oi, ce_change_ltp),
                "pe_oi": pe_oi, "pe_iv": 0.0, "pe_ltp": pe_ltp, "pe_change_ltp": pe_change_ltp, "pe_change_oi": pe_change_oi,
                "pe_trend": get_trend(pe_change_oi, pe_change_ltp),
            })
            
        return {
            "spot": spot, 
            "atm": atm, 
            "rows": rows, 
            "source": "aliceblue", 
            "expiry": expiry_str,
            "available_expiries": [d.strftime("%Y-%m-%d") for d in available_expiries]
        }
    except Exception as e:
        with open("alice_debug.txt", "w") as f:
            f.write(f"Aliceblue option chain error: {e}\n")
            f.write(traceback.format_exc())
        print(f"Aliceblue option chain error: {e}")
        traceback.print_exc()
        return None
