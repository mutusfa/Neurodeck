import logging
from typing import List
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select, delete

from gpt_to_anki.data_objects import Card

LOG = logging.getLogger(__name__)

Base = declarative_base()


class CardRecord(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
    evaluation = Column(String, default="not_evaluated")
    context = Column(String, nullable=False)
    topic = Column(String, nullable=False)


class CardDatabase:
    def __init__(self, db_path: str = "cards.db"):
        self.db_path = db_path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        self._initialized = False

    async def ainit_database(self):
        """Initialize the database and create the cards table if it doesn't exist."""
        if self._initialized:
            return

        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            self._initialized = True
            LOG.info("Database initialized successfully")
        except Exception as e:
            LOG.error("Error initializing database: %s", e)
            raise

    async def asave_cards(self, cards: List[Card]) -> List[Card]:
        """Save cards to the database and return updated cards with database IDs."""
        try:
            async with self.async_session() as session:
                # Get all database IDs for existing cards
                existing_ids = [
                    card.database_id for card in cards if card.database_id is not None
                ]

                # Fetch all existing cards in one query
                existing_cards_map = {}
                if existing_ids:
                    stmt = select(CardRecord).where(CardRecord.id.in_(existing_ids))
                    result = await session.execute(stmt)
                    existing_cards = result.scalars().all()
                    existing_cards_map = {card.id: card for card in existing_cards}

                card_records = []
                for card in cards:
                    if card.database_id in existing_cards_map:
                        # Update existing card
                        existing_card = existing_cards_map[card.database_id]
                        card_data = card.model_dump(
                            exclude_defaults=True, exclude={"database_id"}
                        )
                        for key, value in card_data.items():
                            setattr(existing_card, key, value)
                        card_records.append(existing_card)
                    else:
                        # Create new card
                        new_card_obj = CardRecord(
                            **card.model_dump(
                                exclude_defaults=True, exclude={"database_id"}
                            )
                        )
                        session.add(new_card_obj)
                        card_records.append(new_card_obj)

                await session.commit()

            updated_cards = []
            for i, card_record in enumerate(card_records):
                updated_card = cards[i].model_copy()
                updated_card.database_id = card_record.id
                updated_cards.append(updated_card)

            LOG.info("Saved %d cards", len(cards))
            return updated_cards
        except Exception as e:
            LOG.error("Error saving cards: %s", e)
            raise

    async def aload_cards(self, context: str) -> List[Card]:
        """Load cards and evaluations for a specific context."""
        try:
            async with self.async_session() as session:
                stmt = (
                    select(CardRecord)
                    .where(CardRecord.context == context)
                    .order_by(CardRecord.id)
                )
                result = await session.execute(stmt)
                card_records = result.scalars().all()

                cards = [Card.model_validate(card_orm) for card_orm in card_records]
                for card in cards:
                    card.context = context

                LOG.info("Loaded %d cards for context: %s", len(cards), context)
                return cards
        except Exception as e:
            LOG.error("Error loading cards: %s", e)
            return []

    async def aget_contexts(self) -> List[str]:
        """Get all unique contexts (file paths) that have cards."""
        try:
            async with self.async_session() as session:
                stmt = (
                    select(CardRecord.context).distinct().order_by(CardRecord.context)
                )
                result = await session.execute(stmt)
                contexts = result.scalars().all()
                return list(contexts)
        except Exception as e:
            LOG.error("Error getting contexts: %s", e)
            return []

    async def adelete_context(self, context: str):
        """Delete all cards for a specific context."""
        try:
            async with self.async_session() as session:
                delete_stmt = delete(CardRecord).where(CardRecord.context == context)
                result = await session.execute(delete_stmt)
                await session.commit()
                LOG.info("Deleted %d cards for context: %s", result.rowcount, context)
        except Exception as e:
            LOG.error("Error deleting context: %s", e)

    async def aclear_all_cards(self):
        """Delete all cards from the database."""
        await self.init_database()

        try:
            async with self.async_session() as session:
                delete_stmt = delete(CardRecord)
                result = await session.execute(delete_stmt)
                await session.commit()
                LOG.info("Deleted all %d cards from database", result.rowcount)
        except Exception as e:
            LOG.error("Error clearing all cards: %s", e)

    async def aclose(self):
        """Close the database connection."""
        await self.engine.dispose()
        LOG.info("Database connection closed")
