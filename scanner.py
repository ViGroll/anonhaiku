"""Anonhaiku 2.0: ingest every active /b/ thread, with API-safe pacing."""
from __future__ import annotations
import html
from html.parser import HTMLParser
import re
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json
import cmudict

API = 'https://a.4cdn.org/b'
WORDS = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
NUMBERS = re.compile(r'\d')
URLS = re.compile(r'(?i)https?://\S+|www\.\S+')
DICT = cmudict.dict()
ATTACHMENT_FIELDS = ('tim', 'filename', 'ext', 'filedeleted')

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.result=[]; self.depth=0
    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get('class','').split()
        if self.depth: self.depth += 1
        elif tag in ('script','style','a') or (tag=='span' and ('quote' in classes or 'deadlink' in classes)):
            self.depth=1
        elif tag in ('br','p','div'): self.result.append(' ')
    def handle_endtag(self, tag):
        if self.depth: self.depth -= 1
        elif tag in ('p','div'): self.result.append(' ')
    def handle_data(self, data):
        if not self.depth: self.result.append(data)

def clean_comment(raw):
    parser=TextParser(); parser.feed(raw or '')
    return re.sub(r'\s+', ' ', html.unescape(' '.join(parser.result))).strip()

def syllables(word):
    sounds=DICT.get(word.lower().replace('’',"'"), [])
    counts={sum(any(ch.isdigit() for ch in part) for part in sound) for sound in sounds}
    return next(iter(counts)) if len(counts)==1 else None

def detect_with_boundaries(text, max_results=150):
    tokens=list(WORDS.finditer(text)); counts=[syllables(t.group()) for t in tokens]
    result=[]
    for start in range(len(tokens)):
        idx=start; lines=[]
        for target in (5,7,5):
            total=0; ws=[]
            while idx<len(tokens) and len(ws)<12 and counts[idx] is not None and total+counts[idx]<=target:
                total+=counts[idx]; ws.append(tokens[idx].group()); idx+=1
                if total==target: break
            if total != target: break
            lines.append(' '.join(ws))
        if len(lines)==3:
            before=text[:tokens[start].start()].rstrip()
            after=text[tokens[idx-1].end():].lstrip()
            result.append((tuple(lines),int(not before or before[-1] in '.!?;:…'),int(not after or after[0] in '.!?;:…')))
            if len(result)>=max_results: break
    return result

def setup(conn):
    conn.executescript('''
       CREATE TABLE IF NOT EXISTS ah_posts(post_id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL, seen_utc TEXT NOT NULL);
       CREATE TABLE IF NOT EXISTS ah_cache(url TEXT PRIMARY KEY, modified TEXT, etag TEXT);
       CREATE TABLE IF NOT EXISTS ah_batches(id INTEGER PRIMARY KEY, scanned_utc TEXT NOT NULL, scan_key INTEGER UNIQUE);
       CREATE TABLE IF NOT EXISTS ah_candidates(id INTEGER PRIMARY KEY, batch_id INTEGER NOT NULL,
         post_id INTEGER NOT NULL, thread_id INTEGER NOT NULL, posted_utc TEXT NOT NULL, original TEXT NOT NULL,
         line1 TEXT NOT NULL,line2 TEXT NOT NULL,line3 TEXT NOT NULL, score REAL NOT NULL,
         category TEXT NOT NULL, UNIQUE(post_id), FOREIGN KEY(batch_id) REFERENCES ah_batches(id));
       CREATE TABLE IF NOT EXISTS ah_publications(slot TEXT PRIMARY KEY, candidate_id INTEGER UNIQUE,
         post_id INTEGER UNIQUE, line1 TEXT NOT NULL,line2 TEXT NOT NULL,line3 TEXT NOT NULL,
         original TEXT, published_utc TEXT NOT NULL, category TEXT NOT NULL);
       CREATE TABLE IF NOT EXISTS ah_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
       CREATE INDEX IF NOT EXISTS ah_candidates_batch_idx ON ah_candidates(batch_id);
    ''')

