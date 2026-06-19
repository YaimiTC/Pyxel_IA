"""Proxy inverso minimo: el panel Preview de Claude lo gestiona en un puerto
propio (variable PORT) y reenvia todo a Odoo (127.0.0.1:8069). Permite ver Odoo
en vivo dentro de Claude sin mover el contenedor Docker.
"""
import http.client
import os
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer

UPSTREAM_HOST = "127.0.0.1"
UPSTREAM_PORT = 8069
PORT = int(os.environ.get("PORT", "8169"))

HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-length",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None

        fwd = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        # Se conserva el Host original para que Odoo construya URLs hacia el proxy.

        try:
            conn = http.client.HTTPConnection(UPSTREAM_HOST, UPSTREAM_PORT, timeout=90)
            conn.request(self.command, self.path, body=body, headers=fwd)
            resp = conn.getresponse()
            data = resp.read()
        except Exception as ex:  # noqa: BLE001
            self.send_error(502, "Proxy error: %s" % ex)
            return

        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in HOP:
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:  # noqa: BLE001
            pass
        conn.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = _proxy

    def log_message(self, *args):  # silencio
        pass


class Server(ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    print("Proxy Odoo en 127.0.0.1:%s -> %s:%s" % (PORT, UPSTREAM_HOST, UPSTREAM_PORT))
    Server(("127.0.0.1", PORT), Handler).serve_forever()
