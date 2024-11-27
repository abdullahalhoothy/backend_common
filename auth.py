from datetime import datetime
from typing import Any
import json
from fastapi import Depends, HTTPException, status, Request

from fastapi.security import OAuth2PasswordBearer
from backend_common.database import Database
from backend_common.dtypes.auth_dtypes import (
    ReqCreateFirebaseUser,
    ReqUserLogin,
    ReqResetPassword,
    ReqConfirmReset,
    ReqChangePassword,
    ReqRefreshToken,
    ReqChangeEmail,
    ReqCreateUserProfile,
)
from backend_common.common_config import CONF
from firebase_admin import firestore
import requests
import os
from firebase_admin import auth
import firebase_admin
from firebase_admin import credentials
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import stripe

from sql_object import SqlObject

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
stripe.api_key = CONF.stripe_api_key


if os.path.exists(CONF.firebase_sp_path):
    cred = credentials.Certificate(CONF.firebase_sp_path)
    default_app = firebase_admin.initialize_app(cred)
    db = firestore.client()


class JWTBearer(HTTPBearer):
    """This class is to make endpoints secure with JWT"""

    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        self.request = request
        credentials_obj: HTTPAuthorizationCredentials = await super(
            JWTBearer, self
        ).__call__(request)
        if credentials_obj:
            if not credentials_obj.scheme == "Bearer":
                raise HTTPException(
                    status_code=403, detail="Invalid authentication scheme."
                )
            if not await self.verify_jwt(credentials_obj.credentials):
                raise HTTPException(
                    status_code=403, detail="Invalid token or expired token."
                )
            return credentials_obj.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    async def verify_jwt(self, jwt_token: str) -> bool:
        decoded_token = my_verify_id_token(jwt_token)
        token_user_id = decoded_token["uid"]
        # Check if the token user_id matches the requested user_id
        request_body = await self.request.json()
        if request_body.get("user_id") and token_user_id != request_body.get("user_id"):
            return False
        return True


async def create_firebase_user(req: ReqCreateFirebaseUser) -> dict[str, Any]:
    try:
        # Create user in Firebase
        user = auth.create_user(
            email=req.email, password=req.password, display_name=req.username
        )

        # Send user verify email
        payload = {
            "email": req.email,
            "password": req.password,
            "returnSecureToken": True,
        }
        response = await make_firebase_api_request(
            CONF.firebase_signInWithPassword, payload
        )

        ## Send Verifiy Email
        payload = {"requestType": "VERIFY_EMAIL", "idToken": response["idToken"]}
        _ = await make_firebase_api_request(CONF.firebase_sendOobCode, payload=payload)
        return {"user_id": user.uid, "message": "User profile created successfully"}
    except auth.EmailAlreadyExistsError as emialerrror:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already taken",
        ) from emialerrror


async def login_user(req: ReqUserLogin) -> dict[str, Any]:
    try:
        payload = {
            "email": req.email,
            "password": req.password,
            "returnSecureToken": True,
        }
        response = await make_firebase_api_request(
            CONF.firebase_signInWithPassword, payload
        )
        response["created_at"] = datetime.now()
        if response.get("localId", "") != "":
            user = auth.get_user(response["localId"])
            if user.email_verified:
                return response
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Unverified Email"
                )
        raise auth.UserNotFoundError(message="")
    except auth.UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        ) from e


async def refresh_id_token(req: ReqRefreshToken) -> dict[str, Any]:
    try:
        payload = {"grant_type": req.grant_type, "refresh_token": req.refresh_token}
        response = await make_firebase_api_request(CONF.firebase_refresh_token, payload)
        response["created_at"] = datetime.now()
        response["idToken"] = response["id_token"]
        response["refreshToken"] = response["refresh_token"]
        response["expiresIn"] = response["expires_in"]
        response["localId"] = response["user_id"]
        # drop certain keys from reponse like id_token, refresh_token, expires_in, user_id
        keys_to_drop = ["id_token", "refresh_token", "expires_in", "user_id"]
        response = {
            key: value for key, value in response.items() if key not in keys_to_drop
        }
        return response
    except auth.UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        ) from e


def my_verify_id_token(token: str = Depends(oauth2_scheme)):
    try:
        return auth.verify_id_token(token)
    except auth.InvalidIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid access token={token}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def reset_password(req: ReqResetPassword) -> dict[str, Any]:
    payload = {"requestType": "PASSWORD_RESET", "email": req.email}
    response = await make_firebase_api_request(CONF.firebase_sendOobCode, payload)
    return response


async def confirm_reset(req: ReqConfirmReset) -> dict[str, Any]:
    payload = {"oobCode": req.oob_code, "newPassword": req.new_password}
    response = await make_firebase_api_request(CONF.firebase_resetPassword, payload)
    return response


