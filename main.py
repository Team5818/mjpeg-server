import os

from server import CaptureHTTPServer
from server.vision import start_vision_process
import signal

PORT = 9090


def main():
    comms = '/tmp/mjpeg-{}.sock'.format(os.getpid())
    parent = start_vision_process(comms)
    if parent:
        CaptureHTTPServer(('', PORT), comms).serve_forever()


if __name__ == '__main__':
    # fork main into it's own process group
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0)
    else:
        os.setsid()
        # noinspection PyBroadException
        try:
            main()
        except:
            import traceback
            traceback.print_exc()
        finally:
            os.killpg(os.getpgid(0), signal.SIGTERM)

