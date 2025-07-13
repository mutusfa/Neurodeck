from pydantic import BaseModel, ConfigDict, Field


class Card(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
    question: str
    answer: str
    topic: str = ""
    context: str = ""
    evaluation: str = "not_evaluated"
    database_id: int | None = Field(default=None, alias="id", serialization_alias="id")
