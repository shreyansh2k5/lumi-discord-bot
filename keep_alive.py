from threading import Thread
from http.server import HTTPServer, SimpleHTTPRequestHandler

def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), SimpleHTTPRequestHandler)
    Thread(target=server.serve_forever).start()

