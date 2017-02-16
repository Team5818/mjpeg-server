import time
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler, \
    SimpleHTTPRequestHandler
from multiprocessing.connection import Connection
from os import SEEK_SET, stat
from shutil import copyfileobj
from tempfile import TemporaryFile

from .pickle_classes import MJImage
from .requester import RequesterClient, Request


class CaptureHTTPServer(HTTPServer):
    def __init__(self, addr, comm_addr):
        super().__init__(addr, BaseHTTPRequestHandler)
        self.requests = RequesterClient()
        self.requests.connect(comm_addr)

    def process_request(self, req, client_addr):
        self.requests.send_request(Request(req, client_addr, self))
        # close request here
        self.close_request(req)

    # prevent requests copy
    def __getstate__(self):
        copy = self.__dict__.copy()
        del copy['requests']

        # a few non-pickle things
        del copy['_BaseServer__is_shut_down']
        return copy

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.requests = None


class CaptureHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, request: Request, reader: Connection):
        self.comms = reader
        self.id = request.id
        self.serving = False
        super().__init__(request.req, request.client_address, request.server)

    def do_GET(self):
        if self.path != '/cam':
            return SimpleHTTPRequestHandler.do_GET(self)
        self.serving = True

    def serve(self):
        if not self.serving:
            return
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type',
                             'multipart/x-mixed-replace; '
                             'boundary=--jpgboundary')
            self.end_headers()
            last_recv = time.monotonic()
            # request
            self.comms.send("request")
            while True:
                if not self.comms.poll(0):
                    if (time.monotonic() - last_recv) > 1:
                        # timeout after 100ms
                        raise TimeoutError(str(self.id) + " : no frames for 1s")
                    time.sleep(0.05)
                    continue
                last_recv = time.monotonic()
                jpg = self.comms.recv()  # type: MJImage
                jpg = jpg.to_pil()
                with TemporaryFile(suffix='.jpg') as f:
                    jpg.save(f, 'JPEG')
                    self.wfile.write(b"--jpgboundary")
                    self.send_header('Content-type', 'image/jpeg')
                    self.send_header('Content-length',
                                     str(stat(f.fileno()).st_size))
                    self.end_headers()
                    f.seek(0, SEEK_SET)
                    copyfileobj(f, self.wfile)

                self.comms.send("request")
        except BrokenPipeError:
            pass
        finally:
            super().finish()

    def finish(self):
        if self.serving:
            # if serving later, don't finish now!
            return
        super().finish()
