from __future__ import annotations

"""
Export page — displays SmartSDR TX EQ settings and provides
clipboard copy + file export. Includes raw vs. processed playback.
"""

import numpy as np
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QApplication, QFileDialog, QFrame, QSizePolicy,
)

from ..dsp.eq_solver import SMARTSDR_BANDS, build_sos, apply_eq


def _make_playback_format(sample_rate: int) -> QAudioFormat:
    fmt = QAudioFormat()
    fmt.setSampleRate(sample_rate)
    fmt.setChannelCount(1)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
    return fmt


class BandTable(QWidget):
    """Displays a SmartSDR 10-band EQ table with visual gain bars."""

    BAND_LABELS = ["32", "63", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]

    def __init__(self):
        super().__init__()
        self._gains: dict[int, float] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(2, len(SMARTSDR_BANDS))
        self.table.setHorizontalHeaderLabels(self.BAND_LABELS)
        self.table.setVerticalHeaderLabels(["Gain (dB)", "Bar"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setFixedHeight(100)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 4px;
                gridline-color: #30363d;
            }
            QHeaderView::section {
                background-color: #21262d;
                color: #8b949e;
                border: none;
                padding: 4px;
                font-size: 11px;
            }
            QTableWidget::item {
                color: #e6edf3;
                text-align: center;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.table)

    def set_gains(self, gains: dict[int, float]):
        self._gains = gains
        for col, band in enumerate(SMARTSDR_BANDS.astype(int)):
            g = gains.get(band, 0.0)
            val_item = QTableWidgetItem(f"{g:+.1f}")
            val_item.setTextAlignment(Qt.AlignCenter)

            # Colour-code: green positive, red negative
            if g > 0:
                val_item.setForeground(Qt.green)
            elif g < 0:
                val_item.setForeground(Qt.red)
            else:
                val_item.setForeground(Qt.gray)
            self.table.setItem(0, col, val_item)

            # Bar cell: ASCII-style bar chart in text
            max_bar = 10
            filled = int(abs(g) / max_bar * 8)
            bar = ("▲" * filled) if g >= 0 else ("▼" * filled)
            bar_item = QTableWidgetItem(bar.center(8))
            bar_item.setTextAlignment(Qt.AlignCenter)
            bar_item.setForeground(Qt.green if g >= 0 else Qt.red)
            self.table.setItem(1, col, bar_item)

    def gains_text(self, mode_name: str, callsign: str) -> str:
        lines = [
            f"=== VIRGA — {mode_name.upper()} PROFILE ===",
            f"Operator : {callsign}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "SmartSDR TX EQ — enter these values in the Transmit EQ panel:",
            "",
        ]
        for band, label in zip(SMARTSDR_BANDS.astype(int), self.BAND_LABELS):
            g = self._gains.get(band, 0.0)
            lines.append(f"  {label:>4} Hz:  {g:+5.1f} dB")
        lines += [
            "",
            "Note: Apply the matching compression/limiting in SmartSDR.",
            "For Contest: TX ALC ~80 %, Compander ON.",
            "For Ragchew: TX ALC ~60 %, Compander optional.",
        ]
        return "\n".join(lines)


class ExportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._callsign = ""
        self._ragchew_gains: dict[int, float] = {}
        self._contest_gains: dict[int, float] = {}
        self._raw_audio: np.ndarray | None = None
        self._sample_rate: int = 48_000
        self._sink: QAudioSink | None = None
        self._play_buffer: QBuffer | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Header ──
        hdr = QLabel("SmartSDR TX EQ Settings")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(hdr)

        instr = QLabel(
            "Open SmartSDR → Transmit → TX EQ. Enter the dB values below "
            "for each band. Positive = boost, negative = cut."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(instr)

        # ── Tabs: Ragchew / Contest ──
        self.mode_tabs = QTabWidget()
        layout.addWidget(self.mode_tabs)

        # Ragchew tab
        rq_widget = QWidget()
        rq_layout = QVBoxLayout(rq_widget)
        rq_layout.setContentsMargins(8, 12, 8, 8)
        self.ragchew_table = BandTable()
        rq_layout.addWidget(self.ragchew_table)
        rq_layout.addWidget(self._make_buttons("ragchew"))
        self.mode_tabs.addTab(rq_widget, "  Ragchew  ")

        # Contest tab
        ct_widget = QWidget()
        ct_layout = QVBoxLayout(ct_widget)
        ct_layout.setContentsMargins(8, 12, 8, 8)
        self.contest_table = BandTable()
        ct_layout.addWidget(self.contest_table)
        ct_layout.addWidget(self._make_buttons("contest"))
        self.mode_tabs.addTab(ct_widget, "  Contest  ")

        layout.addStretch()

        # ── F0 info ──
        self.f0_label = QLabel("")
        self.f0_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.f0_label)

        # ── Playback ──
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #30363d;")
        layout.addWidget(sep)

        pb_row = QHBoxLayout()
        pb_label = QLabel("Preview:")
        pb_label.setStyleSheet("color: #8b949e;")
        pb_row.addWidget(pb_label)
        self.play_raw_btn = QPushButton("▶  Play Raw")
        self.play_raw_btn.clicked.connect(self._play_raw)
        pb_row.addWidget(self.play_raw_btn)
        self.play_ragchew_btn = QPushButton("▶  Play Ragchew EQ")
        self.play_ragchew_btn.clicked.connect(lambda: self._play_processed("ragchew"))
        pb_row.addWidget(self.play_ragchew_btn)
        self.play_contest_btn = QPushButton("▶  Play Contest EQ")
        self.play_contest_btn.clicked.connect(lambda: self._play_processed("contest"))
        pb_row.addWidget(self.play_contest_btn)
        self.stop_btn = QPushButton("⏹  Stop")
        self.stop_btn.clicked.connect(self._stop_playback)
        pb_row.addWidget(self.stop_btn)
        pb_row.addStretch()
        layout.addLayout(pb_row)

    def _make_buttons(self, mode: str) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 8, 0, 0)

        copy_btn = QPushButton("📋  Copy to Clipboard")
        copy_btn.setObjectName("primary")
        copy_btn.clicked.connect(lambda: self._copy(mode))
        row.addWidget(copy_btn)

        save_btn = QPushButton("💾  Save to File…")
        save_btn.clicked.connect(lambda: self._save(mode))
        row.addWidget(save_btn)
        row.addStretch()
        return w

    # ── Public ──────────────────────────────────────────────────────────────

    def set_results(self, callsign: str,
                    ragchew_gains: dict[int, float],
                    contest_gains: dict[int, float],
                    f0_label: str = "",
                    raw_audio: np.ndarray | None = None,
                    sample_rate: int = 48_000):
        self._callsign = callsign
        self._ragchew_gains = ragchew_gains
        self._contest_gains = contest_gains
        self._raw_audio = raw_audio
        self._sample_rate = sample_rate
        self.ragchew_table.set_gains(ragchew_gains)
        self.contest_table.set_gains(contest_gains)
        if f0_label:
            self.f0_label.setText(f"Fundamental frequency: {f0_label}")

    # ── Actions ─────────────────────────────────────────────────────────────

    def _copy(self, mode: str):
        table = self.ragchew_table if mode == "ragchew" else self.contest_table
        text = table.gains_text(mode.title(), self._callsign)
        QApplication.clipboard().setText(text)

    def _save(self, mode: str):
        table = self.ragchew_table if mode == "ragchew" else self.contest_table
        text = table.gains_text(mode.title(), self._callsign)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save EQ settings",
            str(Path.home() / f"Virga_{self._callsign}_{mode}.txt"),
            "Text files (*.txt)"
        )
        if path:
            Path(path).write_text(text, encoding="utf-8")

    def _play_raw(self):
        if self._raw_audio is None:
            return
        self._start_playback(self._raw_audio)

    def _play_processed(self, mode: str):
        if self._raw_audio is None:
            return
        gains = self._ragchew_gains if mode == "ragchew" else self._contest_gains
        sos = build_sos(gains, float(self._sample_rate))
        processed = apply_eq(self._raw_audio, sos)
        # Normalise to avoid clipping
        peak = np.max(np.abs(processed))
        if peak > 0.95:
            processed = processed * (0.95 / peak)
        self._start_playback(processed)

    def _start_playback(self, audio: np.ndarray):
        if self._sink:
            self._sink.stop()

        fmt = _make_playback_format(self._sample_rate)
        self._sink = QAudioSink(QMediaDevices.defaultAudioOutput(), fmt)

        data = audio.astype(np.float32).tobytes()
        self._play_buffer = QBuffer()
        self._play_buffer.setData(QByteArray(data))
        self._play_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._sink.start(self._play_buffer)

    def _stop_playback(self):
        if self._sink:
            self._sink.stop()

    def set_raw_audio(self, audio: np.ndarray, sample_rate: int):
        self._raw_audio = audio
        self._sample_rate = sample_rate
