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

