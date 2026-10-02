from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QListWidget, QListWidgetItem

class CheckList(QListWidget):
    def __init__(self, default_checked=False, parent=None):
        super().__init__(parent)
        self.default_checked = default_checked
        self.loaded = False
        self.itemChanged.connect(self._changed)
        self.set_values([])

    def set_values(self, values):
        selected = set(self.selected_values())
        all_selected = self.count()>1 and len(selected)==self.count()-1
        self.blockSignals(True)
        self.clear()
        first = QListWidgetItem('Select All', self)
        first.setFlags(first.flags() | Qt.ItemIsUserCheckable)
        for value in values:
            item = QListWidgetItem(str(value), self)
            item.setData(Qt.UserRole, value)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            checked = (self.default_checked if not self.loaded else all_selected or value in selected)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self._sync_all()
        self.blockSignals(False)
        if values:
            self.loaded = True

    def selected_values(self):
        return [self.item(i).data(Qt.UserRole) for i in range(1,self.count()) if self.item(i).checkState()==Qt.Checked]

    def _sync_all(self):
        count = len(self.selected_values())
        self.item(0).setCheckState(Qt.Checked if count and count==self.count()-1 else Qt.PartiallyChecked if count else Qt.Unchecked)

    def _changed(self, item):
        self.blockSignals(True)
        if self.row(item)==0:
            state = Qt.Checked if item.checkState()==Qt.Checked else Qt.Unchecked
            for i in range(1,self.count()):self.item(i).setCheckState(state)
        self._sync_all()
        self.blockSignals(False)
