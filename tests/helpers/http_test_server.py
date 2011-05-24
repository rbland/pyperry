# An HTTP server designed to make testing easy
import sys
import os
import os.path as path
import stat
import signal
import atexit
import pickle
from time import sleep
from BaseHTTPServer import BaseHTTPRequestHandler
from SocketServer import TCPServer
import httplib

RESPONSE_DIR = path.join(path.abspath(os.path.dirname(__file__)), 'responses')
RESPONSE_PATH = path.join(RESPONSE_DIR, 'current_response.pkl')
LAST_REQUEST_PATH = path.join(RESPONSE_DIR, 'last_request.pkl')
server_pid = None

class ServerAlreadyRunning(Exception):
    pass

def spawn(port=8888):
    """spawns an instance of the HTTP test server as a child process"""
    global server_pid

    if server_pid is not None:
        raise ServerAlreadyRunning("pid: %d, port: %d" % (server_pid, port))

    if not path.exists(RESPONSE_DIR):
        os.mkdir(RESPONSE_DIR)

    pid = os.fork()
    if pid == 0: # in child process
        os.execl(sys.executable, sys.executable, __file__, str(port))
    else: # in parent process
        server_pid = pid
        atexit.register(kill)
        sleep(0.5)
        return server_pid

def run_server(port=8888):
    # Prevents server output from showing up in our test runner output.
    sys.stderr = open('/dev/null', 'w')
    sys.stdout = open('/dev/null', 'w')

    TCPServer.allow_reuse_address = True
    try:
        httpd = TCPServer(('', port), HttpTestRequestHandler)
        print "http_test_server running (pid: %d, port: %d)" % (os.getpid(),
                port)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "http_test_server shutting down (pid: %d, port: %d)" % (
                os.getpid(), port)
        try: httpd.socket.close()
        except: pass
        exit()


def kill():
    """stops this instance of the HTTP test server"""
    global server_pid
    if server_pid is not None:
        os.kill(server_pid, signal.SIGTERM)
        os.wait() # beware of zombies
    server_pid = None

def set_response(**kwargs):
    """sets the response returned for all HTTP requests"""
    response = {
        'status': 200,
        'headers': {},
        'body': 'OK'
    }
    response.update(kwargs)
    _write(response)

def last_request():
    return _read('request')

def _read(which='response'):
    path = RESPONSE_PATH
    if which == 'request':
        path = LAST_REQUEST_PATH
    f = open(path, 'r')
    result = pickle.load(f)
    f.close()
    return result

def _write(obj, which='response'):
    path = RESPONSE_PATH
    if which == 'request':
        path = LAST_REQUEST_PATH
    f = open(path, 'w')
    result = pickle.dump(obj, f)
    f.close()


class HttpTestRequestHandler(BaseHTTPRequestHandler):
    """
    serves the response in 'tests/helpers/resonses/current_response.txt'
    regardless of the request method or paramters.
    """

    def do_response(self):
        global last_request, last_response

        if not path.exists(RESPONSE_PATH):
            set_response()

        response = _read()
        _write({
            'server': str(self.server),
            'path': str(self.path),
            'method': str(self.command),
            'headers': dict(self.headers)
        }, 'request')

        self.send_response(response['status'])
        for k, v in response['headers'].items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(response['body'])

    def do_GET(self):
        self.do_response()

    def do_POST(self):
        self.do_response()

    def do_PUT(self):
        self.do_response()

    def do_DELETE(self):
        self.do_response()

if __name__ == '__main__':
    port = 8888
    if len(sys.argv) == 2:
        try: port = int(sys.argv[1])
        except ValueError: pass
    run_server(port)
