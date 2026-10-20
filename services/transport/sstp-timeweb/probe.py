"""Read-only HTTP payload inside the isolated SSTP namespace."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

PAYLOAD=b'SSTP_TIMEWEB_PROBE_V1\n'*4096

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        if self.path!='/sstp-probe':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Length',str(len(PAYLOAD)))
        self.send_header('Content-Type','application/octet-stream')
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        try:
            self.wfile.write(PAYLOAD)
        except (BrokenPipeError,ConnectionResetError):
            pass

if __name__=='__main__':
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
