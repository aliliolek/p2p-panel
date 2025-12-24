from pydantic import BaseModel


class FiatAutoStartRequest(BaseModel):
    sell: bool = True
    buy: bool = True
