"""Poem eligibility, scoring, category rotation and anti-repetition."""
import re
from difflib import SequenceMatcher
from scanner import detect_with_boundaries

VULGAR=set('fuck fucked fucking shit bullshit dick cock cum horny ass pussy slut slutty porn'.split())
POETIC=set('rain moon night sky snow sun cold lonely alone silent silence beautiful dream dreams wind winter summer heart sad love water dark'.split())
UNEXPECTED=set('guitar dog sauna theatre money oven opium internet awkward strange suddenly accident accidentally cucumber office'.split())
BLOCK=set('nigger chink faggot kike rape raping pedophile pedophilia doxx doxxing'.split())
BAD_END=set('the a an and or but for of to with in on at if when because as your my his her their our is are was were'.split())
BAD_START=set('and or but of to for with because than'.split())

def normalized(lines):
    return ' '.join(lines).lower().replace('’',"'")

def category_counts(lines):
    words=set(re.findall('[a-z]+',normalized(lines)))
    return {'vulgar':len(words&VULGAR),'poetic':len(words&POETIC),'unexpected':len(words&UNEXPECTED)}

def rank_candidate(lines,start,end):
    words=re.findall('[a-z]+',normalized(lines))
    if not words or words[-1] in BAD_END or words[0] in BAD_START or any(w in BLOCK for w in words): return None
    # Ambiguous trailing words can still be worthwhile; grammatical boundary is preference.
    score=10 + 9*start + 12*end
    if words[-1] in ('accidentally','over','again','beautiful'): score+=5
    if len(set(words))/len(words)>0.65: score+=3
    counts=category_counts(lines)
    cat=max(('vulgar','poetic','unexpected'),key=lambda category:(counts[category],{'vulgar':2,'poetic':1,'unexpected':0}[category]))
    return {'lines':lines,'score':score,'category':cat}

def score_comment(text):
    scored=[]
    for lines,start,end in detect_with_boundaries(text):
        result=rank_candidate(lines,start,end)
        if result: scored.append(result)
    return sorted(scored,key=lambda item:item['score'],reverse=True)

def overlaps(lines,old_lines):
    a=[re.sub(r'[^a-z0-9]+',' ',x.lower()).strip() for x in lines]
    b=[re.sub(r'[^a-z0-9]+',' ',x.lower()).strip() for x in old_lines]
    if len(set(a)&set(b))>=2: return True
    wa=normalized(lines).split(); wb=normalized(old_lines).split()
    # Overlapping 6-word run from a different segment / re-post.
    six=lambda w:{tuple(w[i:i+6]) for i in range(max(0,len(w)-5))}
    if six(wa)&six(wb): return True
    return SequenceMatcher(None,' '.join(wa),' '.join(wb)).ratio()>=0.82
