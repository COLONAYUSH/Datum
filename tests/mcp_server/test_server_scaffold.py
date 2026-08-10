"""Exercises the five-tool MCP scaffold end to end against a hand-written
`FakeCorpus` (the real Corpus composition root does not exist yet -- a later
build phase wires this module to it, per this module's own task scope).

Two things are asserted per tool, deliberately kept separate:

1. Calling the plain tool function directly (via `build_tools`, bypassing
   MCP's own wire-format wrapping) returns the exact kernel.surface type
   FRAMEWORK.md §7 specifies -- `Evidence`/`SearchHit`/`StructureView`/`str`/
   `ChangeSet`. `MCPServer.call_tool()` returns a `CallToolResult`, not a
   kernel dataclass, so this suite calls the underlying functions directly
   rather than going through the protocol dispatch path to get a meaningful
   type assertion.
2. `no `principal` parameter anywhere` is checked twice: once against each
   raw function's own `inspect.signature` (catches a future edit that adds
   one back), and once against the registered tool's JSON `input_schema`
   (catches what a model would actually see, which is the load-bearing
   half of FRAMEWORK.md §7's requirement).
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone

from datum.kernel.principal import Principal
from datum.kernel.surface import (
    ChangeRecord,
    ChangeSet,
    Evidence,
    SearchHit,
    StructureNode,
    StructureView,
)
from datum.mcp_server.server import build_server, build_tools
from datum.security.context import bind_principal

ALICE = Principal(id="alice", namespace="tenant:acme")

_TOOL_NAMES = ("search", "fetch", "navigate", "explain", "since")


class FakeCorpus:
    """Just enough of `CorpusLike` to prove the MCP wiring works: every
    method returns a canned kernel.surface value and records the principal
    it was called with, so tests can also assert `current_principal()`
    really was threaded down rather than silently dropped.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, Principal]] = []

    def search(self, query: str, *, principal: Principal, path_glob: str | None = None) -> Evidence:
        self.calls.append(("search", principal))
        hit = SearchHit(hit_id="hit-1", content=f"...matched {query!r}...", source_path="contracts/acme.md")
        return Evidence(hits=(hit,), status="ok", sufficiency=0.81, plan_id="plan-1")

    def fetch(self, hit_id: str, *, principal: Principal) -> SearchHit:
        self.calls.append(("fetch", principal))
        return SearchHit(hit_id=hit_id, content="full text behind the hit", source_path="contracts/acme.md")

    def navigate(self, ref: str, *, principal: Principal, depth: int | None = None) -> StructureView:
        self.calls.append(("navigate", principal))
        root = StructureNode(path=ref, kind="document", children=(StructureNode(path=f"{ref}#s1", kind="section"),))
        return StructureView(root=root)

    def explain(self, plan_id: str, *, principal: Principal) -> str:
        self.calls.append(("explain", principal))
        return f"Plan(plan_id={plan_id!r}, plan_selector='fusion-v3')\n  -> BM25(k=50)"

    def since(self, marker: str, *, principal: Principal) -> ChangeSet:
        self.calls.append(("since", principal))
        change = ChangeRecord(hit_id="hit-1", change_kind="created", occurred_at=datetime.now(timezone.utc))
        return ChangeSet(changes=(change,), since_marker=marker, as_of_marker="wal-42")


def test_search_returns_evidence() -> None:
    fake = FakeCorpus()
    tools = build_tools(fake)
    with bind_principal(ALICE):
        result = tools["search"]("refund policy")
    assert isinstance(result, Evidence)
    assert result.hits[0].hit_id == "hit-1"
    assert fake.calls == [("search", ALICE)]


def test_fetch_returns_search_hit() -> None:
    fake = FakeCorpus()
    tools = build_tools(fake)
    with bind_principal(ALICE):
        result = tools["fetch"]("hit-1")
    assert isinstance(result, SearchHit)
    assert result.hit_id == "hit-1"


def test_navigate_returns_structure_view() -> None:
    fake = FakeCorpus()
    tools = build_tools(fake)
    with bind_principal(ALICE):
        result = tools["navigate"]("contracts/acme.md")
    assert isinstance(result, StructureView)
    assert result.root.kind == "document"


def test_explain_returns_a_string() -> None:
    fake = FakeCorpus()
    tools = build_tools(fake)
    with bind_principal(ALICE):
        result = tools["explain"]("plan-1")
    assert isinstance(result, str)
    assert "plan-1" in result


def test_since_returns_change_set() -> None:
    fake = FakeCorpus()
    tools = build_tools(fake)
    with bind_principal(ALICE):
        result = tools["since"]("wal-0")
    assert isinstance(result, ChangeSet)
    assert result.since_marker == "wal-0"
    assert result.as_of_marker == "wal-42"


def test_all_five_tools_are_registered() -> None:
    server = build_server(FakeCorpus())
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == set(_TOOL_NAMES)


def test_no_raw_tool_function_has_a_principal_parameter() -> None:
    tools = build_tools(FakeCorpus())
    for name in _TOOL_NAMES:
        params = inspect.signature(tools[name]).parameters
        assert "principal" not in params, f"{name}'s signature must not accept principal"


def test_no_tool_schema_exposes_a_principal_property() -> None:
    server = build_server(FakeCorpus())
    tools = asyncio.run(server.list_tools())
    for tool in tools:
        properties = tool.input_schema.get("properties", {})
        required = tool.input_schema.get("required", [])
        assert "principal" not in properties, f"{tool.name}'s input_schema exposes principal to the model"
        assert "principal" not in required, f"{tool.name}'s input_schema requires principal from the model"


def test_registered_tools_are_callable_end_to_end_through_the_server() -> None:
    fake = FakeCorpus()
    server = build_server(fake)
    with bind_principal(ALICE):
        result = asyncio.run(server.call_tool("search", {"query": "refund policy"}))
    # The protocol-level call succeeds and reaches FakeCorpus with the
    # bound principal -- proving the registration, not just the bare
    # function, is wired correctly end to end.
    assert fake.calls == [("search", ALICE)]
    assert result is not None
