from __future__ import annotations

from collections import Counter
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
from autoshelf.gui.widgets import Banner, Card, Dropzone, PrimaryButton, SecondaryButton
from autoshelf.gui.widgets.titlebar import TitleBar
from autoshelf.i18n import t
from autoshelf.scanner import scan_directory


class ScanWorker(QObject):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, root: str, config: AppConfig | None = None) -> None:
        super().__init__()
        self._root = root
        self._config = config or AppConfig()

    def run(self) -> None:
        try:
            root_path = Path(self._root).expanduser()
            if not self._root or not root_path.exists() or not root_path.is_dir():
                self.finished.emit({"files": 0, "size_bytes": 0, "extensions": {}})
                return
            files = scan_directory(root_path.resolve(), self._config)
            extensions: Counter[str] = Counter()
            total_size = 0
            for item in files:
                ext = item.extension or "(none)"
                extensions[ext] += 1
                total_size += item.size_bytes
            self.finished.emit(
                {
                    "files": len(files),
                    "size_bytes": total_size,
                    "extensions": dict(extensions.most_common()),
                    "root": str(root_path.resolve()),
                }
            )
        except Exception as exc:
            logger.exception("scan worker failed")
            self.failed.emit(str(exc))
            self.finished.emit({"files": 0, "size_bytes": 0, "extensions": {}, "error": str(exc)})


class HomeScreen(QWidget):
    scan_started = Signal(str)
    scan_finished = Signal(str, dict)
    plan_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.thread: QThread | None = None
        self.worker: ScanWorker | None = None
        self.scan_requests = 0
        self.last_scan_root = ""
        self._last_stats: dict = {}
        self.setAcceptDrops(True)
        self.setAccessibleName("홈")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.status_bar = TitleBar()
        layout.addWidget(self.status_bar)
        self.banner = Banner(
            "info",
            "100% 온디바이스",
            "선택한 폴더는 이 컴퓨터 안에서만 분석됩니다.",
        )
        layout.addWidget(self.banner)

        self.dropzone = Dropzone()
        self.dropzone.folderSelected.connect(self._select_folder)
        layout.addWidget(self.dropzone, stretch=6)

        compact = QHBoxLayout()
        self.title_label = QLabel("")
        self.root_input = QLineEdit()
        self.root_input.setPlaceholderText("/path/to/folder")
        self.root_input.setAccessibleName("정리할 폴더 경로")
        self.browse_button = SecondaryButton("", "folder")
        self.browse_button.clicked.connect(self._browse_folder)
        compact.addWidget(self.title_label)
        compact.addWidget(self.root_input, stretch=1)
        compact.addWidget(self.browse_button)
        layout.addLayout(compact)

        self.recent_card = Card()
        self.recent_card.body.addWidget(QLabel("최근 폴더"))
        self.recent_grid = QGridLayout()
        self.recent_card.body.addLayout(self.recent_grid)
        self.recent_list = QListWidget()
        self.recent_list.setAccessibleName("최근 폴더 목록")
        self.recent_list.addItem("Recent folders")
        self.recent_card.body.addWidget(self.recent_list)
        layout.addWidget(self.recent_card)

        self.stats_view = QTextEdit()
        self.stats_view.setReadOnly(True)
        self.stats_view.setAccessibleName("스캔 통계")
        self.stats_view.setPlainText("스캔을 시작하면 확장자 분포와 진행률이 표시됩니다.")
        layout.addWidget(self.stats_view)

        self.plan_button = PrimaryButton("")
        self.plan_button.setEnabled(False)
        self.plan_button.clicked.connect(self._on_plan_clicked)
        layout.addWidget(self.plan_button)
        self.apply_config()

    def _select_folder(self, path: Path) -> None:
        self.root_input.setText(str(path))
        self.start_scan(path)

    def _browse_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "정리할 폴더 선택")
        if selected:
            self._select_folder(Path(selected))

    def start_scan(self, root: Path | None = None) -> None:
        if self.thread is not None and self.thread.isRunning():
            logger.debug("Ignoring scan request because a scan is already running")
            return
        self.scan_requests += 1
        if root is not None:
            self.root_input.setText(str(root))
        self.last_scan_root = self.root_input.text().strip()
        self.plan_button.setEnabled(False)
        self.stats_view.setPlainText(
            f"스캔 중... ({self.last_scan_root or '경로 없음'})\n"
            "파일 메타데이터를 수집하고 있습니다."
        )
        self.thread = QThread(self)
        self.worker = ScanWorker(self.last_scan_root)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._render_stats)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.scan_started.emit(self.last_scan_root)
        logger.debug(
            "Starting GUI scan request {} for root {}",
            self.scan_requests,
            self.last_scan_root or ".",
        )
        self.thread.start()

    def _on_plan_clicked(self) -> None:
        root = self.last_scan_root or self.root_input.text().strip()
        logger.debug("Plan button clicked (root={})", root)
        self.plan_button.setEnabled(False)
        self.plan_button.setText("계획 화면으로 이동 중...")
        self.stats_view.append(f"\n→ 계획 세우기 요청됨 ({root})")
        self.plan_requested.emit(root)

    def _render_stats(self, stats: dict) -> None:
        self._last_stats = stats
        extensions = stats.get("extensions", {})
        histogram = "\n".join(f"{suffix:>6}  {count:>4}" for suffix, count in extensions.items())
        root_line = stats.get("root") or self.last_scan_root or "(경로 없음)"
        error = stats.get("error")
        body = "경로 {root}\n파일 {files}개\n크기 {size:,} bytes\n\n{histogram}".format(
            root=root_line,
            files=stats.get("files", 0),
            size=stats.get("size_bytes", 0),
            histogram=histogram or "(확장자 집계 없음)",
        )
        if error:
            body = f"⚠ 스캔 중 오류: {error}\n\n" + body
        self.stats_view.setPlainText(body)
        self.plan_button.setEnabled(stats.get("files", 0) > 0)
        self.scan_finished.emit(self.last_scan_root, stats)
        logger.debug("Rendered GUI scan stats (files={})", stats.get("files", 0))

    def _cleanup_thread(self) -> None:
        logger.debug("Cleaning up GUI scan worker thread")
        if self.worker is not None:
            self.worker.deleteLater()
        if self.thread is not None:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.banner.set_message("100% 온디바이스", t("home.banner.first_run", config), "info")
        self.title_label.setText(t("home.title", config))
        self.browse_button.setText(t("home.browse", config))
        self.plan_button.setText(f"{t('button.plan', config)} 세우기 →")
