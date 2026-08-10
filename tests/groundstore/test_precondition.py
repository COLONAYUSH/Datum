"""Preconditions: allow/reject, fail-closed on a raising check, and the
Haystack #8491 reject-destructive-composition example the mechanism exists
for. No database needed — this is pure registry/evaluation logic.
"""

from __future__ import annotations

import pytest

from datum.groundstore.precondition import PreconditionRegistry
from datum.kernel.errors import AdmissionError
from datum.kernel.record import StructuredBody


def test_no_registered_checks_allows_every_write() -> None:
    reg = PreconditionRegistry()
    reg.evaluate(None, "anything")  # no raise


def test_a_passing_precondition_allows_the_write() -> None:
    reg = PreconditionRegistry()
    reg.register(lambda prior, new: True)
    reg.evaluate(None, StructuredBody(text="ok"))  # no raise


def test_a_failing_precondition_rejects_with_admission_error() -> None:
    reg = PreconditionRegistry()

    @reg.precondition
    def reject_empty(prior, new) -> bool:  # noqa: ANN001
        text = new if isinstance(new, str) else new.text
        return len(text) > 0

    with pytest.raises(AdmissionError, match="reject_empty"):
        reg.evaluate(None, "")


def test_a_raising_precondition_fails_closed() -> None:
    reg = PreconditionRegistry()

    @reg.precondition
    def boom(prior, new) -> bool:  # noqa: ANN001
        raise RuntimeError("check itself is broken")

    with pytest.raises(AdmissionError):
        reg.evaluate(None, "text")  # a broken check denies, never passes through


def test_reject_delimiter_stripping_haystack_8491_example() -> None:
    # The spec's canonical case: a chunker needs a declared delimiter present
    # in the body; a cleaner that stripped it must be rejected before it
    # collapses the document to one chunk.
    reg = PreconditionRegistry()

    @reg.precondition
    def require_delimiter(prior, new) -> bool:  # noqa: ANN001
        text = new if isinstance(new, str) else new.text
        return "\n\n" in text  # the paragraph delimiter the splitter relies on

    reg.evaluate(None, StructuredBody(text="para one\n\npara two"))  # allowed
    with pytest.raises(AdmissionError, match="require_delimiter"):
        reg.evaluate(None, StructuredBody(text="delimiter stripped away"))
