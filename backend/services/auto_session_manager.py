"""Automatic Broker Daily Session Renewal Service.

Handles daily automatic token generation for brokers like Alice Blue and Angel One
before market opens (08:30 AM IST), completely eliminating the need for manual
daily logins or OTP typing.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from db import AsyncSessionLocal
from models import BrokerConnection, ManagedUser
from services.crypto import decrypt_str, encrypt_str

logger = logging.getLogger("auto-session-manager")

IST = timezone(timedelta(hours=5, minutes=30))


def get_ist_now() -> datetime:
    return datetime.now(IST)


def get_today_str() -> str:
    # Use UTC or IST date string consistent with broker_routes.py
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def generate_aliceblue_session(user_id: str, api_key: str) -> Optional[str]:
    """Generate Alice Blue A3 JWT session token using SHA-256 Checksum (Open API V1)."""
    if not user_id or not api_key:
        return None

    # Method 1: Direct Alice Blue A3 Open API (Checksum -> getUserDetails)
    try:
        checksum_raw = f"{user_id}{api_key}".encode("utf-8")
        checksum = hashlib.sha256(checksum_raw).hexdigest()
        payload = {
            "userId": user_id,
            "userData": checksum,
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(
            "https://a3.aliceblueonline.com/open-api/od/v1/users/getUserDetails",
            json=payload,
            headers=headers,
            timeout=12.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            session_id = data.get("sessionID") or data.get("userSession")
            if session_id:
                logger.info(f"[AutoSession] Alice Blue A3 session generated successfully for {user_id}")
                return str(session_id)
            else:
                logger.warning(f"[AutoSession] Alice Blue A3 response missing sessionID: {data}")
    except Exception as e:
        logger.warning(f"[AutoSession] Alice Blue direct API login failed for {user_id}: {e}")

    # Method 2: Fallback to official pya3 SDK
    try:
        from pya3 import Aliceblue
        alice = Aliceblue(user_id=user_id, api_key=api_key)
        res = alice.get_session_id()
        if isinstance(res, dict) and res.get("stat") == "Ok" and res.get("sessionID"):
            logger.info(f"[AutoSession] pya3 session generated successfully for {user_id}")
            return str(res["sessionID"])
        else:
            logger.warning(f"[AutoSession] pya3 get_session_id returned: {res}")
    except Exception as e:
        logger.warning(f"[AutoSession] pya3 SDK login failed for {user_id}: {e}")

    return None


def generate_angel_session(api_key: str, client_code: str, pin: str, totp_secret: str) -> Optional[Dict[str, str]]:
    """Generate Angel One SmartAPI session using pyotp TOTP."""
    if not (api_key and client_code and pin and totp_secret):
        return None

    try:
        from services.brokers.angel_client import AngelClient
        client = AngelClient(
            api_key=api_key,
            client_code=client_code,
            pin=pin,
            totp_secret=totp_secret,
        )
        tokens = client.login()
        if tokens and tokens.get("auth_token"):
            logger.info(f"[AutoSession] Angel One session generated successfully for {client_code}")
            return tokens
    except Exception as e:
        logger.warning(f"[AutoSession] Angel One login failed for {client_code}: {e}")

    return None


async def renew_all_sessions(force: bool = False) -> Dict[str, Any]:
    """Renew sessions for all configured broker connections and managed users."""
    today = get_today_str()
    results: List[Dict[str, Any]] = []
    feed_reconnect_needed = False

    async with AsyncSessionLocal() as session:
        # 1. Main Trader Broker Connections
        stmt = select(BrokerConnection)
        res = await session.execute(stmt)
        connections = res.scalars().all()

        for conn in connections:
            broker_name = (conn.broker or "").lower().strip()
            creds = conn.credentials or {}

            # Skip mock mode broker
            if broker_name == "mock":
                continue

            # Check if already active for today
            if not force and conn.session_date == today and conn.access_token and conn.connected:
                results.append({
                    "type": "trader",
                    "id": conn.id,
                    "broker": conn.broker,
                    "status": "already_active",
                })
                continue

            # --- Alice Blue ---
            if "alice" in broker_name:
                api_key = decrypt_str(creds.get("api_key", ""))
                user_id = decrypt_str(creds.get("user_id", "")) or decrypt_str(creds.get("client_code", ""))
                if not (api_key and user_id):
                    results.append({
                        "type": "trader",
                        "id": conn.id,
                        "broker": conn.broker,
                        "status": "skipped",
                        "reason": "missing credentials",
                    })
                    continue

                session_id = await asyncio.to_thread(generate_aliceblue_session, user_id, api_key)
                if session_id:
                    conn.access_token = encrypt_str(session_id)
                    conn.session_date = today
                    conn.mock_mode = False
                    conn.connected = True
                    if conn.is_data_feed:
                        feed_reconnect_needed = True
                    results.append({
                        "type": "trader",
                        "id": conn.id,
                        "broker": conn.broker,
                        "status": "renewed",
                    })
                else:
                    results.append({
                        "type": "trader",
                        "id": conn.id,
                        "broker": conn.broker,
                        "status": "failed",
                        "reason": "login api error",
                    })

            # --- Angel One ---
            elif "angel" in broker_name:
                api_key = decrypt_str(creds.get("api_key", ""))
                client_code = decrypt_str(creds.get("client_code", ""))
                pin = decrypt_str(creds.get("pin", ""))
                totp_secret = decrypt_str(creds.get("totp_secret", ""))
                if not (api_key and client_code and pin and totp_secret):
                    results.append({
                        "type": "trader",
                        "id": conn.id,
                        "broker": conn.broker,
                        "status": "skipped",
                        "reason": "missing credentials",
                    })
                    continue

                tokens = await asyncio.to_thread(generate_angel_session, api_key, client_code, pin, totp_secret)
                if tokens and tokens.get("auth_token"):
                    new_creds = {
                        **creds,
                        "auth_token": encrypt_str(tokens["auth_token"]),
                        "refresh_token": encrypt_str(tokens.get("refresh_token", "")),
                        "feed_token": encrypt_str(tokens.get("feed_token", "")),
                    }
                    conn.credentials = new_creds
                    conn.access_token = encrypt_str(tokens["auth_token"])
                    conn.session_date = today
                    conn.mock_mode = False
                    conn.connected = True
                    if conn.is_data_feed:
                        feed_reconnect_needed = True
                    results.append({
                        "type": "trader",
                        "id": conn.id,
                        "broker": conn.broker,
                        "status": "renewed",
                    })
                else:
                    results.append({
                        "type": "trader",
                        "id": conn.id,
                        "broker": conn.broker,
                        "status": "failed",
                        "reason": "login api error",
                    })

        await session.commit()

        # 2. Managed / Copy-Trading Users
        stmt_mu = select(ManagedUser).where(ManagedUser.is_active == True)
        res_mu = await session.execute(stmt_mu)
        managed_users = res_mu.scalars().all()

        for mu in managed_users:
            if not mu.brokers:
                continue

            brokers_list = list(mu.brokers or [])
            updated_any = False

            for idx, b_item in enumerate(brokers_list):
                b_dict = dict(b_item)
                b_broker = (b_dict.get("broker") or "").lower().strip()
                b_creds = b_dict.get("credentials") or {}

                if not force and b_dict.get("session_generated") and b_dict.get("session_date") == today and b_dict.get("session_token"):
                    continue

                # Alice Blue for Managed User
                if "alice" in b_broker:
                    user_id = b_creds.get("user_id") or b_dict.get("account_number") or ""
                    api_key = b_creds.get("api_key") or b_dict.get("api_key") or ""
                    if user_id and api_key:
                        session_id = await asyncio.to_thread(generate_aliceblue_session, user_id, api_key)
                        if session_id:
                            b_dict["session_token"] = session_id
                            b_dict["session_generated"] = True
                            b_dict["session_date"] = today
                            brokers_list[idx] = b_dict
                            updated_any = True
                            results.append({
                                "type": "managed_user",
                                "name": mu.name,
                                "broker": b_broker,
                                "status": "renewed",
                            })

                # Angel One for Managed User
                elif "angel" in b_broker:
                    client_code = b_creds.get("client_code") or b_dict.get("account_number") or ""
                    pin = b_creds.get("pin") or b_dict.get("account_password") or ""
                    totp_secret = b_creds.get("totp_secret") or b_dict.get("api_secret") or ""
                    api_key = b_creds.get("api_key") or b_dict.get("api_key") or ""
                    if client_code and pin and totp_secret and api_key:
                        tokens = await asyncio.to_thread(generate_angel_session, api_key, client_code, pin, totp_secret)
                        if tokens and tokens.get("auth_token"):
                            b_dict["session_token"] = tokens["auth_token"]
                            b_dict["session_generated"] = True
                            b_dict["session_date"] = today
                            brokers_list[idx] = b_dict
                            updated_any = True
                            results.append({
                                "type": "managed_user",
                                "name": mu.name,
                                "broker": b_broker,
                                "status": "renewed",
                            })

            if updated_any:
                mu.brokers = brokers_list
                flag_modified(mu, "brokers")

        await session.commit()

    if feed_reconnect_needed:
        try:
            from services.live_feed_manager import live_feed_manager
            await live_feed_manager.force_reconnect()
            logger.info("[AutoSession] Live feed manager reconnected with updated session tokens")
        except Exception as e:
            logger.warning(f"[AutoSession] Live feed manager reconnect failed: {e}")

    summary = {
        "date": today,
        "total_processed": len(results),
        "renewed": sum(1 for r in results if r.get("status") == "renewed"),
        "already_active": sum(1 for r in results if r.get("status") == "already_active"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "details": results,
    }
    logger.info(f"[AutoSession] Renewal run complete: {summary['renewed']} renewed, {summary['already_active']} already active, {summary['failed']} failed")
    return summary


class AutoSessionScheduler:
    """Background scheduler that executes every morning at 08:30 AM IST (Monday to Friday)."""

    def __init__(self) -> None:
        self.running: bool = False
        self._task: Optional[asyncio.Task] = None
        self.last_run_date: str = ""

    async def _loop(self) -> None:
        self.running = True
        logger.info("[AutoSession] Background auto-session scheduler started")

        # Initial startup check: If during trading day after 08:30 AM IST, run a check
        try:
            await asyncio.sleep(5)  # Wait for DB initialization
            now_ist = get_ist_now()
            today_str = get_today_str()
            # Weekdays: Monday is 0, Friday is 4
            if now_ist.weekday() < 5 and (now_ist.hour >= 8 and (now_ist.hour > 8 or now_ist.minute >= 30)) and now_ist.hour < 16:
                logger.info(f"[AutoSession] Server started during trading hours ({now_ist.strftime('%H:%M:%S')} IST). Verifying sessions...")
                await renew_all_sessions(force=False)
                self.last_run_date = today_str
        except Exception as e:
            logger.warning(f"[AutoSession] Startup check error: {e}")

        while self.running:
            try:
                now_ist = get_ist_now()
                today_str = get_today_str()

                # Run Monday to Friday (0 to 4)
                if now_ist.weekday() < 5:
                    # Target time: Between 08:30 AM and 09:10 AM IST
                    is_morning_window = (now_ist.hour == 8 and now_ist.minute >= 30) or (now_ist.hour == 9 and now_ist.minute < 10)
                    if is_morning_window and self.last_run_date != today_str:
                        logger.info(f"[AutoSession] Triggering morning auto-renewal at {now_ist.strftime('%H:%M:%S')} IST")
                        await renew_all_sessions(force=True)
                        self.last_run_date = today_str
            except Exception as e:
                logger.error(f"[AutoSession] Error in scheduler loop: {e}")

            # Sleep 30 seconds before next check
            await asyncio.sleep(30.0)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()


auto_session_scheduler = AutoSessionScheduler()
