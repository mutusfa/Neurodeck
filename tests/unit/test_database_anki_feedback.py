"""Unit tests for anki_feedback database operations."""
import pytest
import tempfile
import os
from datetime import datetime

from gpt_to_anki.database import CardDatabase, AnkiFeedbackRecord
from gpt_to_anki.anki_models import AnkiNoteFeedback


class TestAnkiFeedbackDatabaseOperations:
    """Test suite for anki_feedback database operations."""

    @pytest.fixture
    async def db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        db = CardDatabase(db_path)
        await db.ainit_database()
        yield db
        await db.aclose()
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def sample_feedback(self):
        """Create sample AnkiNoteFeedback objects."""
        return [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="TestDeck1",
                model_name="TestModel1",
                question="Question 1",
                answer="Answer 1",
                topic="Topic 1",
                suspended=False,
                flag=0,
            ),
            AnkiNoteFeedback(
                database_id=2,
                anki_note_id=10002,
                deck_name="TestDeck1",
                model_name="TestModel1",
                question="Question 2",
                answer="Answer 2",
                topic="Topic 2",
                suspended=True,
                flag=1,
            ),
            AnkiNoteFeedback(
                database_id=3,
                anki_note_id=10003,
                deck_name="TestDeck2",
                model_name="TestModel2",
                question="Question 3",
                answer="Answer 3",
                topic="Topic 3",
                suspended=False,
                flag=2,
            ),
        ]

    @pytest.mark.asyncio
    async def test_save_and_load_anki_feedback(self, db, sample_feedback):
        """Test saving and loading AnkiNoteFeedback."""
        # Save feedback
        await db.asave_anki_feedback(sample_feedback)
        
        # Load all feedback
        loaded = await db.aload_anki_feedback([1, 2, 3])
        assert len(loaded) == 3
        
        # Check each feedback is loaded correctly
        for i, fb in enumerate(loaded):
            expected = sample_feedback[i]
            assert fb.database_id == expected.database_id
            assert fb.anki_note_id == expected.anki_note_id
            assert fb.deck_name == expected.deck_name
            assert fb.model_name == expected.model_name
            assert fb.question == expected.question
            assert fb.answer == expected.answer
            assert fb.topic == expected.topic
            assert fb.suspended == expected.suspended
            assert fb.flag == expected.flag

    @pytest.mark.asyncio
    async def test_load_partial_feedback(self, db, sample_feedback):
        """Test loading only some feedback records."""
        await db.asave_anki_feedback(sample_feedback)
        
        # Load only specific IDs
        loaded = await db.aload_anki_feedback([1, 3])
        assert len(loaded) == 2
        assert loaded[0].database_id == 1
        assert loaded[1].database_id == 3

    @pytest.mark.asyncio
    async def test_load_nonexistent_feedback(self, db):
        """Test loading feedback for non-existent database IDs."""
        loaded = await db.aload_anki_feedback([999, 1000])
        assert len(loaded) == 0

    @pytest.mark.asyncio
    async def test_empty_feedback_list(self, db):
        """Test handling empty feedback lists."""
        # Save empty list
        await db.asave_anki_feedback([])  # Should not raise error
        
        # Load empty list
        loaded = await db.aload_anki_feedback([])
        assert loaded == []

    @pytest.mark.asyncio
    async def test_update_existing_feedback(self, db, sample_feedback):
        """Test updating existing feedback records."""
        # Save initial feedback
        await db.asave_anki_feedback(sample_feedback[:2])
        
        # Modify and save again
        modified_feedback = [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="UpdatedDeck",
                model_name="UpdatedModel",
                question="Updated Question 1",
                answer="Updated Answer 1",
                topic="Updated Topic 1",
                suspended=True,  # Changed
                flag=3,  # Changed
            ),
            AnkiNoteFeedback(
                database_id=2,
                anki_note_id=20002,  # Changed
                deck_name="TestDeck1",
                model_name="TestModel1",
                question="Updated Question 2",  # Changed
                answer="Answer 2",
                topic="Topic 2",
                suspended=False,  # Changed
                flag=0,  # Changed
            ),
        ]
        
        await db.asave_anki_feedback(modified_feedback)
        
        # Load and verify updates
        loaded = await db.aload_anki_feedback([1, 2])
        assert len(loaded) == 2
        
        # Check first record
        fb1 = next(fb for fb in loaded if fb.database_id == 1)
        assert fb1.deck_name == "UpdatedDeck"
        assert fb1.model_name == "UpdatedModel"
        assert fb1.question == "Updated Question 1"
        assert fb1.answer == "Updated Answer 1"
        assert fb1.topic == "Updated Topic 1"
        assert fb1.suspended is True
        assert fb1.flag == 3
        
        # Check second record
        fb2 = next(fb for fb in loaded if fb.database_id == 2)
        assert fb2.anki_note_id == 20002
        assert fb2.question == "Updated Question 2"
        assert fb2.suspended is False
        assert fb2.flag == 0

    @pytest.mark.asyncio
    async def test_mixed_insert_update(self, db, sample_feedback):
        """Test mixed insert and update operations."""
        # Save initial feedback
        await db.asave_anki_feedback([sample_feedback[0]])
        
        # Save mix of existing and new
        mixed_feedback = [
            AnkiNoteFeedback(
                database_id=1,  # Existing
                anki_note_id=10001,
                deck_name="UpdatedDeck",
                model_name="TestModel1",
                question="Updated Q1",
                answer="Answer 1",
                topic="Topic 1",
                suspended=True,
                flag=1,
            ),
            sample_feedback[1],  # New
            sample_feedback[2],  # New
        ]
        
        await db.asave_anki_feedback(mixed_feedback)
        
        # Verify all are saved
        loaded = await db.aload_anki_feedback([1, 2, 3])
        assert len(loaded) == 3
        
        # Verify update
        fb1 = next(fb for fb in loaded if fb.database_id == 1)
        assert fb1.deck_name == "UpdatedDeck"
        assert fb1.question == "Updated Q1"
        assert fb1.suspended is True

    @pytest.mark.asyncio
    async def test_database_not_initialized(self):
        """Test operations on uninitialized database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        db = CardDatabase(db_path)
        # Don't call ainit_database()
        
        feedback = [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="Test",
                model_name="Test",
                question="Q",
                answer="A",
                topic="T",
                suspended=False,
                flag=0,
            )
        ]
        
        # Operations should still work (ainit_database called internally)
        await db.asave_anki_feedback(feedback)
        loaded = await db.aload_anki_feedback([1])
        assert len(loaded) == 1
        
        await db.aclose()
        os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_updated_at_timestamp(self, db):
        """Test that updated_at timestamp is set correctly."""
        feedback = AnkiNoteFeedback(
            database_id=1,
            anki_note_id=10001,
            deck_name="Test",
            model_name="Test",
            question="Q",
            answer="A",
            topic="T",
            suspended=False,
            flag=0,
        )
        
        # Save and check timestamp
        before_save = datetime.utcnow()
        await db.asave_anki_feedback([feedback])
        
        # Query directly to check timestamp
        async with db.async_session() as session:
            from sqlalchemy import select
            stmt = select(AnkiFeedbackRecord).where(AnkiFeedbackRecord.database_id == 1)
            result = await session.execute(stmt)
            record = result.scalar_one()
            
            assert record.updated_at is not None
            assert record.updated_at >= before_save