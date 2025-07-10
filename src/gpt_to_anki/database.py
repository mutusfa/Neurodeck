import logging
from typing import List, Tuple, Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

LOG = logging.getLogger(__name__)

Base = declarative_base()


class Card(Base):
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
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self.init_database()

    def init_database(self):
        """Initialize the database and create the cards table if it doesn't exist."""
        try:
            Base.metadata.create_all(bind=self.engine)
            LOG.info("Database initialized successfully")
        except Exception as e:
            LOG.error("Error initializing database: %s", e)
            raise

    def save_cards(
        self,
        cards: List[dict],
        context: str,
        evaluations: Optional[dict] = None,
    ):
        """Save cards to the database"""
        if evaluations is None:
            evaluations = {}

        try:
            with self.SessionLocal() as session:
                for idx, card in enumerate(cards):
                    question = card["question"]
                    answer = card["answer"]
                    topic = card["topic"]
                    evaluation = evaluations.get(idx, "not_evaluated")
                    card = Card(
                        question=question,
                        answer=answer,
                        evaluation=evaluation,
                        context=context,
                        topic=topic,
                    )
                    session.add(card)

                session.commit()
                LOG.info("Saved %d cards for context: %s", len(cards), context)
        except Exception as e:
            LOG.error("Error saving cards: %s", e)
            raise

    def load_cards(self, context: str) -> Tuple[List[dict], dict]:
        """Load cards and evaluations for a specific context."""
        try:
            with self.SessionLocal() as session:
                cards_query = (
                    session.query(Card)
                    .filter(Card.context == context)
                    .order_by(Card.id)
                )

                card_records = cards_query.all()
                cards = [
                    {
                        "question": card.question,
                        "answer": card.answer,
                        "topic": card.topic,
                    }
                    for card in card_records
                ]
                evaluations = {
                    i: card.evaluation for i, card in enumerate(card_records)
                }

                LOG.info("Loaded %d cards for context: %s", len(cards), context)
                return cards, evaluations
        except Exception as e:
            LOG.error("Error loading cards: %s", e)
            return [], {}

    def update_card_evaluation(self, context: str, card_index: int, evaluation: str):
        """Update the evaluation for a specific card."""
        try:
            with self.SessionLocal() as session:
                # Get the card at the specific index for this context
                card = (
                    session.query(Card)
                    .filter(Card.context == context)
                    .order_by(Card.id)
                    .offset(card_index)
                    .first()
                )

                if card:
                    card.evaluation = evaluation
                    session.commit()
                    LOG.info(
                        "Updated evaluation for card %d in context %s: %s",
                        card_index,
                        context,
                        evaluation,
                    )
                else:
                    LOG.warning(
                        "Card not found at index %d for context %s", card_index, context
                    )
        except Exception as e:
            LOG.error("Error updating card evaluation: %s", e)

    def get_contexts(self) -> List[str]:
        """Get all unique contexts (file paths) that have cards."""
        try:
            with self.SessionLocal() as session:
                contexts = (
                    session.query(Card.context).distinct().order_by(Card.context).all()
                )
                return [context[0] for context in contexts]
        except Exception as e:
            LOG.error("Error getting contexts: %s", e)
            return []

    def delete_context(self, context: str):
        """Delete all cards for a specific context."""
        try:
            with self.SessionLocal() as session:
                deleted_count = (
                    session.query(Card).filter(Card.context == context).delete()
                )
                session.commit()
                LOG.info("Deleted %d cards for context: %s", deleted_count, context)
        except Exception as e:
            LOG.error("Error deleting context: %s", e)
