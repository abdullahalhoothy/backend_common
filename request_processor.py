import uuid
from fastapi import HTTPException, status
from typing import TypeVar, Optional, Type, Callable, Awaitable, Any
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)
U = TypeVar("U", bound=BaseModel)


async def request_handling(
    req: Optional[T],
    input_type: Optional[Type[T]],
    output_type: Type[U],
    custom_function: Optional[Callable[..., Awaitable[Any]]],
):
    output = ""
    req = req.request_body
    input_type.model_validate(req)

    if custom_function is not None:
        try:
            output = await custom_function(req=req)
        except HTTPException:
            # If it's already an HTTPException, just re-raise it
            raise
        except Exception as e:
            # For any other type of exception, wrap it in an HTTPException
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {str(e)}",
            ) from e

    request_id = "req-" + str(uuid.uuid4())
    res_body = output_type(
        message="Request received",
        request_id=request_id,
        data=output,
    )
    return res_body
