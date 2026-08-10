"""datum.operators: L5, physical retrieval operators + the conformance gate.

v1 ships one operator, `GrepOperator` (grep_op.py), which reads L2 canonical
records directly. `OperatorRegistry` (registry.py) is the conformance gate
every operator — grep now, BM25/ANN at Milestone B — must pass to register.
The conformance suite itself lives in `operators.conformance`.
"""

from datum.operators.common import QueryFragment
from datum.operators.grep_op import GrepFragment, GrepOperator
from datum.operators.registry import OperatorRegistry

__all__ = ["GrepFragment", "GrepOperator", "OperatorRegistry", "QueryFragment"]
