import cv2
from PIL import Image


class MJImage:
    def __init__(self, cv2_img):
        self.rgb_array = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)

    def to_pil(self):
        return Image.fromarray(self.rgb_array)
