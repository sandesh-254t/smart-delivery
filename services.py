from datetime import date, timedelta
from sqlalchemy import func
from extensions import db
from models import DeliverySlot, Order

STATUSES = {
    "ready_to_schedule": "Ready to schedule",
    "scheduled": "Scheduled",
    "picked_up": "Picked up",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "failed": "Delivery failed",
    "cancelled": "Cancelled",
}

def create_default_slots(days=7, area="Guntur"):
    today = date.today()
    windows = [("09:00", "11:00"), ("11:00", "13:00"), ("14:00", "16:00"), ("16:00", "18:00")]
    created = 0
    for offset in range(days):
        day = today + timedelta(days=offset)
        for start, end in windows:
            exists = DeliverySlot.query.filter_by(date=day, start_time=start, area=area).first()
            if not exists:
                db.session.add(DeliverySlot(date=day, start_time=start, end_time=end, area=area, capacity=8))
                created += 1
    db.session.commit()
    return created

def add_event(order, status, note=None):
    from models import StatusEvent
    db.session.add(StatusEvent(order_id=order.id, status=status, note=note or STATUSES.get(status, status)))
    order.status = status
    db.session.commit()

def group_deliveries_by_area():
    rows = db.session.query(
        Order.area, func.count(Order.id)
    ).filter(Order.status.in_(["scheduled", "picked_up", "out_for_delivery"])).group_by(Order.area).all()
    return [{"area": area, "count": count} for area, count in rows]
