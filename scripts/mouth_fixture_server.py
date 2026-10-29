"""Loopback-only visual QA: fixed synthetic tone/silence, never natural TTS.

Serves one test page, generated WAV and built public assets; no repo directory
listing, credentials, databases or APIs. Run after frontend build.
"""
import argparse
import io
import math
import struct
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit

ROOT=Path(__file__).resolve().parents[1]


def fixture_bytes():
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000)
        audio.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(2*math.pi*440*i/8000))
            if i<2400 or 6400<=i<8800 else 0) for i in range(12800)))
    return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=unquote(urlsplit(self.path).path)
        if path=='/': data=(ROOT/'tests/browser/mouth-check.html').read_bytes();kind='text/html; charset=utf-8'
        elif path=='/fixture.wav': data=fixture_bytes();kind='audio/wav'
        elif path.startswith('/assets/'):
            public=(ROOT/'frontend/dist/lingshan-guide/assets').resolve()
            target=(public/path.removeprefix('/assets/')).resolve()
            if not target.is_relative_to(public) or not target.is_file(): self.send_error(404);return
            data=target.read_bytes()
            kind={'.js':'text/javascript','.json':'application/json','.png':'image/png','.moc3':'application/octet-stream'}.get(target.suffix,'application/octet-stream')
        else: self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def log_message(self,*args): pass


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8092);args=parser.parse_args()
    print(f'Synthetic WAV mouth check: http://127.0.0.1:{args.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
