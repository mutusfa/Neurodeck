from io import BytesIO
import logging
import os
import uuid
from typing import Callable
from PyPDF2 import PdfReader
import requests

import streamlit as st

from gpt_to_anki.cards_generator import CardGenerator
from gpt_to_anki.database import CardDatabase

LOG = logging.getLogger(__name__)


def init_session_state():
    st.session_state.setdefault("document", None)
    st.session_state.setdefault("document_context", None)
    st.session_state.setdefault("local_file_path", None)
    st.session_state.setdefault("document_url", None)
    st.session_state.setdefault("document_key", None)  # Either file path or URL
    st.session_state.setdefault("cards", None)
    st.session_state.setdefault("card_generator", CardGenerator())
    st.session_state.setdefault("current_card_index", 0)
    st.session_state.setdefault("card_evaluations", {})
    st.session_state.setdefault("db", CardDatabase())


def get_card_evaluation(card_index):
    """Get the evaluation state for a card."""
    return st.session_state.card_evaluations.get(card_index, "not_evaluated")


def set_card_evaluation(card_index, evaluation, on_interaction=None):
    """Set the evaluation state for a card."""
    # Only call callback if evaluation actually changed
    old_evaluation = st.session_state.card_evaluations.get(card_index, "not_evaluated")
    if old_evaluation != evaluation:
        st.session_state.card_evaluations[card_index] = evaluation
        # Auto-save to database when evaluation changes
        if st.session_state.document_key:
            st.session_state.db.update_card_evaluation(
                st.session_state.document_key, card_index, evaluation
            )
        if on_interaction:
            on_interaction()
    else:
        st.session_state.card_evaluations[card_index] = evaluation


def mark_card_as_seen(card_index, on_interaction=None):
    """Mark a card as seen if it hasn't been evaluated yet."""
    current_eval = get_card_evaluation(card_index)
    if current_eval == "not_evaluated":
        set_card_evaluation(card_index, "seen", on_interaction)


def advance_to_next_card():
    """Advance to the next card and rerun the app."""
    total_cards = len(st.session_state.cards)
    current_index = st.session_state.current_card_index
    if current_index < total_cards - 1:
        st.session_state.current_card_index = current_index + 1
        st.rerun()


def clear_card_evaluations():
    """Clear all card evaluations."""
    st.session_state.card_evaluations = {}


def get_evaluation_emoji(evaluation):
    """Get emoji representation of evaluation state."""
    match evaluation:
        case "liked":
            return "👍"
        case "disliked":
            return "👎"
        case "seen":
            return "👀"
        case "not_evaluated":
            return "❓"
        case _:
            return "❓"


def save_uploaded_file(uploaded_file):
    """Save uploaded file to media folder with UUID-based filename."""
    # Create media folder if it doesn't exist
    media_folder = "media"
    os.makedirs(media_folder, exist_ok=True)

    # Generate UUID for file uniqueness
    file_uuid = str(uuid.uuid4())

    # Get file extension
    file_extension = os.path.splitext(uploaded_file.name)[1]

    # Create unique filename
    unique_filename = f"{file_uuid}{file_extension}"
    file_path = os.path.join(media_folder, unique_filename)

    # Save the file
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    LOG.info("File saved to: %s", file_path)
    return file_path


