"""Conservative score for accidental haiku candidates.

A poem need not be grammatical or polite to be interesting. Keep original
word order and never rewrite text. Editorial review remains necessary.
"""
import re

WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")
BAD_END = set('a an the or and but if so to of for with at on in from by as than is are was were be been being my your his her their our very just will would could should can do does did have has had'.split())
BAD_START = set('and or but because than which whose whom although unless'.split())
WEAK_END = set('i you we they he she it that this those these though until while before after'.split())
WEAK_START = set('of to for with in at on by from than'.split())
# These are signs of truncation rather than intentionally open-ended endings.
BAD_LAST_TWO = {('a', 'lot'), ('going', 'to'), ('have', 'to')}


def evaluate(lines, start_boundary=None, end_boundary=None):
    """Return (score, reasons). Boundary metadata is absent in older databases."""
    words = [WORD.findall(line.lower().replace('’', "'")) for line in lines]
    if not all(words):
        return None, ['empty line']
    first, last = words[0][0], words[-1][-1]
    if last in BAD_END:
        return None, ['ends with grammatical connector']
    if first in BAD_START:
        return None, ['begins with dangling connector']
    if len(words[-1]) > 1 and tuple(words[-1][-2:]) in BAD_LAST_TWO:
        return None, ['ends with truncated phrase']

    score = 50.0
    reasons = []
    # Favor intact utterances, but DO NOT REQUIRE them: 'i accidentally' can
    # be compelling while a fully closed sentence can be boring.
    if start_boundary == 1:
        score += 18
        reasons.append('begins at natural boundary')
    elif start_boundary == 0:
        score -= 5
    if end_boundary == 1:
        score += 20
        reasons.append('ends at natural boundary')
    elif end_boundary == 0:
        score -= 4
    if last in WEAK_END:
        score -= 13
    if first in WEAK_START:
        score -= 9
    for line in words[:2]:
        if line[-1] in BAD_END:
            score -= 4
    flat = [w for line in words for w in line]
    if len(set(flat)) / len(flat) < .62:
        score -= 8
    if len(flat) < 10:
        score -= 3
    # Heuristic, not censorship: none of these rules checks sexual/slang terms.
    return round(score, 1), reasons


def best_candidates(rows, limit=10, min_score=40):
    best = {}
    for row in rows:
        r = dict(row)
        score, reasons = evaluate((r['line1'], r['line2'], r['line3']),
                                  r.get('start_boundary'), r.get('end_boundary'))
        if score is None or score < min_score:
            continue
        r['score'], r['reasons'] = score, reasons
        post = r['post_id']
        if post not in best or (score, -r['id']) > (best[post]['score'], -best[post]['id']):
            best[post] = r
    return sorted(best.values(), key=lambda r: (-r['score'], r['id']))[:limit]
