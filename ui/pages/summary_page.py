from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtGui import QFont, QColor, QKeySequence
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
                            QTableView, QAbstractItemView, QApplication, QMenu, QHeaderView)

TITLE = 'Yield ARTs machine on summary'


class YieldTableModel(QAbstractTableModel):
    headers = ('EQPID', 'In Qty', 'Out Qty', 'Fail Qty', 'Fail PPM', 'Yield')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def replace(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    def columnCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else 6

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return (row.eqpid, f'{row.in_qty:,}', f'{row.out_qty:,}', f'{row.fail_qty:,}',
                    '—' if row.fail_ppm is None else f'{row.fail_ppm:,.0f}',
                    '—' if row.yield_percent is None else f'{row.yield_percent:.2f}%')[index.column()]
        if role == Qt.TextAlignmentRole:
            return int((Qt.AlignLeft if index.column() == 0 else Qt.AlignRight) | Qt.AlignVCenter)
        if index.row() == len(self.rows)-1:
            if role == Qt.FontRole:
                font = QFont('Arial'); font.setPixelSize(13); font.setBold(True); return font
            if role == Qt.BackgroundRole:
                return QColor('#E2F0D9')


class CopyTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.copy_menu)

    def copy_selection(self, include_headers=True):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        selected = {(i.row(), i.column()): str(i.data() or '') for i in indexes}
        rows = sorted({r for r, c in selected})
        columns = sorted({c for r, c in selected})
        # Blank holes preserve positions; never copy data from unselected cells.
        text = '\n'.join('\t'.join(selected.get((r, c), '') for c in columns) for r in rows)
        if include_headers:
            headers = '\t'.join(str(self.model().headerData(c, Qt.Horizontal)) for c in columns)
            text = headers + '\n' + text
        QApplication.clipboard().setText(text)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_selection(); event.accept(); return
        super().keyPressEvent(event)

    def copy_menu(self, position):
        menu = QMenu(self)
        action = menu.addAction('Copy kèm tiêu đề (Ctrl+C)')
        data_only = menu.addAction('Copy dữ liệu, không kèm tiêu đề')
        for item in (action, data_only):
            item.setEnabled(bool(self.selectedIndexes()))
        chosen = menu.exec_(self.viewport().mapToGlobal(position))
        if chosen is action:
            self.copy_selection()
        elif chosen is data_only:
            self.copy_selection(False)


class SummaryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); content.setStyleSheet('background:white;')
        scroll.setWidget(content); outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        self.title = QLabel(TITLE)
        self.title.setStyleSheet('font-weight:bold;font-size:14px;')
        layout.addWidget(self.title)
        body = QHBoxLayout(); body.setSpacing(28); layout.addLayout(body)
        self.table = CopyTableView()
        self.model = YieldTableModel(self.table); self.table.setModel(self.model)
        self.table.verticalHeader().hide(); self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.horizontalHeader().setFixedHeight(28)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet('QTableView {font-family:Arial;font-size:13px;gridline-color:#222;alternate-background-color:#f0f0f0;selection-background-color:#3478c6;selection-color:white;} QHeaderView::section {font-family:Arial;font-size:13px;background:#E2F0D9;font-weight:bold;padding:4px;border:1px solid #333;}')
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setHighlightSections(True)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setFrameShape(QTableView.NoFrame)
        for column, width in enumerate((58, 56, 67, 66, 72, 59)):
            self.table.setColumnWidth(column, width)
        self.table.setFixedSize(378, 90)
        body.addWidget(self.table, 0, Qt.AlignTop)
        self.chart_layout = QVBoxLayout(); self.chart_layout.setContentsMargins(0, 0, 0, 0)
        self.placeholder = QLabel('Chọn điều kiện và bấm SEARCH.'); self.placeholder.setAlignment(Qt.AlignCenter)
        self.chart_layout.addWidget(self.placeholder)
        body.addLayout(self.chart_layout); body.addStretch()
        self.chart = None
        from ui.widgets.daily_summary_widget import DailySummaryWidget
        self.daily_summary = DailySummaryWidget(self)
        layout.addSpacing(24)
        layout.addWidget(self.daily_summary, 0, Qt.AlignLeft)
        self.handler_daily_summary = DailySummaryWidget(self, by_handler=True)
        layout.addSpacing(24)
        layout.addWidget(self.handler_daily_summary, 0, Qt.AlignLeft)
        from ui.widgets.zone_summary_widget import ZoneSummaryWidget
        self.zone_summary=ZoneSummaryWidget(self)
        layout.addSpacing(24)
        layout.addWidget(self.zone_summary,0,Qt.AlignLeft)
        layout.addStretch()

    def load_result(self, result, criteria):
        rows, total = result[:2]
        self.model.replace([*rows, total] if rows else [])
        self.table.setFixedHeight(28 + 28*self.model.rowCount())
        self.title.setText(f"{TITLE}: {criteria['date_from']} - {criteria['date_to']}")
        if self.chart is None:
            from ui.charts.machine_yield_chart import MachineYieldChart
            self.chart = MachineYieldChart(self)
            self.placeholder.hide(); self.chart_layout.removeWidget(self.placeholder)
            self.placeholder.deleteLater()
            self.chart_layout.addWidget(self.chart, 0, Qt.AlignTop)
        self.chart.update_chart(rows)
        if len(result) > 2:
            self.daily_summary.load_result(result[2], criteria.get('scrap_codes') or [])
        if len(result) > 3:
            self.handler_daily_summary.load_result(result[3], criteria.get('scrap_codes') or [])
        if len(result)>4:
            self.zone_summary.load_result(result[4])

    def clear_result(self, message):
        self.zone_summary.clear_result(message)
        self.daily_summary.clear_result(message)
        self.handler_daily_summary.clear_result(message)
        self.model.replace([])
        self.title.setText(TITLE)
        if self.chart is not None:
            self.chart.show_empty_state(message)
        else:
            self.placeholder.setText(message)
