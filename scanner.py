"""Accidental 5-7-5 haiku finder for public /b/ comments.

Requires: pip install pronouncing
Usage: python scanner.py --demo | python scanner.py --live --threads 8
"""
from __future__ import annotations
import argparse
import html
from html.parser import HTMLParser
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cmudict
from quality import best_candidates

PRONUNCIATIONS = cmudict.dict()

DB = Path(__file__).with_name('haikus.sqlite3')
API = 'https://a.4cdn.org/b'
TOKEN = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
LINK = re.compile(r'(?i)https?://\S+|www\.\S+')

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get('class', '')
        if tag in {'script', 'style'} or (tag == 'span' and ('quote' in classes.split() or 'deadlink' in classes.split())) or tag == 'a':
            self.skip += 1
        elif tag == 'br':
            self.out.append(' ')
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'span', 'a'} and self.skip:
            self.skip -= 1
        elif tag in {'p', 'div'}:
            self.out.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

def clean_comment(raw: str) -> str:
    p = TextParser()
    p.feed(raw or '')
    s = html.unescape(' '.join(p.out))
    s = LINK.sub(' ', s)
    # Collapse boundaries; we deliberately do NOT require original line breaks.
    return re.sub(r'\s+', ' ', s).strip()

def syllables(word: str) -> int | None:
    word = word.lower().replace('’', "'")
    phones = PRONUNCIATIONS.get(word, [])
    if not phones:
        return None  # Precision first: skip unknown slang for MVP.
    counts = {sum(any(ch.isdigit() for ch in phoneme) for phoneme in p) for p in phones}
    return next(iter(counts)) if len(counts) == 1 else None

def detect_with_boundaries(text: str, max_results: int = 60):
    matches = list(TOKEN.finditer(text))
    words = [m.group() for m in matches]
    counts = [syllables(w) for w in words]
    found = []
    for start in range(len(words)):
        if counts[start] is None:
            continue
        lines = []
        index = start
        for target in (5, 7, 5):
            subtotal, line = 0, []
            while index < len(words) and len(line) < 12:
                count = counts[index]
                if count is None or subtotal + count > target:
                    break
                subtotal += count
                line.append(words[index])
                index += 1
                if subtotal == target:
                    break
            if subtotal != target:
                break
            lines.append(' '.join(line))
        if len(lines) == 3:
            result = tuple(lines)
            before = text[:matches[start].start()].rstrip()
            after = text[matches[index-1].end():].lstrip()
            starts = not before or before[-1] in '.!?;:…'
            ends = not after or after[0] in '.!?;:…'
            candidate = (result, int(starts), int(ends))
            if candidate not in found:
                found.append(candidate)
                if len(found) >= max_results:
                    break
    return found

def detect(text: str, max_results: int = 25):
    return [lines for lines, _, _ in detect_with_boundaries(text, max_results)]

