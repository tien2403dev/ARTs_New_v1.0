"""Selectable header row: copying never adds unselected cells or headers."""
from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHeaderView, QMenu, QStyle
from ui.pages.summary_page import CopyTableView


class DailyTableModel(QAbstractTableModel):
    fixed_headers = ('Date', 'In Qty', 'Pass', 'Fail Qty', 'Fail PPM', 'Yield')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.headers = list(self.fixed_headers)
        self.rows = []

    def replace(self, result=None):
        self.beginResetModel()
        self.headers = [*self.fixed_headers, *(result.scrap_codes if result else [])]
        self.rows = result.rows if result else []
        self.endResetModel()

    def rowCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else 1 + len(self.rows)

    def columnCount(self, parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row, column = index.row(), index.column()
        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignCenter)
        if row == 0:
            if role == Qt.DisplayRole:
                return self.headers[column]
            if role == Qt.BackgroundRole:
                return QColor('#E2F0D9')
            if role == Qt.FontRole:
                font = QFont('Arial'); font.setPixelSize(12); font.setBold(True); return font
        elif role == Qt.DisplayRole:
            value = self.rows[row-1]
            if column >= 6:
                qty = value.scrap_qty.get(self.headers[column], 0)
                return f'{qty * 1_000_000 / value.in_qty:.0f}' if qty and value.in_qty else ''
            return (value.date, f'{value.in_qty:,}', f'{value.out_qty:,}', f'{value.fail_qty:,}',
                    '' if value.fail_ppm is None else f'{value.fail_ppm:.0f}',
                    '' if value.yield_percent is None else f'{value.yield_percent:.2f}%')[column]


class DailyCopyTable(CopyTableView):
    def copy_selection(self, include_headers=False):
        super().copy_selection(include_headers=False)

    def copy_menu(self, position):
        menu = QMenu(self)
        action = menu.addAction('Copy phần đã bôi chọn (Ctrl+C)')
        action.setEnabled(bool(self.selectedIndexes()))
        if menu.exec_(self.viewport().mapToGlobal(position)) is action:
            self.copy_selection()


class DailySummaryWidget(QWidget):
    def __init__(self, parent=None, by_handler=False):
        super().__init__(parent)
        self.by_handler = by_handler
        self.base_title = 'Yield ARTs by Handler' if by_handler else 'Yield ARTs Daily'
        self.choose_message = 'Chọn EQP và Handler rồi bấm SEARCH.' if by_handler else 'Chọn EQP rồi bấm SEARCH.'
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(self.base_title+' | '+self.choose_message)
        self.title.setStyleSheet('font-weight:bold;font-size:14px;')
        layout.addWidget(self.title)
        self.table = DailyCopyTable()
        self.model = DailyTableModel(self.table); self.table.setModel(self.model)
        self.table.horizontalHeader().hide(); self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet('QTableView {font-family:Arial;font-size:12px;gridline-color:#D5D5D5;border:1px solid #BFBFBF;alternate-background-color:#F5F7FA;selection-background-color:#3478C6;selection-color:white;}')
        self.table.setToolTip('Bôi cả hàng đầu nếu muốn copy tiêu đề. Ctrl+C chỉ copy các ô được chọn.')
        # Outer Summary scroll handles width; cap only the table height.
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._fit_table()
        layout.addWidget(self.table, 0, Qt.AlignLeft)
        self.placeholder = QLabel('Chọn EQP và Scrap Code rồi bấm SEARCH.')
        layout.addWidget(self.placeholder)
        self.chart = None

    def load_result(self, result, selected_codes):
        if not result or not result.eqpid or (self.by_handler and result.handler is None):
            self.clear_result(self.choose_message)
            return
        title = f'{self.base_title} | EQP: {result.eqpid}'
        if self.by_handler:
            title += f' | Handler: {result.handler}'
        self.title.setText(title)
        self.model.replace(result)
        self.table.resizeColumnsToContents()
        for col in range(self.model.columnCount()):
            self.table.setColumnWidth(col, max(58, self.table.columnWidth(col)+4))
        self._fit_table()
        if self.chart is None:
            from ui.charts.daily_scrap_chart import DailyScrapChart
            self.chart = DailyScrapChart(self)
            self.placeholder.hide()
            self.layout().addWidget(self.chart, 0, Qt.AlignLeft)
        self.chart.chart_title = title
        self.chart.show_eqp_in_title = False
        self.chart.update_chart(result, selected_codes)

    def clear_result(self, message):
        self.model.replace()
        self.title.setText(self.base_title+' | '+message)
        self.table.resizeColumnsToContents()
        self._fit_table()
        if self.chart is not None:
            self.chart.show_empty_state(message)
        else:
            self.placeholder.setText(message)

    def _fit_table(self):
        natural_height = sum(self.table.rowHeight(i) for i in range(self.model.rowCount())) + 2*self.table.frameWidth()
        scrollbar_width = self.table.style().pixelMetric(QStyle.PM_ScrollBarExtent) if natural_height > 560 else 0
        width = sum(self.table.columnWidth(i) for i in range(self.model.columnCount())) + 2*self.table.frameWidth() + scrollbar_width
        self.table.setFixedSize(width, min(560, natural_height))
