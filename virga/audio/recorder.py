from __future__ import annotations

"""
Audio recording via PySide6 QtMultimedia (Windows WASAPI).

No external audio libraries required — uses Qt's native audio stack.
"""

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


def list_input_devices() -> list[tuple[int, str]]:
    """Return [(index, display_name), ...] for all input-capable devices."""
    return [(i, d.description()) for i, d in enumerate(QMediaDevices.audioInputs())]


def default_input_device() -> int | None:
    default = QMediaDevices.defaultAudioInput()
    for i, d in enumerate(QMediaDevices.audioInputs()):
        if d.id() == default.id():
            return i
    return 0


def _make_format(sample_rate: int = 48_000) -> QAudioFormat:
    fmt = QAudioFormat()
    fmt.setSampleRate(sample_rate)
    fmt.setChannelCount(1)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
    return fmt


class RecorderThread(QThread):
    """
    Records from a selected input device on a worker thread.

    Signals:
        level_updated(float): RMS level 0.0–1.0, emitted ~20 Hz
        seconds_elapsed(int): whole seconds elapsed
        finished(np.ndarray, int): (mono float32 audio, sample_rate)
        error(str): human-readable error message
    """

    level_updated = Signal(float)
    seconds_elapsed = Signal(int)
    finished = Signal(object, int)
    error = Signal(str)

    SAMPLE_RATE = 48_000
    BLOCK_MS = 50

    def __init__(self, device_index: int | None, duration_s: int = 35):
        super().__init__()
        self.device_index = device_index
        self.duration_s = duration_s
        self._stop_flag = False

    def run(self):
        self._stop_flag = False

        devices = QMediaDevices.audioInputs()
        if not devices:
            self.error.emit("No audio input devices found on this system.")
            return

        if self.device_index is not None and self.device_index < len(devices):
            device = devices[self.device_index]
        else:
            device = QMediaDevices.defaultAudioInput()

        fmt = _make_format(self.SAMPLE_RATE)
        if not device.isFormatSupported(fmt):
            # Fallback to Int16 if Float not supported
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if not device.isFormatSupported(fmt):
                self.error.emit(
                    f"Device '{device.description()}' does not support "
                    f"48 kHz mono recording."
                )
                return

        source = QAudioSource(device, fmt)
        io = source.start()

        chunks: list[np.ndarray] = []
        elapsed_ms = 0
        last_s = 0

        while elapsed_ms < self.duration_s * 1000 and not self._stop_flag:
            self.msleep(self.BLOCK_MS)
            elapsed_ms += self.BLOCK_MS

            data = io.readAll()
            if len(data) > 0:
                raw = bytes(data)
                if fmt.sampleFormat() == QAudioFormat.SampleFormat.Float:
                    arr = np.frombuffer(raw, dtype=np.float32).copy()
                else:
                    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                chunks.append(arr)
                rms = float(np.sqrt(np.mean(arr ** 2)))
                self.level_updated.emit(min(rms * 8.0, 1.0))

            elapsed_s = elapsed_ms // 1000
            if elapsed_s > last_s:
                last_s = elapsed_s
                self.seconds_elapsed.emit(elapsed_s)

        source.stop()

        audio = np.concatenate(chunks) if chunks else np.zeros(1, dtype=np.float32)
        self.finished.emit(audio, self.SAMPLE_RATE)

    def stop_early(self):
        self._stop_flag = True
