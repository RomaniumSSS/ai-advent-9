"""Настоящий stdio MCP с временным Git, без модели и сети."""
import asyncio
import subprocess
import tempfile
import unittest
from pathlib import Path
from mcp import Client, StdioServerParameters
from day31.mcp_client import GitMcpClient, McpError
from day31.git_mcp_server import resolve_repo
import sys


class McpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-b', 'demo')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-m', 'init')
        self.client = GitMcpClient(self.repo)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def test_real_discovery_branch_change_and_detached(self):
        result = self.client.read()
        self.assertEqual(result['branch'], 'demo')
        self.assertFalse(result['detached'])
        self.assertEqual(result['head'], self.git('rev-parse', 'HEAD'))
        self.assertIn('git_context', self.client.last_discovery['tools'])
        self.assertTrue(self.client.last_discovery['protocol_version'])
        self.git('switch', '-c', 'changed')
        self.assertEqual(self.client.read()['branch'], 'changed')
        self.git('checkout', '--detach')
        detached = self.client.read()
        self.assertIsNone(detached['branch'])
        self.assertTrue(detached['detached'])
        self.assertEqual(detached['repository_id'], result['repository_id'])

    def test_not_a_repo_and_removed_head(self):
        empty = self.repo / 'empty'; empty.mkdir()
        with self.assertRaises(ValueError):
            resolve_repo(empty / 'absent')
        outside = tempfile.TemporaryDirectory(); self.addCleanup(outside.cleanup)
        with self.assertRaises(ValueError):
            resolve_repo(Path(outside.name))
        self.git('update-ref', '-d', 'refs/heads/demo')
        with self.assertRaises(McpError):
            self.client.read()

    def test_tool_rejects_path_argument(self):
        async def run():
            params = StdioServerParameters(command=sys.executable, args=['-m', 'day31.git_mcp_server', '--repo', str(self.repo)], cwd=str(Path(__file__).resolve().parents[2]))
            async with Client(params) as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 1)
                self.assertEqual(tools.tools[0].input_schema.get('properties', {}), {})
                result = await client.call_tool('git_context', {'repo': '/tmp'})
                self.assertTrue(result.is_error)
        asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