def api_get(conn, url, delay_state, timeout=18, use_cache=True):
    # Never exceed one request per second (including failures).
    elapsed=time.monotonic()-delay_state[0]
    if elapsed<1.1: time.sleep(1.1-elapsed)
    existing=conn.execute('SELECT modified,etag FROM ah_cache WHERE url=?',(url,)).fetchone()
    headers={'User-Agent':'Anonhaiku/2.0 (read-only poetry experiment)', 'Accept':'application/json'}
    if existing and use_cache:
        if existing[0]: headers['If-Modified-Since']=existing[0]
        if existing[1]: headers['If-None-Match']=existing[1]
    delay_state[0]=time.monotonic()
    try:
        with urlopen(Request(url,headers=headers),timeout=timeout) as response:
            body=json.load(response)
            conn.execute('INSERT OR REPLACE INTO ah_cache VALUES(?,?,?)', (url,response.headers.get('Last-Modified'),response.headers.get('ETag')))
            return body
    except HTTPError as exc:
        if exc.code in (304,404): return None
        raise

def eligible(post):
    # 4chan's metadata marks images and other attachments. Also exclude deleted attachments.
    if any(k in post for k in ATTACHMENT_FIELDS): return False
    raw=post.get('com','')
    if not raw or NUMBERS.search(clean_comment(raw)): return False
    if URLS.search(clean_comment(raw)): return False
    return True

def harvest(conn, scan_key, now, scorer):
    """Returns (new_posts, total_candidates, errors); doesn't create a batch on total API failure."""
    setup(conn)
    if conn.execute('SELECT 1 FROM ah_batches WHERE scan_key=?',(scan_key,)).fetchone(): return (0,0,0)
    state=[0.0]; errors=0
    try:
        catalog=api_get(conn,f'{API}/catalog.json',state,use_cache=False)
    except (HTTPError,URLError,TimeoutError,ValueError,OSError) as exc:
        print('Catalog unavailable:',exc); return (0,0,1)
    if not catalog:
        print('Catalog unavailable or empty; scan not marked complete.')
        return (0,0,0)
    threads=list(dict.fromkeys(t['no'] for page in catalog for t in page.get('threads',[]) if isinstance(t.get('no'),int)))
    print(f'Scan started: {now.isoformat()}; active threads: {len(threads)}', flush=True)
    potential=[]; newposts=0; successes=0; unchanged=0
    for thread_id in threads:
        try:
            data=api_get(conn,f'{API}/thread/{thread_id}.json',state)
        except (HTTPError,URLError,TimeoutError,ValueError,OSError) as exc:
            errors+=1; continue
        successes+=1
        if not data:
            unchanged+=1
            continue
        for post in data.get('posts',[]):
            pid=post.get('no')
            if not isinstance(pid,int) or conn.execute('SELECT 1 FROM ah_posts WHERE post_id=?',(pid,)).fetchone(): continue
            conn.execute('INSERT INTO ah_posts VALUES(?,?,?)',(pid,thread_id,now.isoformat()))
            newposts+=1
            posted_at=datetime.fromtimestamp(post.get('time',int(now.timestamp())),timezone.utc)
            if posted_at < now-timedelta(hours=12) or posted_at > now+timedelta(minutes=5): continue
            if not eligible(post): continue
            original=clean_comment(post['com'])
            try:
                picks=scorer(original)
            except Exception as exc:
                errors+=1; continue
            if picks:
                best=max(picks,key=lambda item:item['score'])
                potential.append(dict(best,post_id=pid,thread_id=thread_id,original=original,
                                      posted_utc=posted_at.isoformat()))
    if not successes:
        conn.commit(); return (newposts,0,max(1,errors))
    # Max 3 distinct original posts, highest-quality candidates from the whole active board.
    potential.sort(key=lambda c:(c['score'],c['posted_utc']),reverse=True)
    batch=conn.execute('INSERT INTO ah_batches(scanned_utc,scan_key) VALUES(?,?)',(now.isoformat(),scan_key)).lastrowid
    for c in potential[:3]:
        conn.execute('''INSERT OR IGNORE INTO ah_candidates
          (batch_id,post_id,thread_id,posted_utc,original,line1,line2,line3,score,category)
          VALUES(?,?,?,?,?,?,?,?,?,?)''',
          (batch,c['post_id'],c['thread_id'],c['posted_utc'],c['original'],*c['lines'],c['score'],c['category']))
    conn.commit()
    print(f'Active threads: {len(threads)}; checked threads: {successes}; unchanged threads: {unchanged}; new posts: {newposts}; valid source candidates: {len(potential)}; shortlist saved: {min(3,len(potential))}; request errors: {errors}',flush=True)
    return newposts,len(potential),errors
