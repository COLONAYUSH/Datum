"""Derivation Engine (L4): the DAG of registered `View`s over the canonical
Ground Store — chunk -> embed -> enrich -> graph-extract.

Left intentionally import-free: each submodule (chunking.py, views/*) is
built independently by concurrent work and should not have to coordinate
through this file's contents, only its existence as a package marker.
"""

from __future__ import annotations
