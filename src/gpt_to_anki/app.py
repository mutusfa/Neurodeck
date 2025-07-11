import logging
import os
import uuid
from io import BytesIO
from typing import List, Tuple, Optional, Dict, NamedTuple
from PyPDF2 import PdfReader
import requests
import gradio as gr

from gpt_to_anki.cards_generator import CardGenerator
from gpt_to_anki.database import CardDatabase

LOG = logging.getLogger(__name__)


class CardDisplay(NamedTuple):
    """Encapsulates card display information and states"""

    card_info: str = ""
    status: str = ""
    topic: str = ""
    question: str = ""
    answer: str = ""
    prev_btn_update: object = None
    next_btn_update: object = None
    reset_btn_update: object = None

    @classmethod
    def empty(cls) -> "CardDisplay":
        """Create an empty card display"""
        return cls(
            "No cards available",
            "",
            "",
            "",
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
        )


# Global state management
class AppState:
    def __init__(self):
        self.document_context: Optional[str] = None
        self.local_file_path: Optional[str] = None
        self.document_url: Optional[str] = None
        self.document_key: Optional[str] = None
        self.cards: List[Dict[str, str]] = []
        self.card_generator = CardGenerator()
        self.current_card_index: int = 0
        self.card_evaluations: Dict[int, str] = {}
        self.db = CardDatabase()
        self.total_cards: int = 0

    def reset_cards(self):
        """Reset card-related state"""
        self.cards = []
        self.current_card_index = 0
        self.card_evaluations = {}
        self.total_cards = 0

    def get_current_card(self) -> Optional[Dict[str, str]]:
        """Get the current card or None if no cards"""
        if self.cards and 0 <= self.current_card_index < len(self.cards):
            return self.cards[self.current_card_index]
        return None

    def get_card_evaluation(self, card_index: int) -> str:
        """Get the evaluation state for a card"""
        return self.card_evaluations.get(card_index, "not_evaluated")

    def set_card_evaluation(self, card_index: int, evaluation: str):
        """Set the evaluation state for a card"""
        self.card_evaluations[card_index] = evaluation

    def get_evaluation_counts(self) -> Dict[str, int]:
        """Get counts of each evaluation type"""
        counts = {"liked": 0, "disliked": 0, "seen": 0, "not_evaluated": 0}
        for i in range(len(self.cards)):
            eval_state = self.get_card_evaluation(i)
            counts[eval_state] += 1
        return counts


# Initialize global state
app_state = AppState()


def get_evaluation_emoji(evaluation: str) -> str:
    """Get emoji representation of evaluation state"""
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


def save_uploaded_file(file_obj) -> str:
    """Save uploaded file to media folder with UUID-based filename"""
    media_folder = "media"
    os.makedirs(media_folder, exist_ok=True)

    file_uuid = str(uuid.uuid4())
    # Get file extension from the original filename
    file_extension = (
        os.path.splitext(file_obj.name)[1] if hasattr(file_obj, "name") else ""
    )

    unique_filename = f"{file_uuid}{file_extension}"
    file_path = os.path.join(media_folder, unique_filename)

    # For Gradio, the file_obj is already a file path
    if isinstance(file_obj, str):
        # Copy the file to our media folder
        with open(file_obj, "rb") as src, open(file_path, "wb") as dst:
            dst.write(src.read())
    else:
        # Handle file-like objects
        with open(file_path, "wb") as f:
            f.write(file_obj.read())

    LOG.info("File saved to: %s", file_path)
    return file_path


