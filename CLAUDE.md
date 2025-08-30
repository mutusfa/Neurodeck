# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Neurodeck (gpt-to-anki) is a flashcard generation tool that converts documents (PDF, TXT) or URLs into interactive flashcards using LLMs. It features a Gradio web interface for document upload, card generation, evaluation (like/dislike/seen), and persistent storage via SQLAlchemy.

## Key Commands

### Development Setup
```bash
# Install dependencies using uv
uv install

# Install development dependencies
uv install --group dev

# Run the application
uv run python -m gpt_to_anki.app
# or
uv run gpt-to-anki
```

### Testing and Code Quality
```bash
# Run tests
uv run pytest

# Run async tests  
uv run pytest -v

# Format code with black
uv run black src/

# Check types (if mypy is added later)
uv run mypy src/
```

### Running the Application
- Main entry point: `src/gpt_to_anki/app.py`
- Gradio interface runs on `0.0.0.0:7860` by default
- Application also available via console script: `gpt-to-anki`

## Architecture

### Core Components
1. **app.py** - Main Gradio interface and application state management
2. **cards_generator.py** - DSPy-based LLM card generation using GPT-4o-mini
3. **database.py** - Async SQLAlchemy database layer with SQLite backend
4. **data_objects.py** - Pydantic models (Card class)

### Key Design Patterns
- **Global State Management**: `AppState` class manages document context, cards, and current position
- **Async/Await**: All database operations and LLM calls are async
- **Pydantic Models**: Card objects use Pydantic for validation and serialization
- **DSPy Integration**: Card generation uses DSPy framework with structured LLM calls

### Data Flow
1. Document upload/URL → Text extraction (PDF/TXT parsing)
2. Text → DSPy LLM generation → Card objects (10 cards max)
3. Cards → SQLite database via async SQLAlchemy
4. Gradio UI manages card navigation and evaluation states

### Database Schema
- **cards** table with columns: id, question, answer, evaluation, context, topic
- Context field stores document path/URL for card grouping
- Evaluation states: "not_evaluated", "liked", "disliked", "seen"

### File Structure
```
src/gpt_to_anki/
├── app.py           # Main Gradio app and UI logic
├── cards_generator.py   # DSPy-based card generation
├── database.py      # Async SQLAlchemy database layer  
└── data_objects.py  # Pydantic models
```

## Development Notes
- Uses `uv` for dependency management instead of pip
- SQLite database stored as `cards.db` in working directory
- Media uploads saved to `media/` folder with UUID filenames
- Environment configured for Python 3.11-3.13
- DSPy configured to use GPT-4o-mini with temperature 0.7