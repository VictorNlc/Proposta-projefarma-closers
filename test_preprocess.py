from PIL import Image, ImageEnhance
import cv2
import numpy as np
import os
import glob

img_path = max(glob.glob('debug/crop_*.png'), key=os.path.getctime)
pil_img = Image.open(img_path)
img_np = np.array(pil_img.convert('RGB'))
img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
img_cv = cv2.fastNlMeansDenoisingColored(img_cv, None, 10, 10, 7, 21)
img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
enhancer = ImageEnhance.Contrast(img_pil)
img_pil = enhancer.enhance(1.5)
gray = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2GRAY)
thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
Image.fromarray(thresh).save('preprocessed_test.png')
