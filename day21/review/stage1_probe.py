import importlib.util,sys,tempfile,json
from pathlib import Path
# Синтетические регрессии для двух зафиксированных реализаций; приватные данные не читаются.
ROOT=Path(__file__).resolve().parents[3]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
L=load('import_corpus',ROOT/'study/day21/import_corpus.py')
T=load('luna_fixture',ROOT/'study/day21/test_import.py')
S=load('corpus',ROOT/'day21-sol-high/day21/corpus.py')
U=load('sol_fixture',ROOT/'day21-sol-high/day21/test_corpus.py')
results=[]
def emit(case,expected,observed):
 results.append({'case':case,'expected':expected,'observed':observed,'pass':observed==expected})
# Luna: a replacement of an inventoried assignment must not be included twice.
notes,_=L.merge_personal_note(L.empty_personal_note_state('mcp-study:understanding-practice'),T.synthetic_note('note'))
inv={'assignments':[{'id':'125','day':1,'author':'Учебный пример'}]}
a=T.synthetic_row('125','День 1. Initial');b=T.synthetic_row('125','День 1. Changed')
s,_=L.merge_snapshot(L.empty_state('ai-advent-9'),T.synthetic_snapshot(),[a]); m=L.build_selection_manifest(s,inv,'2026-08-31',notes)
s=L.accept_replacement(s,'125',a['version_sha256'],True)
s,_=L.merge_snapshot(s,T.synthetic_snapshot('next'),[b]);m=L.build_selection_manifest(s,inv,'2026-08-31',notes,m)
emit('Luna_pending_assignment_not_included',1,sum(r['decision']=='include' for r in m['telegram_decisions']))
s=L.accept_replacement(s,'125',b['version_sha256'],True);m2=L.build_selection_manifest(s,inv,'2026-08-31',notes,m)
emit('Luna_old_assignment_excluded_after_accept',False,any(r['version_sha256']==a['version_sha256'] and r['decision']=='include' for r in m2['telegram_decisions']))
c=T.synthetic_row('126','🔥 День 25. New assignment');s,_=L.merge_snapshot(s,T.synthetic_snapshot('third'),[c]);mm=L.build_selection_manifest(s,inv,'2026-08-31',notes,m2)
emit('Luna_emoji_day25_recognized','assignment_candidate',next(r['source_type'] for r in mm['telegram_decisions'] if r['message_id']=='126'))
# Sol forwarded metadata are not the wrapper metadata.
html=U.message(6001,'Normal',author='Outer')+'''<div class="message default clearfix joined" id="message6002"><div class="body"><div class="date details" title="02.10.2026 12:00:00 UTC+00:00"></div><div class="forwarded body"><div class="from_name">Forwarded</div><div class="reply_to details"><a href="#go_to_message999">x</a></div><div class="text">Forwarded text</div></div></div></div>'''+U.message(6003,'Next',joined=True)
p=S.TelegramParser('fixture.html');p.feed(html);p.close()
emit('Sol_forwarded_author_does_not_replace_outer',['Outer','Outer'],[p.records[1]['author'],p.records[2]['author']])
emit('Sol_forwarded_reply_not_thread_edge',None,p.records[1]['reply_to'])
with tempfile.TemporaryDirectory() as d:
 root=Path(d);src=root/'src';src.mkdir();U.write_parts(src,[U.message(5001,'Original',reply=7001),'','','',''])
 conn=S.connect(root/'private/x.sqlite3');S.import_snapshot(conn,src,'s1',1,'2026-10-02');S.decide(conn,'telegram:5001','include','reviewed','test')
 U.write_parts(src,[U.message(5001,'Edited',reply=7002),'','','','']);S.import_snapshot(conn,src,'s2',2,'2026-10-03')
 man=S.build_manifest(conn)
 emit('Sol_active_manifest_uses_accepted_reply',7001,man[0]['reply_to'])
 note=root/'note.md';heading='## Понимание и полезные поправки для практики\n';note.write_text(heading+'First note\n');S.import_note(conn,note)
 note.write_text(heading+'Second note\n');S.import_note(conn,note);v=conn.execute("select version_hash from proposals where source_key like 'note:%'").fetchone()[0];S.accept_proposal(conn,'note:mcp-study:understanding',v,'test')
 conn.close(); conn=S.connect(root/'private/x.sqlite3')
 tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 values=[str(tuple(row)) for table in ['accepted','proposals','observations','note_versions','accepted_history'] if table in tables for row in conn.execute('select * from '+table)]
 emit('Sol_previous_note_version_retained',True,any('First note' in x for x in values))
 conn.close()
print(json.dumps(results,ensure_ascii=False,indent=2))
