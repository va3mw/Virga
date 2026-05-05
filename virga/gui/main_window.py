from __future__ import annotations

"""Main application window."""

import numpy as np
from PySide6.QtCore import Qt, Signal
from ..audio.analyzer import AnalysisResult
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QTabWidget, QFrame, QDialog, QLineEdit, QFormLayout,
    QDialogButtonBox, QMessageBox, QSizePolicy,
)

from .. import storage
from ..version import __version__
from ..audio.analyzer import AnalysisResult
from ..audio import analyzer as _analyzer
from .calibration_page import CalibrationPage
from .spectrum_view import SpectrumView
from .export_page import ExportPage

STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0d1117;
    color: #c9d1d9;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QFrame#sidebar {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}
QLabel#logo {
    color: #58a6ff;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 4px;
    padding: 16px 0px 4px 0px;
}
QLabel#tagline {
    color: #8b949e;
    font-size: 10px;
    letter-spacing: 1px;
    padding-bottom: 12px;
}
QLabel#section_header {
    color: #8b949e;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    padding: 8px 0px 4px 0px;
}
QListWidget {
    background-color: #161b22;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 8px 12px;
    border-radius: 4px;
    margin: 1px 4px;
}
QListWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background-color: #21262d;
}
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton:hover { background-color: #30363d; }
QPushButton:pressed { background-color: #161b22; }
QPushButton#primary {
    background-color: #1f6feb;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#primary:hover { background-color: #388bfd; }
QPushButton#danger {
    background-color: #da3633;
    color: #ffffff;
    border: none;
}
QPushButton#danger:hover { background-color: #f85149; }
QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 6px;
    background-color: #0d1117;
}
QTabBar::tab {
    background: #161b22;
    color: #8b949e;
    padding: 8px 20px;
    border: 1px solid #30363d;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #0d1117;
    color: #c9d1d9;
    border-bottom: 2px solid #1f6feb;
}
QLabel#callsign_header {
    color: #58a6ff;
    font-size: 20px;
    font-weight: bold;
    letter-spacing: 2px;
}
QLabel#profile_meta {
    color: #8b949e;
    font-size: 11px;
}
QLineEdit {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 4px;
    color: #c9d1d9;
    padding: 6px 10px;
}
QLineEdit:focus { border-color: #1f6feb; }
"""


class NewProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Operator Profile")
        self.setFixedWidth(340)
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self.callsign_edit = QLineEdit()
        self.callsign_edit.setPlaceholderText("e.g. VA3MW")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Mike")

        layout.addRow("Callsign:", self.callsign_edit)
        layout.addRow("Name:", self.name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate(self):
        cs = self.callsign_edit.text().strip().upper()
        if not cs:
            QMessageBox.warning(self, "Virga", "Please enter a callsign.")
            return
        self.callsign_edit.setText(cs)
        self.accept()

    @property
    def callsign(self) -> str:
        return self.callsign_edit.text().strip().upper()

    @property
    def name(self) -> str:
        return self.name_edit.text().strip() or self.callsign


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Virga {__version__} — SSB Voice Equaliser")
        self.resize(1100, 720)
        self.setStyleSheet(STYLESHEET)

        self._current_callsign: str | None = None
        self._analysis: AnalysisResult | None = None

        self._build_ui()
        self._refresh_profile_list()

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_main_area(), 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 0, 12, 12)
        layout.setSpacing(4)

        logo = QLabel("VIRGA")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        tagline = QLabel("SSB VOICE EQ")
        tagline.setObjectName("tagline")
        tagline.setAlignment(Qt.AlignCenter)
        layout.addWidget(tagline)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #30363d;")
        layout.addWidget(sep)

        ops_label = QLabel("OPERATORS")
        ops_label.setObjectName("section_header")
        layout.addWidget(ops_label)

        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._on_profile_selected)
        layout.addWidget(self.profile_list, 1)

        add_btn = QPushButton("+ New Operator")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._on_new_profile)
        layout.addWidget(add_btn)

        del_btn = QPushButton("Remove")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._on_delete_profile)
        layout.addWidget(del_btn)

        return sidebar

    def _build_main_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Profile header
        header_row = QHBoxLayout()
        self.callsign_label = QLabel("— Select or create an operator —")
        self.callsign_label.setObjectName("callsign_header")
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("profile_meta")
        header_row.addWidget(self.callsign_label)
        header_row.addStretch()
        header_row.addWidget(self.meta_label)
        layout.addLayout(header_row)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setEnabled(False)
        layout.addWidget(self.tabs, 1)

        # Tab: Calibrate
        self.calibration_page = CalibrationPage()
        self.calibration_page.recording_done.connect(self._on_recording_done)
        self.tabs.addTab(self.calibration_page, "  Calibrate  ")

        # Tab: Results
        self.spectrum_view = SpectrumView()
        self.tabs.addTab(self.spectrum_view, "  Results  ")

        # Tab: Export
        self.export_page = ExportPage()
        self.tabs.addTab(self.export_page, "  Export (SmartSDR)  ")

        return container

    # ── Profile management ───────────────────────────────────────────────────

    def _refresh_profile_list(self):
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for p in storage.profile_store.list_profiles():
            item = QListWidgetItem(p["callsign"])
            item.setData(Qt.UserRole, p["callsign"])
            self.profile_list.addItem(item)
        self.profile_list.blockSignals(False)

    def _on_new_profile(self):
        dlg = NewProfileDialog(self)
        dlg.setStyleSheet(self.styleSheet())
        if dlg.exec() != QDialog.Accepted:
            return
        cs = dlg.callsign
        if storage.profile_store.load(cs):
            QMessageBox.information(self, "Virga", f"{cs} already exists.")
            return
        storage.profile_store.create(cs, dlg.name)
        self._refresh_profile_list()
        # Select the new item
        for i in range(self.profile_list.count()):
            if self.profile_list.item(i).data(Qt.UserRole) == cs:
                self.profile_list.setCurrentRow(i)
                break

    def _on_delete_profile(self):
        if not self._current_callsign:
            return
        ans = QMessageBox.question(
            self, "Virga",
            f"Remove profile for {self._current_callsign}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ans != QMessageBox.Yes:
            return
        storage.profile_store.delete(self._current_callsign)
        self._current_callsign = None
        self._analysis = None
        self.tabs.setEnabled(False)
        self.callsign_label.setText("— Select or create an operator —")
        self.meta_label.setText("")
        self._refresh_profile_list()

    def _on_profile_selected(self, current: QListWidgetItem, _previous):
        if current is None:
            return
        cs = current.data(Qt.UserRole)
        self._load_profile(cs)

    def _load_profile(self, callsign: str):
        profile = storage.profile_store.load(callsign)
        if not profile:
            return
        self._current_callsign = callsign
        self.callsign_label.setText(callsign)

        name = profile.get("name", "")
        created = profile.get("created", "")[:10]
        self.meta_label.setText(f"{name}  ·  since {created}" if name != callsign else f"since {created}")

        self.calibration_page.set_callsign(callsign)
        self.tabs.setEnabled(True)

        # Restore previous results if LTASS data is stored
        analysis = profile.get("analysis") or {}
        if analysis.get("freqs") and analysis.get("ltass_db"):
            result = AnalysisResult(
                freqs=np.array(analysis["freqs"]),
                ltass_db=np.array(analysis["ltass_db"]),
                f0_hz=analysis.get("f0_hz", 0.0),
                f0_label=analysis.get("f0_label", ""),
                sample_rate=48_000,
            )
            self.spectrum_view.show_plot(result)
            self.export_page.set_results(
                callsign=callsign,
                result=result,
                f0_label=analysis.get("f0_label", ""),
            )
            self.tabs.setTabEnabled(1, True)
            self.tabs.setTabEnabled(2, True)
        else:
            self.tabs.setTabEnabled(1, False)
            self.tabs.setTabEnabled(2, False)

    # ── Recording result ────────────────────────────────────────────────────

    def _on_recording_done(self, result: AnalysisResult, raw_audio, sample_rate: int):
        if not self._current_callsign:
            return
        self._analysis = result

        storage.profile_store.update_analysis(
            self._current_callsign, result.f0_hz, result.f0_label,
            freqs=result.freqs, ltass_db=result.ltass_db,
        )

        self.spectrum_view.show_plot(result)
        self.export_page.set_results(
            callsign=self._current_callsign,
            result=result,
            raw_audio=raw_audio,
            sample_rate=sample_rate,
        )
        self.tabs.setTabEnabled(1, True)
        self.tabs.setTabEnabled(2, True)
        self.tabs.setCurrentIndex(1)
