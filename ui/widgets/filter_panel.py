from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtWidgets import (QFrame,QGridLayout,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
                            QDateEdit,QPushButton,QWidget,QStyledItemDelegate)
from ui.widgets.check_list import CheckList

class TallRows(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size=super().sizeHint(option,index);size.setHeight(size.height()+16);return size

class FilterPanel(QFrame):
    import_requested = pyqtSignal()
    filter_applied = pyqtSignal(object)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('filterFrame')
        self.setFixedWidth(1148)
        self.ready=False;self.busy=False;self.search_busy=False
        self.setStyleSheet('''
            QFrame#filterFrame {background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;}
            QLabel {color:#1E293B;border:none;font-size:13px;font-weight:700;}
            QComboBox,QDateEdit {background:white;color:#0F172A;border:1px solid #CBD5E1;border-radius:4px;padding-left:8px;font-size:13px;}
            QListWidget {background:white;color:#0F172A;border:1px solid #CBD5E1;border-radius:4px;font-size:13px;}
            QPushButton {color:white;background:#1976D2;border:1px solid #1565C0;border-radius:4px;font-size:13px;font-weight:600;}
            QPushButton:hover {background:#42A5F5;}
            QPushButton:disabled {background:#90CAF9;border-color:#90CAF9;}
        ''')
        layout=QVBoxLayout(self);layout.setContentsMargins(18,16,18,12);layout.setSpacing(14)
        grid=QGridLayout();grid.setHorizontalSpacing(36);grid.setVerticalSpacing(16)
        self.from_date_edit=QDateEdit(QDate.currentDate().addDays(-14))
        self.to_date_edit=QDateEdit(QDate.currentDate())
        for date in (self.from_date_edit,self.to_date_edit):
            date.setCalendarPopup(True);date.setDisplayFormat('yyyy-MM-dd');date.setFixedSize(180,32)
            date.dateChanged.connect(self._dates_changed)
        self.combos={}
        for key,label in [('EQP','EQP'),('Handler','Handler'),('ZONE','Zone'),('SLOT','Slot')]:
            combo=QComboBox();combo.setFixedSize(180,32);combo.setItemDelegate(TallRows(combo))
            combo.addItem('Chọn '+label,None);self.combos[key]=combo
        def group(label,widget):
            box=QWidget();v=QVBoxLayout(box);v.setContentsMargins(0,0,0,0);v.setSpacing(4)
            v.addWidget(QLabel(label));v.addWidget(widget);return box
        grid.addWidget(group('From',self.from_date_edit),0,0)
        grid.addWidget(group('To',self.to_date_edit),0,1)
        grid.addWidget(group('EQP',self.combos['EQP']),0,2)
        for col,(key,label) in enumerate([('Handler','Handler'),('ZONE','Zone'),('SLOT','Slot')]):
            grid.addWidget(group(label,self.combos[key]),1,col)
        self.model_list=CheckList(True);self.scrap_code_list=CheckList(False)
        for col,label,widget in [(3,'Model',self.model_list),(4,'Scrap Code',self.scrap_code_list)]:
            widget.setFixedSize(180,104)
            grid.addWidget(group(label,widget),0,col,2,1,Qt.AlignTop)
        layout.addLayout(grid)
        buttons=QHBoxLayout()
        self.button=QPushButton('IMPORT');self.button.setFixedSize(120,30)
        self.apply_filter_button=QPushButton('SEARCH');self.apply_filter_button.setFixedSize(120,30)
        self.button.clicked.connect(self.import_requested.emit)
        self.apply_filter_button.clicked.connect(lambda:self.filter_applied.emit(self.get_filter_criteria()))
        buttons.addWidget(self.button);buttons.addStretch();buttons.addWidget(self.apply_filter_button)
        layout.addLayout(buttons)
        self.set_ready(False)

    def _dates_changed(self):
        if self.from_date_edit.date()>self.to_date_edit.date():
            if self.sender() is self.from_date_edit:self.to_date_edit.setDate(self.from_date_edit.date())
            else:self.from_date_edit.setDate(self.to_date_edit.date())

    def load_options(self,options):
        for key,combo in self.combos.items():
            previous=combo.currentData();label=combo.itemText(0)
            combo.blockSignals(True);combo.clear();combo.addItem(label,None)
            for value in options.get(key,[]):combo.addItem(str(value),value)
            index=combo.findData(previous);combo.setCurrentIndex(max(0,index));combo.blockSignals(False)
        self.model_list.set_values(options.get('Model',[]));self.scrap_code_list.set_values(options.get('SCRAP',[]))

    def set_ready(self,ready):
        self.ready=ready
        for widget in (*self.combos.values(),self.model_list,self.scrap_code_list):widget.setEnabled(ready and not self.busy and not self.search_busy)
        self.apply_filter_button.setEnabled(ready and not self.busy and not self.search_busy)

    def set_busy(self,busy):
        self.busy=busy;self.button.setEnabled(not busy);self.button.setText('Đang import…' if busy else 'IMPORT')
        self.set_ready(self.ready)

    def set_search_busy(self, busy):
        self.search_busy=busy
        self.button.setEnabled(not busy and not self.busy)
        self.apply_filter_button.setText('Đang search…' if busy else 'SEARCH')
        self.from_date_edit.setEnabled(not busy)
        self.to_date_edit.setEnabled(not busy)
        self.set_ready(self.ready)

    def get_filter_criteria(self):
        return dict(date_from=self.from_date_edit.date().toString('yyyyMMdd'),date_to=self.to_date_edit.date().toString('yyyyMMdd'),
                    eqp=self.combos['EQP'].currentData(),handler=self.combos['Handler'].currentData(),
                    zone=self.combos['ZONE'].currentData(),slot=self.combos['SLOT'].currentData(),
                    models=self.model_list.selected_values(),scrap_codes=self.scrap_code_list.selected_values())