def fetch_url_content(url):
    """Fetch content from URL."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Try to determine content type
        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type:
            pdf_bytes = BytesIO(response.content)
            reader = PdfReader(pdf_bytes)
            return "\n".join(page.extract_text() for page in reader.pages)
        elif "text" in content_type:
            return response.text
        else:
            # Try to decode as text for unknown content types
            return response.text

    except Exception as e:
        raise ValueError(f"Failed to fetch URL content: {str(e)}")


def read_document(file):
    match file.type:
        case "application/pdf":
            reader = PdfReader(file)
            return "\n".join(page.extract_text() for page in reader.pages)
        case "text/plain":
            return file.read().decode("utf-8")
        case _:
            raise ValueError(f"Unsupported file type: {file.type}")


def process_document(file=None, url=None):
    """Process either a file or URL."""
    if file is not None:
        LOG.info("Document uploaded: %s", file)
        st.session_state.document = file
        st.session_state.document_url = None
        # Save file to media folder and store local path
        local_file_path = save_uploaded_file(file)
        st.session_state.local_file_path = local_file_path
        st.session_state.document_key = local_file_path
        text = read_document(file)
        st.session_state.document_context = text
    elif url is not None:
        LOG.info("Processing URL: %s", url)
        st.session_state.document = None
        st.session_state.document_url = url
        st.session_state.local_file_path = None
        st.session_state.document_key = url
        text = fetch_url_content(url)

        st.session_state.document_context = text
    else:
        raise ValueError("Either file or URL must be provided")
    LOG.info("Document context: %s", text[:200] + "..." if len(text) > 200 else text)

    # Check if cards already exist for this document in database
    existing_cards, existing_evaluations = st.session_state.db.load_cards(
        st.session_state.document_key
    )

    if existing_cards:
        LOG.info("Loading existing cards from database...")
        st.session_state.cards = existing_cards
        st.session_state.card_evaluations = existing_evaluations
        st.session_state.current_card_index = 0
    else:
        LOG.info("Generating new cards...")
        qa_cards = st.session_state.card_generator.generate_cards(context=text).qa
        topic = st.session_state.card_generator.generate_cards(context=text).topic
        st.session_state.cards = [
            {"question": qa[0], "answer": qa[1], "topic": topic} for qa in qa_cards
        ]
        # Reset evaluations when new cards are generated
        clear_card_evaluations()
        # Save new cards to database
        autosave_cards()


def autosave_cards():
    """Auto-save cards and evaluations to database."""
    if st.session_state.cards and st.session_state.document_key:
        st.session_state.db.save_cards(
            st.session_state.cards,
            st.session_state.document_key,
            st.session_state.card_evaluations,
        )


def card_navigation(on_interaction: Callable = lambda: None):
    st.subheader("Flashcards")
    current_index = st.session_state.current_card_index
    total_cards = len(st.session_state.cards)
    st.write(f"Card {current_index + 1} of {total_cards}")

    # Mark current card as seen
    mark_card_as_seen(current_index, on_interaction=on_interaction)

    # Get current card and its evaluation
    current_card = st.session_state.cards[current_index]
    question = current_card["question"]
    answer = current_card["answer"]
    topic = current_card["topic"]
    current_evaluation = get_card_evaluation(current_index)
    evaluation_emoji = get_evaluation_emoji(current_evaluation)

    # Display current evaluation status
    st.write(
        f"**Status:** {evaluation_emoji} {current_evaluation.replace('_', ' ').title()}"
    )

    st.write(f"**Topic:** {topic}")

    # Display question
    st.write("**Question:**")
    st.write(question)

    st.write("**Answer:**")
    st.write(answer)

    # Like/Dislike buttons
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        if st.button("👍 Like", key=f"like_{current_index}"):
            set_card_evaluation(current_index, "liked", on_interaction=on_interaction)
            advance_to_next_card()

    with col2:
        if st.button("👎 Dislike", key=f"dislike_{current_index}"):
            set_card_evaluation(
                current_index, "disliked", on_interaction=on_interaction
            )
            advance_to_next_card()

    st.write("---")

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("Previous", disabled=current_index == 0):
            st.session_state.current_card_index = max(0, current_index - 1)
            st.rerun()

    with col2:
        if st.button("Reset Cards"):
            st.session_state.current_card_index = 0
            st.rerun()

    with col3:
        if st.button("Next", disabled=current_index == total_cards - 1):
            st.session_state.current_card_index = min(
                total_cards - 1, current_index + 1
            )
            st.rerun()

    # Show evaluation summary
    st.write("---")
    st.subheader("Evaluation Summary")

    # Count evaluations
    eval_counts = {"liked": 0, "disliked": 0, "seen": 0, "not_evaluated": 0}
    for i in range(total_cards):
        eval_state = get_card_evaluation(i)
        eval_counts[eval_state] += 1

    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("👍 Liked", eval_counts["liked"])
    with col2:
        st.metric("👎 Disliked", eval_counts["disliked"])
    with col3:
        st.metric("👀 Seen", eval_counts["seen"])
    with col4:
        st.metric("❓ Not Evaluated", eval_counts["not_evaluated"])


def main():
    st.title("GPT to Anki")

    # File uploader
    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["pdf", "txt"],
    )

    # URL input
    url_input = st.text_input("Or enter a document URL")

    # Store the uploaded file or URL in session state
    if uploaded_file is not None:
        st.session_state.document = uploaded_file
        st.session_state.document_url = None
        st.write("Document uploaded successfully.")
        st.write(f"File name: {uploaded_file.name}")
    elif url_input:
        st.session_state.document = None
        st.session_state.document_url = url_input
        st.write("URL entered successfully.")
        st.write(f"URL: {url_input}")
    elif st.session_state.document is None and not st.session_state.document_url:
        st.write("Upload a document or enter a URL to get started.")

    # Generate cards button - only show if document is uploaded or URL is provided
    if st.session_state.document is not None or st.session_state.document_url:
        if st.button("Generate cards"):
            try:
                process_document(file=uploaded_file, url=url_input)
                # Check if cards were loaded from database or generated
                existing_cards, _ = st.session_state.db.load_cards(
                    st.session_state.document_key
                )
                if existing_cards:
                    st.success("Cards loaded from database successfully!")
                else:
                    st.success("Cards generated successfully!")
            except Exception as e:
                st.error(f"Error processing document: {str(e)}")

    if st.session_state.cards:
        st.write("---")
        card_navigation(on_interaction=autosave_cards)
    else:
        st.write("No cards available.")

    # Show database statistics
    st.write("---")
    st.subheader("Database Statistics")
    contexts = st.session_state.db.get_contexts()
    if contexts:
        st.write(f"**Saved documents:** {len(contexts)}")
    else:
        st.write("No documents saved yet.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    init_session_state()
    main()
