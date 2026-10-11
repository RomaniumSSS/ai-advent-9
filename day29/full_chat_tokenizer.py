r"""Локальный Qwen2 byte-BPE из metadata уже установленной модели; без весов/сети.

Pre-tokenizer соответствует LLAMA_VOCAB_PRE_TYPE_QWEN2 в llama.cpp/llama-vocab.cpp.
Unicode-категории заменяют \p{L}/\p{N}; шаблон/schema учитываются отдельным запасом.
"""
from functools import lru_cache
import heapq
import re
import unicodedata


def letter(c):return bool(c) and unicodedata.category(c).startswith('L')
def number(c):return bool(c) and unicodedata.category(c).startswith('N')


def pieces(text):
    """Порядок альтернатив существенен: пробел перед буквой входит в её слово."""
    i=0
    while i<len(text):
        start=i;c=text[i]
        contraction=re.match(r"'(?:s|t|re|ve|m|ll|d)",text[i:],re.I)
        if contraction:i+=len(contraction[0])
        elif letter(c) or (c not in '\r\n' and not letter(c) and not number(c) and i+1<len(text) and letter(text[i+1])):
            if not letter(c):i+=1
            while i<len(text) and letter(text[i]):i+=1
        elif number(c):i+=1
        elif (not c.isspace() and not letter(c) and not number(c)) or (c==' ' and i+1<len(text) and not text[i+1].isspace() and not letter(text[i+1]) and not number(text[i+1])):
            if c==' ':i+=1
            while i<len(text) and not text[i].isspace() and not letter(text[i]) and not number(text[i]):i+=1
            while i<len(text) and text[i] in '\r\n':i+=1
        else:
            end=i
            while end<len(text) and text[end].isspace():end+=1
            last_newline=max(text.rfind('\n',i,end),text.rfind('\r',i,end))
            if last_newline>=i:i=last_newline+1
            elif end==len(text):i=end
            elif end-i>1:i=end-1
            else:i=end
        yield text[start:i]


class Qwen2Tokenizer:
    def __init__(self,info):
        if info.get('tokenizer.ggml.model')!='gpt2' or info.get('tokenizer.ggml.pre')!='qwen2':raise ValueError('unsupported_local_tokenizer')
        tokens=info.get('tokenizer.ggml.tokens');merges=info.get('tokenizer.ggml.merges')
        if not isinstance(tokens,list) or not isinstance(merges,list) or len(tokens)<256 or not merges:raise ValueError('missing_local_tokenizer_metadata')
        # GPT-2 byte alphabet: непечатные байты кодируются после U+0100.
        visible=list(range(33,127))+list(range(161,173))+list(range(174,256))
        self.encoder={b:chr(b) for b in visible};extra=0
        for b in range(256):
            if b not in self.encoder:self.encoder[b]=chr(256+extra);extra+=1
        self.vocab=set(tokens);self.ranks={tuple(m.split(' ')):i for i,m in enumerate(merges)}
        if any(self.encoder[b] not in self.vocab for b in range(256)):raise ValueError('incomplete_byte_vocabulary')

    @lru_cache(maxsize=16384)
    def piece_count(self,piece):
        symbols=[self.encoder[b] for b in piece.encode('utf-8')]
        if not symbols:return 0
        count=len(symbols);left=list(range(-1,count-1));right=list(range(1,count+1));right[-1]=-1
        live=[True]*count;versions=[0]*count;heap=[]
        def queue(a):
            if a<0 or not live[a]:return
            b=right[a]
            if b<0:return
            rank=self.ranks.get((symbols[a],symbols[b]))
            if rank is not None:heapq.heappush(heap,(rank,a,b,versions[a],versions[b]))
        for a in range(count-1):queue(a)
        while heap:
            _,a,b,va,vb=heapq.heappop(heap)
            if not live[a] or not live[b] or right[a]!=b or versions[a]!=va or versions[b]!=vb:continue
            symbols[a]+=symbols[b];versions[a]+=1;live[b]=False;count-=1
            right[a]=right[b]
            if right[b]>=0:left[right[b]]=a
            queue(left[a]);queue(a)
        return count

    def count(self,text):return sum(self.piece_count(p) for p in pieces(text))


def check_budget(messages,options,schema,tokenizer):
    import json
    if not messages or any(m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),str) for m in messages):raise ValueError('invalid_messages')
    packed=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
    # AICODE-NOTE: считаем полную JSON-обёртку, хотя Ollama передаёт шаблону
    # только content; это намеренный запас сверх реальных content tokens.
    serialized=tokenizer.count(packed(messages))
    content=sum(tokenizer.count(m['content']) for m in messages)
    bounded_content=max(serialized,content);schema_count=tokenizer.count(packed(schema));reserve=512
    count=bounded_content+schema_count+reserve
    if count+options['num_predict']>options['num_ctx']:raise ValueError('input_exceeds_frozen_context_budget')
    return {'method':'local_qwen2_bpe_with_reserves','input_upper_bound':count,'serialized_messages_tokens':serialized,'content_tokens':content,'bounded_messages_tokens':bounded_content,
            'schema_tokens':schema_count,'template_reserve':reserve,'output_reserved':options['num_predict'],
            'num_ctx':options['num_ctx'],'messages_bytes':len(packed(messages).encode())}
