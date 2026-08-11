"""MarkdownParser unit tests — pure, no database.

The load-bearing one is `test_hash_comments_in_code_fences_are_not_headings`:
a `# comment` line inside a ``` fence is NOT an ATX heading, so it never
becomes a bogus `section_path`. This is the bug real MCP use over FRAMEWORK.md
(full of Python code sketches) surfaced — 11 sentence-fragment "sections" that
mis-anchored citations, section_path being the provenance the surface promises
(decisions.md #33).
"""

from __future__ import annotations

from datum.writepath.policies.document import DocumentInput, MarkdownParser


def _parse(text: str):
    return MarkdownParser().parse(
        DocumentInput(source_id="doc", policy_id="p", text=text)  # type: ignore[arg-type]
    )


def test_real_atx_headings_build_the_section_path():
    text = "# Title\n\nintro\n\n## Section A\n\nbody a\n\n### Sub\n\nbody sub\n"
    secs = _parse(text)
    paths = [s.section_path for s in secs]
    assert ("doc", "Title") in paths
    assert ("doc", "Title", "Section A") in paths
    assert ("doc", "Title", "Section A", "Sub") in paths


def test_hash_comments_in_code_fences_are_not_headings():
    text = (
        "# Real Heading\n\n"
        "Some prose.\n\n"
        "```python\n"
        "# this is a python comment, not a heading\n"
        "def f():\n"
        "    # another comment\n"
        "    return 1\n"
        "```\n\n"
        "More prose after the fence.\n\n"
        "## Second Real Heading\n\n"
        "tail.\n"
    )
    secs = _parse(text)
    leaves = [s.section_path[-1] for s in secs]
    assert "Real Heading" in leaves
    assert "Second Real Heading" in leaves
    # None of the code-fence comment lines became a section.
    assert not any("comment" in leaf for leaf in leaves), leaves
    # The fence content stays as body under its real heading.
    body = "\n".join(s.text for s in secs)
    assert "def f()" in body and "python comment" in body


def test_tilde_fences_and_indented_fences_are_handled():
    text = (
        "# H\n\n"
        "~~~\n"
        "# not a heading (tilde fence)\n"
        "~~~\n\n"
        "text\n"
    )
    secs = _parse(text)
    assert [s.section_path[-1] for s in secs].count("H") == 1
    assert not any("not a heading" in s.section_path[-1] for s in secs)


def test_unclosed_fence_swallows_rest_as_body_not_headings():
    # A malformed doc whose fence never closes must fail safe: the rest is
    # body, and stray `#` lines in it do not spawn heading-shaped sections.
    text = "# H\n\n```\n# looks like a heading but is inside an open fence\nmore code\n"
    secs = _parse(text)
    assert not any("looks like a heading" in s.section_path[-1] for s in secs)
