"""Launchd lifecycle с подставным внешним процессом: наблюдение state/PID, без запуска служб."""
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import deploy

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.env=self.root/'.env'
        self.env.write_text('DAY30_TOKEN=fixture\nDAY30_PRIVATE='+str(self.root)+'\n');self.env.chmod(0o600)
        self.label='org.ai-advent.day30';self.plist=self.root/(self.label+'.plist')
        self.plist.write_bytes(plistlib.dumps({'Label':self.label,'ExitTimeOut':1}))
        self.calls=[];self.events=[];self.bootouted=False;self.registered=True;self.alive=True
        self.state_checks=0;self.clock=0;self.never_exit=False;self.invalid_bootstrap=False;self.exit_first=False
    def tearDown(self):self.tmp.cleanup()
    def run_command(self,cmd,**kwargs):
        self.calls.append(cmd)
        action=cmd[1]
        if action=='print':
            if self.bootouted:
                self.state_checks+=1
                self.registered=self.state_checks<(3 if self.exit_first else 2)
                self.alive=False if self.exit_first else self.never_exit or self.state_checks<3
            if self.registered:return subprocess.CompletedProcess(cmd,0,stdout='job = {\n\tpid = 4242\n}\n',stderr='')
            return subprocess.CompletedProcess(cmd,113,stdout='',stderr='Could not find service "org.ai-advent.day30" in domain for user gui: 501')
        if action=='bootout':self.bootouted=True;self.events.append('bootout');return subprocess.CompletedProcess(cmd,0)
        if action=='bootstrap':
            self.events.append('bootstrap')
            if self.registered or self.alive or self.invalid_bootstrap:raise subprocess.CalledProcessError(5,cmd)
            return subprocess.CompletedProcess(cmd,0)
        raise AssertionError(cmd)
    def kill(self,pid,signal):
        self.assertEqual((pid,signal),(4242,0))
        if not self.alive:raise ProcessLookupError()
    def sleep(self,delay):self.clock+=delay
    def invoke(self,command):
        with patch.object(sys,'argv',['deploy.py',command,'--env',str(self.env)]),patch('deploy.subprocess.run',side_effect=self.run_command),patch('deploy.os.kill',side_effect=self.kill),patch.object(deploy,'time',SimpleNamespace(monotonic=lambda:self.clock,sleep=self.sleep),create=True):
            deploy.main()
    def test_restart_waits_for_both_job_and_prior_pid(self):
        self.invoke('restart')
        self.assertEqual(self.calls[0][1],'print');self.assertGreaterEqual(self.state_checks,3)
        self.assertEqual(self.events,['bootout','bootstrap']);self.assertFalse(self.registered);self.assertFalse(self.alive)
    def test_pid_exit_alone_does_not_allow_bootstrap(self):
        self.exit_first=True;self.invoke('restart');self.assertGreaterEqual(self.state_checks,3)
        self.assertEqual(self.events,['bootout','bootstrap'])
    def test_unknown_launchd_error_is_not_assumed_unregistered(self):
        with patch('deploy.subprocess.run',return_value=subprocess.CompletedProcess(['launchctl'],5,stdout='',stderr='permission denied')):
            with self.assertRaisesRegex(RuntimeError,'state_unavailable'):deploy.job_state('gui/501/'+self.label)
    def test_stop_waits_for_exit_without_bootstrap(self):
        self.invoke('stop');self.assertGreaterEqual(self.state_checks,3);self.assertEqual(self.events,['bootout'])
    def test_exit_timeout_prevents_bootstrap(self):
        self.never_exit=True
        with self.assertRaises(TimeoutError):self.invoke('restart')
        self.assertNotIn('bootstrap',self.events);self.assertLessEqual(self.clock,6.01)
    def test_invalid_bootstrap_not_retried(self):
        self.invalid_bootstrap=True
        with self.assertRaises(subprocess.CalledProcessError):self.invoke('restart')
        self.assertEqual(self.events.count('bootstrap'),1);self.assertGreaterEqual(self.state_checks,3)
    def test_start_performs_one_bootstrap_without_hidden_retry(self):
        self.registered=False;self.alive=False;self.invalid_bootstrap=True
        with self.assertRaises(subprocess.CalledProcessError):self.invoke('start')
        self.assertEqual(self.events,['bootstrap'])

if __name__=='__main__':unittest.main()
