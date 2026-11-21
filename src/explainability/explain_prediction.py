"""Highlighting helpers. Only evidence that was actually detected is ever marked."""
from __future__ import annotations

import html
import re


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[list[int]] = []
    for s, e in sorted(x for x in spans if x[1] > x[0]):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def term_spans(text: str, terms: list[str]) -> list[tuple[int, int]]:
    """Find occurrences of single-word model terms (bigrams / placeholder tokens are skipped)."""
    spans = []
    for t in terms:
        if " " in t or t.endswith("token") or len(t) < 3:
            continue
        pat = rf"\b{re.escape(t)}\b" if t.isascii() else re.escape(t)
        spans += [(m.start(), m.end()) for m in re.finditer(pat, text, re.I)]
    return spans


def highlight_html(text: str, spans: list[tuple[int, int]]) -> str:
    """HTML-escaped text with <mark> around spans. Safe for st.markdown(unsafe_allow_html=True)."""
    parts, pos = [], 0
    for s, e in merge_spans(spans):
        parts.append(html.escape(text[pos:s]))
        parts.append(f'<mark class="gs-mark">{html.escape(text[s:e])}</mark>')
        pos = e
    parts.append(html.escape(text[pos:]))
    return "".join(parts).replace("\n", "<br>")
