#!/usr/bin/env python3
"""Generate 秋芝2046 Stellarium-inspired web page with knowledge card overlays."""
import json, re, pathlib, html as html_mod

BASE = pathlib.Path(r'D:\视频下载\秋芝2046\蒸馏交付物\秋芝2046-mentor-lineage\references')
OUT = pathlib.Path(r'D:\视频下载\秋芝2046\蒸馏交付物\秋芝2046-mentor-lineage\web\index.html')

pkg = json.loads((BASE / 'course_package.json').read_text(encoding='utf-8'))
digest = (BASE / 'course_digest.md').read_text(encoding='utf-8')
quotes_md = (BASE / 'quote_index.md').read_text(encoding='utf-8')
audit = json.loads((BASE / 'distillation_audit.json').read_text(encoding='utf-8'))

def esc(s):
    return html_mod.escape(str(s))

# --- Parse modules ---
modules = []
lines = digest.split('\n')
i = 0
in_sec = False
while i < len(lines):
    line = lines[i].rstrip()
    if '每个模块下对应的课程' in line:
        in_sec = True
        i += 1
        continue
    if in_sec and line.startswith('### ') and '递进' in line:
        break
    if not in_sec or not re.match(r'^- \*\*(.+?)\*\*$', line.strip()):
        i += 1
        continue
    name = re.match(r'^- \*\*(.+?)\*\*$', line.strip()).group(1).strip()
    lessons = []
    i += 1
    while i < len(lines):
        l = lines[i].rstrip()
        if l == '':
            i += 1
            continue
        if re.match(r'^- \*\*(.+?)\*\*$', l.strip()):
            break
        if re.match(r'^\s+- ', l):
            lessons.append(re.sub(r'^\s+- ', '', l).strip())
        else:
            break
        i += 1
    modules.append((name, lessons))

# --- Parse lessons ---
lessons_list = []
in_lessons = False
for line in digest.split('\n'):
    if '逐课精要' in line and '##' in line:
        in_lessons = True
        continue
    if in_lessons and line.startswith('## '):
        break
    if in_lessons and line.startswith('- **'):
        m = re.match(r'^- \*\*(.+?)\*\*', line.strip())
        if m:
            lessons_list.append(m.group(1).strip())

# --- Parse topics ---
topics = []
ti = -1
in_topics = False
for line in digest.split('\n'):
    s = line.strip()
    if '跨课程主题图谱' in line and '##' in line:
        in_topics = True
        ti = -1
        continue
    if in_topics and line.startswith('## ') and '跨课程主题图谱' not in line:
        in_topics = False
        continue
    if in_topics:
        m = re.match(r'^\d+\.\s\*\*(.+?)\*\*', s)
        if m:
            ti += 1
            topics.append({'name': m.group(1).strip(), 'courses': [], 'view': ''})
        elif ti >= 0 and '课程位置' in s:
            ct = s.split('：', 1)[-1] if '：' in s else s
            topics[ti]['courses'] = [c.strip() for c in re.split(r'[;；]', ct) if c.strip()]
        elif ti >= 0 and '核心观点' in s:
            vt = s.split('：', 1)[-1] if '：' in s else s
            topics[ti]['view'] = vt.strip()

# --- Parse quotes ---
quotes = []
for line in quotes_md.split('\n'):
    m = re.match(r'^\d+\.\s+\*\*[^a-zA-Z0-9\s*](.+?)[^a-zA-Z0-9\s*]\*\*', line)
    if m:
        q = m.group(1).strip()
        sm = re.search(r'—\s*(.+?)(?:[【\[]|$)', line)
        quotes.append({'text': q, 'source': sm.group(1).strip() if sm else ''})

# --- Parse actions ---
actions = []
in_a = False
pri = 'medium'
for line in digest.split('\n'):
    if '可执行行动清单' in line:
        in_a = True
        continue
    if in_a and line.startswith('## '):
        break
    if in_a and line.startswith('### '):
        if '高优先级' in line:
            pri = 'high'
        elif '低优先级' in line:
            pri = 'low'
        else:
            pri = 'medium'
        continue
    if in_a:
        m = re.match(r'^\d+\.\s+(.+)$', line.strip())
        if m:
            a = m.group(1).strip().rstrip('。').strip()
            if a:
                actions.append({'text': a, 'priority': pri})

