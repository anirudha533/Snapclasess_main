"""Create speaker embeddings and match them against supplied candidates."""

from collections.abc import Mapping
from io import BytesIO
from threading import Lock

import librosa
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
import streamlit as st

_SAMPLE_RATE = 16_000
_EMBEDDING_SIZE = 256
_MIN_SPEECH_SAMPLES = _SAMPLE_RATE // 2
_MAX_DURATION_SECONDS = 120
_MAX_RECORDING_BYTES = 25 * 1024 * 1024
_DEFAULT_THRESHOLD = 0.65


class VoiceCaptureError(ValueError):
    """The recording could not be used to create a voice embedding."""


@st.cache_resource
def load_voice_encoder() -> tuple[VoiceEncoder, Lock]:
    return VoiceEncoder(device="cpu", verbose=False), Lock()


def _load_audio(audio_bytes: bytes) -> np.ndarray:
    if not audio_bytes or len(audio_bytes) > _MAX_RECORDING_BYTES:
        raise VoiceCaptureError("Provide an audio recording of up to 25 MB.")
    try:
        audio, _ = librosa.load(
            BytesIO(audio_bytes), sr=_SAMPLE_RATE, mono=True,
            duration=_MAX_DURATION_SECONDS + 1,
        )
    except (ValueError, OSError, RuntimeError) as error:
        raise VoiceCaptureError("The recording could not be opened. Try a WAV file.") from error
    if audio.size > _MAX_DURATION_SECONDS * _SAMPLE_RATE:
        raise VoiceCaptureError("Use a recording of up to two minutes.")
    if audio.size < _MIN_SPEECH_SAMPLES or not np.isfinite(audio).all() or not audio.any():
        raise VoiceCaptureError("Provide a recording with at least half a second of clear speech.")
    return audio


def _unit_embedding(value: object) -> np.ndarray | None:
    try:
        embedding = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        return None
    if embedding.shape != (_EMBEDDING_SIZE,) or not np.isfinite(embedding).all():
        return None
    scale = np.max(np.abs(embedding))
    if scale == 0:
        return None
    scaled = embedding / scale
    return scaled / np.linalg.norm(scaled)


def _embed_audio(audio: np.ndarray) -> list[float] | None:
    speech = preprocess_wav(audio, source_sr=_SAMPLE_RATE)
    if speech.size < _MIN_SPEECH_SAMPLES or not np.isfinite(speech).all():
        return None

    encoder, lock = load_voice_encoder()
    with lock:
        embedding = _unit_embedding(encoder.embed_utterance(speech))
    return embedding.tolist() if embedding is not None else None


def get_voice_embedding(audio_bytes: bytes) -> list[float]:
    """Return a JSON-compatible speaker embedding for one recording."""
    embedding = _embed_audio(_load_audio(audio_bytes))
    if embedding is None:
        raise VoiceCaptureError("No usable speech was found. Record a longer sample.")
    return embedding


def identify_speaker(
    new_embedding: object,
    candidates_dict: Mapping[int, object],
    threshold: float = _DEFAULT_THRESHOLD,
) -> tuple[int | None, float]:
    """Return the best match and its cosine score, or no ID below threshold."""
    if not 0 < threshold <= 1:
        raise ValueError("The cosine threshold must be greater than zero and at most one.")
    probe = _unit_embedding(new_embedding)
    if probe is None:
        return None, 0.0

    best_id = None
    best_score = -1.0
    tied = False
    for student_id, candidate in candidates_dict.items():
        reference = _unit_embedding(candidate)
        if reference is None:
            continue
        score = float(np.clip(np.dot(probe, reference), -1.0, 1.0))
        if best_id is None or score > best_score:
            best_id, best_score = student_id, score
            tied = False
        elif score == best_score:
            tied = True

    if best_id is None:
        return None, 0.0
    if tied or best_score < threshold:
        return None, best_score
    return best_id, best_score
