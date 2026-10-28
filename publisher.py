"""Anonhaiku 2.0 CLI. Examples: python publisher.py --run; --test; --build."""
from __future__ import annotations
import argparse
import sqlite3
import time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from scanner import setup, harvest
from selection import score_comment, overlaps, category_counts, rank_candidate, normalized
from site_builder import build

ROOT=Path(__file__).resolve().parent
DB=ROOT/'haikus.sqlite3'; DOCS=ROOT/'docs'
UTC=timezone.utc
FIXED=timezone(timedelta(hours=1))
# Scans are spaced >=150 minutes, checked by GitHub every 30 min.
SCAN_SECONDS=150*60
CATEGORIES=('vulgar','poetic','unexpected')

def slot_for(now):
    local=now.astimezone(FIXED)
    if local.hour<6: local=(local-timedelta(days=1)); hour=18
    else: hour=6 if local.hour<18 else 18
    dt=local.replace(hour=hour,minute=0,second=0,microsecond=0)
    return dt.astimezone(UTC)

def previous_slot(slot): return slot-timedelta(hours=12)

def legacy_import(conn):
    """Import ONLY published legacy haikus. Never import old pending candidates."""
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'publications' not in tables or 'haikus' not in tables: return 0
    count=0
    rows=conn.execute('''SELECT p.slot,p.category,p.published_utc,h.post_id,h.line1,h.line2,h.line3
        FROM publications p JOIN haikus h ON h.id=p.haiku_id ORDER BY p.slot''').fetchall()
    for slot,cat,published,post_id,a,b,c in rows:
        # Previous slots were YYYY-MM-DD-HH in fixed UTC+1.
        slot_date=slot[:10]; hour=int(slot[-2:]); dt=datetime.fromisoformat(f'{slot_date}T{hour:02d}:00:00').replace(tzinfo=FIXED).astimezone(UTC)
        result=conn.execute('''INSERT OR IGNORE INTO ah_publications
          (slot,candidate_id,post_id,line1,line2,line3,original,published_utc,category)
          VALUES(?,NULL,?,?,?,?,NULL,?,?)''',
          (dt.isoformat(),post_id,a,b,c,published,cat))
        count+=result.rowcount
    conn.commit()
    return count

def old_history(conn):
    result=list(conn.execute('SELECT post_id,line1,line2,line3 FROM ah_publications'))
    return result

def choose(conn,slot):
    """Select one from the 4 most recent scan batches within previous publication window."""
    conn.row_factory=sqlite3.Row
    since=previous_slot(slot)
    # scans from (previous publication, current publication] only, no multi-day leftovers
    batches=conn.execute('''SELECT id FROM ah_batches WHERE scanned_utc>? AND scanned_utc<=?
      ORDER BY scanned_utc DESC LIMIT 4''',(since.isoformat(),slot.isoformat())).fetchall()
    if not batches: return None
    ids=[b['id'] for b in batches]
    marks=','.join('?' for _ in ids)
    records=conn.execute(f'SELECT * FROM ah_candidates WHERE batch_id IN ({marks}) ORDER BY score DESC',ids).fetchall()
    published=old_history(conn)
    desired=CATEGORIES[len(published)%3]
    picks=[]
    for row in records:
        if any(row['post_id']==old[0] for old in published): continue
        lines=(row['line1'],row['line2'],row['line3'])
        if any(overlaps(lines,(old[1],old[2],old[3])) for old in published): continue
        if not rank_candidate(lines,1,1): continue
        scores=category_counts(lines)
        priority=(int(scores[desired]>0),row['score']+scores[desired]*18,row['posted_utc'])
        picks.append((priority,dict(row)))
    return max(picks,key=lambda x:x[0])[1] if picks else None

def maybe_publish(conn,now):
    slot=slot_for(now)
    if conn.execute('SELECT 1 FROM ah_publications WHERE slot=?',(slot.isoformat(),)).fetchone():
        print('Already published this slot.');return False
    chosen=choose(conn,slot)
    if chosen is None:
        print('No fresh eligible candidate. Keep previous homepage.');return False
    old_count=conn.execute('SELECT COUNT(*) FROM ah_publications').fetchone()[0]
    conn.execute('''INSERT INTO ah_publications
      (slot,candidate_id,post_id,line1,line2,line3,original,published_utc,category)
      VALUES(?,?,?,?,?,?,?,?,?)''',
      (slot.isoformat(),chosen['id'],chosen['post_id'],chosen['line1'],chosen['line2'],chosen['line3'],chosen['original'],now.isoformat(),CATEGORIES[old_count%3]))
    # Remove all candidates in previous window: no old fragments can leak to future publication.
    conn.execute('DELETE FROM ah_candidates WHERE batch_id IN (SELECT id FROM ah_batches WHERE scanned_utc<=?)',(now.isoformat(),))
    conn.commit()
    print('Published:',chosen['line1'],'/',chosen['line2'],'/',chosen['line3'])
    return True

def due_scan(conn,now):
    last=conn.execute('SELECT scanned_utc FROM ah_batches ORDER BY scanned_utc DESC LIMIT 1').fetchone()
    if not last: return True
    return (now-datetime.fromisoformat(last[0])).total_seconds()>=SCAN_SECONDS

def run(now=None,scan=True,publish=True):
    now=now or datetime.now(UTC)
    with sqlite3.connect(DB) as conn:
        setup(conn)
        imported=legacy_import(conn)
        if imported: print('Imported legacy published poems:',imported)
        # Publish BEFORE scanning, so current-slot fresh scans cannot be used in the previous window.
        if publish: maybe_publish(conn,now)
        if scan and due_scan(conn,now):
            scan_key=int(now.timestamp()//SCAN_SECONDS)
            harvest(conn,scan_key,now,score_comment)
        # After startup, always regenerate even if no new candidate.
        build(conn,DOCS)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='store_true',help='Scan if due, publish if due, rebuild site')
    parser.add_argument('--build',action='store_true',help='Only rebuild site')
    parser.add_argument('--scan',action='store_true',help='Run scan if due; retain legacy command compatibility')
    args=parser.parse_args()
    run(scan=not args.build,publish=not args.build)
