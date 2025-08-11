import asyncio
from typing import Dict, List, Optional

import requests

from gpt_to_anki.anki_base import AbstractAnkiDeck
from gpt_to_anki.anki_models import AnkiNoteFeedback


class AnkiConnectDeck(AbstractAnkiDeck):
    def __init__(
        self,
        deck_name: str,
        model_name: str,
        id_field: str = "id",
        field_map: Optional[Dict[str, str]] = None,
        endpoint: str = "http://127.0.0.1:8765",
    ) -> None:
        self.deck_name = deck_name
        self.model_name = model_name
        self.id_field = id_field
        self.field_map = field_map or {
            "question": "Question",
            "answer": "Answer",
            "topic": "Topic",
        }
        self.endpoint = endpoint

    def _post(self, action: str, **params):
        payload = {"action": action, "version": 6, "params": params}
        response = requests.post(self.endpoint, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise RuntimeError(f"AnkiConnect error: {data['error']}")
        return data.get("result")

    def _build_search_for_id(self, db_id: int) -> str:
        # Restrict by deck, note type and match the id field
        return f'deck:"{self.deck_name}" note:"{self.model_name}" {self.id_field}:{db_id}'

    def _fetch_single_feedback(self, db_id: int) -> Optional[AnkiNoteFeedback]:
        query = self._build_search_for_id(db_id)

        note_ids = self._post("findNotes", query=query) or []
        if not note_ids:
            return None

        # Take first note (should be unique by id field)
        notes = self._post("notesInfo", notes=note_ids) or []
        if not notes:
            return None

        note = notes[0]
        fields = note.get("fields", {})

        def get_field(key: str) -> str:
            name = self.field_map.get(key, key)
            value_obj = fields.get(name) or {}
            return value_obj.get("value", "")

        # Determine suspended/flag from cards
        card_ids = self._post("findCards", query=query) or []
        suspended = False
        flag = 0
        if card_ids:
            cards = self._post("cardsInfo", cards=card_ids) or []
            for card in cards:
                # Either explicit suspended, or queue == -1
                if card.get("suspended") or card.get("queue") == -1:
                    suspended = True
                try:
                    flag_value = int(card.get("flags", 0) or 0)
                except Exception:
                    flag_value = 0
                flag = max(flag, flag_value)

        return AnkiNoteFeedback(
            id=db_id,
            anki_note_id=note.get("noteId"),
            deck_name=self.deck_name,
            model_name=note.get("modelName", self.model_name),
            question=get_field("question"),
            answer=get_field("answer"),
            topic=get_field("topic"),
            suspended=suspended,
            flag=flag,
        )

    async def aget_feedback_for_database_ids(
        self, database_ids: List[int]
    ) -> List[AnkiNoteFeedback]:
        tasks = [asyncio.to_thread(self._fetch_single_feedback, db_id) for db_id in database_ids]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]