from __future__ import annotations

from collections import defaultdict

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from autoshelf.config import AppConfig
from autoshelf.gui.design import LIGHT
from autoshelf.gui.widgets import GhostButton, PrimaryButton, SecondaryButton
from autoshelf.i18n import t
from autoshelf.planner.models import PlannerAssignment
from autoshelf.quarantine import (
    clear_quarantine_assignments,
    quarantine_paths,
    replan_quarantine_assignments,
)

from .review_models import PreviewItem, build_preview_items, summarize_actions
from .review_tree import HINT_ROLE, SOURCE_ROLE, STATUS_ROLE, SUMMARY_ROLE, ReviewTreeWidget


class ReviewScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.preview_items: dict[str, PreviewItem] = {}
        self.loaded_assignments: list[PlannerAssignment] = []
        self.manual_reassignment_baselines: dict[str, list[str]] = {}
        self.active_config = AppConfig()

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.quarantine_label = QLabel("")
        self.quarantine_label.setWordWrap(True)
        layout.addWidget(self.quarantine_label)

        splitter = QSplitter()
        self.current_tree = QTreeWidget()
        self.current_tree.setAccessibleName("현재 트리")
        self.current_tree.setHeaderLabels(["Current Tree"])
        self.proposed_tree = ReviewTreeWidget()
        self.proposed_tree.setAccessibleName("제안 트리")
        self.proposed_tree.setHeaderLabels(["Proposed Tree", "Action", "Preview"])
        self.proposed_tree.setDragDropMode(QTreeWidget.InternalMove)
        self.proposed_tree.setEditTriggers(QTreeWidget.DoubleClicked | QTreeWidget.EditKeyPressed)
        self.proposed_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.proposed_tree.itemSelectionChanged.connect(self._update_hint_panel)
        self.proposed_tree.file_reassigned.connect(self.apply_manual_reassignment)
        self.proposed_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.proposed_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.proposed_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        splitter.addWidget(self.current_tree)
        splitter.addWidget(self.proposed_tree)
        layout.addWidget(splitter)

        self.assignment_table = QTableWidget(0, 6)
        self.assignment_table.setAccessibleName("파일별 계획 표")
        self.assignment_table.setHorizontalHeaderLabels(
            ["Path", "Action", "Target", "Confidence", "Why this folder?", "Also relevant"]
        )
        self.title_label = QLabel("")
        layout.addWidget(self.title_label)
        layout.addWidget(self.assignment_table)

        self.selection_summary = QTextEdit()
        self.selection_summary.setReadOnly(True)
        layout.addWidget(self.selection_summary)
        self.folder_hint = QTextEdit()
        self.folder_hint.setReadOnly(True)
        layout.addWidget(self.folder_hint)

        button_row = QHBoxLayout()
        self.rerun_button: QPushButton = SecondaryButton("")
        self.replan_quarantine_button: QPushButton = SecondaryButton("")
        self.clear_quarantine_button: QPushButton = GhostButton("")
        self.approve_button: QPushButton = PrimaryButton("")
        button_row.addWidget(self.rerun_button)
        button_row.addWidget(self.replan_quarantine_button)
        button_row.addWidget(self.clear_quarantine_button)
        button_row.addWidget(self.approve_button)
        layout.addLayout(button_row)
        self.replan_quarantine_button.clicked.connect(self.replan_selected_quarantine)
        self.clear_quarantine_button.clicked.connect(self.clear_selected_quarantine)
        self.apply_config()
        self.load_preview(self._demo_assignments())

    def load_preview(self, assignments: list[PlannerAssignment]) -> None:
        self.loaded_assignments = list(assignments)
        preview_items = build_preview_items(
            assignments,
            manual_baselines=self.manual_reassignment_baselines,
        )
        self.preview_items = {item.destination_path: item for item in preview_items}
        self.current_tree.clear()
        self.proposed_tree.clear()
        self.assignment_table.setRowCount(0)
        self.selection_summary.clear()

        self._populate_current_tree(preview_items)
        self._populate_proposed_tree(preview_items)
        self._populate_assignment_table(preview_items)
        self._update_summary(preview_items)
        self._refresh_quarantine_controls()
        self.current_tree.expandAll()
        self.proposed_tree.expandAll()
        self.assignment_table.resizeColumnsToContents()
        if self.proposed_tree.topLevelItemCount():
            first_item = self.proposed_tree.topLevelItem(0)
            self.proposed_tree.setCurrentItem(first_item)
            self._update_hint_panel()

    def _populate_current_tree(self, items: list[PreviewItem]) -> None:
        root_items: dict[str, QTreeWidgetItem] = {}
        for item in items:
            cursor = self.current_tree.invisibleRootItem()
            for part in item.source_parts:
                parent_key = self._node_path(cursor)
                key = f"{parent_key}/{part}"
                node = root_items.get(key)
                if node is None:
                    node = QTreeWidgetItem([part])
                    cursor.addChild(node)
                    root_items[key] = node
                cursor = node

    def _populate_proposed_tree(self, items: list[PreviewItem]) -> None:
        root_items: dict[str, QTreeWidgetItem] = {}
        folder_hints = self._folder_hints(items)
        for item in items:
            cursor = self.proposed_tree.invisibleRootItem()
            for depth, part in enumerate(item.target_parts):
                parent_key = self._node_path(cursor)
                key = f"{parent_key}/{part}"
                node = root_items.get(key)
                if node is None:
                    preview = ""
                    action_label = ""
                    if depth == len(item.target_parts) - 1:
                        preview = self._preview_message(item)
                        action_label = self._action_label(item.display_action)
                    node = QTreeWidgetItem([part, action_label, preview])
                    cursor.addChild(node)
                    root_items[key] = node
                    if depth < len(item.target_parts) - 1:
                        hint_key = tuple(item.target_parts[: depth + 1])
                        node.setData(0, HINT_ROLE, folder_hints.get(hint_key, ""))
                        self.proposed_tree.mark_folder_item(node)
                cursor = node
            cursor.setData(0, STATUS_ROLE, item.display_action)
            cursor.setData(0, HINT_ROLE, self._item_hint(item))
            cursor.setData(0, SUMMARY_ROLE, self._selection_summary(item))
            cursor.setData(0, SOURCE_ROLE, item.source_path)
            self.proposed_tree.mark_file_item(cursor)
            self._apply_status_style(cursor, item.display_action)

    def _populate_assignment_table(self, items: list[PreviewItem]) -> None:
        for row, item in enumerate(items):
            self.assignment_table.insertRow(row)
            values = [
                item.source_path,
                self._action_label(item.display_action),
                item.target_folder,
                f"{item.confidence:.2f}",
                item.rationale or "No rationale recorded",
                ", ".join("/".join(parts) for parts in item.also_relevant) or "—",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                self.assignment_table.setItem(row, column, cell)
            action_brush = QBrush(self._status_color(item.display_action))
            self.assignment_table.item(row, 1).setForeground(action_brush)

    def _update_hint_panel(self) -> None:
        item = self.proposed_tree.currentItem()
        if item is None:
            self.folder_hint.clear()
            self.selection_summary.clear()
            return
        hint = item.data(0, HINT_ROLE) or t("review.hint_placeholder")
        summary = item.data(0, SUMMARY_ROLE) or t(
            "review.selection_placeholder", self.active_config
        )
        self.selection_summary.setPlainText(str(summary))
        self.folder_hint.setPlainText(str(hint))

    def _folder_hints(self, items: list[PreviewItem]) -> dict[tuple[str, ...], str]:
        grouped: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for item in items:
            rationale = item.rationale or (
                f"Receives {item.filename} from {item.source_folder or '.'}."
            )
            for depth in range(1, len(item.target_parts)):
                grouped[tuple(item.target_parts[:depth])].append(rationale)
            if item.operator_modified and item.target_parts[:-1]:
                grouped[tuple(item.target_parts[:-1])].append(
                    f"Operator reassigned {item.filename} from {item.baseline_destination_path}."
                )
        return {
            key: "\n".join(dict.fromkeys(lines))
            for key, lines in grouped.items()
        }

    def _item_hint(self, item: PreviewItem) -> str:
        rationale = item.rationale or "No rationale recorded."
        related = ", ".join("/".join(parts) for parts in item.also_relevant) or "none"
        quarantine_note = (
            "This item is quarantined because the planner confidence was too low.\n"
            if item.is_quarantined
            else ""
        )
        operator_note = (
            f"Operator override: originally planned for {item.baseline_destination_path}\n"
            if item.operator_modified
            else ""
        )
        return (
            f"Action: {self._action_label(item.display_action)}\n"
            f"{quarantine_note}"
            f"{operator_note}"
            f"Source folder: {item.source_folder or '.'}\n"
            f"Target folder: {item.target_folder or '.'}\n"
            f"Why this folder: {rationale}\n"
            f"Also relevant: {related}"
        )

    def _preview_message(self, item: PreviewItem) -> str:
        if item.operator_modified:
            return t(
                "review.preview_reassigned",
                self.active_config,
                source=item.baseline_destination_path or ".",
                target=item.destination_path,
            )
        if item.action == "moved":
            return t(
                "review.preview_move",
                self.active_config,
                source=item.source_folder or ".",
                target=item.target_folder or ".",
            )
        if item.action == "kept":
            return t("review.preview_kept", self.active_config)
        if item.action == "quarantine":
            return t("review.preview_quarantine", self.active_config)
        return t("review.preview_placed", self.active_config)

    def _apply_status_style(self, item: QTreeWidgetItem, status: str) -> None:
        brush = QBrush(self._status_color(status))
        item.setForeground(0, brush)
        item.setForeground(1, brush)
        item.setForeground(2, brush)

    def _status_color(self, status: str) -> QColor:
        colors = {
            "moved": QColor(LIGHT.success),
            "kept": QColor(LIGHT.text_muted),
            "placed": QColor(LIGHT.accent),
            "quarantine": QColor(LIGHT.warning),
            "reassigned": QColor(LIGHT.warning),
        }
        return colors.get(status, QColor(LIGHT.text))

    def _action_label(self, action: str) -> str:
        labels = {
            "moved": t("review.action_moved", self.active_config),
            "kept": t("review.action_kept", self.active_config),
            "placed": t("review.action_placed", self.active_config),
            "quarantine": t("review.action_quarantine", self.active_config),
            "reassigned": t("review.action_reassigned", self.active_config),
        }
        return labels.get(action, action)

    def _selection_summary(self, item: PreviewItem) -> str:
        related = ", ".join("/".join(parts) for parts in item.also_relevant) or "none"
        rationale = item.rationale or "No rationale recorded."
        quarantine_note = (
            "Quarantine reason: planner confidence was below the safe apply threshold.\n"
            if item.is_quarantined
            else ""
        )
        operator_note = (
            f"Operator override from: {item.baseline_destination_path}\n"
            if item.operator_modified
            else ""
        )
        return (
            f"{self._action_label(item.display_action)}\n"
            f"{quarantine_note}"
            f"{operator_note}"
            f"Before: {item.source_display}\n"
            f"After: {item.destination_path}\n"
            f"Confidence: {item.confidence:.2f}\n"
            f"Why this folder: {rationale}\n"
            f"Also relevant: {related}"
        )

    def _update_summary(self, items: list[PreviewItem]) -> None:
        counts = summarize_actions(items)
        average_confidence = (
            sum(item.confidence for item in items) / len(items) if items else 0.0
        )
        self.summary_label.setText(
            t(
                "review.summary",
                self.active_config,
                total=len(items),
                moved=counts["moved"],
                kept=counts["kept"],
                placed=counts["placed"],
                quarantine=counts["quarantine"],
                reassigned=counts["reassigned"],
                confidence=f"{average_confidence:.2f}",
            )
        )

    def apply_manual_reassignment(self, source_path: str, target_dir: list[str]) -> None:
        for index, assignment in enumerate(self.loaded_assignments):
            if assignment.path != source_path:
                continue
            if assignment.primary_dir == target_dir:
                return
            self.manual_reassignment_baselines.setdefault(source_path, list(assignment.primary_dir))
            self.loaded_assignments[index] = assignment.model_copy(
                update={"primary_dir": list(target_dir)}
            )
            self.load_preview(self.loaded_assignments)
            self.proposed_tree.select_source_path(source_path)
            self._update_hint_panel()
            return

    def replan_selected_quarantine(self) -> None:
        selected_paths = self._selected_quarantine_paths()
        self._clear_manual_reassignments(selected_paths)
        updated = replan_quarantine_assignments(
            self.loaded_assignments,
            selected_paths=selected_paths,
        )
        self.load_preview(updated)

    def clear_selected_quarantine(self) -> None:
        selected_paths = self._selected_quarantine_paths()
        self._clear_manual_reassignments(selected_paths)
        updated = clear_quarantine_assignments(
            self.loaded_assignments,
            selected_paths=selected_paths,
        )
        self.load_preview(updated)

    def _refresh_quarantine_controls(self) -> None:
        quarantined = quarantine_paths(self.loaded_assignments)
        count = len(quarantined)
        enabled = count > 0
        self.replan_quarantine_button.setEnabled(enabled)
        self.clear_quarantine_button.setEnabled(enabled)
        if enabled:
            self.quarantine_label.setText(
                t("review.quarantine_summary", self.active_config, count=count)
            )
            return
        self.quarantine_label.setText(t("review.quarantine_empty", self.active_config))

    def _selected_quarantine_paths(self) -> set[str]:
        quarantined = quarantine_paths(self.loaded_assignments)
        current = self.proposed_tree.currentItem()
        if current is None:
            return quarantined
        source_path = current.data(0, SOURCE_ROLE)
        if isinstance(source_path, str) and source_path in quarantined:
            return {source_path}
        return quarantined

    def _node_path(self, item: QTreeWidgetItem) -> str:
        parts: list[str] = []
        cursor = item
        while cursor and cursor.parent() is not None:
            parts.append(cursor.text(0))
            cursor = cursor.parent()
        return "/".join(reversed(parts))

    def _clear_manual_reassignments(self, selected_paths: set[str]) -> None:
        for path in selected_paths:
            self.manual_reassignment_baselines.pop(path, None)

    def _demo_assignments(self) -> list[PlannerAssignment]:
        return [
            PlannerAssignment(
                path="Inbox/draft.txt",
                primary_dir=["Documents", "Writing"],
                also_relevant=[["Archive", "Drafts"]],
                summary="Draft notes grouped with other working documents for faster review.",
                confidence=0.90,
            ),
            PlannerAssignment(
                path="Downloads/invoice.pdf",
                primary_dir=["Finance", "2026"],
                also_relevant=[["Documents", "Reference"]],
                summary=(
                    "Invoices stay under Finance by year so monthly statements remain together."
                ),
                confidence=0.94,
            ),
            PlannerAssignment(
                path="incoming/client-a/proposal.txt",
                primary_dir=[".autoshelf", "quarantine"],
                summary="Low-confidence draft kept in quarantine until an operator reviews it.",
                confidence=0.22,
                fallback=True,
            ),
        ]

    def apply_config(self, config: AppConfig | None = None) -> None:
        self.active_config = config or self.active_config
        self.title_label.setText(t("review.title", config))
        self.selection_summary.setPlaceholderText(t("review.selection_placeholder", config))
        self.folder_hint.setPlaceholderText(t("review.hint_placeholder", config))
        self.rerun_button.setText(t("review.rerun", config))
        self.replan_quarantine_button.setText(t("review.quarantine_replan", config))
        self.clear_quarantine_button.setText(t("review.quarantine_clear", config))
        self.approve_button.setText(f"{t('button.apply', config)} →")
        if self.loaded_assignments:
            self.load_preview(self.loaded_assignments)
        else:
            self.summary_label.setText(t("review.summary_empty", config))
            self.quarantine_label.setText(t("review.quarantine_empty", config))
