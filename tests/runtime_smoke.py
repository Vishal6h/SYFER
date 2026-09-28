"""Opt-in real local model smoke test: python3 tests/runtime_smoke.py."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import syfer_chat as s

questions = ['Who developed you?', 'What is your public release date?', 'Can you remember previous chats?', 'What is your performance percentage?']
process = None
try:
    models = s.ollama_models()
    print('Ollama syfer:v1 available:', models is not None and 'syfer:v1' in models, flush=True)
    process, base = s.start_llama(False)
    for backend, address in [('llama', base)] + ([('ollama', s.OLLAMA)] if models is not None and 'syfer:v1' in models else []):
        for question in questions:
            messages = [{'role':'system', 'content':s.system_prompt()}, {'role':'user', 'content':question}]
            if backend == 'ollama':
                answer = s.request(address + '/api/chat', {'model':'syfer:v1', 'messages':messages, 'stream':False}, timeout=600)['message']['content']
            else:
                answer = s.request(address + '/v1/chat/completions', {'messages':messages, 'temperature':0, 'max_tokens':256, 'stream':False}, timeout=600)['choices'][0]['message']['content']
            print(json.dumps({'backend':backend, 'question':question, 'answer':answer}), flush=True)
finally:
    if process is not None:
        s.stop_server(process)
        print('Owned llama-server stopped:', process.poll() is not None, flush=True)
