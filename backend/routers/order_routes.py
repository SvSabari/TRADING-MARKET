"""Orders, positions, trade book, P&L."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import db
from models import Notification, Order, OrderCreate, Position, User
from services.broker_router import get_broker
from services.market_data import tick_engine

router = APIRouter(prefix="/orders", tags=["orders"])


async def _upsert_position(user_id: str, order: Order):
    pos_doc = await db.positions.find_one({"user_id": user_id, "symbol": order.symbol})
    sign = 1 if order.side.upper() == "BUY" else -1
    delta_qty = sign * order.qty
    if pos_doc:
        pos = Position.from_mongo(pos_doc)
        new_qty = pos.qty + delta_qty
        if new_qty == 0:
            await db.positions.delete_one({"_id": pos.id})
            return
        # weighted avg only if adding in same direction
        if (pos.qty > 0 and delta_qty > 0) or (pos.qty < 0 and delta_qty < 0):
            total_cost = pos.avg_price * abs(pos.qty) + order.price * order.qty
            new_avg = total_cost / abs(new_qty)
        else:
            new_avg = pos.avg_price  # reducing — keep avg
        pos.qty = new_qty
        pos.avg_price = round(new_avg, 2)
        pos.last_price = order.price
        pos.updated_at = datetime.now(timezone.utc)
        await db.positions.update_one({"_id": pos.id}, {"$set": pos.to_mongo()})
    else:
        if delta_qty == 0:
            return
        pos = Position(
            user_id=user_id, symbol=order.symbol, qty=delta_qty,
            avg_price=order.price, last_price=order.price,
        )
        await db.positions.insert_one(pos.to_mongo())


@router.post("", response_model=Order, response_model_by_alias=False)
async def place_order(body: OrderCreate, user: User = Depends(get_current_user)):
    from services.broker_router import route_order
    fill = await route_order(
        db, user.id, body.broker,
        symbol=body.symbol, side=body.side, qty=body.qty, price=body.price,
        order_type=body.order_type, product=body.product,
    )
    order = Order(
        user_id=user.id,
        broker=body.broker,
        symbol=body.symbol.upper(),
        side=body.side.upper(),
        qty=body.qty,
        price=fill.get("fill_price", body.price),
        order_type=body.order_type,
        product=body.product,
        status=fill["status"],
        source="manual",
        filled_at=datetime.now(timezone.utc),
    )
    await db.orders.insert_one(order.to_mongo())
    await _upsert_position(user.id, order)
    notif = Notification(
        user_id=user.id, kind="order",
        title=f"Order filled: {order.side} {order.symbol}",
        message=f"{order.qty} @ ₹{order.price} via {order.broker} ({fill.get('mode', 'mock')})",
        severity="success",
    )
    await db.notifications.insert_one(notif.to_mongo())
    from services.telegram import send_for_user
    await send_for_user(
        db, user.id,
        f"*🟢 Order filled* — `{order.side}` {order.symbol} × {order.qty} @ ₹{order.price}\n_via {order.broker} ({fill.get('mode','mock')})_",
    )
    from services.push_fcm import send_for_user as push_for_user
    await push_for_user(
        db, user.id,
        f"Order filled · {order.side} {order.symbol}",
        f"× {order.qty} @ ₹{order.price} via {order.broker}",
        data={"kind": "order", "order_id": order.id},
    )
    return order


@router.get("")
async def list_orders(limit: int = 100, user: User = Depends(get_current_user)):
    cur = db.orders.find({"user_id": user.id}).sort("placed_at", -1).limit(limit)
    out = []
    async for d in cur:
        out.append(Order.from_mongo(d).model_dump())
    return {"orders": out}


@router.get("/positions")
async def list_positions(user: User = Depends(get_current_user)):
    cur = db.positions.find({"user_id": user.id})
    out = []
    total_pnl = 0.0
    async for d in cur:
        pos = Position.from_mongo(d)
        ltp = tick_engine.prices.get(pos.symbol, pos.avg_price)
        pos.last_price = round(ltp, 2)
        pos.pnl = round((ltp - pos.avg_price) * pos.qty, 2)
        total_pnl += pos.pnl
        out.append(pos.model_dump())
    return {"positions": out, "total_pnl": round(total_pnl, 2)}


@router.get("/pnl-summary")
async def pnl_summary(user: User = Depends(get_current_user)):
    pos_cur = db.positions.find({"user_id": user.id})
    realized = 0.0
    unrealized = 0.0
    trades = 0
    async for d in pos_cur:
        pos = Position.from_mongo(d)
        ltp = tick_engine.prices.get(pos.symbol, pos.avg_price)
        unrealized += (ltp - pos.avg_price) * pos.qty
    order_count = await db.orders.count_documents({"user_id": user.id})
    trades = order_count
    return {
        "unrealized_pnl": round(unrealized, 2),
        "realized_pnl": round(realized, 2),
        "total_pnl": round(unrealized + realized, 2),
        "trades": trades,
    }
