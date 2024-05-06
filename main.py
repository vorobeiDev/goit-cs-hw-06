import logging
import mimetypes
import socket
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote_plus
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

from pymongo.mongo_client import MongoClient

URI_DB = 'mongodb://mongodb:27017'
BASE_DIR = Path(__file__).parent
CHUNK_SIZE = 1024
HTTP_PORT = 3000
SOCKET_PORT = 5000
HTTP_HOST = '0.0.0.0'
SOCKET_HOST = 'localhost'


class Server(BaseHTTPRequestHandler):
    def do_GET(self):
        router = urlparse(self.path).path
        match router:
            case '/':
                self.send_html('index.html')
            case '/message.html':
                self.send_html('message.html')
            case _:
                file = BASE_DIR.joinpath(router[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html('error.html', 404)

    def do_POST(self):
        size = int(self.headers['Content-Length'])
        data = self.rfile.read(size)
        try:
            socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_client.sendto(data, (SOCKET_HOST, SOCKET_PORT))
            socket_client.close()
        except Exception as e:
            logging.error('Failed to send data: %s', e)

        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def send_html(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200):
        self.send_response(status)
        mimetype = mimetypes.guess_type(str(filename))[0] or 'text/plain'
        self.send_header('Content-type', mimetype)
        self.end_headers()
        with open(filename, 'rb') as f:
            self.wfile.write(f.read())


def run_http_server():
    httpd = HTTPServer((HTTP_HOST, HTTP_PORT), Server)
    try:
        logging.info(f'HTTP Server started: http://{HTTP_HOST}:{HTTP_PORT}...')
        httpd.serve_forever()
    except Exception as e:
        logging.error(f'Failed to start HTTP server: {e}')
    finally:
        logging.info('HTTP server stopped.')
        httpd.server_close()


def save_to_db(data):
    client = MongoClient(URI_DB)
    db = client.homework
    try:
        data = unquote_plus(data)
        parse_data = dict(item.split('=') for item in data.split('&'))
        parse_data['date'] = datetime.now()
        db.messages.insert_one(parse_data)
    except Exception as e:
        logging.error(e)
    finally:
        client.close()


def run_socket_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((SOCKET_HOST, SOCKET_PORT))
    logging.info(f'Socket server started: socket://{SOCKET_HOST}:{SOCKET_PORT}...')
    try:
        while True:
            data, addr = s.recvfrom(CHUNK_SIZE)
            logging.info(f'Received data from {addr}: {data}')
            save_to_db(data.decode())
    except Exception as e:
        logging.error(e)
    finally:
        logging.info('Socket server stopped.')
        s.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(threadName)s %(message)s')
    Thread(target=run_http_server, name='HTTP server').start()
    Thread(target=run_socket_server, name='Socket server').start()
