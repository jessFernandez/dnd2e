"""ask_controller.py — pure state + decisions for the "Ask the Rules" (Jarvis) feature.

The Qt orchestration necessarily lives in app.py: Jarvis answers stream from a
QThread (AskWorker) via signals that inject deltas into a QWebEngineView, and the
worker's lifecycle is tied to Qt object destruction. But the *decisions* around
that orchestration are pure and belong here — which model to run, whether to show
the setup help or the ask box, and the running conversation thread.

Extracted from MainWindow so this logic is unit-testable without Ollama or a live
app, and so the in-flight question context lives in one object instead of five
loose ``self._ask_*`` attributes.
"""
from rules_agent import DEFAULT_MODEL, pick_default_model


def resolve_model(preferred: str, models=None) -> str:
    """The model to run: the saved preference when it's actually installed,
    otherwise a sensible default from the installed list (or the hard default)."""
    chosen = (preferred or "").strip()
    if models and chosen not in models:
        chosen = pick_default_model(models)
    return chosen or DEFAULT_MODEL


def page_state(ollama_ok: bool, models) -> str:
    """``"ready"`` when Ollama is up with at least one model, else ``"setup"``."""
    return "ready" if (ollama_ok and models) else "setup"


class Conversation:
    """The running Jarvis Q&A thread.

    ``pairs`` is the visible history of ``(question, answer_md)`` tuples. The other
    fields hold the in-flight question's context while a worker streams its answer:
    the model chosen, the models offered, and the view the answer renders onto.
    """

    def __init__(self):
        self.pairs: list = []       # [(question, answer_md), …] — the visible thread
        self.question: str = ""     # the in-flight question
        self.model: str = DEFAULT_MODEL
        self.models = None          # models offered when this question was asked
        self.view = None            # the QWebEngineView the answer streams into
        self.generation = 0         # bumped per question; older workers are ignored

    def reset(self):
        """Start a fresh conversation (a new visit to the Jarvis page)."""
        self.pairs = []
        self.generation += 1        # abandon anything still streaming into the old page

    def begin(self, question: str, model: str, models, view) -> int:
        """Record the context for a question about to be handed to a worker, and
        return the generation that worker's replies must carry.

        Asking a second question while the first is still streaming replaces this
        context wholesale. Cancelling the old worker is not enough to make that
        safe: ``AskWorker.cancel()`` is cooperative, and ``run()`` emits ``finished``
        with the partial answer plus "_(stopped)_" regardless. Without a generation
        the old worker's answer would arrive afterwards, be recorded against the
        *new* question (``record_answer`` reads whatever ``self.question`` now
        holds), and overwrite the page the new answer is streaming into.
        """
        self.generation += 1
        self.question = question
        self.model = model
        self.models = models
        self.view = view
        return self.generation

    def is_current(self, generation: int) -> bool:
        """Whether a worker's reply is still the one being waited for."""
        return generation == self.generation

    def record_answer(self, answer_md: str):
        """Append the finished ``(question, answer)`` pair to the visible thread."""
        self.pairs.append((self.question, answer_md))
