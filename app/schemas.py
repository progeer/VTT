from pydantic import BaseModel

class RoomBase(BaseModel):
    name: str

class RoomCreate(RoomBase):
    pass

class RoomRead(RoomBase):
    id: int

    class Config:
        from_attributes = True