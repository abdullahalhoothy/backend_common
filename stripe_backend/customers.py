from datetime import datetime
from fastapi import HTTPException,status
from backend_common.dtypes.stripe_dtypes import (
    CustomerReq,
    CustomerRes,
)
import stripe
from backend_common.database import Database
import json
from backend_common.auth import get_user_email_and_username
from backend_common.sql_object import SqlObject

# customer functions
async def create_customer(req: CustomerReq) -> CustomerRes:
    # using user_id get from firebase user_email, user_name
    email, username = await get_user_email_and_username(req.user_id)

    # Create a new customer in Stripe
    customer = stripe.Customer.create(
        name=username,
        email=email,
        description=req.description,
        phone=req.phone,
        address=req.address.model_dump(),
        metadata=req.metadata,
    )
    
    # Save the customer in the database

    Database.execute(
        SqlObject.upsert_customer_user_query,
        req.user_id,
        customer.id
    )

    customer_json = dict(customer)
    customer_json["user_id"] = req.user_id

    return  customer_json


async def fetch_customer(req) -> CustomerRes:

    customer_id = await fetch_customer_id(req.user_id)

    customer = stripe.Customer.retrieve(customer_id)

    customer_json = dict(customer)

    return customer_json


async def update_customer(req: CustomerReq) -> CustomerRes:

    customer_id = await fetch_customer_id(req.user_id)
    
    stripe_customer = stripe.Customer.modify(
        customer_id,
        name=req.name,
        email=req.email,
        description=req.description,
        phone=req.phone,
        address=req.address.model_dump(),
        metadata=req.metadata,
    )

    customer_json = dict(stripe_customer)
    return customer_json


async def delete_customer(req) -> dict:
    user_id = req.user_id

    customer_id = await fetch_customer_id(user_id)

    stripe.Customer.delete(customer_id)

    await Database.execute(SqlObject.delete_customer_strip_query, user_id)

    return "Customer deleted"


async def list_customers() -> list[CustomerRes]:
    all_customers = stripe.Customer.list()

    return [CustomerRes(**customer) for customer in all_customers["data"]]

async def fetch_customer_id(user_id:str):
    customer_record = await Database.fetchrow(SqlObject.fetch_customer_id_by_user_id__stripe_query, user_id)
    if not customer_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Not Found")
    customer_id = dict(customer_record)["customer_id"]

    return customer_id