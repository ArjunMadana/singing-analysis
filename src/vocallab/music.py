from __future__ import annotations

import numpy as np


def hz_to_midi(frequency_hz: np.ndarray | float) -> np.ndarray:
    frequency = np.asarray(frequency_hz, dtype=np.float64)
    result = np.full(frequency.shape, np.nan, dtype=np.float64)
    positive = frequency > 0
    result[positive] = 69.0 + 12.0 * np.log2(frequency[positive] / 440.0)
    return result


def midi_to_hz(midi: np.ndarray | float) -> np.ndarray:
    return 440.0 * np.power(2.0, (np.asarray(midi, dtype=np.float64) - 69.0) / 12.0)


def cents_error(user_midi: np.ndarray, reference_midi: np.ndarray) -> np.ndarray:
    return 100.0 * (np.asarray(user_midi) - np.asarray(reference_midi))


def wrap_cents(cents: np.ndarray | float, period: float = 1200.0) -> np.ndarray:
    values = np.asarray(cents, dtype=np.float64)
    return (values + period / 2.0) % period - period / 2.0


def decompose_shift(semitones: int) -> tuple[int, int]:
    pitch_class = ((semitones + 6) % 12) - 6
    octave = semitones - pitch_class
    return pitch_class, octave

