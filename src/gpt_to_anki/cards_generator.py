import dspy

lm = dspy.LM(model="gpt-4o-mini", temperature=0.7)
dspy.configure(lm=lm)


class GenerateCards(dspy.Signature):
    """Given context, generate at most 10 question-answer pairs suitable for flashcards about the topic."""  # noqa

    context: str = dspy.InputField()
    topic: str = dspy.OutputField()
    questions: list[str] = dspy.OutputField(
        desc="List of exactly 10 questions for flashcards"
    )
    answers: list[str] = dspy.OutputField(
        desc="List of exactly 10 answers corresponding to the questions"
    )


class CardGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_cards = dspy.Predict(GenerateCards)

    async def aforward(self, context: str) -> dspy.Prediction:
        result = await self.generate_cards.acall(context=context, temperature=0.3)

        # Convert questions and answers lists to qa tuples
        questions = result.questions if hasattr(result, "questions") else []
        answers = result.answers if hasattr(result, "answers") else []
        min_length = min(len(questions), len(answers))
        qa_pairs = [(questions[i], answers[i]) for i in range(min_length)]
        result.qa = qa_pairs

        return result
