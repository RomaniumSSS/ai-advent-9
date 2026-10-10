import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import metrics
D={'pid':1,'role':'daemon','rss_bytes':100,'identity':'ollama serve'}
R={'pid':2,'role':'runner','rss_bytes':200,'identity':'ollama runner'}
def sample(processes):return {'processes':processes,'sum_rss_bytes':sum(p['rss_bytes'] for p in processes) if processes else None}
class MemoryFairness(unittest.TestCase):
    def test_each_sample_requires_complete_roles(self):
        r=metrics.summarize_samples([sample([D]),sample([D,R])],.5)
        self.assertFalse(r['comparison_eligible']);self.assertEqual(r['incomplete_process_samples'],1)
    def test_runner_change_not_same_process_set(self):
        r=metrics.summarize_samples([sample([D,R]),sample([D,dict(R,pid=3)])],.5)
        self.assertFalse(r['comparison_eligible']);self.assertEqual(r['comparison_reason'],'process_set_changed')
    def test_real_ollama0333_llama_server_descendant(self):
        raw='12925 1 42000 /opt/homebrew/bin/ollama\n2012 12925 6029136 /opt/homebrew/Cellar/ollama/0.33.3/libexec/lib/ollama/llama-server\n9000 1 99999 /some/other/llama-server\n9001 1 11111 /usr/bin/python'
        processes=metrics.parse_processes(raw)
        self.assertEqual([(p['pid'],p['role']) for p in processes],[(12925,'daemon'),(2012,'runner')])
        self.assertEqual(sum(p['rss_bytes'] for p in processes),(42000+6029136)*1024)
        self.assertEqual(processes[1]['ppid'],12925)
    def test_stable_complete_samples(self):
        self.assertTrue(metrics.summarize_samples([sample([D,R]),sample([D,R])],.5)['comparison_eligible'])
if __name__=='__main__':unittest.main()