# --- Load OKF concepts ---
okf = []
okf_dir = BASE / 'okf' / 'concepts'
if okf_dir.exists():
    for f in sorted(okf_dir.glob('*.md')):
        if f.stem == 'index':
            continue
        c = f.read_text(encoding='utf-8')
        tm = re.search(r'^title:\s*(.+)$', c, re.M)
        dm = re.search(r'^description:\s*(.+)$', c, re.M)
        okf.append({'id': f.stem, 'title': tm.group(1).strip() if tm else f.stem, 'desc': dm.group(1).strip() if dm else ''})

# --- Stats ---
chunks_path = BASE.parent / 'text_sources' / 'chunks.jsonl'
chunks = len([l for l in chunks_path.read_text(encoding='utf-8').splitlines() if l.strip()]) if chunks_path.exists() else 116
cards_path = BASE.parent / 'text_distillation' / 'evidence_cards.jsonl'
cards = len([l for l in cards_path.read_text(encoding='utf-8').splitlines() if l.strip()]) if cards_path.exists() else 59
gen_date = audit.get('generated_at', '2026-07-08')[:10]

colors = ['#f0c040', '#5dade2', '#58d68d', '#ec7063', '#bb8fce']

# --- Concept detail map ---
concept_map = {}
for c in pkg.get('concepts', []):
    # Strip markdown bold: **Term**: definition
    clean = re.sub(r'\*\*', '', c)
    clean = re.split(r'[：:]', clean)[0].strip()
    # Find OKF description
    desc = clean
    for o in okf:
        if o['title'] in c or c in o['title']:
            if o['desc']:
                desc = o['desc']
            break
    concept_map[clean] = {'title': clean, 'desc': desc, 'type': 'Concept', 'related': []}

all_names = list(concept_map.keys())
for name in all_names:
    related = [c for c in all_names if c != name][:6]
    concept_map[name]['related'] = related

concept_js = json.dumps(concept_map, ensure_ascii=False)

# ============================================================
# BUILD HTML
# ============================================================
O = []