async def change_password(req: ReqChangePassword) -> dict[str, Any]:
    login_req = ReqUserLogin(email=req.email, password=req.password)
    response = await login_user(login_req)
    if response.get("localId", "") != req.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User id did not match firebase user ID acquired from user name and password",
        )

    # Now change the password
    payload = {
        "idToken": response["idToken"],
        "password": req.new_password,
        "returnSecureToken": True,
    }
    response = await make_firebase_api_request(CONF.firebase_update, payload)

    return response


async def change_email(req: ReqChangeEmail) -> dict[str, Any]:
    login_req = ReqUserLogin(email=req.current_email, password=req.password)
    response = await login_user(login_req)
    if response.get("localId", "") != req.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User id did not match firebase user ID acquired from user name and password",
        )

    ## Send vertification to the new email
    payload = {
        "requestType": "VERIFY_AND_CHANGE_EMAIL",
        "idToken": response["idToken"],
        "newEmail": req.new_email,
    }
    _ = await make_firebase_api_request(CONF.firebase_sendOobCode, payload=payload)

    return response


async def make_firebase_api_request(url, payload):
    try:
        url = url + CONF.firebase_api_key
        response = requests.post(url, json=payload, timeout=120)
        return response.json()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("error", {}).get("message"),
        ) from e


async def get_user_email_and_username(user_id: str):
    try:
        user = auth.get_user(user_id)
        email = user.email
        username = user.display_name
        return email, username
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}",
        )


# firebase and stripe store customer
async def save_customer_mapping(firebase_uid: str, stripe_customer_id: str):
    doc_ref = db.collection("firebase_stripe_mappings").document(firebase_uid)
    doc_ref.set(
        {
            "stripe_customer_id": stripe_customer_id,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )


async def get_stripe_customer_id(firebase_uid: str) -> str:
    doc_ref = db.collection("firebase_stripe_mappings").document(firebase_uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stripe customer not found for this user",
        )
    return doc.to_dict().get("stripe_customer_id")


# User Profile Collection Functions
async def create_user_profile(req: ReqCreateUserProfile):
    user_data = {
        "user_id": req.user_id,
        "email": req.email,
        "username": req.username,
        "prdcer": {
            "prdcer_dataset": {},
            "prdcer_lyrs": {},
            "prdcer_ctlgs": {},
            "draft_ctlgs": {},
        }
    }

    # Add timestamp separately in Firestore but don't include in return data
    doc_ref = db.collection('all_user_profiles').document(req.user_id)
    firestore_data = user_data.copy()
    firestore_data['created_at'] = firestore.SERVER_TIMESTAMP
    doc_ref.set(firestore_data)
    
    return user_data


async def update_user_profile(user_id: str, user_data: dict):
    try:
        doc_ref = db.collection('all_user_profiles').document(user_id)
        
        # Prepare data for Firestore update
        update_data = {
            "user_id": user_data["user_id"],
            "prdcer": {
                "prdcer_dataset": user_data.get("prdcer", {}).get("prdcer_dataset", {}),
                "prdcer_lyrs": user_data.get("prdcer", {}).get("prdcer_lyrs", {}),
                "prdcer_ctlgs": user_data.get("prdcer", {}).get("prdcer_ctlgs", {}),
                "draft_ctlgs": user_data.get("prdcer", {}).get("draft_ctlgs", {}),
            },
            "updated_at": firestore.SERVER_TIMESTAMP
        }
        
        doc_ref.update(update_data)
        
        # Return data without the timestamp
        del update_data['updated_at']
        return update_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user profile: {str(e)}"
        )


async def load_user_profile(user_id: str) -> dict:
    """
    Loads user data from Firestore based on the user ID.
    If the user doesn't exist, creates an empty profile.
    """
    try:
        doc_ref = db.collection('all_user_profiles').document(user_id)
        doc = doc_ref.get()
        

        if not doc.exists:
            # User doesn't exist, create an empty profile
            req = ReqCreateUserProfile(
                user_id=user_id, username="", password="", email=""
            )
            return await create_user_profile(req)
            
        data = doc.to_dict()
        # Remove timestamp fields before returning
        if 'created_at' in data:
            del data['created_at']
        if 'updated_at' in data:
            del data['updated_at']
            
        return {
            "user_id": data["user_id"],
            "prdcer": {
                "prdcer_dataset": data["prdcer"]["prdcer_dataset"],
                "prdcer_lyrs": data["prdcer"]["prdcer_lyrs"],
                "prdcer_ctlgs": data["prdcer"]["prdcer_ctlgs"],
                "draft_ctlgs": data["prdcer"]["draft_ctlgs"],
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading user profile: {str(e)}"
        )