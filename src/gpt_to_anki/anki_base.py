from abc import ABC, abstractmethod
from typing import List

from gpt_to_anki.anki_models import AnkiNoteFeedback


class AbstractAnkiDeck(ABC):
    @abstractmethod
    async def aget_feedback_for_database_ids(
        self, database_ids: List[int]
    ) -> List[AnkiNoteFeedback]:
        """Fetch latest Anki-side note fields and card state for given database ids."""
        raise NotImplementedError