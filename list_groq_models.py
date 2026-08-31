import requests, os
from dotenv import load_dotenv
load_dotenv('.env')
api_key = os.getenv('GROQ_API_KEY')

res = requests.get('https://api.groq.com/openai/v1/models', headers={'Authorization': f'Bearer {api_key}'})
models = res.json()['data']
print('=== ALL GROQ MODELS ===')
for m in models:
    mid = m["id"]
    owned = m["owned_by"]
    print(f'  {mid} | owned_by: {owned}')

print('\n=== ASR / SPEECH MODELS ===')
asr_models = [m["id"] for m in models if 'whisper' in m["id"].lower() or 'speech' in m["id"].lower() or 'asr' in m["id"].lower()]
for m in asr_models:
    print(f'  {m}')

print('\n=== TTS MODELS ===')
tts_models = [m["id"] for m in models if 'orpheus' in m["id"].lower() or 'tts' in m["id"].lower()]
for m in tts_models:
    print(f'  {m}')
