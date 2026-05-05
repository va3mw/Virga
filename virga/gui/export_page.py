from __future__ import annotations

"""
Export page — displays EQ settings for the selected device and provides
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
    QApplication, QFileDialog, QFrame, QSizePolicy, QComboBox,
)

from ..audio.analyzer import AnalysisResult
from ..dsp.eq_devices import EQDevice, BUILTIN_DEVICES, SMARTSDR_TX_EQ
from ..dsp.eq_solver import solve, build_sos, apply_eq
from ..dsp.profiles import RAGCHEW, CONTEST
from .. import storage


def _make_playback_format(sample_rate: int) -> QAudioFormat:
    fmt = QAudioFormat()
    fmt.setSampleRate(sample_rate)
    fmt.setChannelCount(1)
    fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
    return fmt


class BandTable(QWidget):
    """Displays an EQ table whose columns adapt to the selected device."""

    def __init__(self):
        super().__init__()
        self._gains: dict[int, float] = {}
        self._device: EQDevice = SMARTSDR_TX_EQ
        self._build_table()

    def _build_table(self):
        layout = self.layout()
        if layout is None:
            from PySide6.QtWidgets import QVBoxLayout
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)

        # Remove existing table widget if present
        if hasattr(self, 'table') and self.table is not None:
            layout.removeWidget(self.table)
            self.table.deleteLater()

        labels = self._device.band_labels
        self.table = QTableWidget(2, len(labels))
        self.table.setHorizontalHeaderLabels(labels)
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

    def set_device(self, device: EQDevice):
        self._device = device
        self._build_table()
        self.set_gains(self._gains)

    def set_gains(self, gains: dict[int, float]):
        self._gains = gains
        for col, band in enumerate(self._device.bands.astype(int)):
            g = gains.get(int(band), 0.0)
            val_item = QTableWidgetItem(f"{g:+.1f}")
            val_item.setTextAlignment(Qt.AlignCenter)
            if g > 0:
                val_item.setForeground(Qt.green)
            elif g < 0:
                val_item.setForeground(Qt.red)
            else:
                val_item.setForeground(Qt.gray)
            self.table.setItem(0, col, val_item)

            max_bar = max(abs(self._device.min_db), abs(self._device.max_db))
            filled = int(abs(g) / max_bar * 8)
            bar = ("▲" * filled) if g >= 0 else ("▼" * filled)
            bar_item = QTableWidgetItem(bar.center(8))
            bar_item.setTextAlignment(Qt.AlignCenter)
            bar_item.setForeground(Qt.green if g >= 0 else Qt.red)
            self.table.setItem(1, col, bar_item)

    def gains_text(self, mode_name: str, callsign: str, device: EQDevice) -> str:
        lines = [
            f"=== VIRGA — {mode_name.upper()} PROFILE ===",
            f"Operator : {callsign}",
            f"Device   : {device.name}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"{device.name} — enter these values:",
            "",
        ]
        for band, label in zip(device.bands.astype(int), device.band_labels):
            g = self._gains.get(int(band), 0.0)
            lines.append(f"  {label:>5}: {g:+5.1f} dB")
        if device.has_compressor and device.compressor_note:
            lines += ["", "Compressor:", f"  {device.compressor_note}"]
        lines += [
            "",
            "Note: For Contest — TX ALC ~80 %, Compander ON.",
            "      For Ragchew — TX ALC ~60 %, Compander optional.",
        ]
        return "\n".join(lines)


class ExportPage(QWidget):
    def __init__(self):
        super().__init__()
        self._callsign = ""
        self._result: AnalysisResult | None = None
        self._ragchew_gains: dict[int, float] = {}
        self._contest_gains: dict[int, float] = {}
        self._standard_gains: dict[int, float] = {}
        self._raw_audio: np.ndarray | None = None
        self._sample_rate: int = 48_000
        self._sink: QAudioSink | None = None
        self._play_buffer: QBuffer | None = None
        self._device: EQDevice = SMARTSDR_TX_EQ
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(8, 8, 8, 8)

        # ── Header ──
        hdr = QLabel("EQ Settings")
        hdr.setStyleSheet("font-size: 15px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(hdr)

        # ── Device selector ──
        dev_row = QHBoxLayout()
        dev_label = QLabel("EQ Device:")
        dev_label.setStyleSheet("color: #8b949e;")
        dev_row.addWidget(dev_label)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(220)
        for dev in BUILTIN_DEVICES:
            self.device_combo.addItem(dev.name, userData=dev)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        dev_row.addWidget(self.device_combo)

        self.device_desc = QLabel(SMARTSDR_TX_EQ.description)
        self.device_desc.setStyleSheet("color: #8b949e; font-size: 11px;")
        dev_row.addWidget(self.device_desc, 1)
        layout.addLayout(dev_row)

        # ── Compressor note ──
        self.compressor_note = QLabel("")
        self.compressor_note.setWordWrap(True)
        self.compressor_note.setStyleSheet(
            "color: #f0a500; font-size: 11px; "
            "background: #1c1a0e; border: 1px solid #5a4500; "
            "border-radius: 4px; padding: 6px 10px;"
        )
        self.compressor_note.setVisible(False)
        layout.addWidget(self.compressor_note)

        instr = QLabel(
            "Enter the dB values below into your EQ device. "
            "Positive = boost, negative = cut."
        )
        instr.setWordWrap(True)
        instr.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(instr)

        # ── Tabs: Ragchew / Contest / Standard ──
        self.mode_tabs = QTabWidget()
        layout.addWidget(self.mode_tabs)

        rq_widget = QWidget()
        rq_layout = QVBoxLayout(rq_widget)
        rq_layout.setContentsMargins(8, 12, 8, 8)
        self.ragchew_table = BandTable()
        rq_layout.addWidget(self.ragchew_table)
        rq_layout.addWidget(self._make_buttons("ragchew"))
        self.mode_tabs.addTab(rq_widget, "  Ragchew  ")

        ct_widget = QWidget()
        ct_layout = QVBoxLayout(ct_widget)
        ct_layout.setContentsMargins(8, 12, 8, 8)
        self.contest_table = BandTable()
        ct_layout.addWidget(self.contest_table)
        ct_layout.addWidget(self._make_buttons("contest"))
        self.mode_tabs.addTab(ct_widget, "  Contest  ")

        # Standard tab — shown only when at least one standard exists
        std_widget = QWidget()
        std_layout = QVBoxLayout(std_widget)
        std_layout.setContentsMargins(8, 12, 8, 8)

        std_sel_row = QHBoxLayout()
        std_sel_label = QLabel("Target standard:")
        std_sel_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        std_sel_row.addWidget(std_sel_label)
        self.standard_combo = QComboBox()
        self.standard_combo.setMinimumWidth(260)
        self.standard_combo.currentIndexChanged.connect(self._on_standard_changed)
        std_sel_row.addWidget(self.standard_combo)
        std_sel_row.addStretch()
        std_layout.addLayout(std_sel_row)

        self.standard_table = BandTable()
        std_layout.addWidget(self.standard_table)
        std_layout.addWidget(self._make_buttons("standard"))
        self.mode_tabs.addTab(std_widget, "  Standard  ")
        self._std_tab_index = self.mode_tabs.count() - 1
        self.mode_tabs.setTabVisible(self._std_tab_index, False)

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
                    result: AnalysisResult,
                    raw_audio: np.ndarray | None = None,
                    sample_rate: int = 48_000,
                    f0_label: str = ""):
        self._callsign = callsign
        self._result = result
        self._raw_audio = raw_audio
        self._sample_rate = sample_rate
        if f0_label or (result and result.f0_label):
            self.f0_label.setText(
                f"Fundamental frequency: {f0_label or result.f0_label}"
            )
        self._recompute_gains()

    # ── Private ─────────────────────────────────────────────────────────────

    def _on_device_changed(self, _idx: int):
        self._device = self.device_combo.currentData()
        self.device_desc.setText(self._device.description)

        has_comp = self._device.has_compressor
        self.compressor_note.setVisible(has_comp)
        if has_comp:
            self.compressor_note.setText(
                f"⚠  Compressor detected — {self._device.compressor_note}"
            )

        self.ragchew_table.set_device(self._device)
        self.contest_table.set_device(self._device)
        self._recompute_gains()

    def _recompute_gains(self):
        if self._result is None:
            return
        r = self._result
        self._ragchew_gains = solve(r.freqs, r.ltass_db, RAGCHEW,
                                    r.f0_hz, self._device)
        self._contest_gains = solve(r.freqs, r.ltass_db, CONTEST,
                                    r.f0_hz, self._device)
        self.ragchew_table.set_gains(self._ragchew_gains)
        self.contest_table.set_gains(self._contest_gains)
        self._reload_standards()

    def _reload_standards(self):
        standards = storage.standards_store.load_all()
        visible = len(standards) > 0
        self.mode_tabs.setTabVisible(self._std_tab_index, visible)

        self.standard_combo.blockSignals(True)
        prev = self.standard_combo.currentText()
        self.standard_combo.clear()
        for std in standards:
            self.standard_combo.addItem(std.name, userData=std)
        # Restore previous selection if still present
        idx = self.standard_combo.findText(prev)
        if idx >= 0:
            self.standard_combo.setCurrentIndex(idx)
        self.standard_combo.blockSignals(False)

        if visible:
            self._solve_standard()

    def _solve_standard(self):
        if self._result is None:
            return
        std_profile = self.standard_combo.currentData()
        if std_profile is None:
            return
        r = self._result
        self._standard_gains = solve(r.freqs, r.ltass_db, std_profile,
                                     r.f0_hz, self._device)
        self.standard_table.set_gains(self._standard_gains)

    def _on_standard_changed(self, _idx: int):
        self._solve_standard()

    # ── Actions ─────────────────────────────────────────────────────────────

    def _copy(self, mode: str):
        table = self._table_for(mode)
        label = self.standard_combo.currentText() if mode == "standard" else mode.title()
        text = table.gains_text(label, self._callsign, self._device)
        QApplication.clipboard().setText(text)

    def _save(self, mode: str):
        table = self._table_for(mode)
        label = self.standard_combo.currentText() if mode == "standard" else mode.title()
        text = table.gains_text(label, self._callsign, self._device)
        path, _ = QFileDialog.getSaveFileName(
            self, "Save EQ settings",
            str(Path.home() / f"Virga_{self._callsign}_{mode}_{self._device.name.replace(' ', '_')}.txt"),
            "Text files (*.txt)"
        )
        if path:
            Path(path).write_text(text, encoding="utf-8")

    def _play_raw(self):
        if self._raw_audio is None:
            return
        self._start_playback(self._raw_audio)

    def _table_for(self, mode: str) -> BandTable:
        if mode == "ragchew":
            return self.ragchew_table
        if mode == "contest":
            return self.contest_table
        return self.standard_table

    def _play_processed(self, mode: str):
        if self._raw_audio is None:
            return
        if mode == "ragchew":
            gains = self._ragchew_gains
        elif mode == "contest":
            gains = self._contest_gains
        else:
            gains = self._standard_gains
        sos = build_sos(gains, float(self._sample_rate))
        processed = apply_eq(self._raw_audio, sos)
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
