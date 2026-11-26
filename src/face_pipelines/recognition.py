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
MAX_GROUP_PHOTO_PIXELS = 24_000_000


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
    return _get_face_embeddings(photo, group=False)[0]


def get_group_face_embeddings(photo: bytes) -> list[list[float]]:
    """Extract one descriptor per detected face in a classroom photo."""
    return _get_face_embeddings(photo, group=True)


def _get_face_embeddings(photo: bytes, *, group: bool) -> list[list[float]]:
    try:
        with Image.open(BytesIO(photo)) as source:
            pixel_limit = MAX_GROUP_PHOTO_PIXELS if group else 12_000_000
            if source.width * source.height > pixel_limit:
                raise FaceCaptureError("Take a smaller photo and try again.")
            image = ImageOps.exif_transpose(source).convert("RGB")
            max_side = 1920 if group else 960
            image.thumbnail((max_side, max_side))
            pixels = np.array(image)
    except (OSError, Image.DecompressionBombError) as error:
        raise FaceCaptureError("The photo could not be opened. Take a new photo.") from error

    detector, predictor, recognizer, lock = _load_models()
    with lock:
        faces = detector(pixels, 1)
        if not group and len(faces) != 1:
            raise FaceCaptureError("Make sure exactly one face is visible, then take a new photo.")
        return [
            list(recognizer.compute_face_descriptor(pixels, predictor(pixels, face)))
            for face in faces
        ]


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



def match_group_faces(captured, candidates):
    """Return the enrolled IDs within the face threshold for each detection."""
    templates = []
    student_ids = []
    for student_id, value in candidates.items():
        try:
            descriptor = np.asarray(value, dtype=np.float64)
        except (TypeError, ValueError, OverflowError):
            continue
        if descriptor.shape == (_DESCRIPTOR_SIZE,) and np.isfinite(descriptor).all():
            student_ids.append(student_id)
            templates.append(descriptor)

    if not templates:
        return [[] for _ in captured]
    matrix = np.stack(templates)
    return [
        [student_ids[index] for index in np.flatnonzero(
            np.linalg.norm(matrix - np.asarray(probe, dtype=np.float64), axis=1) <= _MAX_DISTANCE
        )]
        for probe in captured
    ]
