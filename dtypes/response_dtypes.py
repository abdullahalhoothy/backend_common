from typing import Dict, TypeVar, Generic, Any

from pydantic import BaseModel


T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    message: str
    responseCode: int
    data: T


ConfigurationResponse = ResponseModel[Dict[str, Dict]]
ConfigurationResponse1 = ResponseModel
