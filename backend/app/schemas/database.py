from pydantic import BaseModel, ConfigDict, Field, model_validator


class DatabaseSelection(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DatabaseInfo(BaseModel):
    name: str
    size_bytes: int
    active: bool


class DatabaseList(BaseModel):
    databases: list[DatabaseInfo]


class CombinedSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=255)
    alias: str = Field(pattern=r'^[a-z][a-z0-9_]{0,23}$')


class CombinedRelationship(BaseModel):
    model_config = ConfigDict(extra='forbid')
    child_source: str = Field(min_length=1, max_length=24)
    child_table: str = Field(min_length=1, max_length=128)
    child_columns: list[str] = Field(min_length=1, max_length=4)
    parent_source: str = Field(min_length=1, max_length=24)
    parent_table: str = Field(min_length=1, max_length=128)
    parent_columns: list[str] = Field(min_length=1, max_length=4)

    @model_validator(mode='after')
    def aligned_keys(self):
        if len(self.child_columns)!=len(self.parent_columns):
            raise ValueError('Child and parent key lengths must match')
        if len(set(self.child_columns))!=len(self.child_columns) or len(set(self.parent_columns))!=len(self.parent_columns):
            raise ValueError('Relationship columns must not repeat')
        if any(not 1<=len(c)<=128 for c in self.child_columns+self.parent_columns):
            raise ValueError('Invalid relationship column length')
        return self


class CombineDatabases(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}$')
    sources: list[CombinedSource] = Field(min_length=2, max_length=5)
    relationships: list[CombinedRelationship] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def distinct_sources(self):
        if len({s.alias for s in self.sources})!=len(self.sources):
            raise ValueError('Source aliases must be unique')
        if len({s.name for s in self.sources})!=len(self.sources):
            raise ValueError('Choose different source databases')
        return self

