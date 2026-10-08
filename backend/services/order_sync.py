import asyncio
import logging
from sqlalchemy import select
from db import AsyncSessionLocal
from models import Order, BrokerConnection
from services.broker_router import get_broker_profile, _LIVE_DISPATCH

logger = logging.getLogger("order-sync")

async def sync_all_orders():
    """Background task to sync order statuses from brokers."""
    while True:
        try:
            await asyncio.sleep(15)  # sync every 15 seconds
            async with AsyncSessionLocal() as session:
                # Get all pending orders (PLACED, OPEN)
                stmt = select(Order).where(Order.status.in_(["PLACED", "OPEN", "PENDING"]))
                res = await session.execute(stmt)
                pending_orders = res.scalars().all()
                
                if not pending_orders:
                    continue

                # Group by user and broker
                users_brokers = set((o.user_id, o.broker) for o in pending_orders)

                for user_id, broker in users_brokers:
                    if broker == "mock":
                        continue
                        
                    if broker == "aliceblue":
                        from services.brokers.aliceblue_client import get_user_aliceblue_client
                        client = await get_user_aliceblue_client(session, user_id)
                        if client:
                            try:
                                ob = client.get_order_book()
                                if isinstance(ob, list):
                                    ob_map = {str(o.get("Nstordno", "")): o for o in ob if "Nstordno" in o}
                                    
                                    for order in pending_orders:
                                        if order.user_id == user_id and order.broker == broker:
                                            b_id = str(order.broker_order_id)
                                            if b_id in ob_map:
                                                remote = ob_map[b_id]
                                                new_status = remote.get("Status", "").upper()
                                                if new_status in ["REJECTED", "COMPLETE", "CANCELLED", "FILLED"]:
                                                    final_status = "FILLED" if new_status == "COMPLETE" else new_status
                                                    if order.status != final_status:
                                                        order.status = final_status
                                                        if final_status == "REJECTED" or final_status == "CANCELLED":
                                                            order.reject_reason = remote.get("RejReason", "")
                                                        session.add(order)
                                                        if final_status == "FILLED":
                                                            from routers.order_routes import _upsert_position
                                                            await _upsert_position(session, user_id, order)
                            except Exception as e:
                                logger.error(f"AliceBlue order sync failed for {user_id}: {e}")
                
                await session.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Order sync loop error: {e}")
