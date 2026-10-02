from PyQt5.QtCore import Qt, QAbstractTableModel
from PyQt5.QtGui import QColor,QFont
from PyQt5.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QHeaderView
from ui.widgets.daily_summary_widget import DailyCopyTable

TITLE = 'Zone Yield by Handler'

class ZoneTableModel(QAbstractTableModel):
    headers = ('Zone','In','Pass','Fail','Yield')
    def __init__(self,parent=None):
        super().__init__(parent); self.rows=[]
    def replace(self,rows):
        self.beginResetModel(); self.rows=rows; self.endResetModel()
    def rowCount(self,parent=None):
        return 0 if parent is not None and parent.isValid() else len(self.rows)+1
    def columnCount(self,parent=None):
        return 0 if parent is not None and parent.isValid() else 5
    def data(self,index,role=Qt.DisplayRole):
        if not index.isValid():return None
        if role==Qt.TextAlignmentRole:return int(Qt.AlignCenter)
        if index.row()==0:
            if role==Qt.DisplayRole:return self.headers[index.column()]
            if role==Qt.BackgroundRole:return QColor('#E2F0D9')
            if role==Qt.FontRole:
                font=QFont('Arial');font.setPixelSize(13);font.setBold(True);return font
        elif role==Qt.DisplayRole:
            row=self.rows[index.row()-1]
            return (row.zone,f'{row.in_qty:,}',f'{row.pass_qty:,}',f'{row.fail_qty:,}',
                    '' if row.yield_percent is None else f'{row.yield_percent:.2f}%')[index.column()]

class ZoneSummaryWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        self.title=QLabel(TITLE+' | Chọn EQP và Handler rồi bấm SEARCH.')
        self.title.setStyleSheet('font-size:14px;font-weight:bold;');root.addWidget(self.title)
        body=QHBoxLayout();body.setContentsMargins(0,0,0,0);body.setSpacing(24);root.addLayout(body)
        self.table=DailyCopyTable();self.model=ZoneTableModel(self.table);self.table.setModel(self.model)
        self.table.horizontalHeader().hide();self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setStyleSheet('QTableView {font-family:Arial;font-size:13px;gridline-color:#D5D5D5;border:1px solid #BFBFBF;selection-background-color:#3478C6;selection-color:white;}')
        for col,width in enumerate((50,80,80,70,80)):self.table.setColumnWidth(col,width)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setFixedSize(362,30);body.addWidget(self.table,0,Qt.AlignTop)
        self.chart_container=QWidget();self.chart_layout=QVBoxLayout(self.chart_container)
        self.chart_layout.setContentsMargins(0,0,0,0)
        self.placeholder=QLabel('Chọn EQP và Handler rồi bấm SEARCH.')
        self.placeholder.setFixedSize(900,360);self.placeholder.setAlignment(Qt.AlignCenter)
        self.chart_layout.addWidget(self.placeholder)
        body.addWidget(self.chart_container,0,Qt.AlignTop);body.addStretch()
        self.chart=None
    def load_result(self,result):
        if not result or not result.rows:
            self.clear_result('Chọn EQP và Handler rồi bấm SEARCH.');return
        self.title.setText(f'{TITLE} | EQP: {result.eqpid} | Handler: {result.handler}')
        self.model.replace(result.rows);self.table.setFixedHeight(self.model.rowCount()*28+2*self.table.frameWidth())
        if self.chart is None:
            from ui.charts.zone_yield_chart import ZoneYieldChart
            self.placeholder.hide();self.chart_layout.removeWidget(self.placeholder);self.placeholder.deleteLater()
            self.chart=ZoneYieldChart(self);self.chart_layout.addWidget(self.chart)
        self.chart.update_chart(result)
    def clear_result(self,message):
        self.model.replace([]);self.table.setFixedHeight(30);self.title.setText(TITLE+' | '+message)
        if self.chart is not None:self.chart.show_empty_state(message)
        else:self.placeholder.setText(message)
