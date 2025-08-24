"""Unit tests for anki_sync module."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from gpt_to_anki.anki_sync import sync_feedback_for_context
from gpt_to_anki.anki_base import AbstractAnkiDeck
from gpt_to_anki.database import CardDatabase
from gpt_to_anki.data_objects import Card
from gpt_to_anki.anki_models import AnkiNoteFeedback


class TestAnkiSync:
    """Test suite for anki_sync functions."""

    @pytest.fixture
    def mock_deck(self):
        """Create a mock AnkiDeck."""
        deck = MagicMock(spec=AbstractAnkiDeck)
        deck.aget_feedback_for_database_ids = AsyncMock()
        return deck

    @pytest.fixture
    def mock_db(self):
        """Create a mock CardDatabase."""
        db = MagicMock(spec=CardDatabase)
        db.aload_cards = AsyncMock()
        db.asave_anki_feedback = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_sync_feedback_success(self, mock_deck, mock_db):
        """Test successful feedback sync for a context."""
        # Mock cards in the database
        cards = [
            Card(
                database_id=1,
                question="Q1",
                answer="A1",
                context="test_context",
                topic="Topic1",
                evaluation="good"
            ),
            Card(
                database_id=2,
                question="Q2",
                answer="A2",
                context="test_context",
                topic="Topic2",
                evaluation="good"
            ),
        ]
        mock_db.aload_cards.return_value = cards

        # Mock feedback from Anki
        feedback = [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="TestDeck",
                model_name="TestModel",
                question="Q1 Updated",
                answer="A1 Updated",
                topic="Topic1",
                suspended=True,
                flag=1
            ),
            AnkiNoteFeedback(
                database_id=2,
                anki_note_id=10002,
                deck_name="TestDeck",
                model_name="TestModel",
                question="Q2",
                answer="A2",
                topic="Topic2",
                suspended=False,
                flag=0
            ),
        ]
        mock_deck.aget_feedback_for_database_ids.return_value = feedback

        # Run sync
        result = await sync_feedback_for_context(mock_deck, mock_db, "test_context")

        # Verify
        assert result == 2
        mock_db.aload_cards.assert_called_once_with("test_context")
        mock_deck.aget_feedback_for_database_ids.assert_called_once_with([1, 2])
        mock_db.asave_anki_feedback.assert_called_once_with(feedback)

    @pytest.mark.asyncio
    async def test_sync_feedback_no_cards(self, mock_deck, mock_db):
        """Test sync when no cards exist for context."""
        mock_db.aload_cards.return_value = []

        result = await sync_feedback_for_context(mock_deck, mock_db, "empty_context")

        assert result == 0
        mock_db.aload_cards.assert_called_once_with("empty_context")
        mock_deck.aget_feedback_for_database_ids.assert_not_called()
        mock_db.asave_anki_feedback.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_feedback_cards_without_ids(self, mock_deck, mock_db):
        """Test sync when cards don't have database IDs."""
        cards = [
            Card(
                database_id=None,  # No ID
                question="Q1",
                answer="A1",
                context="test_context",
                topic="Topic1",
                evaluation="good"
            ),
        ]
        mock_db.aload_cards.return_value = cards

        result = await sync_feedback_for_context(mock_deck, mock_db, "test_context")

        assert result == 0
        mock_deck.aget_feedback_for_database_ids.assert_not_called()
        mock_db.asave_anki_feedback.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_feedback_no_anki_feedback(self, mock_deck, mock_db):
        """Test sync when Anki returns no feedback."""
        cards = [
            Card(
                database_id=1,
                question="Q1",
                answer="A1",
                context="test_context",
                topic="Topic1",
                evaluation="good"
            ),
        ]
        mock_db.aload_cards.return_value = cards
        mock_deck.aget_feedback_for_database_ids.return_value = []

        result = await sync_feedback_for_context(mock_deck, mock_db, "test_context")

        assert result == 0
        mock_db.asave_anki_feedback.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_feedback_partial_results(self, mock_deck, mock_db):
        """Test sync when only some cards have feedback in Anki."""
        cards = [
            Card(database_id=1, question="Q1", answer="A1", context="test", topic="T1", evaluation="good"),
            Card(database_id=2, question="Q2", answer="A2", context="test", topic="T2", evaluation="good"),
            Card(database_id=3, question="Q3", answer="A3", context="test", topic="T3", evaluation="good"),
        ]
        mock_db.aload_cards.return_value = cards

        # Only feedback for cards 1 and 3
        feedback = [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="TestDeck",
                model_name="TestModel",
                question="Q1",
                answer="A1",
                topic="T1",
            ),
            AnkiNoteFeedback(
                database_id=3,
                anki_note_id=10003,
                deck_name="TestDeck",
                model_name="TestModel",
                question="Q3",
                answer="A3",
                topic="T3",
            ),
        ]
        mock_deck.aget_feedback_for_database_ids.return_value = feedback

        result = await sync_feedback_for_context(mock_deck, mock_db, "test")

        assert result == 2
        mock_deck.aget_feedback_for_database_ids.assert_called_once_with([1, 2, 3])
        mock_db.asave_anki_feedback.assert_called_once_with(feedback)

    @pytest.mark.asyncio
    async def test_sync_feedback_mixed_ids(self, mock_deck, mock_db):
        """Test sync with mix of cards with and without database IDs."""
        cards = [
            Card(database_id=1, question="Q1", answer="A1", context="test", topic="T1", evaluation="good"),
            Card(database_id=None, question="Q2", answer="A2", context="test", topic="T2", evaluation="good"),
            Card(database_id=3, question="Q3", answer="A3", context="test", topic="T3", evaluation="good"),
        ]
        mock_db.aload_cards.return_value = cards

        feedback = [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="TestDeck",
                model_name="TestModel",
                question="Q1",
                answer="A1",
                topic="T1",
            ),
        ]
        mock_deck.aget_feedback_for_database_ids.return_value = feedback

        result = await sync_feedback_for_context(mock_deck, mock_db, "test")

        assert result == 1
        # Should only query for cards with IDs
        mock_deck.aget_feedback_for_database_ids.assert_called_once_with([1, 3])
        mock_db.asave_anki_feedback.assert_called_once_with(feedback)