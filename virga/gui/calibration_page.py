"""
Calibration page — displays the reading paragraph, records the user's voice,
runs analysis, and emits results back to the main window.
"""

import numpy as np
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QProgressBar, QTextEdit, QFrame, QSizePolicy,
)

from ..audio.recorder import RecorderThread, list_input_devices, default_input_device
from ..audio import analyzer
from ..dsp import profiles, eq_solver
from ..calibration_text import CONTEST_PARAGRAPH, RAGCHEW_PARAGRAPH


RECORD_DURATION = 35  # seconds


class LevelMeter(QProgressBar):
    """Horizontal RMS level bar, styled like a VU meter."""

    def __init__(self):
        super().__init__()
        self.setRange(0, 100)
        self.setValue(0)
        self.setTextVisible(False)
        self.setFixedHeight(14)
        self.setStyleSheet("""
            QProgressBar {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #238636,
                    stop:0.6 #f0a500,
                    stop:0.85 #da3633
                );
                border-radius: 2px;
            }
        """)


class CalibrationPage(QWidget):
    """
    Emits recording_done(AnalysisResult, ragchew_gains, contest_gains)
    when analysis is complete.
    """
    # (AnalysisResult, ragchew_gains, contest_gains, raw_audio, sample_rate)
    recording_done = Signal(object, dict, dict, object, int)

    def __init__(self):
        super().__init__()
        self._callsign: str = ""
        self._recorder: RecorderThread | None = None
        self._is_recording = False
        self._build_ui()

    def set_callsign(self, callsign: str):
        self._callsign = callsign
        self._update_paragraph()

    def _update_paragraph(self):
        mode = self.mode_combo.currentText()
        if mode == "Contest":
            text = CONTEST_PARAGRAPH.format(callsign=self._callsign or "YOURCALL")
        else:
            text = RAGCHEW_PARAGRAPH
        self.paragraph_box.setPlainText(text)

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Row: mode + device selector ──
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Contest", "Ragchew"])
        self.mode_combo.currentTextChanged.connect(self._update_paragraph)
        top_row.addWidget(self.mode_combo)

        top_row.addSpacing(20)
        top_row.addWidget(QLabel("Input device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(240)
        self._populate_devices()
        top_row.addWidget(self.device_combo, 1)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(32)
        refresh_btn.setToolTip("Refresh device list")
        refresh_btn.clicked.connect(self._populate_devices)
        top_row.addWidget(refresh_btn)

        layout.addLayout(top_row)

        # ── Instruction label ──
        instr = QLabel(
            "Read the paragraph below aloud at a natural, conversational pace. "
            "Try to maintain the same distance from your microphone that you use "
            "during actual operation."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(instr)

        # ── Paragraph display ──
        self.paragraph_box = QTextEdit()
        self.paragraph_box.setReadOnly(True)
        self.paragraph_box.setStyleSheet("""
            QTextEdit {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #e6edf3;
                font-family: 'Georgia', serif;
                font-size: 15px;
                line-height: 1.7;
                padding: 16px;
            }
        """)
        self.paragraph_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.paragraph_box, 1)

        # ── Level meter + timer ──
        meter_row = QHBoxLayout()
        meter_row.addWidget(QLabel("Level:"))
        self.level_meter = LevelMeter()
        meter_row.addWidget(self.level_meter, 1)
        self.timer_label = QLabel("0 / 35 s")
        self.timer_label.setStyleSheet("color: #8b949e; min-width: 60px;")
        self.timer_label.setAlignment(Qt.AlignRight)
        meter_row.addWidget(self.timer_label)
        layout.addLayout(meter_row)

        # ── Record button + status ──
        bottom_row = QHBoxLayout()
        self.record_btn = QPushButton("⏺  Start Recording")
        self.record_btn.setObjectName("primary")
        self.record_btn.setFixedHeight(38)
        self.record_btn.clicked.connect(self._toggle_recording)
        bottom_row.addWidget(self.record_btn)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        bottom_row.addWidget(self.status_label, 1)
        layout.addLayout(bottom_row)

        self._update_paragraph()

    def _populate_devices(self):
        self.device_combo.clear()
        devices = list_input_devices()
        default = default_input_device()
        for idx, name in devices:
            self.device_combo.addItem(name, userData=idx)
            if idx == default:
                self.device_combo.setCurrentIndex(self.device_combo.count() - 1)
        if not devices:
            self.device_combo.addItem("(no input devices found)", userData=None)

    # ── Recording control ────────────────────────────────────────────────────

    def _toggle_recording(self):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        device_idx = self.device_combo.currentData()
        self._recorder = RecorderThread(device_idx, RECORD_DURATION)
        self._recorder.level_updated.connect(self._on_level)
        self._recorder.seconds_elapsed.connect(self._on_tick)
        self._recorder.finished.connect(self._on_finished)
        self._recorder.error.connect(self._on_error)
        self._recorder.start()

        self._is_recording = True
        self.record_btn.setText("⏹  Stop")
        self.record_btn.setStyleSheet("background-color: #da3633; color: #fff; border:none; border-radius:6px; font-weight:bold; padding:6px 14px;")
        self.status_label.setText("Recording…")
        self.mode_combo.setEnabled(False)
        self.device_combo.setEnabled(False)

    def _stop_recording(self):
        if self._recorder:
            self._recorder.stop_early()
        self._is_recording = False
        self.status_label.setText("Stopping…")
        self.record_btn.setEnabled(False)

    def _on_level(self, rms: float):
        self.level_meter.setValue(int(rms * 100))

    def _on_tick(self, elapsed: int):
        self.timer_label.setText(f"{elapsed} / {RECORD_DURATION} s")

    def _on_finished(self, audio: np.ndarray, sample_rate: int):
        self._is_recording = False
        self.record_btn.setText("⏺  Start Recording")
        self.record_btn.setObjectName("primary")
        self.record_btn.setStyleSheet("")
        self.record_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.level_meter.setValue(0)

        if len(audio) < sample_rate * 5:
            self.status_label.setText("Recording too short — please try again.")
            return

        self.status_label.setText("Analysing…")
        result = analyzer.analyse(audio, sample_rate)

        ragchew_gains = eq_solver.solve(result.freqs, result.ltass_db, profiles.RAGCHEW, result.f0_hz)
        contest_gains = eq_solver.solve(result.freqs, result.ltass_db, profiles.CONTEST, result.f0_hz)

        self.status_label.setText(
            f"Done — F₀ {result.f0_label}  ·  {len(audio)/sample_rate:.0f} s recorded"
        )
        self.recording_done.emit(result, ragchew_gains, contest_gains, audio, sample_rate)

    def _on_error(self, msg: str):
        self._is_recording = False
        self.record_btn.setText("⏺  Start Recording")
        self.record_btn.setObjectName("primary")
        self.record_btn.setStyleSheet("")
        self.record_btn.setEnabled(True)
        self.mode_combo.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.status_label.setText(f"Error: {msg}")
        self.timer_label.setText("0 / 35 s")
