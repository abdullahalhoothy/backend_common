from datetime import datetime
from fastapi import HTTPException,status
from backend_common.dtypes.stripe_dtypes import (
    CustomerReq,
    CustomerRes,
)
import stripe
from backend_common.database import Database
import json
from backend_common.auth import get_user_email_and_username,get_stripe_customer_id, save_customer_mapping



# customer functions
async def create_stripe_customer(req: CustomerReq) -> dict:
    # Check if customer mapping already exists
    email, username = await get_user_email_and_username(req.user_id)

    # Create a new customer in Stripe
    req.metadata.update({'user_id': req.user_id})
    
    customer = stripe.Customer.create(
        name=req.name or username,
        email=email,
        description=req.description,
        phone=req.phone,
        address=req.address.model_dump(),
        metadata=req.metadata,
        balance=req.balance,
    )

    # Save the mapping in Firestore
    await save_customer_mapping(req.user_id, customer.id)

    customer_json = dict(customer)
    customer_json["user_id"] = req.user_id

    return  customer_json


async def fetch_customer(req=None, user_id=None) -> dict:
    user_id = user_id or req.user_id
    customer_id = await get_stripe_customer_id(user_id)
    customer = stripe.Customer.retrieve(customer_id)

    customer_json = dict(customer)
    return customer_json


async def update_customer(req: CustomerReq) -> dict:
    customer_id = await get_stripe_customer_id(req.user_id)  # This will raise 404 if not found
    stripe_customer = stripe.Customer.modify(
        customer_id,
        name=req.name,
        email=req.email,
        description=req.description,
        phone=req.phone,
        address=req.address.model_dump(),
        metadata=req.metadata,
    )
    return dict(stripe_customer)


async def list_customers() -> list[dict]:
    all_customers = stripe.Customer.list()
    return [customer for customer in all_customers["data"]]

