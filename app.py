from datetime import date, datetime, timedelta
from functools import wraps
import secrets
import string

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError

from config import Config
from extensions import db, login_manager
from models import User, Order, DeliverySlot, StatusEvent
from services import create_default_slots, add_event, STATUSES, group_deliveries_by_area
from delhivery import tracking_lookup, DelhiveryNotConfigured

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    def role_required(*roles):
        def decorator(fn):
            @wraps(fn)
            @login_required
            def wrapped(*args, **kwargs):
                if current_user.role not in roles:
                    abort(403)
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    @app.context_processor
    def inject_globals():
        return {"STATUSES": STATUSES, "today": date.today()}

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/favicon.ico")
    def favicon():
        return redirect(url_for("static", filename="favicon.svg"))

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "Smart Delivery"})

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            phone = request.form.get("phone", "").strip()
            if not name or not email or len(password) < 8:
                flash("Enter your name, a valid email and a password of at least 8 characters.", "error")
                return render_template("register.html")
            if User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
                return render_template("register.html")
            user = User(name=name, email=email, phone=phone, role="customer")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Account created. Welcome to Smart Delivery!", "success")
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))
            flash("Incorrect email or password.", "error")
        return render_template("login.html")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        flash("You have been signed out.", "success")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.role == "admin":
            return redirect(url_for("admin_dashboard"))
        if current_user.role == "courier":
            return redirect(url_for("courier_dashboard"))
        orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template("customer_dashboard.html", orders=orders)

    @app.route("/orders/<int:order_id>")
    @login_required
    def order_detail(order_id):
        order = db.session.get(Order, order_id) or abort(404)
        if current_user.role == "customer" and order.customer_id != current_user.id:
            abort(403)
        if current_user.role == "courier" and order.courier_id != current_user.id:
            abort(403)
        slots = DeliverySlot.query.filter_by(area=order.area, is_active=True).filter(
            DeliverySlot.date >= date.today()
        ).order_by(DeliverySlot.date, DeliverySlot.start_time).all()
        return render_template("order_detail.html", order=order, slots=slots)

    @app.route("/orders/<int:order_id>/book", methods=["POST"])
    @role_required("customer")
    def book_slot(order_id):
        order = db.session.get(Order, order_id) or abort(404)
        if order.customer_id != current_user.id:
            abort(403)
        slot = db.session.get(DeliverySlot, request.form.get("slot_id", type=int))
        if not slot or not slot.is_active or slot.date < date.today() or slot.area != order.area:
            flash("That delivery slot is not valid for this order.", "error")
            return redirect(url_for("order_detail", order_id=order.id))
        if slot.remaining <= 0:
            flash("That slot has just filled up. Please choose another.", "error")
            return redirect(url_for("order_detail", order_id=order.id))
        if order.status in ("delivered", "cancelled", "failed"):
            flash("This order can no longer be scheduled.", "error")
            return redirect(url_for("order_detail", order_id=order.id))
        order.slot_id = slot.id
        order.status = "scheduled"
        order.updated_at = datetime.utcnow()
        db.session.add(StatusEvent(order_id=order.id, status="scheduled", note=f"Customer selected {slot.date} {slot.label}"))
        db.session.commit()
        flash("Delivery slot confirmed.", "success")
        return redirect(url_for("order_detail", order_id=order.id))

    @app.route("/orders/<int:order_id>/cancel", methods=["POST"])
    @role_required("customer")
    def cancel_order(order_id):
        order = db.session.get(Order, order_id) or abort(404)
        if order.customer_id != current_user.id:
            abort(403)
        if order.status in ("delivered", "out_for_delivery", "cancelled"):
            flash("This order cannot be cancelled at its current stage.", "error")
        else:
            add_event(order, "cancelled", "Cancelled by customer")
            flash("Order cancelled.", "success")
        return redirect(url_for("order_detail", order_id=order.id))

    @app.route("/courier")
    @role_required("courier")
    def courier_dashboard():
        orders = Order.query.filter_by(courier_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template("courier_dashboard.html", orders=orders)

    @app.route("/courier/orders/<int:order_id>/status", methods=["POST"])
    @role_required("courier", "admin")
    def update_delivery_status(order_id):
        order = db.session.get(Order, order_id) or abort(404)
        if current_user.role == "courier" and order.courier_id != current_user.id:
            abort(403)
        status = request.form.get("status")
        allowed = {"picked_up", "out_for_delivery", "delivered", "failed"}
        if status not in allowed:
            abort(400)
        if status == "out_for_delivery" and not order.slot_id:
            flash("Schedule a delivery slot before marking it out for delivery.", "error")
        else:
            add_event(order, status, f"Updated by {current_user.name}")
            flash("Delivery status updated.", "success")
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/admin")
    @role_required("admin")
    def admin_dashboard():
        orders = Order.query.order_by(Order.created_at.desc()).all()
        customers = User.query.filter_by(role="customer").count()
        couriers = User.query.filter_by(role="courier").count()
        courier_users = User.query.filter_by(role="courier").order_by(User.name).all()
        slots = DeliverySlot.query.filter(DeliverySlot.date >= date.today()).order_by(DeliverySlot.date, DeliverySlot.start_time).limit(12).all()
        areas = group_deliveries_by_area()
        stats = {
            "orders": len(orders),
            "scheduled": Order.query.filter_by(status="scheduled").count(),
            "delivered": Order.query.filter_by(status="delivered").count(),
            "failed": Order.query.filter_by(status="failed").count(),
            "customers": customers,
            "couriers": couriers,
        }
        return render_template("admin_dashboard.html", orders=orders[:20], slots=slots, stats=stats, areas=areas, courier_users=courier_users)

    @app.route("/admin/couriers/new", methods=["POST"])
    @role_required("admin")
    def create_courier():
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter a courier name, email and password of at least 8 characters.", "error")
            return redirect(url_for("admin_dashboard"))
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return redirect(url_for("admin_dashboard"))
        courier = User(name=name, email=email, role="courier")
        courier.set_password(password)
        db.session.add(courier)
        db.session.commit()
        flash("Courier account created.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/orders/new", methods=["GET", "POST"])
    @role_required("admin")
    def create_order():
        customers = User.query.filter_by(role="customer").order_by(User.name).all()
        couriers = User.query.filter_by(role="courier").order_by(User.name).all()
        if request.method == "POST":
            customer = db.session.get(User, request.form.get("customer_id", type=int))
            if not customer or customer.role != "customer":
                flash("Select a valid customer.", "error")
                return redirect(url_for("create_order"))
            item = request.form.get("item_name", "").strip()
            address = request.form.get("address", "").strip()
            area = request.form.get("area", "Guntur").strip()
            pincode = request.form.get("pincode", "").strip()
            if not item or not address or not pincode:
                flash("Complete all required order details.", "error")
                return redirect(url_for("create_order"))
            code = "SD" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(9))
            order = Order(
                tracking_code=code, item_name=item, customer_id=customer.id,
                address=address, area=area, pincode=pincode,
                courier_id=request.form.get("courier_id", type=int) or None,
                status="ready_to_schedule", provider="Demo"
            )
            db.session.add(order)
            db.session.commit()
            db.session.add(StatusEvent(order_id=order.id, status="ready_to_schedule", note="Order created by admin"))
            db.session.commit()
            flash(f"Order {code} created.", "success")
            return redirect(url_for("admin_dashboard"))
        return render_template("create_order.html", customers=customers, couriers=couriers)

    @app.route("/admin/slots", methods=["POST"])
    @role_required("admin")
    def create_slot():
        try:
            slot_date = date.fromisoformat(request.form.get("date", ""))
            capacity = max(1, min(100, int(request.form.get("capacity", "8"))))
        except (ValueError, TypeError):
            flash("Enter a valid date and capacity.", "error")
            return redirect(url_for("admin_dashboard"))
        start = request.form.get("start_time", "")
        end = request.form.get("end_time", "")
        area = request.form.get("area", "Guntur").strip()
        if slot_date < date.today() or not start or not end or start >= end:
            flash("Choose a valid future date and time window.", "error")
            return redirect(url_for("admin_dashboard"))
        slot = DeliverySlot(date=slot_date, start_time=start, end_time=end, area=area, capacity=capacity)
        db.session.add(slot)
        try:
            db.session.commit()
            flash("Delivery slot created.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Could not create this slot.", "error")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/slots/generate", methods=["POST"])
    @role_required("admin")
    def generate_slots():
        created = create_default_slots(days=7, area=request.form.get("area", "Guntur"))
        flash(f"Generated {created} new slots.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/couriers/assign", methods=["POST"])
    @role_required("admin")
    def assign_courier():
        order = db.session.get(Order, request.form.get("order_id", type=int)) or abort(404)
        courier = db.session.get(User, request.form.get("courier_id", type=int))
        if not courier or courier.role != "courier":
            flash("Choose a valid courier.", "error")
        else:
            order.courier_id = courier.id
            db.session.commit()
            flash("Courier assigned.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/track", methods=["GET", "POST"])
    def public_track():
        order = None
        if request.method == "POST":
            code = request.form.get("tracking_code", "").strip().upper()
            order = Order.query.filter_by(tracking_code=code).first()
            if not order:
                flash("No demo shipment found with that tracking code.", "error")
        return render_template("track.html", order=order)

    @app.route("/api/orders/<tracking_code>")
    def api_order(tracking_code):
        order = Order.query.filter_by(tracking_code=tracking_code.upper()).first_or_404()
        return jsonify({
            "tracking_code": order.tracking_code,
            "item": order.item_name,
            "status": order.status,
            "status_label": STATUSES.get(order.status, order.status),
            "area": order.area,
            "slot": f"{order.slot.date} {order.slot.label}" if order.slot else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None
        })

    @app.route("/integrations/delhivery/status")
    @role_required("admin")
    def delhivery_status():
        configured = bool(
            app.config["DELHIVERY_ENABLED"] and app.config["DELHIVERY_API_TOKEN"]
            and app.config["DELHIVERY_BASE_URL"] and app.config["DELHIVERY_TRACKING_PATH"]
        )
        return jsonify({
            "integration": "Delhivery",
            "configured": configured,
            "mode": "live-ready" if configured else "demo",
            "message": "Credentials and verified endpoint configuration detected." if configured
                       else "Add verified Delhivery account credentials and endpoint settings to .env."
        })

    @app.route("/integrations/delhivery/track/<waybill>")
    @role_required("admin")
    def delhivery_track(waybill):
        try:
            return jsonify(tracking_lookup(waybill))
        except DelhiveryNotConfigured as exc:
            return jsonify({"error": str(exc), "mode": "demo"}), 503
        except Exception as exc:
            app.logger.exception("Delhivery tracking request failed")
            return jsonify({"error": "Delhivery request failed. Check server logs and API configuration."}), 502

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="We couldn't find that page."), 404

    with app.app_context():
        db.create_all()
        seed_demo_data(app)

    return app

def seed_demo_data(app):
    if User.query.count() > 0:
        return
    admin = User(name="Platform Admin", email="admin@smartdelivery.demo", role="admin")
    admin.set_password("Admin@123")
    courier = User(name="Demo Courier", email="courier@smartdelivery.demo", role="courier", phone="9000000001")
    courier.set_password("Courier@123")
    customer = User(name="Demo Customer", email="customer@smartdelivery.demo", role="customer", phone="9000000002")
    customer.set_password("Customer@123")
    db.session.add_all([admin, courier, customer])
    db.session.commit()
    create_default_slots(days=10, area="Guntur")
    order = Order(
        tracking_code="SD-DEMO-1001", item_name="Wireless headphones",
        customer_id=customer.id, courier_id=courier.id,
        address="Lakshmipuram, Guntur, Andhra Pradesh",
        area="Guntur", pincode="522007", status="ready_to_schedule",
        provider="Demo"
    )
    db.session.add(order)
    db.session.commit()
    db.session.add(StatusEvent(order_id=order.id, status="ready_to_schedule", note="Demo order created"))
    db.session.commit()

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False), host="0.0.0.0", port=5000)
