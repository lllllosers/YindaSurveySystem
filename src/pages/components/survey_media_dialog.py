from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QUrl,
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from forms.engineering.registry import (
    get_engineering_form_definition,
)
from services.survey_media import (
    MEDIA_ROLES,
    delete_survey_media,
    get_survey_media,
    import_survey_media,
    update_media_metadata,
)


MEDIA_ROLE_LABELS = {
    "overview": "全景",
    "location": "位置",
    "detail": "细部",
    "problem": "问题/隐患",
    "other": "其他",
}

MEDIA_KIND_LABELS = {
    "photo": "照片",
    "video": "视频",
}


def _format_file_size(
    size,
):
    try:
        value = int(size or 0)
    except (
        TypeError,
        ValueError,
    ):
        return ""

    units = (
        "B",
        "KB",
        "MB",
        "GB",
    )

    amount = float(value)

    for unit in units:
        if (
            amount < 1024
            or unit == units[-1]
        ):
            if unit == "B":
                return (
                    f"{int(amount)} {unit}"
                )

            return (
                f"{amount:.1f} {unit}"
            )

        amount /= 1024

    return f"{value} B"


class MediaMetadataDialog(QDialog):
    def __init__(
        self,
        *,
        media,
        evaluation_items,
        parent=None,
    ):
        super().__init__(parent)

        self.media = media
        self.evaluation_items = tuple(
            evaluation_items or ()
        )

        self.setWindowTitle(
            "编辑影像信息"
        )
        self.resize(520, 430)

        self._init_ui()
        self._load_values()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.role_combo = QComboBox()

        for role in MEDIA_ROLES:
            self.role_combo.addItem(
                MEDIA_ROLE_LABELS.get(
                    role,
                    role,
                ),
                role,
            )

        self.part_edit = QLineEdit()

        self.item_combo = QComboBox()
        self.item_combo.addItem(
            "不关联分项评价",
            None,
        )

        for item in self.evaluation_items:
            self.item_combo.addItem(
                (
                    f"{item['category']} / "
                    f"{item['item_name']}"
                ),
                item["item_code"],
            )

        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(
            1,
            9999,
        )

        self.captured_at_edit = QLineEdit()
        self.captured_at_edit.setPlaceholderText(
            "例如：2026-09-17 10:30"
        )

        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setMaximumHeight(
            110
        )

        form.addRow(
            "影像用途：",
            self.role_combo,
        )
        form.addRow(
            "工程部位：",
            self.part_edit,
        )
        form.addRow(
            "关联评价项：",
            self.item_combo,
        )
        form.addRow(
            "影像序号：",
            self.sequence_spin,
        )
        form.addRow(
            "拍摄时间：",
            self.captured_at_edit,
        )
        form.addRow(
            "备注：",
            self.notes_edit,
        )

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            (
                QDialogButtonBox
                .StandardButton
                .Save
            )
            | (
                QDialogButtonBox
                .StandardButton
                .Cancel
            )
        )

        buttons.accepted.connect(
            self.accept
        )
        buttons.rejected.connect(
            self.reject
        )

        layout.addWidget(buttons)

    def _load_values(self):
        role = (
            self.media.get(
                "media_role"
            )
            or "other"
        )

        role_index = (
            self.role_combo.findData(
                role
            )
        )

        if role_index >= 0:
            self.role_combo.setCurrentIndex(
                role_index
            )

        self.part_edit.setText(
            str(
                self.media.get(
                    "part_name"
                )
                or ""
            )
        )

        item_code = self.media.get(
            "item_code"
        )

        item_index = (
            self.item_combo.findData(
                item_code
            )
        )

        if item_index >= 0:
            self.item_combo.setCurrentIndex(
                item_index
            )

        self.sequence_spin.setValue(
            int(
                self.media.get(
                    "sequence_no"
                )
                or 1
            )
        )

        self.captured_at_edit.setText(
            str(
                self.media.get(
                    "captured_at"
                )
                or ""
            )
        )

        self.notes_edit.setPlainText(
            str(
                self.media.get(
                    "notes"
                )
                or ""
            )
        )

    def values(self):
        return {
            "media_role": (
                self.role_combo.currentData()
            ),
            "part_name": (
                self.part_edit
                .text()
                .strip()
                or None
            ),
            "item_code": (
                self.item_combo.currentData()
            ),
            "sequence_no": (
                self.sequence_spin.value()
            ),
            "captured_at": (
                self.captured_at_edit
                .text()
                .strip()
                or None
            ),
            "notes": (
                self.notes_edit
                .toPlainText()
                .strip()
                or None
            ),
        }


