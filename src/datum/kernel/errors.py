"""Kernel-level exceptions.

These are the load-bearing failure modes, not a generic error hierarchy:
each one corresponds to a specific requirement the design exists to
enforce. In particular, PrincipalResolutionError is what makes "no default
principal, ever" an enforced property rather than a convention — see
security.context.current_principal().
"""

from __future__ import annotations


class DatumError(Exception):
    """Base class for every exception this package raises on purpose."""


class PrincipalResolutionError(DatumError):
    """Raised by security.context.current_principal() when no principal is
    bound to the current call. There is no fallback identity — this is the
    exception, not a default, per CI-05.
    """


class AdmissionError(DatumError):
    """Raised by writepath.orchestrator when a write fails admission control
    (a precondition rejects it, or authority_tier is claimed without the
    verified_source capability).
    """


class ConformanceError(DatumError):
    """Raised by datum.register_operator() when an Operator fails the
    conformance suite. Registration is refused, not merely logged.
    """


class BudgetExhaustedError(DatumError):
    """Raised when a Plan's declared Budget is exhausted mid-execution and
    the caller asked for a hard stop rather than a degrade tier.
    """
