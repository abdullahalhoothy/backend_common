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

{
  "message": "Request received.",
  "request_id": "req-2d9b1944-b532-40bd-b52d-e98c14e74275",
  "data": {
    "kind": "identitytoolkit#VerifyPasswordResponse",
    "localId": "dpI5qXNkfgRBFpUn5taucoNuJUg2",
    "email": "quodeine@hotmail.com",
    "displayName": "testemail3",
    "idToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6ImU2YWMzNTcyNzY3ZGUyNjE0ZmM1MTA4NjMzMDg3YTQ5MjMzMDNkM2IiLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoidGVzdGVtYWlsMyIsImlzcyI6Imh0dHBzOi8vc2VjdXJldG9rZW4uZ29vZ2xlLmNvbS9maXItbG9jYXRvci0zNTgzOSIsImF1ZCI6ImZpci1sb2NhdG9yLTM1ODM5IiwiYXV0aF90aW1lIjoxNzMwMjMwODUwLCJ1c2VyX2lkIjoiZHBJNXFYTmtmZ1JCRnBVbjV0YXVjb051SlVnMiIsInN1YiI6ImRwSTVxWE5rZmdSQkZwVW41dGF1Y29OdUpVZzIiLCJpYXQiOjE3MzAyMzA4NTAsImV4cCI6MTczMDIzNDQ1MCwiZW1haWwiOiJxdW9kZWluZUBob3RtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmaXJlYmFzZSI6eyJpZGVudGl0aWVzIjp7ImVtYWlsIjpbInF1b2RlaW5lQGhvdG1haWwuY29tIl19LCJzaWduX2luX3Byb3ZpZGVyIjoicGFzc3dvcmQifX0.ZePi0o150CVa-BuzzCykjWZENL3OHrMMNgfavXDAzVd8B5evfoIkSD7BaHuDURcvCCfsSpbuDzQPQIaicFnHm_ipEEe45Km-5LtX9z2wuxjNg43ZCOlzAgwRdwsWktFKyPWr7pimKhE9-tZZvM_erUaGplxJWaFcKTqETqwOkqv7oBMlGX-nB2gv5oK1yERUXQF8HeRehbpoHcshdWhXsemzY4knzrkfrLLchORfnYzGdlicZi0j0dOWRNkMh2hY2Mr8W_dIiCgUWj2MRihtNcP5455IjqKfdShZSRIe4OthQNBuzN1Y1cthHawZ-buPchWmt7cVvXCBwiXUenfyew",
    "registered": True,
    "refreshToken": "AMf-vBwgh0IuRHdJ1mp17cHBsB2r57aMg-FokF5RHBiguz31uhap-UheIZJN2mxiaol7Yi26uj1CTVkaWb1Ua5GgbZ0znEWLSrXZLhYOuw5OaS8jNVaCfn-1sKZOJKVsDYebdhur90-gI38x2WvlyGKRmtU9YUrENW_LeWfVGdE65z4To1slM1E-U2ZPKu8SmkQPcNNkKlR_spZYt7O-ajJ_bucix070B2rrxjj3W1W6rGvt-8cbYhA",
    "expiresIn": "3600",
    "created_at": "2024-10-30T00:40:51.026697"
  }
}


# customer functions
async def create_customer(req: CustomerReq) -> CustomerRes:
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
    )

    # Save the customer in the database

    await Database.execute(
        CommonSql.firebase_strip_mapping,req.user_id, customer.id
    )

    customer_json = dict(customer)
    customer_json["user_id"] = req.user_id

    return  CustomerRes(**customer_json)


async def fetch_customer(req=None, user_id=None) -> CustomerRes:
    user_id = user_id or req.user_id
    customer_id = await fetch_customer_id(user_id)

    customer = stripe.Customer.retrieve(customer_id)

    customer_json = dict(customer)

    return CustomerRes(**customer_json)


async def update_customer(req: CustomerReq) -> CustomerRes:

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


async def delete_customer(req) -> str:
    user_id = req.user_id

    customer_id = await fetch_customer_id(user_id)

    stripe.Customer.delete(customer_id)

    await Database.execute(CommonSql.delete_customer_strip_query, customer_id)

    return "Customer deleted"


async def list_customers() -> list[CustomerRes]:
    all_customers = stripe.Customer.list()

    return [CustomerRes(**customer) for customer in all_customers["data"]]

async def fetch_customer_id(user_id:str):
    customer_record = await Database.fetchrow(CommonSql.fetch_customer_id_by_user_id__stripe_query, user_id)
    if not customer_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Not Found")
    customer_id = dict(customer_record)["customer_id"]

    return customer_id