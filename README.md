# Smart Delivery Slot Scheduling

A Flask-based hackathon MVP for customer-selected delivery windows, capacity-aware booking, courier workflows and operations dashboards.

## Features

- Customer registration/login and role-based access.
- Customer dashboard, package details, slot booking and rescheduling.
- Capacity-limited delivery slots with server-side validation.
- Courier dashboard and delivery status updates.
- Admin dashboard, order creation, courier assignment and slot management.
- Public demo tracking page and JSON tracking endpoint.
- Demo data seeded automatically on first run.
- Optional Delhivery adapter scaffold; demo mode works without external credentials.
- Responsive dark UI with CSS 3D parcel illustration and animated effects.

## Quick start

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

python app.py
```

Open http://127.0.0.1:5000

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Admin | admin@smartdelivery.demo | Admin@123 |
| Courier | courier@smartdelivery.demo | Courier@123 |
| Customer | customer@smartdelivery.demo | Customer@123 |

Sample tracking code: `SD-DEMO-1001`

Change demo passwords and `SECRET_KEY` before any deployment. The app seeds demo accounts only when the database is empty.

## Demo flow

1. Sign in as customer and open the demo order.
2. Book an available slot; try selecting a different slot to demonstrate rescheduling.
3. Sign out and sign in as courier to update shipment status.
4. Sign in as admin to create orders, generate slots and view operational metrics.
5. Use `/track` or `/api/orders/SD-DEMO-1001` to view shipment tracking information.

## Delhivery integration notes

The application includes `delhivery.py` and admin-only endpoints:

- `GET /integrations/delhivery/status`
- `GET /integrations/delhivery/track/<waybill>`

The adapter is intentionally disabled by default. Set the following in `.env` only after receiving credentials and confirming the exact API base URL, tracking endpoint path, authentication format and account permissions from Delhivery's official documentation/support:

```env
DELHIVERY_ENABLED=1
DELHIVERY_API_TOKEN=your_server_side_token
DELHIVERY_BASE_URL=https://your-confirmed-api-host
DELHIVERY_TRACKING_PATH=your-confirmed-tracking-path
```

**Important:** Shipment tracking is not the same as a delivery appointment API. This MVP stores the customer's preferred slot in its own database. Do not claim that a Delhivery courier is committed to that exact time unless Delhivery confirms and enables a suitable appointment/rescheduling API for your account. Never put API credentials in frontend code or commit `.env`.

## Deployment

- Set a strong `SECRET_KEY`.
- Set `DATABASE_URL` to a managed PostgreSQL connection string.
- Set `FLASK_DEBUG=0` and run with a production WSGI server such as Gunicorn (`gunicorn app:app`).
- Use HTTPS.
- Add CSRF protection, rate limiting, email/phone verification, audit logging and concurrency-safe slot reservation before production use.
- For a real multi-courier operation, extend the scheduler with per-area/per-courier workload constraints and a route optimization provider.

## Current MVP limitations

This is a hackathon-ready functional prototype, not a production-certified logistics platform. Slot booking has basic capacity checks; for high concurrency, use database transactions/locking or an atomic reservation strategy. Notifications, live GPS, real courier appointment control and verified Delhivery endpoints require additional integration and credentials.
