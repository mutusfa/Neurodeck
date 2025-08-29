"""Unit tests for AnkiNoteFeedback model."""
import pytest
from pydantic import ValidationError

from gpt_to_anki.anki_models import AnkiNoteFeedback


class TestAnkiNoteFeedback:
    """Test suite for AnkiNoteFeedback model."""

    def test_create_with_all_fields(self):
        """Test creating AnkiNoteFeedback with all fields."""
        feedback = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Test Question",
            answer="Test Answer",
            topic="Test Topic",
            suspended=True,
            flag=2,
        )
        
        assert feedback.database_id == 1
        assert feedback.anki_note_id == 10001
        assert feedback.deck_name == "TestDeck"
        assert feedback.model_name == "TestModel"
        assert feedback.question == "Test Question"
        assert feedback.answer == "Test Answer"
        assert feedback.topic == "Test Topic"
        assert feedback.suspended is True
        assert feedback.flag == 2

    def test_create_with_defaults(self):
        """Test creating AnkiNoteFeedback with default values."""
        feedback = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Question",
            answer="Answer",
            # topic, suspended, and flag should use defaults
        )
        
        assert feedback.topic == ""
        assert feedback.suspended is False
        assert feedback.flag == 0

    def test_alias_support(self):
        """Test that 'id' alias works for database_id."""
        # Test creation with alias
        feedback = AnkiNoteFeedback(
            id=123,  # Using alias
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q",
            answer="A",
        )
        
        assert feedback.database_id == 123
        
        # Test serialization uses alias
        data = feedback.model_dump(mode='json', by_alias=True)
        assert data["id"] == 123
        assert "database_id" not in data

    def test_from_orm_attributes(self):
        """Test creating from ORM-like object."""
        class MockORMObject:
            database_id = 1
            anki_note_id = 10001
            deck_name = "TestDeck"
            model_name = "TestModel"
            question = "Q"
            answer = "A"
            topic = "T"
            suspended = True
            flag = 1
        
        feedback = AnkiNoteFeedback.model_validate(MockORMObject())
        assert feedback.database_id == 1
        assert feedback.suspended is True

    def test_validation_errors(self):
        """Test validation errors for required fields."""
        # Missing required fields
        with pytest.raises(ValidationError) as exc_info:
            AnkiNoteFeedback(
                database_id=1,
                # Missing anki_note_id and other required fields
            )
        
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("anki_note_id",) for e in errors)
        assert any(e["loc"] == ("deck_name",) for e in errors)

    def test_model_dump_json(self):
        """Test JSON serialization."""
        feedback = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q",
            answer="A",
            topic="T",
            suspended=True,
            flag=1,
        )
        
        # Test with alias
        json_data = feedback.model_dump(mode='json', by_alias=True)
        assert json_data["id"] == 1
        assert json_data["suspended"] is True
        assert json_data["flag"] == 1
        
        # Test without alias
        json_data = feedback.model_dump(mode='json', by_alias=False)
        assert json_data["database_id"] == 1

    def test_equality(self):
        """Test equality comparison between AnkiNoteFeedback instances."""
        feedback1 = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q",
            answer="A",
        )
        
        feedback2 = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q",
            answer="A",
        )
        
        feedback3 = AnkiNoteFeedback(
            database_id=2,  # Different ID
            anki_note_id=10001,
            deck_name="TestDeck",
            model_name="TestModel",
            question="Q",
            answer="A",
        )
        
        assert feedback1 == feedback2
        assert feedback1 != feedback3