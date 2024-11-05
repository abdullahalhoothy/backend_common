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
from backend_common.common_sql import CommonSql


# customer functions
async def create_customer(req: CustomerReq) -> dict:
    # using user_id get from firebase user_email, user_name

    row = await Database.fetchrow(
        CommonSql.fetch_customer_id_by_user_id__stripe_query,req.user_id
    )
    if row:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Customer with user id already exists")

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

    # Save the customer in the database

    await Database.execute(
        CommonSql.firebase_strip_mapping,req.user_id, customer.id
    )

    customer_json = dict(customer)
    customer_json["user_id"] = req.user_id

    return  customer_json


async def fetch_customer(req=None, user_id=None) -> dict:
    user_id = user_id or req.user_id
    customer_id = await fetch_customer_id(user_id)

    customer = stripe.Customer.retrieve(customer_id)

    customer_json = dict(customer)
    return customer_json


async def update_customer(req: CustomerReq) -> dict:

    row = await Database.fetchrow(
        CommonSql.fetch_customer_id_by_user_id__stripe_query,req.user_id
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Customer with user id not found")
    stripe_customer = stripe.Customer.modify(
        dict(row).get('customer_id'),
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

    customer = stripe.Customer.delete(customer_id)

    await Database.execute(CommonSql.delete_customer_strip_query, customer_id)

    return customer.to_dict_recursive()


async def list_customers() -> list[dict]:
    all_customers = stripe.Customer.list()
    return [customer for customer in all_customers["data"]]


async def fetch_customer_id(user_id:str):
    customer_record = await Database.fetchrow(CommonSql.fetch_customer_id_by_user_id__stripe_query, user_id)
    if not customer_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Not Found")
    customer_id = dict(customer_record)["customer_id"]

    return customer_id