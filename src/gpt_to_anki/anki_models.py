from pydantic import BaseModel, ConfigDict, Field


class AnkiNoteFeedback(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    # Database/card identity
    database_id: int = Field(..., alias="id", serialization_alias="id")
    anki_note_id: int

    # Provenance
    deck_name: str
    model_name: str

    # Fields that may have been changed by the user in Anki
    question: str
    answer: str
    topic: str = ""

    # Card state in Anki
    suspended: bool = False
    flag: int = 0