from typing import List

from gpt_to_anki.anki_base import AbstractAnkiDeck
from gpt_to_anki.database import CardDatabase


async def sync_feedback_for_context(
    deck: AbstractAnkiDeck, db: CardDatabase, context: str
) -> int:
    """Fetch feedback from Anki for all cards in a context and persist it.

    Returns number of feedback rows saved.
    """
    cards = await db.aload_cards(context)
    if not cards:
        return 0

    database_ids: List[int] = [c.database_id for c in cards if c.database_id is not None]
    if not database_ids:
        return 0

    feedback = await deck.aget_feedback_for_database_ids(database_ids)
    if not feedback:
        return 0

    await db.asave_anki_feedback(feedback)
    return len(feedback)