"""Generate static HTML and a faithful text image from the source comment."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from html import escape
import re
import textwrap
from datetime import datetime, timedelta, timezone

TITLE='Accidental poetry, found on /b/.'
FOOTER="A new haiku every 12 hours. Sorry if it's offensive, blame /b/. Independent project, not affiliated with 4chan."
CSS='''body{margin:0;background:linear-gradient(#fed6ae,#ffffee 220px);background-attachment:fixed;font:14px Helvetica,Arial,sans-serif;color:#800000}main{max-width:680px;margin:auto;padding:48px 18px}header{text-align:center;margin-bottom:36px}h1{font-size:40px;margin:0 0 7px}.subtitle{font-size:12px}nav{display:flex;gap:30px;justify-content:center;margin:27px 0 36px}a{color:#34345c;text-decoration:none}a:hover{text-decoration:underline}.poem{background:#f0e0d6;border:1px solid #d9bfb7;margin:0 0 20px;padding:26px 30px}.byline{color:#117743;font-size:12px;font-weight:bold}.verse{font-size:21px;line-height:1.7;overflow-wrap:anywhere}.verse div{margin:0}details{margin-top:22px}summary{cursor:pointer;color:#34345c}details img{display:block;width:100%;height:auto;margin-top:15px;border:1px solid #d9bfb7}footer{text-align:center;font-size:12px;margin-top:45px;line-height:1.8}@media(max-width:600px){.verse{font-size:18px}.poem{padding:19px}}'''

def formatted(lines):
    text=[s.lower() for s in lines]
    text[0]=text[0][:1].upper()+text[0][1:]
    text[2]=text[2].rstrip('.!?')+'.'
    return text

FIXED_TZ = timezone(timedelta(hours=1))

def post_timestamp(item):
    """Show publication timestamp using Anonhaiku fixed UTC+1; EU 24h format."""
    raw = item.get('published_utc') or ''
    try:
        moment = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(FIXED_TZ).strftime('%H:%M %d/%m/%y')
    except (TypeError, ValueError):
        return ''

def render_poem(item,show_original=False):
    lines=formatted([item['line1'],item['line2'],item['line3']])
    dt=datetime.fromisoformat(item['slot']).astimezone(timezone(timedelta(hours=1)))
    date=dt.strftime('%H:%M (%d/%m/%y)')
    text=''.join(f'<div>{escape(line)}</div>' for line in lines)
    original=''
    if show_original and item.get('original'):
        original=f'<details><summary>Original post</summary><img alt="Original 4chan comment, preserved as text" src="original.svg"></details>'
    return f'<article class="poem"><div class="byline">Anonymous &bull; /b/ &bull; {date}</div><div class="verse">{text}</div>{original}</article>'

def wrap_html(body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
      '<title>Anonhaiku</title><style>'+CSS+'</style></head><body><main><header><h1>Anonhaiku</h1><div class="subtitle">'+TITLE+'</div></header>'
      '<nav><a href="index.html">Today’s haiku</a><a href="archive.html">Archive</a></nav>'+body+'<footer>'+FOOTER+'</footer></main></body></html>')

def save_svg(text,filename):
    # Text-accurate reconstruction, not a literal screenshot of 4chan. No external content.
    lines=[]
    for paragraph in text.splitlines():
        lines.extend(textwrap.wrap(paragraph,width=66,break_long_words=True,break_on_hyphens=False) or [''])
    lines=lines[:45]
    height=max(135,90+len(lines)*20)
    spans=''.join(f'<tspan x="22" dy="20">{escape(line)}</tspan>' for line in lines)
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="690" height="{height}" viewBox="0 0 690 {height}">'
         '<rect width="690" height="100%" fill="#f0e0d6"/><text x="22" y="33" fill="#117743" font-family="Arial" font-weight="bold" font-size="15">Anonymous</text>'
         f'<text x="22" y="60" fill="#800000" font-family="Arial" font-size="15">{spans}</text></svg>')
    Path(filename).write_text(svg,encoding='utf-8')

def build(conn,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    conn.row_factory=__import__('sqlite3').Row
    current=conn.execute('SELECT * FROM ah_publications ORDER BY slot DESC LIMIT 1').fetchone()
    history=conn.execute('SELECT * FROM ah_publications ORDER BY slot DESC').fetchall()
    if history:
        homepage=render_poem(dict(current),show_original=True)
        if current['original']: save_svg(current['original'],folder/'original.svg')
        elif (folder/'original.svg').exists(): (folder/'original.svg').unlink()
        archived=''.join(render_poem(dict(row)) for row in history)
    else:
        homepage='<p style="text-align:center">The first haiku is being discovered.</p>'
        archived='<p style="text-align:center">No poems published yet.</p>'
        if (folder/'original.svg').exists(): (folder/'original.svg').unlink()
    (folder/'index.html').write_text(wrap_html(homepage),encoding='utf-8')
    (folder/'archive.html').write_text(wrap_html(archived),encoding='utf-8')
    (folder/'.nojekyll').touch()