class SurveyMediaDialog(QDialog):
    """
    一条工程调查记录的影像资料管理。

    第一版提供：
    - 批量导入照片/视频；
    - 编辑用途、部位、评价项、序号、拍摄时间、备注；
    - 使用系统默认程序打开原影像；
    - 删除托管影像。
    """

    def __init__(
        self,
        *,
        survey_record_id,
        form_code,
        record_summary=None,
        parent=None,
    ):
        super().__init__(parent)

        self.survey_record_id = int(
            survey_record_id
        )
        self.form_code = str(
            form_code
        )
        self.record_summary = (
            record_summary
            or {}
        )

        definition = (
            get_engineering_form_definition(
                self.form_code
            )
        )

        self.evaluation_items = (
            tuple(
                definition.evaluation_items
            )
            if definition is not None
            else ()
        )

        self.media_records = []

        self.setWindowTitle(
            "调查影像资料"
        )
        self.resize(
            1160,
            680,
        )

        self._init_ui()
        self.load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel(
            "调查影像资料"
        )
        title.setStyleSheet(
            "font-size: 20px; "
            "font-weight: bold;"
        )
        layout.addWidget(title)

        summary_parts = []

        for label, key in (
            (
                "业务编号",
                "business_code",
            ),
            (
                "工程名称",
                "asset_name",
            ),
            (
                "渠系",
                "canal_name",
            ),
            (
                "工程位置",
                "engineering_position",
            ),
        ):
            value = str(
                self.record_summary.get(
                    key
                )
                or ""
            ).strip()

            if value:
                summary_parts.append(
                    f"{label}：{value}"
                )

        summary_label = QLabel(
            "    ".join(
                summary_parts
            )
            or (
                f"调查记录 ID："
                f"{self.survey_record_id}"
            )
        )
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(
            "color: #52606d;"
        )
        layout.addWidget(
            summary_label
        )

        button_row = QHBoxLayout()

        import_button = QPushButton(
            "批量导入影像"
        )
        import_button.clicked.connect(
            self.import_files
        )

        edit_button = QPushButton(
            "编辑信息"
        )
        edit_button.clicked.connect(
            self.edit_selected
        )

        open_button = QPushButton(
            "打开影像"
        )
        open_button.clicked.connect(
            self.open_selected
        )

        delete_button = QPushButton(
            "删除影像"
        )
        delete_button.clicked.connect(
            self.delete_selected
        )

        refresh_button = QPushButton(
            "刷新"
        )
        refresh_button.clicked.connect(
            self.load_data
        )

        button_row.addWidget(
            import_button
        )
        button_row.addWidget(
            edit_button
        )
        button_row.addWidget(
            open_button
        )
        button_row.addWidget(
            delete_button
        )
        button_row.addWidget(
            refresh_button
        )
        button_row.addStretch()

        layout.addLayout(
            button_row
        )

        self.table = QTableWidget()
        self.table.setColumnCount(9)

        self.table.setHorizontalHeaderLabels(
            [
                "序号",
                "类型",
                "用途",
                "部位",
                "关联评价项",
                "原文件名",
                "文件大小",
                "拍摄时间",
                "备注",
            ]
        )

        self.table.setEditTriggers(
            QAbstractItemView
            .EditTrigger
            .NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QAbstractItemView
            .SelectionBehavior
            .SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView
            .SelectionMode
            .SingleSelection
        )
        self.table.setAlternatingRowColors(
            True
        )
        self.table.cellDoubleClicked.connect(
            lambda row, column:
            self.open_selected()
        )

        widths = [
            70,
            75,
            100,
            120,
            190,
            220,
            95,
            145,
            180,
        ]

        for column, width in enumerate(
            widths
        ):
            self.table.setColumnWidth(
                column,
                width,
            )

        layout.addWidget(
            self.table,
            1,
        )

        self.count_label = QLabel()
        self.count_label.setStyleSheet(
            "color: #52606d;"
        )
        layout.addWidget(
            self.count_label
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox
            .StandardButton
            .Close
        )
        buttons.rejected.connect(
            self.reject
        )
        layout.addWidget(buttons)

    def _evaluation_item_label(
        self,
        item_code,
    ):
        if not item_code:
            return ""

        for item in self.evaluation_items:
            if (
                item["item_code"]
                == item_code
            ):
                return (
                    f"{item['category']} / "
                    f"{item['item_name']}"
                )

        return str(item_code)

    def load_data(self):
        self.media_records = (
            get_survey_media(
                self.survey_record_id
            )
        )

        self.table.setRowCount(
            len(self.media_records)
        )

        photo_count = 0
        video_count = 0

        for row_index, media in enumerate(
            self.media_records
        ):
            if (
                media["media_kind"]
                == "photo"
            ):
                photo_count += 1
            elif (
                media["media_kind"]
                == "video"
            ):
                video_count += 1

            values = [
                media["sequence_no"],
                MEDIA_KIND_LABELS.get(
                    media["media_kind"],
                    media["media_kind"],
                ),
                MEDIA_ROLE_LABELS.get(
                    media["media_role"],
                    media["media_role"],
                ),
                media["part_name"] or "",
                self._evaluation_item_label(
                    media["item_code"]
                ),
                media[
                    "original_filename"
                ],
                _format_file_size(
                    media["file_size"]
                ),
                media["captured_at"] or "",
                media["notes"] or "",
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        int(media["id"]),
                    )

                self.table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.count_label.setText(
            (
                f"共 {len(self.media_records)} 个影像文件"
                f"  |  照片 {photo_count}"
                f"  |  视频 {video_count}"
            )
        )

    def _selected_media(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return None

        media_id = item.data(
            Qt.ItemDataRole.UserRole
        )

        if media_id is None:
            return None

        for media in self.media_records:
            if (
                int(media["id"])
                == int(media_id)
            ):
                return media

        return None

    def import_files(self):
        file_paths, _ = (
            QFileDialog.getOpenFileNames(
                self,
                "选择调查照片或视频",
                "",
                (
                    "影像文件 "
                    "(*.jpg *.jpeg *.png *.webp "
                    "*.bmp *.tif *.tiff *.heic *.heif "
                    "*.mp4 *.mov *.avi *.mkv *.m4v);;"
                    "所有文件 (*.*)"
                ),
            )
        )

        if not file_paths:
            return

        next_sequence = (
            max(
                (
                    int(
                        media[
                            "sequence_no"
                        ]
                    )
                    for media
                    in self.media_records
                ),
                default=0,
            )
            + 1
        )

        imported_count = 0
        failures = []

        for offset, file_path in enumerate(
            file_paths
        ):
            try:
                import_survey_media(
                    survey_record_id=(
                        self.survey_record_id
                    ),
                    source_file=file_path,
                    media_role="other",
                    sequence_no=(
                        next_sequence
                        + offset
                    ),
                )

                imported_count += 1

            except Exception as error:
                failures.append(
                    (
                        f"{Path(file_path).name}："
                        f"{error}"
                    )
                )

        self.load_data()

        if failures:
            QMessageBox.warning(
                self,
                "部分影像未导入",
                (
                    f"成功导入："
                    f"{imported_count} 个\n"
                    f"失败："
                    f"{len(failures)} 个\n\n"
                    + "\n".join(
                        failures
                    )
                ),
            )
        else:
            QMessageBox.information(
                self,
                "导入完成",
                (
                    f"已导入 "
                    f"{imported_count} 个影像文件。\n\n"
                    "可选中记录后使用“编辑信息”"
                    "补充用途、部位、评价项等信息。"
                ),
            )

    def edit_selected(self):
        media = self._selected_media()

        if media is None:
            QMessageBox.warning(
                self,
                "未选择影像",
                "请先选择一条影像记录。",
            )
            return

        dialog = MediaMetadataDialog(
            media=media,
            evaluation_items=(
                self.evaluation_items
            ),
            parent=self,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            return

        values = dialog.values()

        try:
            update_media_metadata(
                int(media["id"]),
                **values,
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "保存失败",
                str(error),
            )
            return

        self.load_data()

    def open_selected(self):
        media = self._selected_media()

        if media is None:
            QMessageBox.warning(
                self,
                "未选择影像",
                "请先选择一条影像记录。",
            )
            return

        file_path = Path(
            media["absolute_path"]
        )

        if not file_path.exists():
            QMessageBox.warning(
                self,
                "影像文件缺失",
                (
                    "数据库中存在影像记录，"
                    "但托管文件已经不存在：\n\n"
                    f"{file_path}"
                ),
            )
            return

        opened = (
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(file_path)
                )
            )
        )

        if not opened:
            QMessageBox.warning(
                self,
                "无法打开影像",
                (
                    "系统没有找到可用于打开"
                    "该文件的默认程序。"
                ),
            )

    def delete_selected(self):
        media = self._selected_media()

        if media is None:
            QMessageBox.warning(
                self,
                "未选择影像",
                "请先选择一条影像记录。",
            )
            return

        reply = QMessageBox.question(
            self,
            "确认删除影像",
            (
                "确定要删除这份影像吗？\n\n"
                f"文件："
                f"{media['original_filename']}\n"
                f"序号："
                f"{media['sequence_no']}\n\n"
                "删除后，系统托管文件也会删除，"
                "此操作无法从软件中恢复。"
            ),
            (
                QMessageBox
                .StandardButton
                .Yes
                | QMessageBox
                .StandardButton
                .No
            ),
            QMessageBox.StandardButton.No,
        )

        if (
            reply
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            delete_survey_media(
                int(media["id"])
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "删除失败",
                str(error),
            )
            return

        self.load_data()
