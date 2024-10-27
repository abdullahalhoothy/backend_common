import json
import uuid

from fastapi import HTTPException, status
from typing import TypeVar, Optional, Type, Callable, Awaitable, Any, Required
from pydantic import BaseModel
from backend_common.logging_wrapper import log_and_validate
import logging


logger = logging.getLogger(__name__)


T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)


@log_and_validate(logger)
async def request_handling(
    req: Optional[T],
    input_type: Optional[Type[T]],
    output_type: Optional[Type[U]],
    custom_function: Optional[Callable[..., Awaitable[Any]]],
    output: Optional[T] = ""
):
    if req:
        req = req.request_body
        input_type.model_validate(req)

    if custom_function is not None:
        try:
            if req:
                output = await custom_function(req=req.request_body)
            else:
                output = await custom_function()
        except HTTPException:
            # If it's already an HTTPException, just re-raise it
            raise
        except Exception as e:
            # For any other type of exception, wrap it in an HTTPException
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {str(e)}",
            ) from e
    res_body = output_type(**output) if output_type else output
    return res_body


def output_update_with_req_msg(func: Type[T]):
    """Decorator to update response dictionary"""
    async def update_fields(*args, **kwargs):
        """Update fields"""
        return {
            'data': await func(*args, **kwargs),
            'message': "Request received.",
            'request_id': "req-" + str(uuid.uuid4())
        }
    return update_fields