# --- CSS (Stellarium theme) ---
O.append('<style>')
O.append(':root{--bg:#1e1e1f;--bgp:#2b2b2c;--bgc:#2a2a2d;--bgh:#353538;--bgs:#3d3d41;--bd:#444448;--bds:#38383b;--t1:#d4d4d4;--t2:#9e9ea3;--t3:#6b6b70;--g:#a28c42;--g2:#c9a84c;--a:#f5b041;--h:#fdd886;--hbg:rgba(253,216,134,0.12);--gp:linear-gradient(180deg,#2d2d30,#1e1e1f);--gc:linear-gradient(135deg,#2f2f32,#28282b);--fu:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;--fm:"Cascadia Code","Fira Code",Consolas,monospace;--r:2px;--sh:0 2px 8px rgba(0,0,0,0.5)}')
O.append('*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}body{font-family:var(--fu);background:var(--bg);color:var(--t1);font-size:13px;line-height:1.6;min-height:100vh;display:flex;flex-direction:column}')
O.append('::-webkit-scrollbar{width:5px;height:5px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--bd);border-radius:3px}')
O.append('.hdr{background:var(--gp);border-bottom:1px solid var(--bd);position:sticky;top:0;z-index:200;box-shadow:0 1px 6px rgba(0,0,0,0.4)}')
O.append('.hi{max-width:1400px;margin:0 auto;padding:10px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}')
O.append('.brand{display:flex;align-items:center;gap:10px}.bi{width:30px;height:30px;border-radius:var(--r);background:linear-gradient(135deg,var(--g2),var(--g));display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:700;color:#1a1a1a;flex-shrink:0}')
O.append('.bt{font-size:15px;font-weight:600}.bs{font-size:10px;color:var(--t3);letter-spacing:.8px;text-transform:uppercase}')
O.append('.sw{position:relative;margin-left:auto}.sw input{width:240px;padding:6px 10px 6px 28px;background:var(--bg);border:1px solid var(--bd);border-radius:var(--r);color:var(--t1);font-size:12px;font-family:var(--fu)}.sw input:focus{outline:none;border-color:var(--g)}.sw input::placeholder{color:var(--t3)}.sw .si{position:absolute;left:8px;top:50%;transform:translateY(-50%);color:var(--t3);font-size:12px;pointer-events:none}')
O.append('.sb{background:var(--bgp);border-bottom:1px solid var(--bds)}.sbi{max-width:1400px;margin:0 auto;padding:6px 20px;display:flex;gap:18px;overflow-x:auto}.st{display:flex;align-items:baseline;gap:5px;white-space:nowrap}.sv{font-family:var(--fm);font-size:13px;font-weight:700;color:var(--h)}.sl{font-size:10px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px}')
O.append('.layout{display:flex;flex:1;max-width:1400px;margin:0 auto;width:100%}')
O.append('.sidebar{width:210px;min-width:210px;background:var(--bgp);border-right:1px solid var(--bd);padding:6px 0;overflow-y:auto;max-height:calc(100vh - 100px);position:sticky;top:78px}')
O.append('.sbs{margin-bottom:1px}.sbh{display:flex;align-items:center;gap:6px;padding:6px 12px;cursor:pointer;user-select:none;color:var(--t3);font-size:11px;text-transform:uppercase;letter-spacing:.7px;border-left:2px solid transparent;transition:all .15s}.sbh:hover{color:var(--t1);background:rgba(255,255,255,0.02)}.sbh.act{color:var(--h);border-left-color:var(--g2);background:var(--bgs)}.sbh .arr{font-size:8px;transition:transform .15s;width:10px;text-align:center}.sbh.open .arr{transform:rotate(90deg)}.sbi2{display:none}.sbi2.open{display:block}')
O.append('.sbitem{display:block;padding:3px 12px 3px 26px;color:var(--t2);font-size:11px;cursor:pointer;border-left:2px solid transparent;transition:all .15s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sbitem:hover{color:var(--t1);background:rgba(255,255,255,0.03)}.sbitem.act{color:var(--h);background:var(--hbg);border-left-color:var(--g)}')
O.append('.main{flex:1;overflow-y:auto;max-height:calc(100vh - 78px)}')
O.append('.tnav{background:var(--bgp);border-bottom:1px solid var(--bd);display:flex;padding:0 12px;overflow-x:auto;scrollbar-width:none}.tnav::-webkit-scrollbar{display:none}')
O.append('.tbtn{padding:9px 12px;background:0 0;border:none;border-bottom:2px solid transparent;color:var(--t2);font-size:12px;font-family:var(--fu);cursor:pointer;white-space:nowrap;transition:all .15s}.tbtn:hover{color:var(--t1)}.tbtn.act{color:var(--h);border-bottom-color:var(--g2)}')
O.append('.tbd{display:inline-block;font-size:9px;padding:1px 5px;border-radius:7px;background:var(--bg);color:var(--t3);margin-left:3px;font-family:var(--fm)}.tbtn.act .tbd{background:var(--g);color:#1a1a1a}')
O.append('.panel{display:none;padding:18px}.panel.act{display:block;animation:fi .2s ease}@keyframes fi{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}')
O.append('.sh{display:flex;align-items:center;gap:10px;margin-bottom:14px;padding-bottom:8px;border-bottom:1px solid var(--bds)}.si2{width:24px;height:24px;border-radius:var(--r);background:linear-gradient(135deg,var(--g),var(--g2));display:flex;align-items:center;justify-content:center;font-size:12px;color:#1a1a1a;flex-shrink:0}.st2{font-size:15px;font-weight:600}.sd{font-size:11px;color:var(--t3);margin-top:1px}')
O.append('.ov{background:var(--gc);border:1px solid var(--bds);border-radius:var(--r);padding:22px;margin-bottom:20px;color:var(--t2);font-size:13px;line-height:1.85}.ov strong{color:var(--h)}')
O.append('.mg{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}.mc{background:var(--bgc);border:1px solid var(--bds);border-radius:var(--r);overflow:hidden;transition:all .15s}.mc:hover{border-color:var(--bd);background:var(--bgh)}.mh{padding:10px 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--bds)}.mdot{width:8px;height:8px;border-radius:50%;flex-shrink:0}.mn{font-size:13px;font-weight:600}.mb{padding:6px 12px 10px}.ml{display:flex;align-items:flex-start;gap:6px;padding:3px 0;font-size:12px;color:var(--t2);border-bottom:1px solid rgba(255,255,255,0.03);cursor:pointer;transition:color .1s}.ml:last-child{border-bottom:none}.ml:hover{color:var(--h)}.ml::before{content:"\\203a";color:var(--g);font-weight:700;flex-shrink:0;margin-top:-1px}')
O.append('.ll{display:flex;flex-direction:column;gap:4px}.lc{display:flex;align-items:center;gap:10px;padding:9px 14px;background:var(--bgc);border:1px solid var(--bds);border-radius:var(--r);cursor:pointer;transition:all .15s}.lc:hover{background:var(--bgh);border-color:var(--bd)}.li{font-family:var(--fm);font-size:10px;color:var(--t3);min-width:22px}.ln{font-size:13px}')
O.append('.cg{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}.cc{padding:10px 12px;background:var(--bgc);border:1px solid var(--bds);border-left:3px solid var(--g);border-radius:var(--r);cursor:pointer;transition:all .15s}.cc:hover{background:var(--bgh);border-left-color:var(--h)}.ct{font-size:13px;font-weight:600;color:var(--h);margin-bottom:2px}.cd{font-size:11px;color:var(--t2);line-height:1.5}')
O.append('.qg{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:10px}.qc{background:var(--gc);border:1px solid var(--bds);border-radius:var(--r);padding:16px 16px 12px;position:relative;cursor:pointer;transition:all .15s}.qc:hover{border-color:var(--g);box-shadow:var(--sh)}.qm{position:absolute;top:4px;left:10px;font:42px Georgia,serif;color:var(--g);opacity:.2;line-height:1}.qb{font-size:13px;color:var(--t1);line-height:1.8;padding-left:4px;font-style:italic}.qs{display:block;margin-top:6px;font-size:10px;color:var(--g);font-style:normal;font-family:var(--fm)}')
O.append('.al{display:flex;flex-direction:column;gap:4px}.ar{display:flex;align-items:center;gap:10px;padding:8px 14px;background:var(--bgc);border:1px solid var(--bds);border-radius:var(--r);transition:all .15s}.ar:hover{background:var(--bgh)}.ar.ph{border-left:3px solid var(--a)}.ar.pm{border-left:3px solid var(--g)}.ar.pl{border-left:3px solid var(--t3)}.ad{width:6px;height:6px;border-radius:50%;flex-shrink:0}.ph .ad{background:var(--a)}.pm .ad{background:var(--g)}.pl .ad{background:var(--t3)}.ap{font-size:9px;color:var(--t3);min-width:36px;text-transform:uppercase;letter-spacing:.5px}.at{font-size:13px;color:var(--t2)}')
O.append('.tg{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}.tc{background:var(--bgc);border:1px solid var(--bds);border-radius:var(--r);padding:14px;transition:all .15s}.tc:hover{border-color:var(--bd);background:var(--bgh)}.tc h4{font-size:13px;font-weight:600;color:var(--h);margin-bottom:8px}.tcc{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:6px}.tt{font-size:10px;padding:2px 6px;background:var(--bg);border:1px solid var(--bds);border-radius:var(--r);color:var(--t2);cursor:pointer;transition:all .15s}.tt:hover{border-color:var(--g2);color:var(--h);background:var(--hbg)}.tv{font-size:11px;color:var(--t3);line-height:1.55;padding-top:6px;border-top:1px solid var(--bds)}')
O.append('.bl{list-style:none}.bi{display:flex;align-items:flex-start;gap:10px;padding:9px 14px;background:var(--bgc);border:1px solid var(--bds);border-left:3px solid #c0392b;border-radius:var(--r);margin-bottom:6px;font-size:12px;color:var(--t2)}.bi2{color:#c0392b;font-size:14px;flex-shrink:0;margin-top:1px}')
O.append('.ovb{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:300;justify-content:center;align-items:center;padding:20px}.ovb.open{display:flex}')
O.append('.ovp{background:var(--gp);border:1px solid var(--bd);border-radius:var(--r);width:100%;max-width:520px;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 4px 24px rgba(0,0,0,0.6)}.ovh{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--bd)}.ovt{font-size:14px;font-weight:600}.ovx{width:26px;height:26px;border:1px solid var(--bd);border-radius:var(--r);background:var(--bgc);color:var(--t2);cursor:pointer;font-size:13px;display:flex;align-items:center;justify-content:center;transition:all .15s}.ovx:hover{background:var(--bgh);color:var(--t1)}')
O.append('.ovbd{padding:16px;overflow-y:auto;flex:1}.ovm{font-size:10px;color:var(--t3);margin-bottom:10px;font-family:var(--fm)}.ovd{color:var(--t2);line-height:1.8;font-size:13px}.ovr{margin-top:12px}.ovrt{font-size:10px;color:var(--t3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}.rl{display:inline-block;padding:3px 8px;margin:2px 4px 2px 0;background:var(--bgc);border:1px solid var(--bds);border-radius:var(--r);font-size:11px;color:var(--g);cursor:pointer;transition:all .15s}.rl:hover{border-color:var(--g2);color:var(--h);background:var(--hbg)}')
O.append('.sf{border-top:1px solid var(--bds);padding:10px 20px;text-align:center;color:var(--t3);font-size:10px;margin-top:20px}.hid{display:none!important}.hl{background:var(--hbg);color:var(--h);padding:0 2px;border-radius:2px}')
O.append('@media(max-width:860px){.sidebar{display:none}.mg,.cg,.qg,.tg{grid-template-columns:1fr}.hi{flex-wrap:wrap}.sw{width:100%;margin-left:0}.sw input{width:100%}}')
O.append('</style>\n')

