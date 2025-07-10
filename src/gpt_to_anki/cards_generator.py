import dspy

lm = dspy.LM(model="gpt-4o-mini")
dspy.configure(lm=lm)


class GenerateCards(dspy.Signature):
    """Given context, generate at most 10 question-answer pairs suitable for flashcards about the topic."""

    context: str = dspy.InputField()
    topic: str = dspy.OutputField()
    qa: list[tuple[str, str]] = dspy.OutputField()


class CardGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate_cards = dspy.Predict(GenerateCards)

    async def aforward(self, context: str) -> dspy.Prediction:
        return await self.generate_cards.ainvoke(context=context)
