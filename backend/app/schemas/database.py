from pydantic import BaseModel, Field


class DatabaseSelection(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DatabaseInfo(BaseModel):
    name: str
    size_bytes: int
    active: bool


class DatabaseList(BaseModel):
    databases: list[DatabaseInfo]

