"""Unit tests for AnkiDeck abstract interface."""
import pytest
from typing import List

from gpt_to_anki.anki_base import AbstractAnkiDeck
from gpt_to_anki.anki_models import AnkiNoteFeedback


class MockAnkiDeck(AbstractAnkiDeck):
    """Mock implementation of AbstractAnkiDeck for testing."""
    
    def __init__(self, feedback_data: List[AnkiNoteFeedback]):
        self.feedback_data = feedback_data
        self.call_count = 0
    
    async def aget_feedback_for_database_ids(
        self, database_ids: List[int]
    ) -> List[AnkiNoteFeedback]:
        """Return mock feedback data."""
        self.call_count += 1
        return [f for f in self.feedback_data if f.database_id in database_ids]


class TestAbstractAnkiDeck:
    """Test suite for AbstractAnkiDeck interface."""
    
    def test_abstract_class_cannot_be_instantiated(self):
        """Test that AbstractAnkiDeck cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractAnkiDeck()
    
    @pytest.mark.asyncio
    async def test_mock_implementation(self):
        """Test that mock implementation works correctly."""
        feedback1 = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q1",
            answer="A1",
            topic="T1",
            suspended=False,
            flag=0
        )
        feedback2 = AnkiNoteFeedback(
            database_id=2,
            anki_note_id=10002,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q2",
            answer="A2",
            topic="T2",
            suspended=True,
            flag=1
        )
        
        mock_deck = MockAnkiDeck([feedback1, feedback2])
        
        # Test getting all feedback
        results = await mock_deck.aget_feedback_for_database_ids([1, 2])
        assert len(results) == 2
        assert results[0] == feedback1
        assert results[1] == feedback2
        
        # Test getting partial feedback
        results = await mock_deck.aget_feedback_for_database_ids([1])
        assert len(results) == 1
        assert results[0] == feedback1
        
        # Test getting no feedback
        results = await mock_deck.aget_feedback_for_database_ids([3, 4])
        assert len(results) == 0
        
        # Verify method was called
        assert mock_deck.call_count == 3