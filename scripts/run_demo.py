"""Safe local demonstration: TF-IDF, extractive text and a synthetic test tone only."""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    if not (ROOT/'frontend/dist/lingshan-guide/assets/guide-runtime.js').exists():
        raise SystemExit('Run npm ci --ignore-scripts and npm run build in frontend first.')
    runtime=ROOT/'.runtime/demo'
    runtime.mkdir(parents=True,exist_ok=True)
    os.environ.update(GUIDE_NO_ENV_FILE='1',DEMO_MODE='true',LLM_API_KEY='',LLM_FALLBACK_API_KEY='',
        DATABASE_URL='sqlite+aiosqlite:///'+(runtime/'guide.sqlite3').as_posix(),
        VECTOR_CACHE=str(runtime/'vectors.npz'),TTS_CACHE_DIR=str(runtime/'tts'),ADMIN_API_KEY=os.environ.get('ADMIN_API_KEY',''))
    sys.path.insert(0,str(ROOT/'backend'))
    import uvicorn
    print('DEMO: local TF-IDF and extractive answers; synthetic tone, no real model/ASR/TTS calls.',flush=True)
    print(f'http://127.0.0.1:{args.port}/pages/home.html',flush=True)
    uvicorn.run('app.main:app',host='127.0.0.1',port=args.port,access_log=False,log_level='warning')


if __name__=='__main__': main()
