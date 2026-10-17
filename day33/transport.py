"""Общий дедлайн сети, включая DNS и заголовки; один ограниченный ответ."""
import io
import multiprocessing
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import ssl

MAX_RESPONSE_BYTES = 1_000_000

def _worker(connection, url, data, headers, timeout):
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=timeout) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES: raise ValueError('response_too_large')
        connection.send(('ok', body))
    except HTTPError as exc:
        try: connection.send(('http', exc.code, exc.read(65536)))
        finally: exc.close()
    except Exception as exc:
        tls = isinstance(exc,ssl.SSLError) or isinstance(exc,URLError) and isinstance(exc.reason,ssl.SSLError)
        connection.send(('tls' if tls else 'error', type(exc).__name__))
    finally: connection.close()

def request_with_deadline(request, timeout=90):
    if timeout <= 0: raise TimeoutError('network_deadline')
    context = multiprocessing.get_context('spawn')
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(send,request.full_url,request.data,dict(request.header_items()),timeout),daemon=True)
    deadline=time.monotonic()+timeout
    try:
        process.start();send.close()
        remaining=deadline-time.monotonic()
        if remaining <= 0 or not receive.poll(remaining):raise TimeoutError('network_deadline')
        result=receive.recv()
        if time.monotonic() >= deadline:raise TimeoutError('network_deadline')
        if result[0]=='http':raise HTTPError(request.full_url,result[1],'provider error',{},io.BytesIO(result[2]))
        if result[0]=='tls':raise ssl.SSLError('TLS failure')
        if result[0]!='ok':raise RuntimeError('network_transport:'+result[1])
        return io.BytesIO(result[1])
    finally:
        receive.close();send.close()
        if process.pid is not None:
            if process.is_alive():process.terminate()
            process.join(timeout=.2)
            if process.is_alive():process.kill();process.join()
