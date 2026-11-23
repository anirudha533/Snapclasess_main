"""Extract and compare dlib face descriptors."""

from io import BytesIO
from threading import Lock

import dlib
import face_recognition_models
import numpy as np
from PIL import Image, ImageOps
import streamlit as st

_DESCRIPTOR_SIZE = 128
_MAX_DISTANCE = 0.5


class FaceCaptureError(ValueError):
    pass


@st.cache_resource
def _load_models():
    return (
        dlib.get_frontal_face_detector(),
        dlib.shape_predictor(face_recognition_models.pose_predictor_model_location()),
        dlib.face_recognition_model_v1(face_recognition_models.face_recognition_model_location()),
        Lock(),
    )


def get_face_embedding(photo: bytes) -> list[float]:
    try:
        with Image.open(BytesIO(photo)) as source:
            if source.width * source.height > 12_000_000:
                raise FaceCaptureError("Take a smaller photo and try again.")
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((960, 960))
            pixels = np.array(image)
    except (OSError, Image.DecompressionBombError) as error:
        raise FaceCaptureError("The photo could not be opened. Take a new photo.") from error

    detector, predictor, recognizer, lock = _load_models()
    with lock:
        faces = detector(pixels, 1)
        if len(faces) != 1:
            raise FaceCaptureError("Make sure exactly one face is visible, then take a new photo.")
        landmarks = predictor(pixels, faces[0])
        return list(recognizer.compute_face_descriptor(pixels, landmarks))


def face_matches(captured: object, enrolled: object) -> bool:
    try:
        probe = np.asarray(captured, dtype=np.float64)
        template = np.asarray(enrolled, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        return False

    if probe.shape != (_DESCRIPTOR_SIZE,) or template.shape != probe.shape:
        return False
    if not np.isfinite(probe).all() or not np.isfinite(template).all():
        return False
    return bool(np.linalg.norm(probe - template) <= _MAX_DISTANCE)
