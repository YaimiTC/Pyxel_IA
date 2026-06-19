import http.server, socketserver, urllib.request, urllib.error

TARGET = "http://localhost:8469"


# No seguir redirects: así el Set-Cookie del 303 de /web/login llega al navegador
# (urllib, por defecto, sigue el 3xx internamente y se pierde la cookie de sesión).
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


class H(http.server.BaseHTTPRequestHandler):
    def _send(self, status, headers, data):
        self.send_response(status)
        for k, v in headers:
            if k.lower() not in ('transfer-encoding', 'connection', 'content-encoding', 'content-length'):
                self.send_header(k, v)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _proxy(self):
        url = TARGET + self.path
        body = None
        cl = self.headers.get('Content-Length')
        if cl:
            body = self.rfile.read(int(cl))
        req = urllib.request.Request(url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in ('host', 'content-length', 'accept-encoding'):
                req.add_header(k, v)
        try:
            r = _opener.open(req, timeout=40)
            self._send(r.status, r.getheaders(), r.read())
        except urllib.error.HTTPError as e:
            # 3xx/4xx/5xx: reenviar status, cabeceras (Set-Cookie/Location) y cuerpo.
            self._send(e.code, e.headers.items(), e.read())
        except Exception:
            self.send_response(502)
            self.end_headers()

    do_GET = _proxy
    do_POST = _proxy

    def log_message(self, *a):
        pass


socketserver.ThreadingTCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer(("127.0.0.1", 8470), H).serve_forever()
