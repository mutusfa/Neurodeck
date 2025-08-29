"""Integration tests for Anki feedback synchronization."""
import pytest
import pytest_asyncio
import tempfile
import os
from unittest.mock import patch, AsyncMock

from gpt_to_anki.anki_connect import AnkiConnectDeck
from gpt_to_anki.database import CardDatabase
from gpt_to_anki.anki_models import AnkiNoteFeedback


class TestAnkiSyncIntegration:
    """Integration test suite for Anki feedback synchronization."""

    @pytest_asyncio.fixture
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
    def deck(self):
        """Create an AnkiConnectDeck instance."""
        return AnkiConnectDeck(
            deck_name="TestDeck",
            model_name="TestModel",
            id_field="id",
            field_map={
                "question": "Front",
                "answer": "Back",
                "topic": "Topic",
            },
        )

    @pytest.mark.asyncio
    async def test_full_sync_flow(self, db, deck):
        """Test the complete flow: fetch from Anki -> save to database -> load from database."""
        # Mock AnkiConnect responses
        with patch.object(deck, '_post') as mock_post:
            # Setup mock responses for 3 different cards
            def mock_post_side_effect(action, **params):
                if action == "findNotes":
                    query = params.get("query", "")
                    if "id:1" in query:
                        return [10001]
                    elif "id:2" in query:
                        return [10002]
                    elif "id:3" in query:
                        return []  # Not found in Anki
                    return []
                
                elif action == "notesInfo":
                    note_ids = params.get("notes", [])
                    if 10001 in note_ids:
                        return [{
                            "noteId": 10001,
                            "modelName": "TestModel",
                            "fields": {
                                "Front": {"value": "What is Python?"},
                                "Back": {"value": "A programming language"},
                                "Topic": {"value": "Programming"}
                            }
                        }]
                    elif 10002 in note_ids:
                        return [{
                            "noteId": 10002,
                            "modelName": "TestModel",
                            "fields": {
                                "Front": {"value": "What is async/await?"},
                                "Back": {"value": "Asynchronous programming syntax"},
                                "Topic": {"value": "Python"}
                            }
                        }]
                    return []
                
                elif action == "findCards":
                    query = params.get("query", "")
                    if "id:1" in query:
                        return [20001, 20002]
                    elif "id:2" in query:
                        return [20003]
                    return []
                
                elif action == "cardsInfo":
                    card_ids = params.get("cards", [])
                    if 20001 in card_ids or 20002 in card_ids:
                        return [
                            {"suspended": False, "queue": 1, "flags": 0},
                            {"suspended": True, "queue": -1, "flags": 2}
                        ]
                    elif 20003 in card_ids:
                        return [{"suspended": False, "queue": 2, "flags": 1}]
                    return []
            
            mock_post.side_effect = mock_post_side_effect
            
            # Fetch feedback from Anki
            feedback_list = await deck.aget_feedback_for_database_ids([1, 2, 3])
            
            # Should get 2 results (ID 3 not found in Anki)
            assert len(feedback_list) == 2
            
            # Verify first feedback
            fb1 = next(fb for fb in feedback_list if fb.database_id == 1)
            assert fb1.anki_note_id == 10001
            assert fb1.question == "What is Python?"
            assert fb1.answer == "A programming language"
            assert fb1.topic == "Programming"
            assert fb1.suspended is True  # One card is suspended
            assert fb1.flag == 2  # Max flag value
            
            # Verify second feedback
            fb2 = next(fb for fb in feedback_list if fb.database_id == 2)
            assert fb2.anki_note_id == 10002
            assert fb2.question == "What is async/await?"
            assert fb2.answer == "Asynchronous programming syntax"
            assert fb2.topic == "Python"
            assert fb2.suspended is False
            assert fb2.flag == 1
        
        # Save to database
        await db.asave_anki_feedback(feedback_list)
        
        # Load from database
        loaded = await db.aload_anki_feedback([1, 2, 3])
        assert len(loaded) == 2  # Only 2 were saved
        
        # Verify loaded data matches
        loaded_fb1 = next(fb for fb in loaded if fb.database_id == 1)
        assert loaded_fb1.question == "What is Python?"
        assert loaded_fb1.suspended is True
        
        loaded_fb2 = next(fb for fb in loaded if fb.database_id == 2)
        assert loaded_fb2.question == "What is async/await?"
        assert loaded_fb2.suspended is False
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_sync_with_updates(self, db, deck):
        """Test syncing updates from Anki to existing database records."""
        # Initial feedback
        initial_feedback = [
            AnkiNoteFeedback(
                database_id=1,
                anki_note_id=10001,
                deck_name="TestDeck",
                model_name="TestModel",
                question="Old Question",
                answer="Old Answer",
                topic="Old Topic",
                suspended=False,
                flag=0,
            )
        ]
        await db.asave_anki_feedback(initial_feedback)
        
        # Mock updated data from Anki
        with patch.object(deck, '_post') as mock_post:
            mock_post.side_effect = [
                [10001],  # findNotes
                [{  # notesInfo - user edited in Anki
                    "noteId": 10001,
                    "modelName": "TestModel",
                    "fields": {
                        "Front": {"value": "Updated Question in Anki"},
                        "Back": {"value": "Updated Answer in Anki"},
                        "Topic": {"value": "Updated Topic"}
                    }
                }],
                [20001],  # findCards
                [{  # cardsInfo - user suspended the card
                    "suspended": True,
                    "queue": -1,
                    "flags": 3
                }]
            ]
            
            # Fetch updated feedback
            updated_feedback = await deck.aget_feedback_for_database_ids([1])
            assert len(updated_feedback) == 1
            
            fb = updated_feedback[0]
            assert fb.question == "Updated Question in Anki"
            assert fb.answer == "Updated Answer in Anki"
            assert fb.topic == "Updated Topic"
            assert fb.suspended is True
            assert fb.flag == 3
        
        # Save updates to database
        await db.asave_anki_feedback(updated_feedback)
        
        # Verify updates persisted
        loaded = await db.aload_anki_feedback([1])
        assert len(loaded) == 1
        assert loaded[0].question == "Updated Question in Anki"
        assert loaded[0].suspended is True
        assert loaded[0].flag == 3
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_sync_error_handling(self, deck):
        """Test error handling during sync operations."""
        # Test network error
        with patch.object(deck, '_post') as mock_post:
            mock_post.side_effect = RuntimeError("AnkiConnect error: collection is not available")
            
            feedback = await deck.aget_feedback_for_database_ids([1])
            assert len(feedback) == 0  # Should return empty list on error
        
        await deck.close()

    @pytest.mark.asyncio  
    async def test_sync_mixed_results(self, db, deck):
        """Test syncing when some cards exist in Anki and others don't."""
        # Mock responses where only some IDs exist in Anki
        with patch.object(deck, '_post') as mock_post:
            def mock_post_side_effect(action, **params):
                if action == "findNotes":
                    query = params.get("query", "")
                    if "id:1" in query:
                        return [10001]
                    elif "id:2" in query:
                        return []  # Not in Anki
                    elif "id:3" in query:
                        return [10003]
                    return []
                
                elif action == "notesInfo":
                    note_ids = params.get("notes", [])
                    result = []
                    if 10001 in note_ids:
                        result.append({
                            "noteId": 10001,
                            "fields": {
                                "Front": {"value": "Card 1"},
                                "Back": {"value": "Answer 1"},
                                "Topic": {"value": "Topic 1"}
                            }
                        })
                    if 10003 in note_ids:
                        result.append({
                            "noteId": 10003,
                            "fields": {
                                "Front": {"value": "Card 3"},
                                "Back": {"value": "Answer 3"}, 
                                "Topic": {"value": "Topic 3"}
                            }
                        })
                    return result
                
                elif action == "findCards":
                    return []  # No cards for simplicity
                
                return []
            
            mock_post.side_effect = mock_post_side_effect
            
            # Try to sync 3 IDs, but only 2 exist in Anki
            feedback = await deck.aget_feedback_for_database_ids([1, 2, 3])
            assert len(feedback) == 2
            
            db_ids = [fb.database_id for fb in feedback]
            assert 1 in db_ids
            assert 2 not in db_ids  # Skipped
            assert 3 in db_ids
        
        # Save to database
        await db.asave_anki_feedback(feedback)
        
        # Verify only existing ones saved
        loaded = await db.aload_anki_feedback([1, 2, 3])
        assert len(loaded) == 2
        assert any(fb.database_id == 1 for fb in loaded)
        assert not any(fb.database_id == 2 for fb in loaded)
        assert any(fb.database_id == 3 for fb in loaded)
        
        await deck.close()