def setup(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS posts (post_id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS haikus (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          post_id INTEGER NOT NULL,
          thread_id INTEGER NOT NULL,
          posted_utc TEXT NOT NULL,
          line1 TEXT NOT NULL, line2 TEXT NOT NULL, line3 TEXT NOT NULL,
          source_url TEXT NOT NULL,
          start_boundary INTEGER, end_boundary INTEGER,
          UNIQUE(post_id, line1, line2, line3));
        CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, last_modified TEXT NOT NULL);
    ''')
    existing = {row[1] for row in conn.execute('PRAGMA table_info(haikus)')}
    for column in ('start_boundary', 'end_boundary'):
        if column not in existing:
            conn.execute(f'ALTER TABLE haikus ADD COLUMN {column} INTEGER')

def store_posts(conn, posts, thread_id):
    scanned, discovered = 0, 0
    for p in posts:
        pid = p.get('no')
        if not isinstance(pid, int):
            continue
        comment = clean_comment(p.get('com', ''))
    if any(char.isdigit() for char in comment):
            continue
        cur = conn.execute('INSERT OR IGNORE INTO posts(post_id,thread_id) VALUES(?,?)', (pid, thread_id))
        if not cur.rowcount:
            continue
        scanned += 1
        for lines, starts, ends in detect_with_boundaries(clean_comment(p.get('com', ''))):
            url = f'https://boards.4chan.org/b/thread/{thread_id}#p{pid}'
            timestamp = datetime.fromtimestamp(p.get('time', time.time()), timezone.utc).isoformat()
            cur = conn.execute('''INSERT OR IGNORE INTO haikus
              (post_id,thread_id,posted_utc,line1,line2,line3,source_url,start_boundary,end_boundary)
              VALUES(?,?,?,?,?,?,?,?,?)''', (pid,thread_id,timestamp,*lines,url,starts,ends))
            discovered += cur.rowcount
    conn.commit()
    return scanned, discovered

class Client:
    def __init__(self, conn):
        self.conn = conn
        self.last = 0.0
    def get(self, url):
        elapsed = time.monotonic() - self.last
        if self.last and elapsed < 1.15:
            time.sleep(1.15 - elapsed)
        stored = self.conn.execute('SELECT last_modified FROM cache WHERE url=?', (url,)).fetchone()
        headers = {'User-Agent': 'AnonhaikuResearchPrototype/0.2 (read-only haiku experiment)', 'Accept': 'application/json'}
        if stored:
            headers['If-Modified-Since'] = stored[0]
        self.last = time.monotonic()
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                payload = json.load(response)
                changed = response.headers.get('Last-Modified')
                if changed:
                    self.conn.execute('INSERT OR REPLACE INTO cache VALUES (?,?)', (url,changed))
                    self.conn.commit()
                return payload
        except HTTPError as e:
            if e.code in (304, 404):
                return None
            raise

def live(conn, limit):
    client = Client(conn)
    index = client.get(API + '/threads.json')
    if index is None:
        print('Thread index unchanged; no new scans in this run.')
        return
    threads = [item['no'] for page in index for item in page['threads']]
    scanned = hits = 0
    for tid in threads[:limit]:
        try:
            thread = client.get(f'{API}/thread/{tid}.json')
            if thread is None:
                continue
            a,b = store_posts(conn, thread.get('posts', []), tid)
            scanned += a
            hits += b
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            print(f'Thread {tid}: {exc}')
    print(f'New posts scanned: {scanned}; new candidate haikus: {hits}')

def demo(conn):
    sample = [
      {'no': 100001, 'time': 1761470000, 'com': 'the old cat is here and the rain is falling on us it is a cold day'},
      {'no': 100002, 'time': 1761470000, 'com': 'hello world this is just a test'},
      {'no': 100003, 'time': 1761470000, 'com': 'the moon is so bright and the wind is blowing all night the sun will come soon'},
    ]
    n,k = store_posts(conn, sample, 999999)
    print(f'Demo: {n} posts processed, {k} candidates. Example posts are invented, not sourced from 4chan.')

def print_candidates(conn, limit, strict=True):
    conn.row_factory = sqlite3.Row
    if strict:
        # Evaluate existing database candidates as well as new ones.
        rows = conn.execute('SELECT * FROM haikus ORDER BY id DESC').fetchall()
        records = best_candidates(rows, limit=limit)
    else:
        records = [dict(r) for r in conn.execute('SELECT * FROM haikus ORDER BY id DESC LIMIT ?', (limit,))]
    if not records:
        print('Geen geschikte kandidaat. Probeer meer threads of --all om de ruwe resultaten te bekijken.')
    for r in records:
        label = f"  Quality score: {r['score']} / heuristic" if strict else ''
        print(f"\n{r['line1']}\n{r['line2']}\n{r['line3']}\n  Source: {r['source_url']}\n  Original timestamp (UTC): {r['posted_utc']}\n{label}")
    if records:
        print('\nATTENTION: Heuristic ranking is not AI quality assurance or safety moderation. Review before publishing.')


def export_site(conn):
    from site_builder import export_html
    conn.row_factory = sqlite3.Row
    candidates = best_candidates(conn.execute('SELECT * FROM haikus ORDER BY id DESC').fetchall(), limit=100)
    outfile = Path(__file__).with_name('anonhaiku-preview.html')
    export_html(outfile, candidates)
    print(f'Websitevoorbeeld gemaakt: {outfile}')

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--demo', action='store_true', help='Use invented test comments, without network')
    mode.add_argument('--live', action='store_true', help='Read current public /b/ threads')
    mode.add_argument('--review', action='store_true', help='Review all saved candidates without network')
    parser.add_argument('--threads', type=int, default=8, help='Number of active threads to scan (default 8)')
    parser.add_argument('--show', type=int, default=10, help='Candidates to print')
    parser.add_argument('--all', action='store_true', help='Show raw unfiltered results')
    parser.add_argument('--site', action='store_true', help='Make local HTML preview using filtered candidates')
    args = parser.parse_args()
    if args.threads < 1 or args.threads > 100:
        parser.error('--threads must be between 1 and 100')
    with sqlite3.connect(DB) as conn:
        setup(conn)
        if args.demo:
            demo(conn)
        elif args.live:
            live(conn, args.threads)
        print_candidates(conn, args.show, strict=not args.all)
        if args.site:
            export_site(conn)

if __name__ == '__main__':
    main()