# --- HEAD ---
O.append('<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>秋芝2046 - AI Course Knowledge Base</title></head><body>\n')

# --- HEADER ---
O.append('<header class="hdr"><div class="hi"><div class="brand"><div class="bi">秋</div><div><div class="bt">秋芝2046</div><div class="bs">AI Course Knowledge Base</div></div></div><div class="sw"><span class="si">&#x2315;</span><input type="text" id="searchInput" placeholder="Search concepts, lessons, quotes..."></div></div></header>\n')

# --- STATS ---
O.append('<div class="sb"><div class="sbi">')
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Modules</span></div>' % len(modules))
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Lessons</span></div>' % len(lessons_list))
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Concepts</span></div>' % len(pkg.get('concepts', [])))
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Quotes</span></div>' % len(quotes))
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Actions</span></div>' % len(actions))
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Topics</span></div>' % len(topics))
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Cards</span></div>' % cards)
O.append('<div class="st"><span class="sv">%d</span><span class="sl">Chunks</span></div>' % chunks)
O.append('</div></div>\n')

# --- LAYOUT ---
O.append('<div class="layout">\n')

# --- SIDEBAR ---
O.append('<nav class="sidebar" id="sidebar">\n')
O.append('<div class="sbs"><div class="sbh act" data-nav="overview"><span class="arr">&#x25b6;</span> Overview</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="modules"><span class="arr">&#x25b6;</span> Modules</div><div class="sbi2">\n')
for idx, (mname, mlessons) in enumerate(modules):
    dot = '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:' + colors[idx % 5] + ';margin-right:4px;vertical-align:middle"></span>'
    O.append('  <div class="sbitem" data-nav="modules" data-scroll="mod-%d">%s%s</div>\n' % (idx, dot, esc(mname)))
