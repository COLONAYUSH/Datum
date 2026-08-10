"""datum.writepath: L3, the admission-controlled write path.

`WriteOrchestrator` runs a raw input through its `WritePolicy` and applies
each resulting `WriteOp` under admission control (authority-tier clamp,
write-side namespace guard, preconditions) before it reaches the ground
store. v1 ships one policy, `DocumentPolicy` (policies/document.py).
"""

from datum.writepath.orchestrator import WriteOrchestrator
from datum.writepath.policies.document import DocumentInput, DocumentPolicy, MarkdownParser

__all__ = ["WriteOrchestrator", "DocumentInput", "DocumentPolicy", "MarkdownParser"]
