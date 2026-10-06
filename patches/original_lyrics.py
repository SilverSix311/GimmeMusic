"""Place supplied source words on ASR timing; keep the uncorrected ASR for verification."""
from difflib import SequenceMatcher
import re

from .alignment import normalize_words
from .asr import AsrWord


def original_words(text, heard):
    tokens = [t for t in re.sub(r"\[[^\]]*\]", " ", text).split() if normalize_words(t)]
    if not tokens:
        raise ValueError("Paste the original song's words, not only section labels.")
    if not heard:
        raise ValueError("No source words were transcribed. Check the recording and language, or edit the Song Sheet manually.")
    key = lambda word: " ".join(normalize_words(word))
    matcher = SequenceMatcher(None, [key(t) for t in tokens], [key(w.word) for w in heard], autojunk=False)
    placed = []
    matched = 0
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == 'equal':
            matched += b - a
            placed.extend(AsrWord(w.start, w.end, t, w.p, w.segment)
                          for t, w in zip(tokens[a:b], heard[c:d]))
        elif a < b:
            start = heard[c].start if c < d else (heard[c - 1].end if c else heard[0].start)
            end = heard[d - 1].end if c < d else (heard[c].start if c < len(heard) else heard[-1].end)
            width = max(0, end - start) / (b - a)
            segment = heard[min(c, len(heard) - 1)].segment
            placed.extend(AsrWord(start + i * width, start + (i + 1) * width, t, 0.0, segment)
                          for i, t in enumerate(tokens[a:b]))
    return placed, {'supplied_words': len(tokens), 'matched_words': matched,
                    'estimated_words': len(tokens) - matched,
                    'method': 'ASR word matching with interpolated timing; not acoustic forced alignment'}
