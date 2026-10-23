"""Per-request diagnostics; no keys, URLs, capabilities or provider error bodies."""
from contextvars import ContextVar
import re

model_trace = ContextVar('model_trace', default=None)


def safe_reason(reason):
    return reason if reason in {'empty_stream','truncated_stream','invalid_stream_protocol','incomplete_finish',
        'ReadTimeout','ConnectTimeout','ConnectError','ReadError','HTTPError'} or re.fullmatch(r'http_\d{3}',reason) else 'provider_error'


class CitationFilter:
    """Only retrieved IDs may be rendered as structured [cite:id] references.

    This checks ID membership, not whether a cited passage supports a statement.
    All output and source text still require HTML escaping on the client.
    """
    def __init__(self, chunks):
        self.allowed={str(c['chunk_id']) for c in chunks if c.get('chunk_id')}
        self.pending=''
        self.rejected=0

    def feed(self, text, final=False):
        self.pending+=text
        def replace(match):
            if match.group(1) in self.allowed: return '[cite:'+match.group(1)+']'
            self.rejected+=1
            return '[引用编号无效]'
        value=re.sub(r'\[(?:cite|source):([^\]]*)\]',replace,self.pending,flags=re.I)
        cut=value.rfind('[')
        if not final and cut>=0 and ']' not in value[cut:] and len(value)-cut<160:
            self.pending=value[cut:]
            return value[:cut]
        self.pending=''
        if cut>=0 and re.match(r'\[(?:cite|source):',value[cut:],flags=re.I) and ']' not in value[cut:]:
            self.rejected+=1
            value=value[:cut]+'[引用编号无效]'
        return value
