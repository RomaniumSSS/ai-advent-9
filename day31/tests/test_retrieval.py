"""Проверки чтения корпуса: реальные файлы, свежесть и границы."""
import tempfile
import unittest
from pathlib import Path
from day31.retrieval import RetrievalIndex, tokens


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'docs').mkdir()
        (self.root / 'README.md').write_text('# Помощник\n\nЗапуск приложения: python -m day31.cli\n')
        (self.root / 'docs/git.md').write_text('# Git MCP\n\n## Устройство\n\nСервер get_recent_commits читает последние коммиты Git.\n\n## Ограничения\n\nИстория не изменяется.\n')
        self.index = RetrievalIndex(self.root, self.root / 'index.sqlite3')

    def test_readme_docs_and_real_lines(self):
        for query, path in [('запуск', 'README.md'), ('get_recent_commits', 'docs/git.md'), ('ограничения', 'docs/git.md')]:
            with self.subTest(query=query):
                found = self.index.search(query)
                self.assertEqual(found[0].path, path)
                source = found[0]
                lines = (self.root / path).read_text().splitlines()
                self.assertEqual(source.text, '\n'.join(lines[source.start_line-1:source.end_line]))
                self.assertTrue(source.sha256)

    def test_paraphrase_and_limit(self):
        self.assertTrue(self.index.search('Как устроен Git MCP?', limit=1))
        self.assertEqual(len(self.index.search('Git', limit=1)), 1)

    def test_unknown_and_fts_syntax(self):
        self.assertEqual(self.index.search('погода завтра Барселона'), [])
        self.assertEqual(self.index.search('" OR * : ()'), [])

    def test_freshness_stable_ids(self):
        before = self.index.search('запуск')[0]
        self.assertEqual(before.id, self.index.search('запуск')[0].id)
        (self.root / 'README.md').write_text('# Помощник\n\nЗапуск изменён: python -m day31.web\n')
        after = self.index.search('запуск')[0]
        self.assertNotEqual(before.id, after.id)
        self.assertIn('day31.web', after.text)
        (self.root / 'README.md').unlink()
        self.assertEqual(self.index.search('запуск'), [])

    def test_allowlist_symlinks_and_limit(self):
        (self.root / '.env').write_text('secretmarker')
        (self.root / 'history.md').write_text('secretmarker')
        (self.root / 'docs/leak.md').symlink_to(self.root / '.env')
        self.assertEqual(self.index.search('secretmarker'), [])
        with self.assertRaises(ValueError):
            self.index.search('git', limit=0)


class LexicalExpansionTests(unittest.TestCase):
    def test_original_terms_retained_expansion_bounded_unique_and_contextual(self):
        found=tokens('действия параметры схема MCP')
        self.assertEqual(found[:4],['действия','параметры','схема','mcp'])
        self.assertTrue({'tool','инструмент','discovery','list_tools','parameters','arguments','input_schema','schema'}<=set(found))
        self.assertEqual(tokens('действия в отпуске'),['действия','отпуске'])
        self.assertEqual(tokens('действия Kubernetes'),['действия','kubernetes'])
        self.assertEqual(tokens('данные доступны понимает передать'),['данные','доступны','понимает','передать'])
        self.assertEqual(len(found),len(set(found)))
        many=tokens(' '.join(['действия','mcp']+[f'слово{i}' for i in range(100)]))
        self.assertLessEqual(len(many),40)
        self.assertEqual(many[:24],['действия','mcp']+[f'слово{i}' for i in range(22)])

    def test_general_api_synonyms_retrieve_synthetic_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'README.md').write_text('# API\n\nTool discovery list_tools. Function parameters arguments input_schema.\n')
            index=RetrievalIndex(root,root/'index.db')
            for question in ('Какие действия доступны у сервера?', 'Каталог сервера', 'Параметры инструмента', 'Аргументы функции', 'Схема MCP'):
                with self.subTest(question=question):
                    self.assertTrue(index.search(question))
            self.assertEqual(index.search('действия в отпуске'),[])
            self.assertEqual(index.search('действия Kubernetes'),[])

    def test_project_paraphrases_find_real_model_tools_and_list_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            index=RetrievalIndex(Path(__file__).resolve().parents[1],Path(temporary)/'index.db')
            questions=[
                'Откуда помощник Day17 понимает, какие действия доступны у сервера и какие данные нужно передать для выбранного действия?',
                'Какие действия и параметры предлагает сервер MCP?',
                'Как помощник получает каталог инструментов и схему аргументов?',
                'Как узнать доступные инструменты сервера Day17?',
            ]
            for question in questions:
                with self.subTest(question=question):
                    chunks=index.search(question)
                    self.assertTrue(any('ToolRuntime.model_tools()' in c.text and 'list_tools' in c.text for c in chunks))
                    self.assertLessEqual(len(chunks),5)
            for question,required in [('Как запустить MCP-сервер Day17?','uv run --frozen python day17/git_mcp_server.py --repo'),('Какой limit принимает get_recent_commits?','от 1 до 10'),('Какая сейчас Git-ветка?','detached HEAD')]:
                with self.subTest(question=question):
                    self.assertTrue(any(required in c.text for c in index.search(question)))
            kubernetes=tokens('Как настроить Kubernetes и ingress?')
            self.assertFalse({'tool','инструмент','discovery','list_tools','input_schema'}&set(kubernetes))


if __name__ == '__main__':
    unittest.main()
