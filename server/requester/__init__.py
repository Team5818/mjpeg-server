import struct
from io import BytesIO
from multiprocessing.reduction import dump
from pickle import loads
from socket import socket, AF_UNIX, SOCK_STREAM
from typing import List, Iterator, Optional

from ..socketutil import get_readable, read_or_eof, wait_for_data


class RqMessage:
    ACCEPTED = b'accepted'


_id = 0


def _next_id():
    global _id
    _id += 1
    return _id


class Request:
    def __init__(self, req: socket, client_address, server):
        self.id = _next_id()
        self.req = req
        self.client_address = client_address
        self.server = server


class RequesterClient:
    def __init__(self):
        self.sock = None  # type: socket

    def connect(self, addr):
        self.sock = socket(AF_UNIX, SOCK_STREAM)
        self.sock.setblocking(0)
        self.sock.connect(addr)

    def send_request(self, request: Request):
        data = BytesIO()
        dump(request, data)
        data_buf = data.getvalue()

        self.sock.send(struct.pack('>I', len(data_buf)) + data_buf)

        # wait for the response, in 1s
        wait_for_data(self.sock, RqMessage.ACCEPTED, 1)


class RequesterServer:
    def __init__(self):
        self._server_sock = None  # type: socket
        self._client_socks = []  # type: List[socket]

    def bind(self, addr):
        ss = socket(AF_UNIX, SOCK_STREAM)
        ss.bind(addr)
        ss.listen()
        ss.setblocking(0)
        self._server_sock = ss

    def get_requests(self) -> Iterator[Request]:
        rlist = [self._server_sock] + self._client_socks
        readable_sockets = get_readable(rlist)
        if not readable_sockets:
            return

        try:
            ss_index = readable_sockets.index(self._server_sock)
            del readable_sockets[ss_index]

            self.accept_client()
        except ValueError:
            pass

        for sock in readable_sockets:
            request = self.read_request(sock)
            if request is None:
                self._client_socks.remove(sock)
            else:
                yield request

    def accept_client(self):
        ss = self._server_sock
        cs = ss.accept()[0]
        cs.setblocking(0)
        self._client_socks.append(cs)

    @staticmethod
    def read_request(sock: socket) -> Optional[Request]:
        try:
            length = struct.unpack('>I', read_or_eof(sock, 4))[0]
            data = read_or_eof(sock, length)
            req = loads(data)

            # notify of loaded data
            # must be done after since this closes FDs
            sock.send(RqMessage.ACCEPTED)
            return req
        except EOFError:
            return None
