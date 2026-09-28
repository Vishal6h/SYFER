"""Opt-in Linux launcher integration checks using an installed local model."""
import os
from pathlib import Path
import signal
import subprocess

root = Path(__file__).resolve().parents[1]
for backend in ('llama', 'ollama'):
    for action in ('exit', 'eof', 'interrupt'):
        process = subprocess.Popen([str(root / 'syfer'), '--backend', backend], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env={**os.environ, 'PYTHONUNBUFFERED': '1'})
        try:
            if action == 'interrupt':
                while True:
                    line = process.stdout.readline()
                    if not line:
                        raise RuntimeError('Frontend exited before readiness')
                    if 'Starting SYFER...' in line:
                        break
                process.send_signal(signal.SIGINT)
                output, _ = process.communicate(timeout=30)
            else:
                output, _ = process.communicate('/exit\n' if action == 'exit' else '', timeout=180)
            assert 'SYFER > Goodbye.' in output, output
            assert 'Traceback' not in output, output
            assert process.returncode == (130 if action == 'interrupt' else 0), (process.returncode, output)
            print(backend, action, 'PASS', flush=True)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
