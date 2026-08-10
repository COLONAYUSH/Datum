"""datum.derivation.views: the L4 view builders the DerivationEngine drives.

v1 ships two (FRAMEWORK.md §MVP definition): a lexical BM25-shaped view
(lexical.py) and one dense embedding view (dense.py). Both implement the
ViewBuilder contract in base.py; the engine (derivation/engine.py) is the
only caller of `derive`/`remove`, and owns the transaction they run in.
"""
