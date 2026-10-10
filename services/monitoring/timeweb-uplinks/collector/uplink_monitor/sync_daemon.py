"""Mac history mirror: bounded pull over the existing SSH forward."""
import argparse
import fcntl
import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from .history_cache import Cache


def fetch(after, limit=100):
    request=urllib.request.Request(f'http://127.0.0.1:19106/api/sync?after={after}&limit={limit}')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request,timeout=5) as response:
        body=response.read(1_000_001)
    if len(body)>1_000_000:
        raise ValueError('response_size_limit')
    return json.loads(body)


def synchronize(cache, get=fetch, clock=time.time):
    page=get(-1,1)
    origin=page['database_id']
    cursor=cache.cursor(origin)
    deadline=time.monotonic()+20
    for _ in range(16):
        if cursor!=-1:
            page=get(cursor,100)
        if page['database_id']!=origin:
            raise ValueError('source_changed_during_sync')
        cache.apply(page,clock())
        cursor=page['next']
        if cursor==page['head']:
            return True
        if time.monotonic()>deadline:
            break
    return False


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',required=True)
    parser.add_argument('--port',type=int,default=19107)
    args=parser.parse_args()
    cache=Cache(args.database)
    lock=open(str(cache.path)+'.lock','a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    stop=threading.Event()

    def worker():
        failures=0
        while not stop.is_set():
            delay=30
            try:
                if not synchronize(cache):
                    delay=1
                failures=0
            except Exception as error:
                failures+=1
                delay=min(120,30*2**min(failures-1,2))
                if failures==1:
                    print('sync failed: '+type(error).__name__,flush=True)
                try:
                    cache.error(type(error).__name__)
                except Exception:
                    pass
            stop.wait(delay)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def do_GET(self):
            try:
                url=urlsplit(self.path)
                if url.path=='/api/current':
                    result=cache.snapshot(time.time())
                elif url.path=='/api/history':
                    query=parse_qs(url.query,strict_parsing=True)
                    if set(query)!={'from','to','metric'} or any(len(v)!=1 for v in query.values()):
                        raise ValueError('invalid_query')
                    result=cache.history(float(query['from'][0])/1000,float(query['to'][0])/1000,query['metric'][0])
                else:
                    self.send_error(404); return
                body=json.dumps(result,allow_nan=False).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (ValueError,KeyError,TypeError):
                self.send_error(400)
            except Exception:
                self.send_error(503)

    thread=threading.Thread(target=worker,daemon=True)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    thread.start()
    print(f'history API listening on http://127.0.0.1:{args.port}',flush=True)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        thread.join(timeout=25)
        lock.close()


if __name__=='__main__':
    main()
