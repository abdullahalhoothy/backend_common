from typing import Dict, List, TypeVar, Generic, Optional, Any

from pydantic import BaseModel


class ReqUserId(BaseModel):
    user_id: str


class ReqCreateUserProfile(BaseModel):
    username: str
    email: str
    password: str


class ReqUserLogin(BaseModel):
    email: str
    password: str


class ReqUserProfile(BaseModel):
    user_id: str


class ReqResetPassword(BaseModel):
    email: str


class ReqConfirmReset(BaseModel):
    oob_code: str
    new_password: str


class ReqChangePassword(BaseModel):
    user_id: str
    email: str
    password: str
    new_password: str


class ReqChangeEmail(BaseModel):
    user_id: str
    current_email: str
    new_email: str
    password: str


## Added it for Refresh token
class ReqRefreshToken(BaseModel):
    grant_type: str
    refresh_token: str
