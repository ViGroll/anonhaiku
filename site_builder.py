"""Build Anonhaiku static pages; no scanner/publisher/database changes required.

Original post is a screenshot-like SVG reconstruction of the stored original text,
not a literal screenshot from 4chan. Only the current homepage links to it.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from html import escape
import sqlite3
import textwrap

TITLE = "accidental haiku's found on /b/."
FOOTER = ("A new haiku every 12 hours. Sorry if it's offensive, blame /b/. "
          "Independent project, not affiliated with 4chan.")
FIXED_TZ = timezone(timedelta(hours=1))

# Inspired by 4chan's classic dark 'Tomorrow' palette.
CSS = '''
:root{color-scheme:dark;--bg:#1d1f21;--panel:#282a2e;--ink:#c5c8c6;
      --muted:#969896;--border:#373b41;--link:#81a2be;--name:#b5bd68}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);font:14px Helvetica,Arial,sans-serif;color:var(--ink)}
main{max-width:680px;margin:auto;padding:48px 18px 28px}
header{text-align:center;margin-bottom:32px}
h1{font-size:40px;margin:0 0 7px;line-height:1.15}
h1 a{color:var(--ink);text-decoration:none}
h1 a:hover,h1 a:focus-visible{color:var(--link);text-decoration:none}
.subtitle{font-size:12px;color:var(--muted)}
nav{display:flex;gap:30px;justify-content:center;margin:27px 0 36px}
a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}
.poem{background:var(--panel);border:1px solid var(--border);margin:0 0 20px;padding:26px 30px}
.byline{color:var(--name);font-size:12px;font-weight:bold}
.verse{font-size:21px;line-height:1.7;margin-top:16px;overflow-wrap:anywhere}
.verse div{margin:0}
details{margin-top:22px}
summary{cursor:pointer;color:var(--link);width:fit-content}
details img{display:block;width:100%;height:auto;margin-top:15px;border:1px solid var(--border);background:var(--panel)}
footer{text-align:center;font-size:12px;color:var(--muted);margin-top:45px;line-height:1.8}
@media(max-width:600px){main{padding-top:32px}.verse{font-size:18px}.poem{padding:19px}h1{font-size:34px}}
'''

def formatted(lines):
    text = [str(s or '').lower() for s in lines]
    if text:
        text[0] = text[0][:1].upper() + text[0][1:]
    if len(text) > 2:
        text[2] = text[2].rstrip('.!?') + '.'
    return text


def post_timestamp(item):
    """Retained for compatibility; fixed UTC+1, 24-hour EU notation."""
    raw = item.get('published_utc') or ''
    try:
        moment = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(FIXED_TZ).strftime('%H:%M %d/%m/%y')
    except (TypeError, ValueError):
        return ''


def render_poem(item, show_original=False):
    lines = formatted([item['line1'], item['line2'], item['line3']])
    dt = datetime.fromisoformat(item['slot'])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    date = dt.astimezone(FIXED_TZ).strftime('%H:%M (%d/%m/%y)')
    verse = ''.join(f'<div>{escape(line)}</div>' for line in lines)
    original = ''
    if show_original and item.get('original'):
        original = ('<details><summary>Original post</summary>'
                    '<img alt="Reconstructed original 4chan comment" '
                    'src="original.svg" loading="lazy"></details>')
    return (f'<article class="poem"><div class="byline">Anonymous &bull; /b/ &bull; {date}</div>'
            f'<div class="verse">{verse}</div>{original}</article>')


def wrap_html(body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="theme-color" content="#1d1f21">'
            '<title>Anonhaiku.org</title><style>' + CSS + '</style></head><body>'
            '<main><header><h1><a href="index.html" aria-label="Anonhaiku.org - today">'
            'Anonhaiku.org</a></h1><div class="subtitle">' + escape(TITLE) + '</div></header>'
            '<nav aria-label="Primary"><a href="index.html">Today’s haiku</a>'
            '<a href="archive.html">Archive</a></nav>' + body +
            '<footer>' + escape(FOOTER) + '</footer></main></body></html>')


def save_svg(text, filename):
    """Render all stored source text without arbitrary 45-line clipping."""
    lines = []
    for paragraph in str(text).split('\n'):
        # Preserve blank lines, and wrap for readability rather than discarding text.
        lines.extend(textwrap.wrap(paragraph, width=66, break_long_words=True,
                                   break_on_hyphens=False, replace_whitespace=False,
                                   drop_whitespace=False) or [''])
    height = max(135, 82 + len(lines) * 20 + 24)
    tspans = ''.join(f'<tspan x="22" dy="20">{escape(line)}</tspan>' for line in lines)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="690" height="{height}" '
           f'viewBox="0 0 690 {height}" role="img">'
           '<rect width="690" height="100%" fill="#282a2e"/>'
           '<rect x="1" y="1" width="688" height="100%" fill="none" stroke="#373b41"/>'
           '<text x="22" y="33" fill="#b5bd68" font-family="Arial,sans-serif" '
           'font-weight="bold" font-size="15">Anonymous</text>'
           f'<text x="22" y="57" fill="#c5c8c6" font-family="Arial,sans-serif" '
           f'font-size="15" xml:space="preserve">{tspans}</text></svg>')
    Path(filename).write_text(svg, encoding='utf-8')


def build(conn, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    conn.row_factory = sqlite3.Row
    current = conn.execute('SELECT * FROM ah_publications ORDER BY slot DESC LIMIT 1').fetchone()
    history = conn.execute('SELECT * FROM ah_publications ORDER BY slot DESC').fetchall()
    screenshot = folder / 'original.svg'
    if history:
        homepage = render_poem(dict(current), show_original=True)
        if current['original']:
            save_svg(current['original'], screenshot)
        elif screenshot.exists():
            screenshot.unlink()
        # Archive entries contain NO 'Original post' section or screenshot link.
        archived = ''.join(render_poem(dict(row), show_original=False) for row in history)
    else:
        homepage = '<p style="text-align:center">The first haiku is being discovered.</p>'
        archived = '<p style="text-align:center">No poems published yet.</p>'
        if screenshot.exists():
            screenshot.unlink()
    (folder / 'index.html').write_text(wrap_html(homepage), encoding='utf-8')
    (folder / 'archive.html').write_text(wrap_html(archived), encoding='utf-8')
    (folder / '.nojekyll').touch()