O.append('</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="lessons"><span class="arr">&#x25b6;</span> Lessons</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="concepts"><span class="arr">&#x25b6;</span> Concepts</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="quotes"><span class="arr">&#x25b6;</span> Quotes</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="actions"><span class="arr">&#x25b6;</span> Actions</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="topics"><span class="arr">&#x25b6;</span> Topics</div></div>\n')
O.append('<div class="sbs"><div class="sbh" data-nav="boundaries"><span class="arr">&#x25b6;</span> Boundaries</div></div>\n')
O.append('</nav>\n')

# --- MAIN ---
O.append('<div class="main">\n')

# Tab nav
O.append('<div class="tnav">\n')
tab_labels = [('overview', 'Overview'), ('modules', 'Modules'), ('lessons', 'Lessons'), ('concepts', 'Concepts'), ('quotes', 'Quotes'), ('actions', 'Actions'), ('topics', 'Topics'), ('boundaries', 'Boundaries')]
tab_counts = [0, len(modules), len(lessons_list), len(pkg.get('concepts', [])), len(quotes), len(actions), len(topics), 0]
for idx, (key, label) in enumerate(tab_labels):
    if tab_counts[idx] > 0:
        O.append('  <button class="tbtn%s" data-tab="%s">%s <span class="tbd">%d</span></button>\n' % (' act' if idx == 0 else '', key, label, tab_counts[idx]))
    else:
        O.append('  <button class="tbtn%s" data-tab="%s">%s</button>\n' % (' act' if idx == 0 else '', key, label))
