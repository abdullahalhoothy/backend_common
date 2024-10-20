from datetime import datetime
from typing import Dict

from fastapi import Depends, HTTPException, status, Request

from fastapi.security import OAuth2PasswordBearer
from backend_common.dtypes.auth_dtypes import (
    ReqCreateUserProfile,
    ReqUserLogin,
    ReqResetPassword,
    ReqConfirmReset,
    ReqChangePassword,
    ReqRefreshToken,
    ReqChangeEmail,
)
from backend_common.common_config import CONF

import requests
import os
from firebase_admin import auth
import firebase_admin
from firebase_admin import credentials
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


if os.path.exists(CONF.firebase_sp_path):
    cred = credentials.Certificate(CONF.firebase_sp_path)
    default_app = firebase_admin.initialize_app(cred)


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
        if (
            hasattr(self.request.request_body, "user_id")
            and token_user_id != self.request.request_body.user_id
        ):
            return False
        return True


async def create_user(req: ReqCreateUserProfile) -> Dict[str, str]:
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


async def login_user(req: ReqUserLogin) -> Dict[str, str]:
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


async def refresh_id_token(req: ReqRefreshToken) -> Dict[str, str]:
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


async def reset_password(req: ReqResetPassword) -> Dict[str, str]:
    payload = {"requestType": "PASSWORD_RESET", "email": req.email}
    response = await make_firebase_api_request(CONF.firebase_sendOobCode, payload)
    return response


async def confirm_reset(req: ReqConfirmReset) -> Dict[str, str]:
    payload = {"oobCode": req.oob_code, "newPassword": req.new_password}
    response = await make_firebase_api_request(CONF.firebase_resetPassword, payload)
    return response


async def change_password(req: ReqChangePassword) -> Dict[str, str]:
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


async def change_email(req: ReqChangeEmail) -> Dict[str, str]:
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
