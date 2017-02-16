import multiprocessing as mp
import time
from multiprocessing import Event
from multiprocessing.managers import Namespace, SyncManager

import cv2
from typing import Optional, Tuple

from .pickle_classes import MJImage


def start_vision_process(manager: SyncManager) -> Tuple[Namespace, Event]:
    ns = manager.Namespace()
    evt = manager.Event()
    proc = mp.Process(target=vision_starter, args=(ns, evt,))
    proc.start()
    return ns, evt


def vision_starter(ns: Namespace, evt: Event):
    VisionMain(ns, evt).run()


class VisionMain:
    def __init__(self, ns: Namespace, evt: Event):
        self.ns = ns
        self.evt = evt
        self.camera = cv2.VideoCapture(0)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 200)

    def run(self):
        while True:
            # noinspection PyBroadException
            try:
                frame = self.get_vision_frame()

                if frame:
                    self.send_vision_frame(frame)
            except Exception:
                import traceback
                traceback.print_exc()
            time.sleep(0.05)

    def get_vision_frame(self) -> Optional[MJImage]:
        rc, image = self.camera.read()
        if not rc:
            return None

        return MJImage(image)

    def send_vision_frame(self, frame: MJImage):
        self.ns.image = frame

        if not getattr(self.ns, '_evt_set', False):
            self.evt.set()
            setattr(self.ns, '_evt_set', True)