O.append('</div>\n')

# === OVERVIEW ===
O.append('<div class="panel act" id="tab-overview">\n')
O.append('<div class="ov">')
O.append('《秋芝2046》是一门面向<strong>AI技术和工具应用</strong>的课程体系，旨在为AI初学者和爱好者提供从理论到实践的全面指导。课程内容涵盖了AI的应用现状、发展趋势、具体工具使用教程以及相关案例分析。通过本课程的学习，学员能够了解AI技术的基本原理，掌握多种AI工具的使用方法，提高在不同场景下的问题解决能力。')
O.append('</div>\n')
O.append('<div class="sh"><div class="si2">&#x1f5ea;</div><div><div class="st2">Course Structure</div><div class="sd">%d core modules</div></div></div>\n' % len(modules))
O.append('<div class="mg">\n')
for idx, (mname, mlessons) in enumerate(modules):
    c = colors[idx % 5]
    li = ''.join('<div class="ml" data-nav="lessons">%s</div>' % esc(l) for l in mlessons)
    O.append('  <div class="mc" id="mod-%d"><div class="mh"><span class="mdot" style="background:%s"></span><span class="mn">%s</span></div><div class="mb">%s</div></div>\n' % (idx, c, esc(mname), li))
O.append('</div>\n</div>\n')

# === MODULES ===
O.append('<div class="panel" id="tab-modules">\n')
O.append('<div class="sh"><div class="si2">&#x1f5c2;</div><div><div class="st2">Course System Map</div><div class="sd">Complete module structure</div></div></div>\n')
O.append('<div class="mg">\n')
for idx, (mname, mlessons) in enumerate(modules):
    c = colors[idx % 5]
    li = ''.join('<div class="ml" data-nav="lessons">%s</div>' % esc(l) for l in mlessons)
    O.append('  <div class="mc" id="mod-%d"><div class="mh"><span class="mdot" style="background:%s"></span><span class="mn">%s</span></div><div class="mb">%s</div></div>\n' % (idx, c, esc(mname), li))
O.append('</div>\n</div>\n')

# === LESSONS ===
O.append('<div class="panel" id="tab-lessons">\n')
O.append('<div class="sh"><div class="si2">&#x1f4da;</div><div><div class="st2">Lesson Summaries</div><div class="sd">%d lessons</div></div></div>\n' % len(lessons_list))
O.append('<div class="ll">\n')
for idx, title in enumerate(lessons_list):
    O.append('  <div class="lc"><span class="li">%02d</span><span class="ln">%s</span></div>\n' % (idx + 1, esc(title)))
O.append('</div>\n</div>\n')

# === CONCEPTS (clickable) ===
O.append('<div class="panel" id="tab-concepts">\n')
O.append('<div class="sh"><div class="si2">&#x1f4a1;</div><div><div class="st2">Concept Glossary</div><div class="sd">%d concepts - click any card</div></div></div>\n' % len(pkg.get('concepts', [])))
O.append('<div class="cg">\n')
for c in pkg.get('concepts', []):
    clean = re.sub(r'\*\*', '', c)
    clean = re.split(r'[：:]', clean)[0].strip()
    display = re.sub(r'\*\*', '', c)
    display = re.split(r'[：:]', display)[0].strip()
    O.append('  <div class="cc" data-concept="%s"><div class="ct">%s</div><div class="cd">Click to view knowledge card &rarr;</div></div>\n' % (esc(clean), esc(display)))
O.append('</div>\n</div>\n')

# === QUOTES ===
O.append('<div class="panel" id="tab-quotes">\n')
O.append('<div class="sh"><div class="si2">&#x1f4ac;</div><div><div class="st2">Key Quotes</div><div class="sd">%d quotes</div></div></div>\n' % len(quotes))
O.append('<div class="qg">\n')
for q in quotes:
    src = '<span class="qs">&mdash; %s</span>' % esc(q['source']) if q['source'] else ''
    O.append('  <div class="qc"><div class="qm">&ldquo;</div><div class="qb">%s</div>%s</div>\n' % (esc(q['text']), src))
