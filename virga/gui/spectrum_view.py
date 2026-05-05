from __future__ import annotations

"""
Spectrum results view — shows measured LTASS, Bell Labs reference,
ragchew and contest target curves, saved standards, F0 marker and harmonics.
"""

import numpy as np
import pyqtgraph as pg
from scipy.signal import savgol_filter
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton,
    QInputDialog, QMessageBox,
)

from ..audio.analyzer import AnalysisResult
from ..dsp.ltass_reference import get_ltass_at
from ..dsp.profiles import RAGCHEW, CONTEST
from ..dsp.eq_solver import SMARTSDR_BANDS, solve
from ..dsp.eq_devices import SMARTSDR_TX_EQ
from .. import storage

pg.setConfigOption('background', '#0d1117')
pg.setConfigOption('foreground', '#c9d1d9')
pg.setConfigOption('antialias', True)

# Colours cycled for multiple saved standards
_STANDARD_COLOURS = ['#e040fb', '#00bcd4', '#ff7043', '#b2ff59', '#ffd740']


class SpectrumView(QWidget):
    def __init__(self):
        super().__init__()
        self._result: AnalysisResult | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Toggles row ──
        top = QHBoxLayout()
        top.setContentsMargins(8, 8, 8, 0)

        self._cb_ref       = self._make_checkbox("Bell Labs LTASS",      "#888888")
        self._cb_ragchew   = self._make_checkbox("Ragchew target",       "#3fb950")
        self._cb_contest   = self._make_checkbox("Contest target",       "#f0a500")
        self._cb_corrected = self._make_checkbox("Your corrected voice", "#58a6ff")
        self._cb_standards = self._make_checkbox("Standards",            "#e040fb")
        self._cb_f0        = self._make_checkbox("F₀ harmonics",         "#f85149")

        for cb in (self._cb_ref, self._cb_ragchew, self._cb_contest,
                   self._cb_corrected, self._cb_standards, self._cb_f0):
            cb.stateChanged.connect(self._refresh_plot)
            top.addWidget(cb)

        top.addStretch()

        self._save_btn = QPushButton("💾  Save as Standard…")
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet(
            "font-size: 11px; padding: 3px 10px; margin-left: 8px;"
        )
        self._save_btn.clicked.connect(self._on_save_standard)
        top.addWidget(self._save_btn)

        layout.addLayout(top)

        # ── Plot widget ──
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Level (dB, relative)')
        self.plot_widget.setLabel('bottom', 'Frequency (Hz)')
        self.plot_widget.setLogMode(x=True, y=False)
        self.plot_widget.setXRange(np.log10(80), np.log10(12000), padding=0)
        self.plot_widget.setYRange(-30, 15, padding=0)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.getAxis('bottom').setTicks(self._freq_ticks())
        self.plot_widget.addLegend(offset=(5, 5))

        layout.addWidget(self.plot_widget, 1)

        # ── F0 info strip ──
        self.f0_strip = QLabel("")
        self.f0_strip.setAlignment(Qt.AlignCenter)
        self.f0_strip.setStyleSheet(
            "background: #161b22; border-top: 1px solid #30363d; "
            "color: #8b949e; font-size: 11px; padding: 4px;"
        )
        layout.addWidget(self.f0_strip)

    @staticmethod
    def _make_checkbox(label: str, colour: str) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(True)
        cb.setStyleSheet(f"color: {colour}; font-size: 11px; margin-right: 12px;")
        return cb

    @staticmethod
    def _freq_ticks():
        major = [(np.log10(f), f"{f} Hz" if f < 1000 else f"{f//1000} kHz")
                 for f in (100, 200, 500, 1000, 2000, 5000, 10000)]
        minor = [(np.log10(f), "") for f in
                 (125, 160, 250, 315, 400, 630, 800, 1250, 1600, 2500, 3150, 4000, 6300, 8000)]
        return [major, minor]

    # ── Public ──────────────────────────────────────────────────────────────

    def show_plot(self, result: AnalysisResult):
        self._result = result
        self._save_btn.setEnabled(True)
        self._refresh_plot()

        f0 = result.f0_hz
        if f0 > 0:
            harmonics = [f0 * n for n in range(1, 6) if f0 * n < 8000]
            in_ssb = [h for h in harmonics if 300 <= h <= 2700]
            note = (
                f"F₀ = {result.f0_label}  ·  "
                f"Harmonics in SSB passband (300–2700 Hz): "
                f"{', '.join(f'{h:.0f} Hz' for h in in_ssb)}"
            )
        else:
            note = ""
        self.f0_strip.setText(note)

    # ── Private ─────────────────────────────────────────────────────────────

    def _on_save_standard(self):
        if self._result is None:
            return
        name, ok = QInputDialog.getText(
            self, "Save as Standard",
            "Name for this reference standard\n"
            "(e.g. \"DX Standard – RadioSport HS-2\"):"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        desc, ok2 = QInputDialog.getText(
            self, "Save as Standard",
            "Short description (operator, headset, date):"
        )
        if not ok2:
            desc = ""
        storage.standards_store.save(
            name, desc.strip(),
            self._result.freqs, self._result.ltass_db
        )
        QMessageBox.information(
            self, "Virga",
            f"Standard \"{name}\" saved.\n"
            "It will appear as an EQ target in the Export tab."
        )
        self._refresh_plot()

    def _refresh_plot(self):
        if self._result is None:
            return

        pw = self.plot_widget
        pw.clear()
        result = self._result
        freqs = result.freqs
        mask = (freqs >= 80) & (freqs <= 12000)
        f = freqs[mask]

        DASH = Qt.PenStyle.DashLine
        DOT  = Qt.PenStyle.DotLine

        # 1. Measured LTASS — Savitzky-Golay smoothed
        raw = result.ltass_db[mask]
        win = min(len(raw) | 1, 51)
        if win % 2 == 0:
            win -= 1
        smoothed = savgol_filter(raw, window_length=win, polyorder=3)
        pw.plot(f, smoothed,
                pen=pg.mkPen('#c9d1d9', width=2),
                name="Your voice (measured)")

        # 2. Bell Labs LTASS reference
        if self._cb_ref.isChecked():
            pw.plot(f, get_ltass_at(f),
                    pen=pg.mkPen('#888888', width=1.5, style=DASH),
                    name="Bell Labs LTASS")

        # 3. Ragchew target
        if self._cb_ragchew.isChecked():
            pw.plot(f, RAGCHEW.at(f),
                    pen=pg.mkPen('#3fb950', width=1.5, style=DOT),
                    name="Ragchew target")

        # 4. Contest target
        if self._cb_contest.isChecked():
            pw.plot(f, CONTEST.at(f),
                    pen=pg.mkPen('#f0a500', width=1.5, style=DOT),
                    name="Contest target")

        # 5. Saved standards
        if self._cb_standards.isChecked():
            standards = storage.standards_store.load_all()
            for i, std in enumerate(standards):
                colour = _STANDARD_COLOURS[i % len(_STANDARD_COLOURS)]
                std_f = std.at(f)
                pw.plot(f, std_f,
                        pen=pg.mkPen(colour, width=2, style=DASH),
                        name=std.name)

        # 6. Corrected voice
        if self._cb_corrected.isChecked():
            gains = solve(result.freqs, result.ltass_db, RAGCHEW,
                          result.f0_hz, SMARTSDR_TX_EQ)
            correction = np.interp(f,
                                   np.array(list(gains.keys()), dtype=float),
                                   np.array(list(gains.values())))
            corrected = savgol_filter(result.ltass_db[mask] + correction,
                                      window_length=win, polyorder=3)
            pw.plot(f, corrected,
                    pen=pg.mkPen('#58a6ff', width=2),
                    name="Your voice (corrected)")

        # 7. F0 harmonic markers
        if self._cb_f0.isChecked() and result.f0_hz > 0:
            for n, harmonic in enumerate(result.f0_hz * np.arange(1, 8), start=1):
                if harmonic > 12000:
                    break
                line = pg.InfiniteLine(
                    pos=np.log10(harmonic), angle=90,
                    pen=pg.mkPen('#f85149', width=1, style=DASH),
                )
                if n <= 4:
                    line.label = pg.InfLineLabel(line, text=f"H{n}",
                                                 position=0.9, color='#f85149')
                pw.addItem(line)

        # SmartSDR band markers
        for band in SMARTSDR_BANDS:
            if 80 <= band <= 12000:
                pw.addItem(pg.InfiniteLine(
                    pos=np.log10(float(band)), angle=90,
                    pen=pg.mkPen('#30363d', width=1)
                ))

        pw.enableAutoRange(axis='y')
