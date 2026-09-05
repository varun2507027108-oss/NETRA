"""ArUco fiducial utilities — version-adaptive across OpenCV 4.7+ / legacy.

Detection and marker generation work on both the modern ArucoDetector API
and the contrib-era free functions, so the same core runs on desktop
opencv-python and whatever OpenCV the Android/Chaquopy build carries.
"""
from __future__ import annotations

import cv2
import numpy as np

DEFAULT_DICT = cv2.aruco.DICT_4X4_50


def get_dictionary(dict_id=None):
    ar = cv2.aruco
    dict_id = DEFAULT_DICT if dict_id is None else dict_id
    if hasattr(ar, "getPredefinedDictionary"):
        return ar.getPredefinedDictionary(dict_id)
    return ar.Dictionary_get(dict_id)


def _parameters():
    ar = cv2.aruco
    if hasattr(ar, "DetectorParameters"):
        try:
            return ar.DetectorParameters()
        except TypeError:
            pass
    return ar.DetectorParameters_create()


def detect_markers(gray):
    """Detect ArUco markers.

    -> list of (corners, id, area_px); corners (4,2) float32 in OpenCV
    order (top-left, top-right, bottom-right, bottom-left); sorted by
    descending area so markers[0] is the calibration card.
    """
    ar = cv2.aruco
    dictionary = get_dictionary()
    if hasattr(ar, "ArucoDetector"):
        detector = ar.ArucoDetector(dictionary, _parameters())
        corners, ids, _ = detector.detectMarkers(gray)
    else:
        corners, ids, _ = ar.detectMarkers(gray, dictionary, parameters=_parameters())
    found = []
    if ids is not None:
        for quad, marker_id in zip(corners, np.asarray(ids).flatten()):
            quad = np.asarray(quad, dtype=np.float32).reshape(4, 2)
            found.append((quad, int(marker_id), float(cv2.contourArea(quad))))
    found.sort(key=lambda m: -m[2])
    return found


def generate_image(marker_id, side_px, dict_id=None):
    """Render a marker bitmap (fiducial card generation / tests)."""
    ar = cv2.aruco
    dictionary = get_dictionary(dict_id)
    if hasattr(ar, "generateImageMarker"):
        return ar.generateImageMarker(dictionary, marker_id, int(side_px))
    return ar.drawMarker(dictionary, marker_id, int(side_px))
