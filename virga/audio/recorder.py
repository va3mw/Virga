from __future__ import annotations

"""
Audio recording via sounddevice.

RecorderThread captures from a selected input device for a fixed duration,
emitting real-time RMS levels so the GUI can drive a level meter, then
emitting the complete recording when done.
"""

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal


def list_input_devices() -> list[tuple[int, str]]:
    """Return [(device_index, display_name), ...] for all input-capable devices."""
    results = []
    try:
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                results.append((i, d['name']))
    except Exception:
        pass
    return results


def default_input_device() -> int | None:
    try:
        return sd.default.device[0]
    except Exception:
        return None


class RecorderThread(QThread):
    """
    Records from an input device on a worker thread.

    Signals:
        level_updated(float): RMS level 0.0–1.0, emitted ~20 Hz
        seconds_elapsed(int): elapsed whole seconds
        finished(np.ndarray, int): (mono float32 audio, sample_rate)
        error(str): if recording fails
    """

    level_updated = Signal(float)
    seconds_elapsed = Signal(int)
    finished = Signal(object, int)
    error = Signal(str)

    SAMPLE_RATE = 48_000
    BLOCK_MS = 50  # ms per callback block

    def __init__(self, device_index: int | None, duration_s: int = 35):
        super().__init__()
        self.device_index = device_index
        self.duration_s = duration_s
        self._stop_flag = False
        self._chunks: list[np.ndarray] = []

    def run(self):
        self._chunks = []
        self._stop_flag = False
        block_frames = int(self.SAMPLE_RATE * self.BLOCK_MS / 1000)
        total_blocks = int(self.duration_s * 1000 / self.BLOCK_MS)
        elapsed_s = 0

        def callback(indata, frames, time_info, status):
            mono = indata[:, 0].copy().astype(np.float32)
            self._chunks.append(mono)
            rms = float(np.sqrt(np.mean(mono ** 2)))
            # Scale RMS to a 0–1 meter range assuming typical speech ~ 0.1 RMS
            self.level_updated.emit(min(rms * 8.0, 1.0))

        try:
            with sd.InputStream(
                device=self.device_index,
                channels=1,
                samplerate=self.SAMPLE_RATE,
                dtype='float32',
                blocksize=block_frames,
                callback=callback,
            ):
                for block in range(total_blocks):
                    if self._stop_flag:
                        break
                    self.msleep(self.BLOCK_MS)
                    new_elapsed = int((block + 1) * self.BLOCK_MS / 1000)
                    if new_elapsed > elapsed_s:
                        elapsed_s = new_elapsed
                        self.seconds_elapsed.emit(elapsed_s)

        except Exception as exc:
            self.error.emit(str(exc))
            return

        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(1, dtype=np.float32)
        self.finished.emit(audio, self.SAMPLE_RATE)

    def stop_early(self):
        self._stop_flag = True
