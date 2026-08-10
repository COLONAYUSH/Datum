"""datum.policy: plan-selection and consumer policies (NOT the kernel Policy
Protocol, which lives in kernel.plan).

v1 ships `RuleTablePolicy` (rule_table.py), the declared static table filling
the plan-compiler's fusion slot. `SearcherShim` (the weak-model consumer) is
Phase 3 and deliberately absent.
"""

from datum.policy.rule_table import Fusion, RuleTablePolicy

__all__ = ["Fusion", "RuleTablePolicy"]
