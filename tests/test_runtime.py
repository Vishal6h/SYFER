"""Frontend contracts, portable setup, and owned process lifecycle."""
import contextlib
import io
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import syfer_chat as chat
import syfer_setup as setup


class RuntimeTests(unittest.TestCase):
    def run_chat(self, prompts, backend='llama'):
        output = io.StringIO()
        with patch('builtins.input', side_effect=prompts), patch.object(chat, 'request', return_value={'choices': [{'message': {'content': 'ok'}}], 'message': {'content': 'ok'}}) as request, contextlib.redirect_stdout(output):
            chat.chat(backend, 'http://127.0.0.1:1', 'system facts')
        return output.getvalue(), request

    def test_exit_aliases_never_reach_backend(self):
        for backend in ('ollama', 'llama'):
            for alias in chat.EXIT_COMMANDS:
                for prompt in (alias, alias.upper(), '  ' + alias.title() + '  '):
                    with self.subTest(backend=backend, prompt=prompt):
                        _, request = self.run_chat([prompt], backend)
                        request.assert_not_called()

    def test_normal_exit_words(self):
        prompts = ['How do I exit a Python loop?', 'Explain sys.exit()', 'Explain exit status 1.', 'Write quit_game().']
        _, request = self.run_chat(prompts + ['/exit'])
        self.assertEqual(request.call_count, 4)

    def test_clear_help(self):
        output, request = self.run_chat(['hello', '/clear', '/help', 'again', '/exit'])
        self.assertIn('SYFER > Conversation cleared.', output)
        self.assertIn('SYFER Commands', output)
        self.assertEqual(request.call_args.args[1]['messages'], [{'role': 'system', 'content': 'system facts'}, {'role': 'user', 'content': 'again'}])

    def test_facts(self):
        prompt = chat.system_prompt()
        for fact in ('SYFER', 'VISHAL K', 'September 27, 2026', 'https://github.com/Vishal6h/SYFER', 'NO built-in persistent memory', 'Qwen team / Alibaba Cloud'):
            self.assertIn(fact, prompt)
        self.assertNotIn('95%', prompt)

    def test_context_and_windows_arguments(self):
        model = PureWindowsPath(r'C:\Users\Test User\SYFER\model\SYFER-v1-Q4_K_M.gguf')
        binary = PureWindowsPath(r'C:\Users\Test User\SYFER\runtime\llama.cpp\build\bin\Release\llama-server.exe')
        for context in (None, '8192'):
            env = {} if context is None else {'SYFER_CONTEXT': context}
            with patch.dict(os.environ, env, clear=True), patch.object(chat, 'MODEL') as m, patch.object(chat, 'server_binary', return_value=binary), patch.object(chat.subprocess, 'Popen') as popen, patch.object(chat, 'request', return_value={'status': 'ok'}):
                m.is_file.return_value = True
                m.__str__.return_value = str(model)
                popen.return_value.poll.return_value = None
                process, base = chat.start_llama(False)
                args = popen.call_args.args[0]
                self.assertEqual(args[0], str(binary))
                self.assertEqual(args[2], str(model))
                self.assertEqual(args[4], context or '4096')
                self.assertEqual(args[6], '127.0.0.1')
                self.assertNotIn('shell', popen.call_args.kwargs)
                self.assertTrue(base.startswith('http://127.0.0.1:'))
        for value in ('0', '-1', 'abc', '32769', '1.5'):
            with patch.dict(os.environ, {'SYFER_CONTEXT': value}), self.assertRaisesRegex(RuntimeError, 'SYFER_CONTEXT'):
                chat.start_llama(False)

    def test_discovery_release_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='SYFER test ') as directory:
            root = Path(directory)
            binary = root / 'runtime/llama.cpp/build/bin/Release/llama-server.exe'
            binary.parent.mkdir(parents=True)
            binary.write_text('test')
            binary.chmod(0o755)
            with patch.object(chat, 'ROOT', root), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(chat.server_binary(), binary)
            with patch.object(chat, 'ROOT', root), patch.dict(os.environ, {'SYFER_LLAMA_SERVER': str(binary)}):
                self.assertEqual(chat.server_binary(), binary)

    def test_backend_selection(self):
        with patch.object(chat, 'ollama_models', return_value={'syfer:v1'}):
            self.assertEqual(chat.select_backend('auto'), 'ollama')
        with patch.object(chat, 'ollama_models', return_value=None), patch.object(chat, 'server_binary', return_value=Path('server')):
            self.assertEqual(chat.select_backend('auto'), 'llama')
            with self.assertRaisesRegex(RuntimeError, 'not responding'):
                chat.select_backend('ollama')
        with patch.object(chat, 'ollama_models', return_value=set()):
            with self.assertRaisesRegex(RuntimeError, 'syfer:v1 is missing'):
                chat.select_backend('ollama')

    def test_shutdown_on_exit_eof_interrupt(self):
        for event in ('/exit', EOFError(), KeyboardInterrupt()):
            process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            try:
                with patch.object(sys, 'argv', ['syfer', '--backend', 'llama']), patch.object(chat, 'start_llama', return_value=(process, 'http://127.0.0.1:1')), patch('builtins.input', side_effect=[event]), contextlib.redirect_stdout(io.StringIO()):
                    if isinstance(event, KeyboardInterrupt):
                        with self.assertRaises(KeyboardInterrupt):
                            chat.main()
                    else:
                        chat.main()
                self.assertIsNotNone(process.poll())
            finally:
                chat.stop_server(process)

    def test_startup_cancellation_stops_child(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            with patch.object(chat, 'MODEL') as model, patch.object(chat, 'server_binary', return_value=Path('server')), patch.object(chat.subprocess, 'Popen', return_value=process), patch.object(chat, 'request', side_effect=KeyboardInterrupt):
                model.is_file.return_value = True
                with self.assertRaises(KeyboardInterrupt):
                    chat.start_llama(False)
            self.assertIsNotNone(process.poll())
        finally:
            chat.stop_server(process)

    def test_hash_and_preserve_corrupt_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.gguf'
            path.write_bytes(b'abc')
            self.assertEqual(setup.checksum(path), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
            with patch.object(setup, 'MODEL', path), self.assertRaisesRegex(RuntimeError, 'checksum failed'):
                setup.verify_model()
            self.assertEqual(path.read_bytes(), b'abc')

    def test_free_port(self):
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', chat.free_port()))

    def test_no_color_when_redirected(self):
        with patch.object(sys.stdout, 'isatty', return_value=False):
            self.assertFalse(chat.color_supported())

    def test_powershell_static(self):
        launch = (chat.ROOT / 'syfer.ps1').read_text()
        install = (chat.ROOT / 'setup.ps1').read_text()
        for text in (launch, install):
            self.assertIn('$PSScriptRoot', text)
            self.assertNotIn('Invoke-Expression', text)
            self.assertNotIn('Set-ExecutionPolicy', text)
        self.assertIn("@('py', 'python', 'python3')", launch)
        self.assertIn("@('-3')", launch)
        self.assertIn('@args', launch)
        self.assertIn('Python 3.8 or newer is required', launch)

    def test_missing_model_and_runtime_errors(self):
        with patch.object(chat, 'MODEL') as model:
            model.is_file.return_value = False
            with self.assertRaisesRegex(RuntimeError, 'model missing'):
                chat.start_llama(False)
        with patch.object(chat, 'MODEL') as model, patch.object(chat, 'server_binary', return_value=None):
            model.is_file.return_value = True
            with self.assertRaisesRegex(RuntimeError, 'llama-server is unavailable'):
                chat.start_llama(False)

    def test_ollama_setup_idempotent_context(self):
        with patch.object(setup, 'request', return_value={'system': chat.system_prompt(), 'parameters': 'temperature 0\nnum_ctx 32768'}), patch.object(setup, 'run') as run:
            setup.prepare_ollama(io.StringIO(), False)
            run.assert_not_called()

    def test_setup_failure_logs_quietly(self):
        output, log = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaisesRegex(RuntimeError, 'logs/setup.log'):
            setup.run([sys.executable, '-c', 'print("compiler detail"); raise SystemExit(1)'], log, False)
        self.assertEqual(output.getvalue(), '')
        self.assertIn('compiler detail', log.getvalue())

    def test_setup_debug_output(self):
        output, log = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output):
            setup.run([sys.executable, '-c', 'print("compiler detail")'], log, True)
        self.assertIn('compiler detail', output.getvalue())
        self.assertIn('compiler detail', log.getvalue())

    def test_existing_llama_not_rebuilt(self):
        with patch.object(setup, 'server_binary', return_value=Path('server')), patch.object(setup, 'run') as run:
            setup.prepare_llama(io.StringIO(), False)
            run.assert_not_called()

    def test_generation_cancel_and_failure_cleanup(self):
        for failure in (KeyboardInterrupt(), OSError('backend stopped')):
            process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            try:
                with patch.object(sys, 'argv', ['syfer', '--backend', 'llama']), patch.object(chat, 'start_llama', return_value=(process, 'http://127.0.0.1:1')), patch('builtins.input', return_value='hello'), patch.object(chat, 'request', side_effect=failure), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(type(failure)):
                        chat.main()
                self.assertIsNotNone(process.poll())
            finally:
                chat.stop_server(process)

    def test_download_resume_and_ignored_range(self):
        for status, payload, expected in ((206, b'def', b'abcdef'), (200, b'abcdef', b'abcdef')):
            with tempfile.TemporaryDirectory() as directory:
                partial = Path(directory) / 'model.part'
                partial.write_bytes(b'abc')
                response = io.BytesIO(payload)
                response.status = status
                response.headers = {'Content-Range': 'bytes 3-5/6'}
                with patch.object(setup, 'urlopen', return_value=response) as open_url:
                    setup.download_model('https://example.invalid/model', partial)
                self.assertEqual(open_url.call_args.args[0].get_header('Range'), 'bytes=3-')
                self.assertEqual(partial.read_bytes(), expected)

    def test_bad_resume_range_preserves_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            partial = Path(directory) / 'model.part'
            partial.write_bytes(b'abc')
            response = io.BytesIO(b'bad')
            response.status = 206
            response.headers = {'Content-Range': 'bytes 0-2/6'}
            with patch.object(setup, 'urlopen', return_value=response), self.assertRaisesRegex(RuntimeError, 'invalid resume range'):
                setup.download_model('https://example.invalid/model', partial)
            self.assertEqual(partial.read_bytes(), b'abc')


if __name__ == '__main__':
    unittest.main()
