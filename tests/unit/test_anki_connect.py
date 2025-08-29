"""Unit tests for AnkiConnectDeck class."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp

from gpt_to_anki.anki_connect import AnkiConnectDeck
from gpt_to_anki.anki_models import AnkiNoteFeedback


class TestAnkiConnectDeck:
    """Test suite for AnkiConnectDeck class."""

    @pytest.fixture
    def deck(self):
        """Create an AnkiConnectDeck instance for testing."""
        return AnkiConnectDeck(
            deck_name="TestDeck",
            model_name="TestModel",
            id_field="id",
            field_map={
                "question": "Front",
                "answer": "Back",
                "topic": "Topic",
            },
            endpoint="http://127.0.0.1:8765",
        )

    @pytest.mark.asyncio
    async def test_init(self, deck):
        """Test AnkiConnectDeck initialization."""
        assert deck.deck_name == "TestDeck"
        assert deck.model_name == "TestModel"
        assert deck.id_field == "id"
        assert deck.field_map["question"] == "Front"
        assert deck.field_map["answer"] == "Back"
        assert deck.field_map["topic"] == "Topic"
        assert deck.endpoint == "http://127.0.0.1:8765"
        assert deck._session is None

    @pytest.mark.asyncio
    async def test_ensure_session(self, deck):
        """Test _ensure_session creates a session when needed."""
        session = await deck._ensure_session()
        assert isinstance(session, aiohttp.ClientSession)
        assert deck._session is session
        
        # Test it returns existing session
        session2 = await deck._ensure_session()
        assert session2 is session
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, deck):
        """Test async context manager functionality."""
        async with deck as d:
            assert d is deck
            assert deck._session is not None
            assert not deck._session.closed
        
        # Session should be closed after context exit
        assert deck._session.closed

    @pytest.mark.asyncio
    async def test_post_success(self, deck):
        """Test successful _post method."""
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"result": "test_result", "error": None})
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(aiohttp.ClientSession, 'post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await deck._post("testAction", param1="value1")
            
            assert result == "test_result"
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://127.0.0.1:8765"
            assert call_args[1]["json"]["action"] == "testAction"
            assert call_args[1]["json"]["version"] == 6
            assert call_args[1]["json"]["params"]["param1"] == "value1"
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_post_error(self, deck):
        """Test _post method with AnkiConnect error."""
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"result": None, "error": "Test error"})
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(aiohttp.ClientSession, 'post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(RuntimeError, match="AnkiConnect error: Test error"):
                await deck._post("testAction")
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_post_http_error(self, deck):
        """Test _post method with HTTP error."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("HTTP Error"))
        
        with patch.object(aiohttp.ClientSession, 'post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(aiohttp.ClientError):
                await deck._post("testAction")
        
        await deck.close()

    def test_build_search_for_id(self, deck):
        """Test _build_search_for_id method."""
        query = deck._build_search_for_id(123)
        assert query == 'deck:"TestDeck" note:"TestModel" id:123'

    @pytest.mark.asyncio
    async def test_fetch_single_feedback_success(self, deck):
        """Test successful _fetch_single_feedback."""
        # Mock the _post responses
        with patch.object(deck, '_post') as mock_post:
            # Setup mock responses for each call
            mock_post.side_effect = [
                [12345],  # findNotes response
                [{  # notesInfo response
                    "noteId": 12345,
                    "modelName": "TestModel",
                    "fields": {
                        "Front": {"value": "Test question"},
                        "Back": {"value": "Test answer"},
                        "Topic": {"value": "Test topic"}
                    }
                }],
                [54321, 54322],  # findCards response
                [{  # cardsInfo response
                    "suspended": False,
                    "queue": 1,
                    "flags": 2
                }, {
                    "suspended": True,
                    "queue": -1,
                    "flags": 1
                }]
            ]
            
            result = await deck._fetch_single_feedback(123)
            
            assert isinstance(result, AnkiNoteFeedback)
            assert result.database_id == 123
            assert result.anki_note_id == 12345
            assert result.deck_name == "TestDeck"
            assert result.model_name == "TestModel"
            assert result.question == "Test question"
            assert result.answer == "Test answer"
            assert result.topic == "Test topic"
            assert result.suspended is True  # One card is suspended
            assert result.flag == 2  # Max flag value
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_fetch_single_feedback_no_note(self, deck):
        """Test _fetch_single_feedback when note is not found."""
        with patch.object(deck, '_post') as mock_post:
            mock_post.return_value = []  # Empty findNotes response
            
            result = await deck._fetch_single_feedback(123)
            assert result is None
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_fetch_single_feedback_no_cards(self, deck):
        """Test _fetch_single_feedback when no cards exist."""
        with patch.object(deck, '_post') as mock_post:
            mock_post.side_effect = [
                [12345],  # findNotes
                [{  # notesInfo
                    "noteId": 12345,
                    "fields": {
                        "Front": {"value": "Question"},
                        "Back": {"value": "Answer"},
                        "Topic": {"value": "Topic"}
                    }
                }],
                [],  # No cards found
            ]
            
            result = await deck._fetch_single_feedback(123)
            
            assert result is not None
            assert result.suspended is False
            assert result.flag == 0
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_aget_feedback_for_database_ids(self, deck):
        """Test aget_feedback_for_database_ids method."""
        # Create mock feedback objects
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
        
        with patch.object(deck, '_fetch_single_feedback') as mock_fetch:
            mock_fetch.side_effect = [feedback1, None, feedback2]  # Second ID returns None
            
            results = await deck.aget_feedback_for_database_ids([1, 2, 3])
            
            assert len(results) == 2  # None is filtered out
            assert results[0] == feedback1
            assert results[1] == feedback2
            
            # Verify all IDs were queried
            assert mock_fetch.call_count == 3
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_field_map_defaults(self):
        """Test default field mapping."""
        deck = AnkiConnectDeck(
            deck_name="Test",
            model_name="Test",
        )
        
        assert deck.field_map["question"] == "Question"
        assert deck.field_map["answer"] == "Answer"
        assert deck.field_map["topic"] == "Topic"
        
        await deck.close()

    @pytest.mark.asyncio
    async def test_invalid_flag_handling(self, deck):
        """Test handling of invalid flag values."""
        with patch.object(deck, '_post') as mock_post:
            mock_post.side_effect = [
                [12345],  # findNotes
                [{  # notesInfo
                    "noteId": 12345,
                    "fields": {"Front": {"value": "Q"}, "Back": {"value": "A"}}
                }],
                [54321],  # findCards
                [{  # cardsInfo with invalid flag
                    "suspended": False,
                    "flags": "invalid"  # Non-integer flag
                }]
            ]
            
            result = await deck._fetch_single_feedback(123)
            assert result.flag == 0  # Should default to 0
        
        await deck.close()