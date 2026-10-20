import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import desktop


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'Workspace'
        self.config = self.root / 'apps.local.json'
        self.patches = [patch.object(desktop, 'WORKSPACE', self.workspace), patch.object(desktop, 'APPS_PATH', self.config)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_three_language_commands_and_multiple_apps(self):
        for text, expected in [('Excel аш', 'excel'), ('Открой PowerPoint', 'powerpoint'), ('Open task manager', 'taskmanager'), ('Open Chrome browser', 'chrome')]:
            self.assertEqual(desktop.parse_command(text)['action'], expected)
        request = desktop.parse_command('Word пен браузерді аш')
        self.assertEqual(request['action'], 'launch_many')
        self.assertEqual(set(request['argument'].split(',')), {'word', 'browser'})

    def test_questions_never_run_actions(self):
        for text in ('Excel деген не?', 'How to open Chrome', 'Бума жаса деген не?', 'Что такое блокнот', 'Explain notepad'):
            self.assertIsNone(desktop.parse_command(text), text)

    def test_note_content_is_data(self):
        request = desktop.parse_command('Жазба сақта: Қалай оқимыз? <script>test</script>')
        result = desktop.execute(**request)
        self.assertEqual(Path(result['saved_path']).read_text(), 'Қалай оқимыз? <script>test</script>')
        second = desktop.execute(**request)
        self.assertNotEqual(result['saved_path'], second['saved_path'])

    def test_folder_rejects_paths_and_preserves_existing(self):
        for name in ('../outside', '..', 'C:\\Windows', '/tmp/foo', 'NUL', 'con.txt', 'bad?name'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                desktop.execute('make_folder', name)
        path = Path(desktop.execute('make_folder', 'Word сабағы')['saved_path'])
        (path / 'existing.txt').write_text('keep')
        with self.assertRaises(ValueError):
            desktop.execute('make_folder', 'Word сабағы')
        self.assertEqual((path / 'existing.txt').read_text(), 'keep')

    def test_registered_app_has_no_shell_arguments(self):
        executable = self.root / 'My App.exe'
        executable.touch()
        item = desktop.register_app('My App', str(executable), ['менің қосымшам', 'my app'])
        self.assertEqual(desktop.parse_command('Open my app')['action'], item['id'])
        with patch.object(desktop.sys, 'platform', 'win32'), patch.object(desktop.subprocess, 'Popen') as popen:
            desktop.launch(item['id'])
            popen.assert_called_once_with([str(executable)], shell=False)
        for path in ('relative.exe', str(executable) + ' & calc.exe', str(self.root / 'script.bat')):
            with self.assertRaises(ValueError):
                desktop.register_app('Other', path, ['other'])
        with self.assertRaises(ValueError):
            desktop.register_app('Dup', str(executable), ['word'])

    def test_unknown_app_cannot_be_run(self):
        with patch.object(desktop, 'launch') as launch:
            with self.assertRaises(ValueError):
                desktop.execute('launch_many', 'word,unregistered')
            launch.assert_not_called()

    def test_batch_reports_partial_failure(self):
        def fake(name):
            if name == 'excel':
                raise RuntimeError('Excel missing')
        with patch.object(desktop, 'launch', side_effect=fake):
            result = desktop.execute('launch_many', 'word,excel', 'en-US')
        self.assertIn('launch requested', result['message'])
        self.assertIn('Excel missing', result['message'])

    def test_search_is_bounded_and_skips_external_symlinks(self):
        self.workspace.mkdir()
        (self.workspace / 'lesson.docx').touch()
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'hidden.docx').touch()
        (self.workspace / 'linked').symlink_to(outside, target_is_directory=True)
        with patch.object(desktop, 'search_roots', return_value=[self.workspace]):
            files, limited = desktop.find_files('*.docx')
            self.assertEqual([x['name'] for x in files], ['lesson.docx'])
            for n in range(40):
                (self.workspace / f'file{n}.pdf').touch()
            files, limited = desktop.find_files('*.pdf')
            self.assertEqual(len(files), 30)
            self.assertTrue(limited)
        with patch.object(desktop, 'search_roots', return_value=[self.workspace]), patch.object(desktop, 'open_directory') as opened:
            with self.assertRaises(ValueError):
                desktop.open_search_folder(outside)
            opened.assert_not_called()

    def test_lesson_workflow_has_real_outputs(self):
        with patch.object(desktop, 'launch') as launch:
            result = desktop.execute('lesson_workspace', language='en-US')
        path = Path(result['saved_path'])
        self.assertTrue((path / 'Materials').is_dir())
        self.assertTrue((path / 'Tasks').is_dir())
        self.assertTrue((path / 'Results').is_dir())
        self.assertIn('Lesson topic:', (path / 'Lesson_notes.txt').read_text())
        self.assertEqual([call.args[0] for call in launch.call_args_list], ['word', 'browser'])

    def test_report_contains_actual_metrics(self):
        result = desktop.execute('full_report', language='en-US')
        report = Path(result['saved_path']).read_text()
        self.assertIn('CPU logical cores:', report)
        self.assertIn('RAM total (GiB):', report)
        self.assertIn('Top 10 processes by RAM', report)
        self.assertTrue(Path(result['saved_path']).is_relative_to(self.workspace))


if __name__ == '__main__':
    unittest.main()
