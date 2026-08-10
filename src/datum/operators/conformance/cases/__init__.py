"""operators.conformance.cases: the four mandatory conformance checks.

Every module here exposes exactly one function, `check(operator) ->
CaseResult`, as a plain function with zero `import pytest` -- see any
case module's own docstring for why. `suite.py` is the only thing that
imports these as a group; nothing needs re-exporting here.
"""

from __future__ import annotations
