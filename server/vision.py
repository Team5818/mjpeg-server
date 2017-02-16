import os
import time
from multiprocessing import Condition, Value, RLock, Pipe
from typing import Optional

import cv2

from . import CaptureHTTPHandler
from .pickle_classes import MJImage
from .requester import RequesterServer


def start_vision_process(comm_addr):
    reader, writer = Pipe(duplex=False)

    pid = os.fork()
    if pid:
        # parent
        reader.recv()
        reader.close()
        print("Vision thread is now running!")
        return pid
    else:
        # child
        server = RequesterServer()
        server.bind(comm_addr)
        vm = VisionMain(server)
        writer.send("running")
        writer.close()
        vm.run()
        # child does not exit normally
        return 0


class VisionMain:
    def __init__(self, requests: RequesterServer):
        self.childs = []
        self.requests = requests
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 600)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 400)

    def run(self):
        while True:
            # noinspection PyBroadException
            try:
                self.accept_children()
                frame = self.get_vision_frame()

                if frame:
                    self.send_vision_frame(frame)
            except Exception:
                import traceback
                traceback.print_exc()
            time.sleep(0.05)

    def accept_children(self):
        for request in self.requests.get_requests():
            parent_comms, child_comms = Pipe()
            fork_child(request, child_comms)
            self.childs.append((request, parent_comms))

    def get_vision_frame(self) -> Optional[MJImage]:
        rc, image = self.camera.read()
        if not rc:
            return None

        return MJImage(image)

    def send_vision_frame(self, frame: MJImage):
        dead = []
        for i in range(len(self.childs)):
            (req, writer) = self.childs[i]
            if writer.closed:
                dead.append(i)
                continue

            try:
                if writer.poll(0):
                    writer.recv()
                    writer.send(frame)
            except (BrokenPipeError, EOFError):
                dead.append(i)

        for i in reversed(dead):
            del self.childs[i]


def fork_child(request, comms):
    val = Value('i', 0)
    lock = RLock()
    cond = Condition(lock)

    pid = os.fork()
    if pid:
        # parent
        with lock:
            val.value = 1
            cond.notify_all()
            cond.wait_for(lambda: val.value == 2)
        return pid
    else:
        # child
        # noinspection PyBroadException
        try:
            handler = CaptureHTTPHandler(request, comms)
            with lock:
                cond.wait_for(lambda: val.value == 1)
                val.value = 2
                cond.notify_all()
            handler.serve()
        except Exception:
            request.server.handle_error(request.req, request.client_address)
            with lock:
                cond.wait_for(lambda: val.value == 1)
                val.value = 2
                cond.notify_all()
        finally:
            request.server.shutdown_request(request.req)
            comms.close()
            # child does not exit normally
            import signal
            os.kill(os.getpid(), signal.SIGKILL)
