#!/usr/bin/env python3
"""Mechanical scorer for the adversarial retrieval benchmark.

Scoring rule (benchmarks/adversarial/README.md): a question PASSES only if a
passage containing the expected answer appears in the TOP FIVE retrieved
results. Contradiction-trap questions ("kind": "conflict") require BOTH
conflicting values to surface — each value may appear in a different passage
within the top five.

Inputs
------
questions JSON  {"questions": [{"id", "query", "kind", "match"}, ...]}
    kind "single":  match is a list of alternative term-groups. The question
                    passes if ANY group has ALL its terms present in at least
                    ONE of the top-5 passages (all terms in the same passage).
    kind "conflict": match is exactly two term-group-lists, one per
                    conflicting value. The question passes only if EACH
                    value's terms are found somewhere in the top-5 (the two
                    values may sit in different passages).
results JSON    {"Q01": ["passage text 1", ..., "passage text 5"], ...}

Terms are written in the JSON as they appear in the document or the answer
key; both terms and passages go through the SAME generic normalization below
before matching, so surface variants ("62 h"/"62 hours", "1,800"/"1800",
"Fernández"/"Fernandez", "35%"/"35 per cent") compare equal.

Usage:  python score.py questions-a.json datum-results-a.json [--verbose]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from html import unescape

# Unicode dash/quote variants folded to ASCII (generic typography cleanup).
_DASH_QUOTE_MAP = {ord(c): "-" for c in "‐‑‒–—―−"}
_DASH_QUOTE_MAP.update({ord("‘"): "'", ord("’"): "'",
                        ord("“"): '"', ord("”"): '"'})

# Common measurement-unit spellings folded to one canonical short form.
# Applied to whole words only, on BOTH the passage and the match term, so
# "62 hours", "62 hrs" and "62 h" all normalize to "62 h".
_UNIT_WORDS = {
    "hour": "h", "hours": "h", "hr": "h", "hrs": "h",
    "metre": "m", "metres": "m", "meter": "m", "meters": "m",
    "kilometre": "km", "kilometres": "km", "kilometer": "km", "kilometers": "km",
    "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "second": "s", "seconds": "s", "sec": "s", "secs": "s",
}

_THOUSANDS_SEP = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
# A digit glued to a KNOWN unit word gets a space ("62h" -> "62 h",
# "96mb" -> "96 mb") — restricted to unit words so identifiers like
# "M-3R" or "0x1021" are never split.
_UNIT_TOKENS = ("hours|hour|hrs|hr|h|minutes|minute|min|ms|seconds|second|secs|sec|s|"
                "kilometres|kilometers|kilometre|kilometer|km|cm|mm|m|kg|g|"
                "litres|liters|litre|liter|l|ml|kwh|kw|mw|w|mb|gb|kb|tb|"
                "khz|mhz|hz|mpa|kpa|pa|percent")
_DIGIT_UNIT = re.compile(rf"(?<=\d)({_UNIT_TOKENS})\b")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """The ONE normalization applied to every passage and every match term.

    Every step is generic (never keyed to a particular question):
      1. HTML-entity unescape and backslash removal — markdown-export
         artifacts ("&lt;", "chunk\\_size\\_kb").
      2. NFKC compatibility fold (fullwidth forms, ligatures), dash/quote
         variants to ASCII, casefold.
      3. Diacritic strip: NFKD, then drop combining marks (Mn) and invisible
         format chars (Cf, e.g. ZWNJ) — "Fernández" == "fernandez",
         "März" == "marz". Applied to both sides, so marked scripts
         (Tamil, Arabic) also compare consistently.
      4. Percent unification: "%" and the words "per cent"/"percent" all
         become the single token "percent".
      5. A space is inserted between a digit and a glued-on KNOWN unit word
         ("62h" -> "62 h", "96MB" -> "96 mb"); identifiers like "M-3R" or
         "0x1021" are never split.
      6. Unit-word canonicalization per _UNIT_WORDS (whole words only).
      7. Thousand separators stripped: "5,204" -> "5204", "34.800" -> "34800"
         (separator = "." or "," followed by exactly three digits).
      8. Remaining decimal commas become decimal points: "9,0" -> "9.0",
         "104,5" -> "104.5".
      9. All whitespace (incl. newlines) collapsed to single spaces.
    """
    text = unescape(text).replace("\\", "")
    text = unicodedata.normalize("NFKC", text).translate(_DASH_QUOTE_MAP).casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Mn", "Cf"))
    text = text.replace("%", " percent ")
    text = _DIGIT_UNIT.sub(r" \1", text)
    text = _WORD.sub(lambda m: _UNIT_WORDS.get(m.group(0), m.group(0)), text)
    text = _THOUSANDS_SEP.sub("", text)
    text = _DECIMAL_COMMA.sub(".", text)
    text = _WS.sub(" ", text).strip()
    text = re.sub(r"\bper cent\b", "percent", text)
    return text


def term_in(term_norm: str, passage_norm: str) -> bool:
    """Substring match with word-ish boundaries: when a term starts/ends with
    a word character, that edge must not butt against another word character
    in the passage — so the term "3" matches "| 3 |" but never "35",
    and "m-3" never matches "m-3r"."""
    pattern = re.escape(term_norm)
    if re.match(r"\w", term_norm[0]):
        pattern = r"(?<!\w)" + pattern
    if re.match(r"\w", term_norm[-1]):
        pattern = pattern + r"(?!\w)"
    return re.search(pattern, passage_norm) is not None


def group_in_passage(group: list[str], passage_norm: str) -> bool:
    """ALL terms of the group present in this single passage."""
    return all(term_in(normalize(t), passage_norm) for t in group)


def any_group_hit(groups: list[list[str]], passages_norm: list[str]) -> bool:
    """ANY alternative group fully contained in at least ONE passage."""
    return any(group_in_passage(g, p) for g in groups for p in passages_norm)


def score_question(question: dict, passages: list[str]) -> tuple[bool, str]:
    """Returns (passed, detail). Only the top FIVE passages are considered."""
    passages_norm = [normalize(p) for p in passages[:5]]
    if question["kind"] == "conflict":
        value_a, value_b = question["match"]
        got_a = any_group_hit(value_a, passages_norm)
        got_b = any_group_hit(value_b, passages_norm)
        detail = f"value1={'hit' if got_a else 'MISS'} value2={'hit' if got_b else 'MISS'}"
        return got_a and got_b, detail
    hit = any_group_hit(question["match"], passages_norm)
    return hit, "hit" if hit else "no passage matched any term-group"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("questions", help="questions-a.json / questions-b.json")
    parser.add_argument("results", help='results JSON: {"Q01": ["passage", ...], ...}')
    parser.add_argument("--verbose", action="store_true",
                        help="print the top-5 passages of every failing question")
    args = parser.parse_args()

    with open(args.questions, encoding="utf-8") as fh:
        spec = json.load(fh)
    with open(args.results, encoding="utf-8") as fh:
        results = json.load(fh)

    questions = spec["questions"]
    passed_total = 0
    print(f"{'ID':<5} {'kind':<9} {'result':<6} detail")
    print("-" * 72)
    for question in questions:
        qid = question["id"]
        passages = results.get(qid, [])
        ok, detail = score_question(question, passages)
        passed_total += ok
        print(f"{qid:<5} {question['kind']:<9} {'PASS' if ok else 'FAIL':<6} {detail}")
        if not ok and args.verbose:
            for i, passage in enumerate(passages[:5], 1):
                one_line = " ".join(passage.split())
                print(f"        [{i}] {one_line[:300]}")
    print("-" * 72)
    print(f"TOTAL: {passed_total}/{len(questions)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