O.append('</div>\n</div>\n')

# === ACTIONS ===
pri_labels = {'high': 'HIGH', 'medium': 'MED', 'low': 'LOW'}
O.append('<div class="panel" id="tab-actions">\n')
O.append('<div class="sh"><div class="si2">&#x26a1;</div><div><div class="st2">Action Items</div><div class="sd">Prioritized tasks</div></div></div>\n')
O.append('<div class="al">\n')
for a in actions:
    cls = {'high': 'ph', 'medium': 'pm', 'low': 'pl'}.get(a['priority'], 'pm')
    lbl = pri_labels.get(a['priority'], 'MED')
    O.append('  <div class="ar %s"><span class="ad"></span><span class="ap">%s</span><span class="at">%s</span></div>\n' % (cls, lbl, esc(a['text'])))
O.append('</div>\n</div>\n')

# === TOPICS ===
O.append('<div class="panel" id="tab-topics">\n')
O.append('<div class="sh"><div class="si2">&#x1f517;</div><div><div class="st2">Topic Graph</div><div class="sd">Cross-lesson connections</div></div></div>\n')
O.append('<div class="tg">\n')
for t in topics:
    ch = ''.join('<span class="tt">%s</span>' % esc(c) for c in t['courses'])
    vw = '<div class="tv">%s</div>' % esc(t['view']) if t['view'] else ''
    O.append('  <div class="tc"><h4>%s</h4><div class="tcc">%s</div>%s</div>\n' % (esc(t['name']), ch, vw))
O.append('</div>\n</div>\n')

# === BOUNDARIES ===
bnds = [
    ('Content timeliness', 'AI technology evolves rapidly. Tools and models referenced may be outdated. Always verify against current information.'),
    ('Tool performance', 'Performance of evaluated tools changes over time. Check current versions before use.'),
    ('Local deployment', 'Some tutorials require local LLM deployment with GPU and command-line skills.'),
    ('AI-generated content', 'This course uses AI-assisted production. Critically evaluate and cross-reference sources.'),
    ('Paid tool costs', 'Several tools require paid subscriptions. Verify costs before subscribing.'),
]
O.append('<div class="panel" id="tab-boundaries">\n')
O.append('<div class="sh"><div class="si2">&#x26a0;&#xfe0f;</div><div><div class="st2">Boundaries & Risks</div><div class="sd">Limitations and注意事项</div></div></div>\n')
O.append('<ul class="bl">\n')
for icon, text in bnds:
    O.append('  <li class="bi"><span class="bi2">&#x26a0;</span><span>%s</span></li>\n' % esc(text))
O.append('</ul>\n</div>\n')

# === CLOSE ===
O.append('</div><!-- /main -->\n')
O.append('</div><!-- /layout -->\n')
O.append('<footer class="sf">秋芝2046 Knowledge Base &middot; Lineage Skill &middot; %s</footer>\n' % gen_date)

# === KNOWLEDGE CARD OVERLAY ===
O.append('<div class="ovb" id="overlay"><div class="ovp">')
O.append('<div class="ovh"><span class="ovt" id="ovTitle"></span><button class="ovx" id="ovClose">&times;</button></div>')
O.append('<div class="ovbd"><div class="ovm" id="ovMeta"></div><div class="ovd" id="ovDesc"></div><div class="ovr" id="ovRelated"></div></div>')
O.append('</div></div>\n')

