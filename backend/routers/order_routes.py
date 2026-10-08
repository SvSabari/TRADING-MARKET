"""Orders, positions, trade book, P&L."""
from datetime import datetime, timezone
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from auth import get_current_user
from db import get_db
from models import Notification, Order, Position, User, BrokerConnection
from schemas import OrderCreate
from services.broker_router import get_broker
from services.market_data import tick_engine

router = APIRouter(prefix="/orders", tags=["orders"])


async def _upsert_position(session: AsyncSession, user_id: str, order: Order):
    stmt = select(Position).where(
        Position.user_id == user_id, 
        Position.symbol == order.symbol,
        Position.is_mock == order.is_mock
    )
    result = await session.execute(stmt)
    pos = result.scalar_one_or_none()
    
    sign = 1 if order.side.upper() == "BUY" else -1
    delta_qty = sign * order.qty
    
    if pos:
        new_qty = pos.qty + delta_qty
        if new_qty == 0:
            await session.delete(pos)
            await session.commit()
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
        await session.commit()
    else:
        if delta_qty == 0:
            return
        pos = Position(
            id=str(uuid.uuid4()),
            user_id=user_id, 
            symbol=order.symbol, 
            qty=delta_qty,
            avg_price=order.price, 
            last_price=order.price,
            updated_at=datetime.now(timezone.utc),
            is_mock=order.is_mock
        )
        session.add(pos)
        await session.commit()


@router.post("")
async def place_order(body: OrderCreate, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    from services.broker_router import route_order
    
    actual_broker = body.broker
    if not body.force_mock:
        stmt = select(BrokerConnection).where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.is_order_exec == True,
            BrokerConnection.connected == True
        )
        result = await session.execute(stmt)
        exec_broker_doc = result.scalar_one_or_none()
        
        if not exec_broker_doc:
            raise HTTPException(status_code=400, detail="NO_EXECUTION_BROKER")
        actual_broker = exec_broker_doc.broker
    else:
        actual_broker = "mock"

    fill = await route_order(
        session, user.id, actual_broker,
        symbol=body.symbol, side=body.side, qty=body.qty, price=body.price,
        order_type=body.order_type, product=body.product,
    )
    order = Order(
        id=str(uuid.uuid4()),
        user_id=user.id,
        broker=actual_broker,
        broker_order_id=fill.get("broker_order_id"),
        symbol=body.symbol.upper(),
        side=body.side.upper(),
        qty=body.qty,
        price=fill.get("fill_price", body.price),
        order_type=body.order_type,
        product=body.product,
        status=fill["status"],
        source="manual",
        placed_at=datetime.now(timezone.utc),
        filled_at=datetime.now(timezone.utc) if fill["status"] == "FILLED" else None,
        target=body.target,
        stop_loss=body.stop_loss,
        is_bracket=body.target is not None or body.stop_loss is not None,
        reject_reason=fill.get("reject_reason", ""),
        is_mock=actual_broker == "mock"
    )
    session.add(order)
    await session.commit()
    if order.status == "FILLED":
        await _upsert_position(session, user.id, order)
    
    notif = Notification(
        id=str(uuid.uuid4()),
        user_id=user.id, 
        kind="order",
        title=f"Order filled: {order.side} {order.symbol}",
        message=f"{order.qty} @ ₹{order.price} via {order.broker} ({fill.get('mode', 'mock')})",
        severity="success",
        created_at=datetime.now(timezone.utc)
    )
    session.add(notif)
    await session.commit()
    
    from services.telegram import send_for_user
    await send_for_user(
        session, user.id,
        f"*🟢 Order filled* — `{order.side}` {order.symbol} × {order.qty} @ ₹{order.price}\n_via {order.broker} ({fill.get('mode','mock')})_",
    )
    from services.push_fcm import send_for_user as push_for_user
    await push_for_user(
        session, user.id,
        f"Order filled · {order.side} {order.symbol}",
        f"× {order.qty} @ ₹{order.price} via {order.broker}",
        data={"kind": "order", "order_id": order.id},
    )
    
    # Mirror order to all eligible managed users (fire-and-forget)
    if body.copy_to_users:
        import asyncio
        from services.managed_order_engine import mirror_order_to_managed_users
        asyncio.create_task(mirror_order_to_managed_users(session, user.id, order))
    
    # Return as dict to avoid validation errors if model mapping is imprecise
    return {
        "id": order.id, "user_id": order.user_id, "broker": order.broker,
        "symbol": order.symbol, "side": order.side, "qty": order.qty,
        "price": order.price, "order_type": order.order_type, "product": order.product,
        "status": order.status, "source": order.source, "target": order.target,
        "stop_loss": order.stop_loss, "is_bracket": order.is_bracket,
    }


@router.get("")
async def list_orders(limit: int = 100, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Order).where(Order.user_id == user.id).order_by(Order.placed_at.desc()).limit(limit)
    result = await session.execute(stmt)
    orders = result.scalars().all()
    
    out = []
    for order in orders:
        out.append({
            "id": order.id, "user_id": order.user_id, "broker": order.broker,
            "symbol": order.symbol, "side": order.side, "qty": order.qty,
            "price": order.price, "order_type": order.order_type, "product": order.product,
            "status": order.status, "source": order.source, "target": order.target,
            "stop_loss": order.stop_loss, "is_bracket": order.is_bracket,
            "placed_at": order.placed_at.isoformat() + "Z" if order.placed_at else None, 
            "reject_reason": order.reject_reason,
            "is_mock": order.broker == "mock" or (order.broker_order_id and order.broker_order_id.startswith("MOC")),
            "broker_order_id": order.broker_order_id
        })
    return {"orders": out}


@router.get("/positions")
async def list_positions(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Position).where(Position.user_id == user.id, Position.is_mock == False)
    result = await session.execute(stmt)
    positions = result.scalars().all()
    
    out = []
    total_pnl = 0.0
    for pos in positions:
        ltp = tick_engine.prices.get(pos.symbol, pos.avg_price)
        pos.last_price = round(ltp, 2)
        pnl = round((ltp - pos.avg_price) * pos.qty, 2)
        
        out.append({
            "id": pos.id, "user_id": pos.user_id, "symbol": pos.symbol,
            "qty": pos.qty, "avg_price": pos.avg_price, "last_price": pos.last_price,
            "pnl": pnl, "updated_at": pos.updated_at
        })
        total_pnl += pnl
    return {"positions": out, "total_pnl": round(total_pnl, 2)}


@router.get("/pnl-summary")
async def pnl_summary(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    stmt = select(Position).where(Position.user_id == user.id, Position.is_mock == False)
    result = await session.execute(stmt)
    positions = result.scalars().all()
    
    realized = 0.0
    unrealized = 0.0
    
    for pos in positions:
        ltp = tick_engine.prices.get(pos.symbol, pos.avg_price)
        unrealized += (ltp - pos.avg_price) * pos.qty
        
    stmt_count = select(func.count(Order.id)).where(Order.user_id == user.id, Order.is_mock == False)
    result_count = await session.execute(stmt_count)
    trades = result_count.scalar_one()
    
    return {
        "unrealized_pnl": round(unrealized, 2),
        "realized_pnl": round(realized, 2),
        "total_pnl": round(unrealized + realized, 2),
        "trades": trades,
    }
