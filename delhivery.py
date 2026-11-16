"""
Optional Delhivery adapter.

This module deliberately does not guess endpoint paths or claim that a normal
tracking API can book a customer-selected delivery appointment. Configure the
official endpoint path and base URL only after confirming the API products and
permissions enabled for your Delhivery account.
"""
import requests
from flask import current_app

class DelhiveryNotConfigured(Exception):
    pass

def tracking_lookup(waybill):
    enabled = current_app.config["DELHIVERY_ENABLED"]
    token = current_app.config["DELHIVERY_API_TOKEN"]
    base = current_app.config["DELHIVERY_BASE_URL"]
    path = current_app.config["DELHIVERY_TRACKING_PATH"]

    if not (enabled and token and base and path):
        raise DelhiveryNotConfigured(
            "Delhivery is not configured. Use Demo mode or add verified API settings in .env."
        )

    # Path is account/documentation-specific and must be verified before use.
    url = base + "/" + path.lstrip("/")
    response = requests.get(
        url,
        params={"waybill": waybill},
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
