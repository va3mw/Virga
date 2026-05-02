from __future__ import annotations

"""
Spectrum results view — shows measured LTASS, Bell Labs reference,
ragchew and contest target curves, F0 marker and harmonics.
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
)

from ..audio.analyzer import AnalysisResult
from ..dsp.ltass_reference import get_ltass_at
from ..dsp.profiles import RAGCHEW, CONTEST
from ..dsp.eq_solver import SMARTSDR_BANDS

pg.setConfigOption('background', '#0d1117')
pg.setConfigOption('foreground', '#c9d1d9')
pg.setConfigOption('antialias', True)


class SpectrumView(QWidget):
    def __init__(self):
        super().__init__()
        self._result: AnalysisResult | None = None
        self._ragchew_gains: dict = {}
        self._contest_gains: dict = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Toggles ──
        top = QHBoxLayout()
        top.setContentsMargins(8, 8, 8, 0)
        top.addStretch()

        self._cb_ref      = self._make_checkbox("Bell Labs LTASS",    "#888888")
        self._cb_ragchew  = self._make_checkbox("Ragchew target",     "#3fb950")
        self._cb_contest  = self._make_checkbox("Contest target",     "#f0a500")
        self._cb_corrected = self._make_checkbox("Your corrected voice", "#58a6ff")
        self._cb_f0       = self._make_checkbox("F₀ harmonics",       "#f85149")

        for cb in (self._cb_ref, self._cb_ragchew, self._cb_contest,
                   self._cb_corrected, self._cb_f0):
            cb.stateChanged.connect(self._refresh_plot)
            top.addWidget(cb)

        layout.addLayout(top)

        # ── Plot widget — named plot_widget to avoid clash with show_plot() method ──
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel('left', 'Level (dB, relative)')
        self.plot_widget.setLabel('bottom', 'Frequency (Hz)')
        self.plot_widget.setLogMode(x=True, y=False)
        self.plot_widget.setXRange(np.log10(80), np.log10(12000))
        self.plot_widget.setYRange(-35, 20)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.getAxis('bottom').setTicks(self._freq_ticks())
        self.plot_widget.addLegend()

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

    def show_plot(self, result: AnalysisResult,
                  ragchew_gains: dict, contest_gains: dict):
        self._result = result
        self._ragchew_gains = ragchew_gains
        self._contest_gains = contest_gains
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

    def _refresh_plot(self):
        if self._result is None:
            return

        pw = self.plot_widget
        pw.clear()
        result = self._result
        freqs = result.freqs
        mask = (freqs >= 80) & (freqs <= 12000)
        f = freqs[mask]
        log_f = np.log10(f)

        # 1. Measured LTASS (user)
        pw.plot(log_f, result.ltass_db[mask],
                pen=pg.mkPen('#c9d1d9', width=2),
                name="Your voice (measured)")

        # 2. Bell Labs LTASS reference
        if self._cb_ref.isChecked():
            pw.plot(log_f, get_ltass_at(f),
                    pen=pg.mkPen('#888888', width=1.5, style=Qt.DashLine),
                    name="Bell Labs LTASS")

        # 3. Ragchew target
        if self._cb_ragchew.isChecked():
            pw.plot(log_f, RAGCHEW.at(f),
                    pen=pg.mkPen('#3fb950', width=1.5, style=Qt.DotLine),
                    name="Ragchew target")

        # 4. Contest target
        if self._cb_contest.isChecked():
            pw.plot(log_f, CONTEST.at(f),
                    pen=pg.mkPen('#f0a500', width=1.5, style=Qt.DotLine),
                    name="Contest target")

        # 5. Corrected voice (measured + ragchew correction applied)
        if self._cb_corrected.isChecked() and self._ragchew_gains:
            correction = np.interp(f,
                                   np.array(list(self._ragchew_gains.keys())),
                                   np.array(list(self._ragchew_gains.values())))
            pw.plot(log_f, result.ltass_db[mask] + correction,
                    pen=pg.mkPen('#58a6ff', width=2),
                    name="Your voice (corrected)")

        # 6. F0 harmonic markers
        if self._cb_f0.isChecked() and result.f0_hz > 0:
            for n, harmonic in enumerate(result.f0_hz * np.arange(1, 8), start=1):
                if harmonic > 12000:
                    break
                colour = '#f85149' if n == 1 else '#f8514966'
                line = pg.InfiniteLine(
                    pos=np.log10(harmonic),
                    angle=90,
                    pen=pg.mkPen(colour, width=1, style=Qt.DashLine),
                    label=f"H{n}" if n <= 4 else "",
                    labelOpts={'color': '#f85149', 'position': 0.9}
                )
                pw.addItem(line)

        # SmartSDR band markers
        for band in SMARTSDR_BANDS:
            if 80 <= band <= 12000:
                pw.addItem(pg.InfiniteLine(
                    pos=np.log10(band), angle=90,
                    pen=pg.mkPen('#30363d', width=1)
                ))
