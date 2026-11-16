from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    phone = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship("Order", backref="customer", foreign_keys="Order.customer_id", lazy=True)
    deliveries = db.relationship("Order", backref="courier", foreign_keys="Order.courier_id", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class DeliverySlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    area = db.Column(db.String(100), nullable=False, default="Guntur")
    capacity = db.Column(db.Integer, nullable=False, default=8)
    is_active = db.Column(db.Boolean, default=True)

    bookings = db.relationship("Order", backref="slot", lazy=True)

    @property
    def booked_count(self):
        return Order.query.filter_by(slot_id=self.id).filter(
            Order.status.notin_(["cancelled"])
        ).count()

    @property
    def remaining(self):
        return max(0, self.capacity - self.booked_count)

    @property
    def label(self):
        return f"{self.start_time} – {self.end_time}"

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tracking_code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    item_name = db.Column(db.String(160), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    courier_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    slot_id = db.Column(db.Integer, db.ForeignKey("delivery_slot.id"))
    address = db.Column(db.String(250), nullable=False)
    area = db.Column(db.String(100), nullable=False, default="Guntur")
    pincode = db.Column(db.String(10), nullable=False, default="522001")
    status = db.Column(db.String(30), nullable=False, default="ready_to_schedule")
    preferred_note = db.Column(db.String(250))
    provider = db.Column(db.String(30), default="Demo")
    provider_waybill = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class StatusEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    status = db.Column(db.String(40), nullable=False)
    note = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.relationship("Order", backref=db.backref("events", lazy=True, order_by="StatusEvent.created_at.desc()"))
