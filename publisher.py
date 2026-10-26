"""Automatic, idempotent local-time publication of accidental haiku."""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from html import escape
from quality import evaluate
from site_builder import display_lines

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'haikus.sqlite3'
SITE = ROOT / 'docs'
TIMEZONE = timezone(timedelta(hours=1))  # fixed GMT+1, no daylight-saving changes
CATEGORIES = ('vulgar', 'poetic', 'unexpected')
# Editorial heuristics. Categories are guides, not language-model judgements.
VULGAR = set('fuck fucked fucking shit bullshit dick cock cum slut slutty horny ass pussy blowjob masturbate damn porn'.split())
POETIC = set('night moon rain wind cold lonely alone sad beautiful summer winter silence sky sun dream dreams sleep dark quiet ocean water stars home friend love lost floor memory'.split())
UNEXPECTED = set('dog guitar sauna theatre oven opium beach beaches awkward weird internet job pay paid money accident accidentally condom mushroom ridiculous'.split())
# Strict, separate guardrail: do not auto-publicize targeted slurs or sexual violence.
# Imperfect by design; for a public site, further review/moderation is recommended.
BLOCK = set('nigger chink faggot kike retard retarded rape raping pedophile pedophilia cp doxx doxxing'.split())

def category_scores(row):
    line = ' '.join(row[f'line{i}'] for i in (1,2,3)).lower().replace('’', "'")
    tokens = set(re.findall(r"[a-z]+", line))
    vulgar = len(tokens & VULGAR)
    poetic = len(tokens & POETIC)
    unexpected = len(tokens & UNEXPECTED)
    # Reward combinations of mundane subject and surprising/melancholic reflection.
    if any(x in line for x in ('sad times', 'i accidentally', 'you can imagine', 'for safety', 'looking back')):
        unexpected += 2
    return {'vulgar':vulgar, 'poetic':poetic, 'unexpected':unexpected}

def safe_to_publish(row):
    text = ' '.join(row[f'line{i}'] for i in (1,2,3)).lower()
    tokens = set(re.findall('[a-z]+', text))
    return not tokens.intersection(BLOCK) and not re.search(r'(?:https?://|www\.|@\w+|\b\d{3}[- .]?\d{3}[- .]?\d{4}\b)', text)

def setup(conn):
    from scanner import setup as scanner_setup
    scanner_setup(conn)
    conn.execute('''CREATE TABLE IF NOT EXISTS publications (
        slot TEXT PRIMARY KEY, category TEXT NOT NULL, haiku_id INTEGER NOT NULL UNIQUE,
        published_utc TEXT NOT NULL,
        FOREIGN KEY (haiku_id) REFERENCES haikus(id))''')
    conn.commit()

def current_slot(now=None):
    local = (now or datetime.now(TIMEZONE)).astimezone(TIMEZONE)
    # Slots begin at 06:00 and 18:00 in fixed GMT+1.
    # Between midnight and 05:59, we still belong to yesterday's 18:00 slot.
    if local.hour < 6:
        slot_day = (local - timedelta(days=1)).date()
        hour = 18
    else:
        slot_day = local.date()
        hour = 6 if local.hour < 18 else 18
    return f'{slot_day:%Y-%m-%d}-{hour:02d}', local

