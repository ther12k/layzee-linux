import http.server
import socketserver
import threading
import os

class StaticServer:
    def __init__(self, directory, port=0):
        self.directory = directory
        self.port = port
        self.httpd = None
        self.thread = None

        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(h_self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)

            def end_headers(h_self):
                # Ensure CORS and caching headers
                h_self.send_header("Access-Control-Allow-Origin", "*")
                h_self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                h_self.send_header("Access-Control-Allow-Headers", "*")
                super().end_headers()

            def log_message(h_self, format, *args):
                pass

        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("127.0.0.1", self.port), Handler)
        self.port = self.httpd.server_address[1]

    def start(self):
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def get_url(self, page="index.html"):
        return f"http://127.0.0.1:{self.port}/{page}"

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
