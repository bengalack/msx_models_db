"""Model revisions: the 1st / 2nd / ... generation of the same model.

openMSX models each revision as its own machine named ``<model> (vN)``
(``HB-F500 (v2)``); revision 1 is the plain name. msx.org describes the
revisions on one page and marks revision-specific facts in free text
("2nd Gen HB-F500", "(HB-F500 second version)", "(version 2)").

Design: .claude/artifacts/planning/2026-09-26-model-revisions-design.md
"""

from __future__ import annotations

import re

# Internal marker on an msx.org record that describes revision N >= 2.
# The merge drops such records when openMSX has no matching machine.
REVISION_FIELD = "_revision"

_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
}
_WORD = r"(?:gen(?:eration)?|version|revision|model|edition)"

# "2nd Gen", "second version", "first model" | "version 2", "revision 3" | "v2"
REVISION_RE = re.compile(
    rf"\b(?:(?P<ord>\d+)(?:st|nd|rd|th)|(?P<word>{'|'.join(_ORDINAL_WORDS)}))\s+{_WORD}\b"
    rf"|\b(?:version|revision|generation)\s+(?P<num>\d+)\b(?!\.\d)"
    # lowercase v and 1-2 digits only, so chip names like "V9938" are not revisions
    rf"|(?<![\w.])(?-i:v)(?P<v>\d{{1,2}})\b(?!\.\d)",
    re.IGNORECASE,
)

_SUFFIX_RE = re.compile(r"^(?P<base>.*?)\s*\(v(?P<n>\d+)\)$")


def _number(m: re.Match[str]) -> int:
    if m.group("ord"):
        return int(m.group("ord"))
    if m.group("word"):
        return _ORDINAL_WORDS[m.group("word").lower()]
    return int(m.group("num") or m.group("v"))


def revision_numbers(text: str) -> set[int]:
    """Revision numbers referenced in *text* (empty when none)."""
    return {_number(m) for m in REVISION_RE.finditer(text or "")}


def revision_name(model: str, n: int) -> str:
    """``HB-F500`` for revision 1, ``HB-F500 (v2)`` for revision 2."""
    return model if n <= 1 else f"{model} (v{n})"


def split_revision(model: str) -> tuple[str, int]:
    """``"HB-F500 (v2)"`` → ``("HB-F500", 2)``; a plain name is revision 1."""
    m = _SUFFIX_RE.match(model or "")
    return (m.group("base"), int(m.group("n"))) if m else (model, 1)
