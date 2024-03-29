from typing import Tuple

import cv2
import numba
import numpy as np
from vinbigdata import BoxCoordsFloat, BoxCoordsInt


def is_interactive():
    import __main__ as main
    return not hasattr(main, '__file__')


@numba.jit
def compute_intersection_area(bbox1: BoxCoordsInt, bbox2: BoxCoordsInt) -> int:
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])
    h = x2 - x1
    w = y2 - y1
    if h < 0:
        h = 0
    if w < 0:
        h = 0
    return h * w


@numba.jit
def compute_area(bbox: BoxCoordsInt) -> int:
    return (bbox[3] - bbox[1]) * (bbox[2] - bbox[0])


@numba.jit
def compute_union_area(bbox1: BoxCoordsInt, bbox2: BoxCoordsInt) -> int:
    x1 = min(bbox1[0], bbox2[0])
    y1 = min(bbox1[1], bbox2[1])
    x2 = max(bbox1[2], bbox2[2])
    y2 = max(bbox1[3], bbox2[3])
    h = x2 - x1
    w = y2 - y1
    if h < 0:
        h = 0
    if w < 0:
        h = 0
    return h * w


def resize(img: np.array, max_size: Tuple[int, int]) -> np.array:
    return cv2.resize(img, max_size, interpolation=cv2.INTER_LANCZOS4)


@numba.jit
def rel2abs(box: BoxCoordsFloat, img_shape: Tuple[int, int]) -> BoxCoordsFloat:
    return (box[0] * img_shape[0], box[1] * img_shape[1], box[2] * img_shape[0], box[3] * img_shape[1])


@numba.jit
def abs2rel(box: BoxCoordsFloat, img_shape: Tuple[int, int]) -> BoxCoordsFloat:
    return (box[0] / img_shape[0], box[1] / img_shape[1], box[2] / img_shape[0], box[3] / img_shape[1])