# === JAVASCRIPT ===
O.append('<script>\n')
O.append('(function(){\n')
O.append('var tabs=document.querySelectorAll(".tbtn"),panels=document.querySelectorAll(".panel"),shdrs=document.querySelectorAll(".sbh"),sbits=document.querySelectorAll(".sbitem");\n')
O.append('function switchTab(name){tabs.forEach(function(t){t.classList.remove("act")});panels.forEach(function(p){p.classList.remove("act")});var btn=document.querySelector(".tbtn[data-tab="+name+"]");if(btn)btn.classList.add("act");var panel=document.getElementById("tab-"+name);if(panel)panel.classList.add("act");shdrs.forEach(function(h){h.classList.remove("act");var s=h.nextElementSibling;if(s&&s.classList.contains("sbi2"))s.classList.remove("open")});sbits.forEach(function(s){s.classList.remove("act")});var sh=document.querySelector(".sbh[data-nav="+name+"]");if(sh){sh.classList.add("act");sh.classList.add("open");var si=sh.nextElementSibling;if(si&&si.classList.contains("sbi2"))si.classList.add("open")}}\n')
O.append('tabs.forEach(function(b){b.addEventListener("click",function(){switchTab(b.dataset.tab)})});\n')
O.append('shdrs.forEach(function(h){h.addEventListener("click",function(){switchTab(h.dataset.nav)})});\n')
O.append('sbits.forEach(function(s){s.addEventListener("click",function(){switchTab(s.dataset.nav);var el=document.getElementById(s.dataset.scroll);if(el)el.scrollIntoView({behavior:"smooth",block:"start"})})});\n')
O.append('var si=document.getElementById("searchInput"),timer;\n')
O.append('si.addEventListener("input",function(){clearTimeout(timer);timer=setTimeout(function(){var q=si.value.trim().toLowerCase();if(!q){document.querySelectorAll(".hid").forEach(function(e){e.classList.remove("hid")});return}document.querySelectorAll(".cc,.lc,.qc,.ar,.tc,.bi,.mc,.ml").forEach(function(el){if(el.textContent.toLowerCase().includes(q)){el.classList.remove("hid");hl(el,q)}else{el.classList.add("hid")}})},150)});\n')
O.append('function hl(el,q){if(el.querySelector(".hl"))return;var w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT,null),ns=[];while(w.nextNode())ns.push(w.currentNode);ns.forEach(function(n){var t=n.textContent,i=t.toLowerCase().indexOf(q);if(i<0)return;var s=document.createElement("span");s.innerHTML=eh(t.slice(0,i))+"<span class=\\"hl\\">"+eh(t.slice(i,i+q.length))+"</span>"+eh(t.slice(i+q.length));n.parentNode.replaceChild(s,n)})}\n')
O.append('function eh(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML}\n')
O.append('var ov=document.getElementById("overlay"),ovT=document.getElementById("ovTitle"),ovM=document.getElementById("ovMeta"),ovD=document.getElementById("ovDesc"),ovR=document.getElementById("ovRelated"),ovX=document.getElementById("ovClose");\n')
O.append('ovX.addEventListener("click",function(){ov.classList.remove("open")});\n')
O.append('ov.addEventListener("click",function(e){if(e.target===ov)ov.classList.remove("open")});\n')
O.append('document.addEventListener("keydown",function(e){if(e.key==="Escape")ov.classList.remove("open")});\n')
O.append('var cdata=%s;\n' % concept_js)
O.append('document.querySelectorAll(".cc").forEach(function(card){card.addEventListener("click",function(){var term=card.dataset.concept;var d=cdata[term];if(!d)return;ovT.textContent=d.title;ovM.textContent=d.type;ovD.textContent=d.desc;var rh="";if(d.related&&d.related.length){rh="<div class=\\"ovrt\\">Related</div>";d.related.forEach(function(r){rh+="<span class=\\"rl\\" data-concept="+r+">"+r+"</span>"})}ovR.innerHTML=rh;ov.classList.add("open")})});\n')
O.append('ovR.addEventListener("click",function(e){if(e.target.classList.contains("rl")){var term=e.target.dataset.concept;var d=cdata[term];if(!d)return;ovT.textContent=d.title;ovM.textContent=d.type;ovD.textContent=d.desc;var rh="";if(d.related&&d.related.length){rh="<div class=\\"ovrt\\">Related</div>";d.related.forEach(function(r){rh+="<span class=\\"rl\\" data-concept="+r+">"+r+"</span>"})}ovR.innerHTML=rh}});\n')
O.append('})();\n')
O.append('</script>\n')
O.append('</body>\n</html>\n')

# --- Write ---
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(''.join(O), encoding='utf-8')
print("Written: " + str(OUT))
print("Size: " + format(OUT.stat().st_size, ',') + " bytes")
print("Modules: " + str(len(modules)) + ", Lessons: " + str(len(lessons_list)) + ", Concepts: " + str(len(pkg.get('concepts', []))) + ", Quotes: " + str(len(quotes)) + ", Actions: " + str(len(actions)) + ", Topics: " + str(len(topics)))
print("OKF concepts: " + str(len(okf)))