def pick(conn, desired):
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''SELECT h.* FROM haikus h
        LEFT JOIN publications p ON p.haiku_id=h.id
        WHERE p.haiku_id IS NULL ORDER BY h.id DESC''').fetchall()
    choices = []
    for row in rows:
        record = dict(row)
        if not safe_to_publish(record):
            continue
        score, _ = evaluate((record['line1'],record['line2'],record['line3']),
                            record['start_boundary'],record['end_boundary'])
        if score is None:
            continue
        tags = category_scores(record)
        # Allow weaker finds only if stronger ones have been exhausted.
        target_bonus = tags[desired] * 17
        # Category matching is strongly favored but falls back to another category.
        priority = (1 if tags[desired] else 0, score + target_bonus,
                    record['posted_utc'], -record['id'])
        choices.append((priority, record))
    return max(choices, key=lambda x:x[0])[1] if choices else None

def publish(conn, now=None, force=False):
    slot, local = current_slot(now)
    if not force and conn.execute('SELECT 1 FROM publications WHERE slot=?', (slot,)).fetchone():
        print(f'Already published slot {slot}; no duplicate.'); return False
    previous = conn.execute('SELECT COUNT(*) FROM publications').fetchone()[0]
    desired = CATEGORIES[previous % len(CATEGORIES)]
    record = pick(conn, desired)
    if record is None:
        print('No unpublished eligible haiku; retained previous site. Scan more posts.'); return False
    if force and conn.execute('SELECT 1 FROM publications WHERE slot=?', (slot,)).fetchone():
        # Do not overwrite existing slots: force means publish immediately only if missing.
        print('Slot already occupied; force cannot overwrite.'); return False
    conn.execute('INSERT INTO publications VALUES (?,?,?,?)',
                 (slot,desired,record['id'],datetime.now(timezone.utc).isoformat()))
    conn.commit()
    print(f'Published {slot}: {desired} | source {record["source_url"]}')
    return True

def render(conn):
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute('''SELECT p.slot,p.category,h.* FROM publications p
        JOIN haikus h ON h.id=p.haiku_id ORDER BY p.slot DESC''')]
    SITE.mkdir(exist_ok=True)
    def poem(row, archive=False):
        lines = '\n'.join(f'<div class="verse">{escape(x)}</div>' for x in display_lines(row))
        link = escape(row['source_url'],quote=True)
        return f'''<article class="poem"><div class="byline">Anonymous &bull; /b/ &bull; {escape(row['slot'])}</div>
        <div class="haiku">{lines}</div><a href="{link}" target="_blank" rel="noopener noreferrer">Original comment</a></article>'''
    latest = poem(rows[0]) if rows else '<p>No poem has been published yet.</p>'
    archive = '\n'.join(poem(row, True) for row in rows[1:]) or '<p>No older poems yet.</p>'
    common = '''<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Anonhaiku — poetry from /b/</title><style>
    body{margin:0;background:linear-gradient(#fed6ae 0px,#ffffee 220px) fixed;color:#800000;font:14px Helvetica,Arial,sans-serif}
    main{max-width:680px;margin:0 auto;padding:54px 20px 90px} header{text-align:center;margin-bottom:60px}h1{font-size:42px;margin:0 0 8px}
    .subtitle{font-size:12px}.poem{background:#f0e0d6;border:1px solid #d9bfb7;margin-bottom:22px;padding:26px 32px}
    .byline{font-size:12px;color:#117743;font-weight:bold}.haiku{font-size:21px;line-height:1.75;margin:24px 0;color:#800000;overflow-wrap:anywhere}
    .verse{margin:0}a{color:#34345c;text-decoration:underline}nav{text-align:center;margin:25px}footer{text-align:center;font-size:12px;line-height:1.7;padding-top:40px}
    @media(max-width:550px){.haiku{font-size:18px}.poem{padding:20px}h1{font-size:34px}}</style>'''
    def page(body, nav):
        return f'''<!doctype html><html lang="en"><head>{common}</head><body><main><header><h1>Anonhaiku</h1><div class="subtitle">Accidental poetry, found on /b/.</div></header>
        {body}<nav>{nav}</nav><footer>A new haiku every 12 hours. Sorry if it's offensive, blame /b/. Independent project, not affiliated with 4chan.</footer></main></body></html>'''
    (SITE/'index.html').write_text(page(latest,'<a href="archive.html">Previous poems</a>'),encoding='utf-8')
    (SITE/'archive.html').write_text(page(archive,'<a href="index.html">Today’s poem</a>'),encoding='utf-8')
    (SITE/'.nojekyll').touch()
    print('Site generated in docs/index.html and docs/archive.html')

def main():
    parser=argparse.ArgumentParser(description='Publish at 06:00 and 18:00 fixed GMT+1')
    parser.add_argument('--scan',action='store_true',help='Scan current /b/ threads before publishing')
    parser.add_argument('--threads',type=int,default=40)
    parser.add_argument('--force',action='store_true',help='Publish in current 12-hour slot now (if empty)')
    args=parser.parse_args()
    if not 1 <= args.threads <= 100: parser.error('--threads must be between 1 and 100')
    with sqlite3.connect(DB) as conn:
        setup(conn)
        if args.scan:
            from scanner import live
            live(conn,args.threads)
        publish(conn,force=args.force)
        render(conn)
if __name__=='__main__': main()
