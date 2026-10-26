"""Generate a standalone HTML file; no hosting or JS necessary."""
from html import escape
from datetime import datetime
def display_lines(row):
    lines = [row[f"line{i}"].lower() for i in (1, 2, 3)]
    lines[0] = lines[0][:1].upper() + lines[0][1:]
    lines[-1] = lines[-1].rstrip(".!? ") + "."
    return lines



def export_html(path, candidates):
    sections = []
    for i, row in enumerate(candidates):
        lines = ''.join('<div class="verse">'+escape(line)+'</div>' for line in display_lines(row))
        source = escape(row['source_url'], quote=True)
        date = escape(row['posted_utc'][:10])
        sections.append(f'<article class="poem" id="poem-{i}"><div class="byline">Anonymous &bull; /b/ &bull; {date}</div><div class="haiku">{lines}</div><a href="{source}" target="_blank" rel="noopener noreferrer">View original comment</a></article>')
    content = '\n'.join(sections) or '<p>No filtered haikus yet. Run the scanner first.</p>'
    html = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Anonhaiku — accidental poetry from /b/</title><style>
    :root { color-scheme: light; } body { margin:0; background:linear-gradient(#fed6ae 0px,#ffffee 220px); background-attachment:fixed; color:#800000; font:14px Helvetica,Arial,sans-serif; }
    main {max-width:680px; margin:0 auto; padding:54px 20px 90px;} header{text-align:center;margin-bottom:65px;} h1{font-size:40px;letter-spacing:-1px;margin:0 0 8px;} .sub{font-size:12px;opacity:.83;}
    .poem{background:#f0e0d6;border:1px solid #d9bfb7;margin-bottom:22px;padding:26px 32px;box-shadow:1px 1px 0 #ded3cc;} .byline{font-size:12px;color:#117743;font-weight:bold}.haiku{font-size:21px;line-height:1.75;color:#800000;margin:24px 0 22px;overflow-wrap:anywhere}.verse{margin:0}a{color:#0000ee;text-decoration:none}a:hover{text-decoration:underline}footer{text-align:center;font-size:12px;line-height:1.7;padding-top:40px} @media(max-width:550px){.haiku{font-size:18px}.poem{padding:20px}main{padding-top:35px}h1{font-size:33px}}
    </style></head><body><main><header><h1>Anonhaiku</h1><div class="sub">Accidental poetry, found in the noise.</div></header><section>''' + content + '''</section><footer>Independent poetry experiment · Source: public posts on 4chan /b/ · Not affiliated with 4chan.<br>Local preview only; nothing is published automatically.</footer></main></body></html>'''
    path.write_text(html, encoding='utf-8')