async def fetch_url_content(url: str) -> str:
    """Fetch content from URL"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type:
            pdf_bytes = BytesIO(response.content)
            reader = PdfReader(pdf_bytes)
            return "\n".join(page.extract_text() for page in reader.pages)
        elif "text" in content_type:
            return response.text
        else:
            return response.text
    except Exception as e:
        raise ValueError(f"Failed to fetch URL content: {str(e)}")


def read_document(file_path: str) -> str:
    """Read document from file path"""
    try:
        if file_path.lower().endswith(".pdf"):
            with open(file_path, "rb") as file:
                reader = PdfReader(file)
                return "\n".join(page.extract_text() for page in reader.pages)
        elif file_path.lower().endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
    except Exception as e:
        raise ValueError(f"Error reading file: {str(e)}")


async def process_document(
    file_path: Optional[str] = None, url: Optional[str] = None
) -> Tuple[str, str]:
    """Process either a file or URL and return status message and card info"""
    try:
        if file_path:
            LOG.info("Processing uploaded file: %s", file_path)
            app_state.document_url = None
            app_state.local_file_path = save_uploaded_file(file_path)
            app_state.document_key = app_state.local_file_path
            text = read_document(file_path)
            app_state.document_context = text

        elif url:
            LOG.info("Processing URL: %s", url)
            app_state.local_file_path = None
            app_state.document_url = url
            app_state.document_key = url
            text = await fetch_url_content(url)
            app_state.document_context = text
        else:
            return "❌ Error: No file or URL provided", ""

        LOG.info(
            "Document context: %s", text[:200] + "..." if len(text) > 200 else text
        )

        # Check if cards already exist for this document
        existing_cards, existing_evaluations = await app_state.db.aload_cards(
            app_state.document_key
        )

        if existing_cards:
            LOG.info("Loading existing cards from database...")
            app_state.cards = existing_cards
            app_state.card_evaluations = existing_evaluations
            app_state.current_card_index = 0
            app_state.total_cards = len(existing_cards)
            return (
                "✅ Cards loaded from database successfully!",
                f"📚 {len(existing_cards)} cards loaded",
            )
        else:
            LOG.info("Generating new cards...")
            cards_result = await app_state.card_generator.aforward(context=text)
            qa_cards = cards_result.qa
            topic = cards_result.topic

            app_state.cards = [
                {"question": qa[0], "answer": qa[1], "topic": topic} for qa in qa_cards
            ]
            app_state.card_evaluations = {}
            app_state.current_card_index = 0
            app_state.total_cards = len(app_state.cards)

            # Save new cards to database
            await app_state.db.asave_cards(
                app_state.cards, app_state.document_key, app_state.card_evaluations
            )

            return (
                "✅ Cards generated successfully!",
                f"🎯 {len(app_state.cards)} new cards created",
            )

    except Exception as e:
        LOG.error("Error processing document: %s", e)
        return f"❌ Error: {str(e)}", ""


def get_card_display() -> CardDisplay:
    """Get current card display information"""
    if not app_state.cards:
        return CardDisplay.empty()

    current_card = app_state.get_current_card()
    if not current_card:
        return CardDisplay.empty()

    current_evaluation = app_state.get_card_evaluation(app_state.current_card_index)
    evaluation_emoji = get_evaluation_emoji(current_evaluation)

    # Card info
    card_info = f"Card {app_state.current_card_index + 1} of {len(app_state.cards)}"
    status = (
        f"**Status:** {evaluation_emoji} {current_evaluation.replace('_', ' ').title()}"
    )
    topic = f"**Topic:** {current_card['topic']}"
    question = f"**Question:** {current_card['question']}"
    answer = f"**Answer:** {current_card['answer']}"

    # Button states
    prev_disabled = app_state.current_card_index == 0
    next_disabled = app_state.current_card_index >= len(app_state.cards) - 1

    return CardDisplay(
        card_info=card_info,
        status=status,
        topic=topic,
        question=question,
        answer=answer,
        prev_btn_update=gr.update(interactive=not prev_disabled),
        next_btn_update=gr.update(interactive=not next_disabled),
        reset_btn_update=gr.update(interactive=True),
    )


def get_summary_display() -> str:
    """Get evaluation summary display"""
    if not app_state.cards:
        return "No cards to summarize"

    counts = app_state.get_evaluation_counts()
    summary = f"""
    **Evaluation Summary:**
    - 👍 Liked: {counts['liked']}
    - 👎 Disliked: {counts['disliked']}
    - 👀 Seen: {counts['seen']}
    - ❓ Not Evaluated: {counts['not_evaluated']}
    """
    return summary


async def mark_card_as_seen_if_needed():
    """Mark current card as seen if not evaluated"""
    if app_state.cards and app_state.current_card_index < len(app_state.cards):
        current_eval = app_state.get_card_evaluation(app_state.current_card_index)
        if current_eval == "not_evaluated":
            app_state.set_card_evaluation(app_state.current_card_index, "seen")
            if app_state.document_key:
                await app_state.db.aupdate_card_evaluation(
                    app_state.document_key, app_state.current_card_index, "seen"
                )


async def handle_like_card():
    """Handle like button click"""
    await mark_card_as_seen_if_needed()
    app_state.set_card_evaluation(app_state.current_card_index, "liked")

    if app_state.document_key:
        await app_state.db.aupdate_card_evaluation(
            app_state.document_key, app_state.current_card_index, "liked"
        )

    # Auto-advance to next card
    if app_state.current_card_index < len(app_state.cards) - 1:
        app_state.current_card_index += 1

    return (*get_card_display(), get_summary_display())


async def handle_dislike_card():
    """Handle dislike button click"""
    await mark_card_as_seen_if_needed()
    app_state.set_card_evaluation(app_state.current_card_index, "disliked")

    if app_state.document_key:
        await app_state.db.aupdate_card_evaluation(
            app_state.document_key, app_state.current_card_index, "disliked"
        )

    # Auto-advance to next card
    if app_state.current_card_index < len(app_state.cards) - 1:
        app_state.current_card_index += 1

    return (*get_card_display(), get_summary_display())


async def handle_previous_card():
    """Handle previous button click"""
    if app_state.current_card_index > 0:
        app_state.current_card_index -= 1
    await mark_card_as_seen_if_needed()
    return (*get_card_display(), get_summary_display())


async def handle_next_card():
    """Handle next button click"""
    if app_state.current_card_index < len(app_state.cards) - 1:
        app_state.current_card_index += 1
    await mark_card_as_seen_if_needed()
    return (*get_card_display(), get_summary_display())


async def handle_reset_cards():
    """Handle reset button click"""
    app_state.current_card_index = 0
    await mark_card_as_seen_if_needed()
    return (*get_card_display(), get_summary_display())


def get_database_stats() -> str:
    """Get database statistics"""
    contexts = app_state.db.get_contexts()
    if contexts:
        return f"**Database Statistics:**\n📁 Saved documents: {len(contexts)}"
    return "**Database Statistics:**\nNo documents saved yet."


def create_interface():
    """Create the Gradio interface"""
    with gr.Blocks(title="GPT to Anki", theme=gr.themes.Soft()) as app:
        gr.Markdown("# 🎯 GPT to Anki")
        gr.Markdown("Upload a document or enter a URL to generate flashcards!")

        with gr.Row():
            with gr.Column(scale=1):
                # File upload section
                gr.Markdown("### 📁 Upload Document")
                file_input = gr.File(
                    label="Choose a PDF or TXT file",
                    file_types=[".pdf", ".txt"],
                    file_count="single",
                )

                gr.Markdown("### 🌐 Or Enter URL")
                url_input = gr.Textbox(
                    label="Document URL",
                    placeholder="https://example.com/document.pdf",
                    lines=1,
                )

                process_btn = gr.Button(
                    "🚀 Generate Cards", variant="primary", size="lg"
                )

                # Status display
                status_output = gr.Markdown("Ready to process documents!")
                card_count_output = gr.Markdown("")

            with gr.Column(scale=2):
                # Card display section
                gr.Markdown("### 📚 Flashcards")

                # Card navigation info
                card_info = gr.Markdown("No cards loaded")
                card_status = gr.Markdown("")
                card_topic = gr.Markdown("")
                card_question = gr.Markdown("")
                card_answer = gr.Markdown("")

                # Action buttons
                with gr.Row():
                    like_btn = gr.Button("👍 Like", variant="secondary")
                    dislike_btn = gr.Button("👎 Dislike", variant="secondary")

                # Navigation buttons
                with gr.Row():
                    prev_btn = gr.Button("Previous")
                    reset_btn = gr.Button("Reset")
                    next_btn = gr.Button("Next")

                # Summary section
                gr.Markdown("---")
                summary_output = gr.Markdown(
                    "### 📊 Evaluation Summary\nNo evaluations yet"
                )

                # Database stats
                gr.Markdown("---")
                db_stats = gr.Markdown(get_database_stats())

        # Event handlers
        async def process_document_handler(file_path, url):
            # Mark current card as seen before processing
            await mark_card_as_seen_if_needed()

            status_msg, card_info_msg = await process_document(file_path, url)
            card_display = get_card_display()
            summary = get_summary_display()
            stats = get_database_stats()

            return (status_msg, card_info_msg, *card_display, summary, stats)

        # Define common output lists to reduce repetition
        card_display_outputs = [
            card_info,
            card_status,
            card_topic,
            card_question,
            card_answer,
            prev_btn,
            next_btn,
            reset_btn,
            summary_output,
        ]

        process_outputs = [
            status_output,
            card_count_output,
            *card_display_outputs,
            db_stats,
        ]

        # Helper function to set up card action buttons with common outputs
        def setup_card_action_button(button, handler_func):
            button.click(handler_func, outputs=card_display_outputs)

        # Wire up events
        process_btn.click(
            process_document_handler,
            inputs=[file_input, url_input],
            outputs=process_outputs,
        )
        setup_card_action_button(like_btn, handle_like_card)
        setup_card_action_button(dislike_btn, handle_dislike_card)
        setup_card_action_button(prev_btn, handle_previous_card)
        setup_card_action_button(next_btn, handle_next_card)
        setup_card_action_button(reset_btn, handle_reset_cards)

    return app


def main():
    """Main function to run the Gradio app"""
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    app = create_interface()
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
