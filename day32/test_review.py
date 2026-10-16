"""Офлайн-контракты: настоящий локальный Git, SQLite и FTS5; без сети."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from cli import fixture
from review import Fixture, GitSnapshot, OpenRouter, Runner, Store, context, git, validate, visible_lines


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.repo,self.meta=fixture(self.root)
        self.snap=GitSnapshot.build(self.repo,'offline/fixture',1,self.meta['base'],self.meta['head'])
    def tearDown(self): self.tmp.cleanup()
    def store(self): return Store(self.root/'state')
    def test_real_git_rag_contract_and_modes(self):
        messages,data=context(self.snap,'rag')
        self.assertEqual({s['kind'] for s in data['sources']},{'docs','code'})
        self.assertIn('недоверенные',messages[0]['content'])
        raw=Fixture()(messages);answer=json.loads(raw['choices'][0]['message']['content'])
        findings=validate(answer,self.snap,data)
        self.assertEqual(findings[0]['line'],7)
        self.assertTrue(findings[0]['source_ids'])
        self.assertEqual(context(self.snap,'diff')[1]['files'],{})
        self.assertFalse(context(self.snap,'files')[1]['sources'])
    def test_persistent_dedupe_new_sha_and_modes(self):
        store=self.store();runner=Runner(store,Fixture())
        ident,new=runner.run(self.snap);self.assertTrue(new)
        self.assertFalse(Runner(self.store(),Fixture()).run(self.snap)[1])
        self.assertTrue(runner.run(self.snap,'files')[1])
        subprocess.run(['git','-C',str(self.repo),'commit','--allow-empty','-qm','new head'],check=True)
        head=git(self.repo,'rev-parse','HEAD').decode().strip()
        changed=GitSnapshot.build(self.repo,'offline/fixture',1,self.meta['base'],head)
        self.assertTrue(runner.run(changed)[1])
        report=json.loads((store.root/ident/'report.json').read_text())
        self.assertIsNone(report['cost']['prompt_tokens'])
        self.assertEqual(report['provider'],'offline fixture')
        self.assertEqual(report['status'],'complete')
    def test_budget_reserve_unknown_and_no_retry(self):
        class Paid:
            name='test paid'
            calls=0
            def __call__(self,messages):
                self.calls+=1; raise TimeoutError('ambiguous')
        paid=Paid(); store=self.store()
        runner=Runner(store,paid,0.00001)
        ident,new=runner.run(self.snap);self.assertFalse(new);self.assertEqual(paid.calls,0)
        self.assertEqual(store.reports()[0]['status'],'budget_blocked')
        # Новый снимок с отдельным ключом; неоднозначный вызов сохраняет резерв.
        snap=copy.deepcopy(self.snap);snap['number']=2
        runner=Runner(store,paid,1)
        ident,new=runner.run(snap);self.assertTrue(new);self.assertEqual(paid.calls,1)
        self.assertFalse(Runner(self.store(),paid,1).run(snap)[1]);self.assertEqual(paid.calls,1)
        row=store.reports()[0];self.assertEqual(row['status'],'error');self.assertIsNone(row['actual']);self.assertGreater(row['reserve'],0)
    def test_validation_untrusted_ids_line_and_paths(self):
        messages,data=context(self.snap,'rag');a=json.loads(Fixture()(messages)['choices'][0]['message']['content'])
        for field,value in [('line',True),('line',999),('path','../../secret'),('version','base'),('source_ids',['fabricated']),('category','execute')]:
            b=copy.deepcopy(a);b['findings'][0][field]=value
            with self.assertRaises(ValueError):validate(b,self.snap,data)
        self.assertEqual(validate({'findings':[]},self.snap,data),[])
    def test_delete_rename_snapshot(self):
        subprocess.run(['git','-C',str(self.repo),'mv','git_tool.py','history.py'],check=True)
        subprocess.run(['git','-C',str(self.repo),'rm','docs/provenance.md'],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','rename and delete'],check=True)
        head=git(self.repo,'rev-parse','HEAD').decode().strip()
        snap=GitSnapshot.build(self.repo,'offline/fixture',3,self.meta['head'],head)
        self.assertIn('merge_base:git_tool.py',snap['files']);self.assertIn('head:history.py',snap['files'])
        self.assertIn('merge_base:docs/provenance.md',snap['files'])
        _,data=context(snap,'rag')
        f=dict(category='recommendation',path='docs/provenance.md',version='merge_base',line=1,evidence='Удалён provenance',suggestion='Проверить сохранение происхождения',source_ids=[])
        self.assertEqual(validate({'findings':[f]},snap,data),[f])
    def test_limits_and_symlink(self):
        (self.repo/'large.md').write_text('a'*30000)
        (self.repo/'linked.py').symlink_to('/etc/passwd')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','bounded'],check=True)
        head=git(self.repo,'rev-parse','HEAD').decode().strip()
        snap=GitSnapshot.build(self.repo,'offline/fixture',4,self.meta['head'],head)
        self.assertTrue(snap['limitations']);self.assertNotIn('head:linked.py',snap['files'])
        self.assertNotIn('root:',json.dumps(snap))
    def test_abandoned_claim_not_retried(self):
        store=self.store();ident,new=store.claim('crashed',0.1,1)
        self.assertTrue(new);self.assertFalse(self.store().claim('crashed',0.1,1)[1])
    def test_provider_exact_profile_and_single_request(self):
        from unittest.mock import patch
        request=OpenRouter.request(context(self.snap,'rag')[0])
        self.assertEqual(request['provider']['only'],['alibaba/us-east-1'])
        self.assertFalse(request['provider']['allow_fallbacks'])
        self.assertEqual(request['model'],'qwen/qwen3.8-max-0902')
        self.assertEqual(request['max_tokens'],4096)
        with self.assertRaises(ValueError):OpenRouter()
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':'dummy-offline-test'}):
            with patch('review.urllib.request.urlopen',side_effect=TimeoutError('offline simulated')) as call:
                runner=Runner(self.store(),OpenRouter(True),1)
                ident,new=runner.run(self.snap)
                self.assertTrue(new);self.assertEqual(call.call_count,1)
                req=json.loads((runner.store.root/ident/'request.json').read_text())
                self.assertEqual(req,request)
                self.assertNotIn('dummy-offline-test',json.dumps(runner.store.reports()))
    def test_watcher_readonly_adapter(self):
        from unittest.mock import patch
        import cli
        rows=[dict(number=1,baseRefOid=self.meta['base'],headRefOid=self.meta['head'])]
        # Cache здесь настоящий fixture Git; только gh/fetch заменены, чтение snapshot реальное.
        with patch('cli.gh',return_value=rows) as gh_call:
            with patch('cli.subprocess.run') as fetch:
                snapshots=list(cli.poll('owner/repo',self.repo))
        self.assertEqual(len(snapshots),1)
        self.assertEqual(snapshots[0]['head_sha'],self.meta['head'])
        self.assertIn('fetch',fetch.call_args.args[0])
        self.assertEqual(gh_call.call_args.args[:2],('pr','list'))
        with self.assertRaises(ValueError):list(cli.poll('https://evil/repo',self.repo))
    def test_context_limit_does_not_mutate_snapshot(self):
        from unittest.mock import patch
        original=copy.deepcopy(self.snap)
        with patch('review.MAX_PROMPT',800):context(self.snap,'rag')
        self.assertEqual(self.snap,original)
    def test_incomplete_model_output_rejected(self):
        class Truncated(Fixture):
            name='offline fixture'
            def __call__(self,messages):
                raw=super().__call__(messages);raw['choices'][0]['finish_reason']='length';return raw
        store=self.store();ident,new=Runner(store,Truncated()).run(self.snap)
        self.assertEqual(store.reports()[0]['status'],'error')
        self.assertIn('Incomplete provider output',store.reports()[0]['report']['error'])
    def test_large_tree_and_manifest_persist_limited(self):
        # Реальные object tree и diff превышают caps; никакой подмены Git/SQLite/provider.
        folder=self.repo/'many';folder.mkdir()
        for i in range(5000):
            (folder/('file_' + str(i).zfill(5) + '_' + 'x'*24 + '.py')).write_text('value = 1\n')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','large tree'],check=True)
        head=git(self.repo,'rev-parse','HEAD').decode().strip()
        snap=GitSnapshot.build(self.repo,'offline/fixture',5,self.meta['head'],head)
        self.assertEqual(snap['changed_files'],[])
        self.assertEqual(snap['corpus'],[])
        self.assertIn('changed manifest exceeds limit; manifest unavailable',snap['limitations'])
        self.assertIn('tree exceeds limit; corpus unavailable',snap['limitations'])
        store=self.store();ident,new=Runner(store,Fixture()).run(snap)
        self.assertTrue(new)
        report=store.reports()[0]['report']
        self.assertEqual(report['status'],'limited')
        self.assertFalse(Runner(self.store(),Fixture()).run(snap)[1])
        self.assertEqual(json.loads((store.root/ident/'report.json').read_text())['status'],'limited')
    def test_visible_lines_diff_full_file_and_pruned_prompt(self):
        path=self.repo/'long.py';path.write_text(''.join(f'value_{i} = {i}\n' for i in range(1,101)))
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','long baseline'],check=True)
        base=git(self.repo,'rev-parse','HEAD').decode().strip()
        path.write_text(path.read_text().replace('value_50 = 50','value_50 = 500'))
        subprocess.run(['git','-C',str(self.repo),'commit','-qam','long change'],check=True)
        head=git(self.repo,'rev-parse','HEAD').decode().strip()
        snap=GitSnapshot.build(self.repo,'offline/fixture',6,base,head)
        f=dict(category='architecture',path='long.py',version='head',line=1,evidence='Контракт структуры',suggestion='Проверить структуру',source_ids=[])
        _,data=context(snap,'diff')
        with self.assertRaisesRegex(ValueError,'not provided'):validate({'findings':[f]},snap,data)
        for line in (47,50,53):
            f['line']=line;self.assertEqual(validate({'findings':[f]},snap,data),[f])
        _,data=context(snap,'files');f['line']=1
        self.assertEqual(validate({'findings':[f]},snap,data),[f])
        from unittest.mock import patch
        with patch('review.MAX_PROMPT',500): _,pruned=context(snap,'files')
        self.assertFalse(pruned['files']);self.assertFalse(pruned['diff']);self.assertFalse(pruned['sources'])
        with self.assertRaisesRegex(ValueError,'not provided'):validate({'findings':[f]},snap,pruned)
    def test_visible_source_ranges_require_snapshot_sha(self):
        _,data=context(self.snap,'rag');data['files']={};data['diff']=''
        source=next(s for s in data['sources'] if s['path']=='git_tool.py')
        data['sources']=[dict(source,start_line=7,end_line=7,text=source['text'].splitlines()[6])]
        f=dict(category='bug',path='git_tool.py',version='head',line=7,evidence='Граница',suggestion='Исправить',source_ids=[source['id']])
        self.assertEqual(validate({'findings':[f]},self.snap,data),[f])
        f['line']=1
        with self.assertRaisesRegex(ValueError,'not provided'):validate({'findings':[f]},self.snap,data)
        f['line']=7;data['sources'][0]['sha']='0'*40
        with self.assertRaisesRegex(ValueError,'not provided'):validate({'findings':[f]},self.snap,data)
    def test_visible_diff_rename_delete_and_no_newline(self):
        data={'files':{},'sources':[],'diff': 'diff --git a/old.py b/new.py\n--- a/old.py\n+++ b/new.py\n@@ -2,2 +2,2 @@\n context\n-old\n\\ No newline at end of file\n+new\n\\ No newline at end of file\n' }
        visible=visible_lines(data)
        self.assertEqual(visible[('merge_base','old.py')],{2,3})
        self.assertEqual(visible[('head','new.py')],{2,3})
        data['diff']='diff --git a/old.py b/old.py\n--- a/old.py\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-one\n-two\n'
        visible=visible_lines(data)
        self.assertEqual(visible,{('merge_base','old.py'):{1,2}})
    def test_real_git_space_filename_visible_hunk(self):
        path=self.repo/'space name.py'
        path.write_text(''.join(f'value_{i} = {i}\n' for i in range(1,101)))
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','space baseline'],check=True)
        base=git(self.repo,'rev-parse','HEAD').decode().strip()
        path.write_text(path.read_text().replace('value_50 = 50','value_50 = 500'))
        subprocess.run(['git','-C',str(self.repo),'commit','-qam','space change'],check=True)
        head=git(self.repo,'rev-parse','HEAD').decode().strip()
        snap=GitSnapshot.build(self.repo,'offline/fixture',7,base,head)
        self.assertIn('--- a/space name.py\t',snap['diff'])
        _,data=context(snap,'diff')
        f=dict(category='bug',path='space name.py',version='head',line=50,evidence='Изменённое значение',suggestion='Проверить значение',source_ids=[])
        self.assertEqual(validate({'findings':[f]},snap,data),[f])
        f['line']=1
        with self.assertRaisesRegex(ValueError,'not provided'):validate({'findings':[f]},snap,data)
    def test_target_boundary(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('target',Path(__file__).parent/'target/git_tool.py')
        target=importlib.util.module_from_spec(spec);spec.loader.exec_module(target)
        self.assertTrue(target.recent_commits(self.repo,10))
        for value in (True,0,11,1.5,'10'):
            with self.assertRaises(ValueError):target.recent_commits(self.repo,value)

if __name__=='__main__':unittest.main(verbosity=2)
