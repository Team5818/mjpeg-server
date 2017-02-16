from multiprocessing import Manager

from server import CaptureHTTPServer
from server.vision import start_vision_process

PORT = 9090


def main():
    manager = Manager()
    comms, evt = start_vision_process(manager)
    CaptureHTTPServer(('', PORT), comms, evt).serve_forever(poll_interval=0)


if __name__ == '__main__':
    main()
