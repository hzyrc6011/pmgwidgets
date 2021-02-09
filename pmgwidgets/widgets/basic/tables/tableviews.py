"""
这是一个利用QT的MVC架构进行数据查看的表格。这个表格十分适合大量数据的查看，1000*1000规模的数据集可以做到秒开。
其中定义了若干类。可以直接显示pd.DataFrame,np.array和list的TableView。

目前增加了切片索引查看功能和編輯功能。对dataframe而言，切片时可以编辑
但是array在切片的时候编辑。

作者：侯展意
"""
import os
import sys

import typing
from qtpy.QtWidgets import QTableView, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, \
    QMessageBox, QInputDialog, QMenu, QDialog, QDialogButtonBox
from qtpy.QtCore import QAbstractTableModel, QModelIndex, Signal, QLocale
from qtpy.QtCore import Qt, QPoint
from qtpy.QtGui import QContextMenuEvent, QKeyEvent

from pmgwidgets.utilities.source.translation import create_translator

if typing.TYPE_CHECKING:
    import numpy as np


class InputValueDialog(QDialog):
    UP = -1
    DOWN = 1
    signal_move_cursor = Signal(int)
    signal_edit_finished = Signal(str)

    def __init__(self, parent):
        super(InputValueDialog, self).__init__(parent)
        self.setLayout(QVBoxLayout())
        self.edit = QLineEdit()
        self.layout().addWidget(self.edit)
        self.edit.returnPressed.connect(self.edit_finished)
        self.button_box = QDialogButtonBox()
        self.button_box.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout().addWidget(self.button_box)
        self.button_box.rejected.connect(self.close)
        self.button_box.accepted.connect(self.edit_finished)

    def edit_finished(self):
        self.close()
        self.signal_edit_finished.emit(self.edit.text())

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key_Up:
            self.close()
            self.signal_move_cursor.emit(self.UP)
            e.accept()
        elif e.key() == Qt.Key_Down:
            self.close()
            self.signal_move_cursor.emit(self.DOWN)
            e.accept()

        super(InputValueDialog, self).keyPressEvent(e)


def to_decimal_str(cell_data: 'np.ndarray', decimals: int = 6):
    import numpy as np
    try:
        rounded_data = np.around(cell_data, decimals)
        return repr(rounded_data)
    except:
        return str(cell_data)


def dataformat(val, decimals=6, sci=False):
    """
    这只是暂时的strformat函数。如有可能，应当使用cython重写并且部署在动态链接库中,从而提升性能。
    Args:
        val:
        decimals:
        sci:

    Returns:

    """
    global type_float_set
    return to_decimal_str(val, decimals)


class BaseAbstractTableModel(QAbstractTableModel):
    @property
    def default_slicing_statement(self):
        raise NotImplementedError


class TableModelForList(BaseAbstractTableModel):
    """
    输入为list的table model
    """

    def __init__(self, data: list):
        super(TableModelForList, self).__init__()
        import numpy as np
        self._data: np.ndarray = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return dataformat(self._data[index.row()][index.column()])

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        return len(self._data[0])


class TableModelForNumpyArray(BaseAbstractTableModel):
    """
    输入为pandas.DataFram的TableModel，用于在表格中显示数据。
    """

    def __init__(self, data):
        super(TableModelForNumpyArray, self).__init__()
        self._data = data
        self.horizontal_start: int = 0
        self.vertical_start: int = 0

    def setData(self, index: 'QModelIndex', value: typing.Any = None, role='Qt.EditRole'):
        """
        # View中编辑后，View会调用这个方法修改Model中的数据
        :param index:
        :param value:
        :param role:
        :return:
        """

        if index.isValid() and 0 <= index.row() < self._data.shape[0] and value:
            col = index.column()
            row = index.row()

            if len(self._data.shape) == 1:
                self.beginResetModel()
                self._data[row] = value
                self.dirty = True
                self.endResetModel()
                return True
            else:
                if 0 <= col < self._data.shape[1]:
                    self.beginResetModel()
                    self._data[row, col] = value
                    self.dirty = True
                    self.endResetModel()
                    return True
        return False

    def data(self, index, role):
        if role == Qt.DisplayRole:
            if len(self._data.shape) >= 2:
                value = self._data[index.row(), index.column()]
            else:
                value = self._data[index.row()]
            return dataformat(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        if len(self._data.shape) == 1:
            return 1
        else:
            return self._data.shape[1]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> typing.Any:
        if role == Qt.DisplayRole:
            if role == Qt.DisplayRole:
                if orientation == Qt.Horizontal:
                    return str(self.horizontal_start + section)
                if orientation == Qt.Vertical:
                    return str(self.vertical_start + section)

    @property
    def default_slicing_statement(self):
        """
        默认切片数组
        :return:
        """
        data_dim = len(self._data.shape)
        if data_dim in (1, 2):

            return '[%s]' % (':,' * data_dim).strip(',')
        else:
            return '[%s]' % (':,:,' + '0,' * (data_dim - 2)).strip(',')


class TableModelForPandasDataframe(BaseAbstractTableModel):
    """
    输入为pandas.DataFram的TableModel，用于在表格中显示数据。
    """

    def __init__(self, data, original_data):
        super(TableModelForPandasDataframe, self).__init__()
        self._data: 'pd.DataFrame' = data
        self.original_data = original_data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            value = self._data.iloc[index.row(), index.column()]
            return dataformat(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = ...) -> typing.Any:
        if role == Qt.DisplayRole:
            if role == Qt.DisplayRole:
                if orientation == Qt.Horizontal:
                    return str(self._data.columns[section])
                if orientation == Qt.Vertical:
                    return str(self._data.index[section])

    @property
    def default_slicing_statement(self):
        """
        默认切片数组
        :return:
        """
        data_dim = len(self._data.shape)
        return '.iloc[%s]' % (':,' * data_dim).strip(',')

    # def update_item(self, row, col, value):
    #     ix = self.index(row, col)
    #     self.setData(ix, value)

    def setData(self, index, value=None, role=Qt.EditRole):
        # 编辑后更新模型中的数据 View中编辑后，View会调用这个方法修改Model中的数据
        if index.isValid() and 0 <= index.row() < self._data.shape[0] and value:
            col = index.column()
            row = index.row()
            if 0 <= col < self._data.shape[1]:
                self.beginResetModel()
                col_label = self._data.columns[col]
                row_label = self._data.index[row]
                self.original_data.loc[row_label, col_label] = value
                self._data.loc[row_label, col_label] = value
                self.dirty = True
                self.endResetModel()
                return True
        return False


class PMTableView(QTableView):
    """
    基类，用于显示数据。输入数据类型为列表。
    """
    INSERT_ROW = 0
    DELETE_ROW = 1
    INSERT_COLUMN = 2
    DELETE_COLUMN = 3

    def __init__(self, data=None):
        super().__init__()
        self.translator = create_translator(
            path=os.path.join(os.path.dirname(__file__), 'translations',
                              'qt_{0}.qm'.format(QLocale.system().name())))  # translator
        self.data = None
        self.menu = QMenu()
        self.action_insert_row = self.menu.addAction(self.tr('Insert Row'))
        self.action_insert_row.triggered.connect(lambda: self.on_change_row_col(self.INSERT_ROW))
        self.action_delete_row = self.menu.addAction(self.tr('Delete Row'))
        self.action_insert_col = self.menu.addAction(self.tr('Insert Column'))
        self.action_insert_col.triggered.connect(lambda: self.on_change_row_col(self.INSERT_COLUMN))
        self.action_delete_col = self.menu.addAction(self.tr('Delete Column'))

        # self.menu.addAction("aaaaaa")
        if data is not None:
            self.set_data(data)

    def on_change_row_col(self, operation: int):
        pd_data: pd.DataFrame = self.model._data
        current_index = self.currentIndex()
        row, column = current_index.row(), current_index.column()
        if operation == self.INSERT_ROW:
            prev = pd_data.iloc[:row]
            lat = pd_data.iloc[row:]
            self.model._data = pd.concat([prev, pd.DataFrame([[]]), lat])

        elif operation == self.INSERT_COLUMN:
            col_name, _ = QInputDialog.getText(self, self.tr('Input Column Title'), self.tr('Title'))
            if _:
                pd_data.insert(column, col_name, np.nan)
        else:
            raise NotImplementedError
        self.model.layoutChanged.emit()

    def set_data(self, data):
        self.data = data
        self.show_data(data)

    def show_data(self, data):
        import pandas as pd
        import numpy as np
        if isinstance(data, pd.DataFrame):
            self.model = TableModelForPandasDataframe(data, self.data)
        elif isinstance(data, np.ndarray):
            self.model = TableModelForNumpyArray(data)
            self.menu.setEnabled(False)
        elif isinstance(data, list):
            self.model = TableModelForList(data)
            self.menu.setEnabled(True)
        else:
            raise Exception("data type %s is not supported in PMTableView.\
                            \n Supported Types are: numpy.array,list and pandas.DataFrame." % type(data))
        self.setModel(self.model)

    def get_default_slicing_statement(self):
        return self.model.default_slicing_statement

    def mouseDoubleClickEvent(self, event: 'QMouseEvent') -> None:
        """
        TODO:编辑功能无效，暂时需要屏蔽掉。
        Args:
            event:

        Returns:

        """
        super().mouseDoubleClickEvent(event)
        self.show_edit_dialog(self.currentIndex().row(), self.currentIndex().column())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        super(PMTableView, self).keyPressEvent(event)
        if event.key() == Qt.Key_Return:
            self.show_edit_dialog(self.currentIndex().row(), self.currentIndex().column())

    def show_edit_dialog(self, row, col):

        data = self.model._data
        if isinstance(data, pd.DataFrame):
            def on_edited(text):

                try:
                    result = eval(text)
                    print(result)
                    data.iloc[row, col] = result
                except:
                    import traceback
                    QMessageBox.warning(self, self.tr('Warning'), self.tr(traceback.format_exc()))
                    return

            def on_move_current_cell(direction: int):
                target_row = row + direction
                print(target_row, self.model.rowCount(col))
                if 0 <= target_row < self.model.rowCount(col):
                    self.setCurrentIndex(self.model.index(target_row, col))
                    self.show_edit_dialog(target_row, col)

            from pandas import Timestamp, Period, Interval
            original_data = data.iloc[row, col]
            print(original_data)
            print(self.columnViewportPosition(col), self.rowViewportPosition(row))

            dlg = InputValueDialog(self)
            dlg.setWindowTitle(self.tr('Input New Value'))
            dlg.edit.setText(repr(original_data))
            dlg.signal_edit_finished.connect(on_edited)
            dlg.signal_move_cursor.connect(on_move_current_cell)
            global_pos = self.mapToGlobal(
                QPoint(self.columnViewportPosition(col) + 50, self.rowViewportPosition(row) + 50))
            dlg.setGeometry(global_pos.x(), global_pos.y(), dlg.width(), dlg.height())
            dlg.exec_()
            # QInputDialog.getText(self, self.tr('Input New Value'), '', QLineEdit.Normal,
            # text=repr(original_data))

    def contextMenuEvent(self, event: QContextMenuEvent):
        print(event)
        self.menu.exec_(event.globalPos())


class PMGTableViewer(QWidget):
    """
    一个含有QTableView的控件。
    有切片和保存两个按钮。点击Slice的时候可以切片查看，点击Save保存。
    """
    data_modified_signal = Signal()

    def __init__(self, parent=None, table_view: 'PMTableView' = None):
        super().__init__(parent)

        self.setLayout(QVBoxLayout())
        self.top_layout = QHBoxLayout()
        self.layout().addLayout(self.top_layout)
        self.table_view = table_view
        self.slice_input = QLineEdit()

        self.slice_refresh_button = QPushButton(self.tr('Slice'))
        # self.save_change_button = QPushButton(self.tr('Save'))
        # self.save_change_button.clicked.connect(self.data_modified_signal.emit)
        self.slice_refresh_button.clicked.connect(self.slice)
        self.top_layout.addWidget(self.slice_input)
        self.top_layout.addWidget(self.slice_refresh_button)
        # self.top_layout.addWidget(self.save_change_button)
        if table_view is not None:
            self.layout().addWidget(self.table_view)

    def set_data(self, data: typing.Any) -> None:
        """
        set_data方法在初次调用时，设置其内部的data参数；
        当后面调用的时候，不会更改内部的data参数。
        get_default_slicing_statement的意思是可以获取默认的切片索引。
        这是因为表格一般只能显示二维的数据，当数组维数超过二维的时候，就需要尽可能地利用切片进行显示了。
        比如对于四维np.array张量，返回的默认就是[:,:,0,0]。用户可以根据自己的需要进行切片。
        :param data:
        :return:
        """
        if self.table_view is not None:
            self.table_view.set_data(data)
            self.slice_input.setText(self.table_view.get_default_slicing_statement())
            self.slice()

    def get_data(self):
        return self.table_view.data

    def slice(self):
        """
        切片操作。同时屏蔽可能出现的非法字符。
        目前做不到对array数组进行索引。
        :return:
        """
        data = self.table_view.data
        text = self.slice_input.text().strip()
        for char in text:
            if not char in "[]:,.1234567890iloc":
                QMessageBox.warning(self, self.tr('Invalid Input'),
                                    self.tr("invalid character \"%s\" in slicing statement.") % char)
                return
        try:
            data = eval('data' + text)
        except Exception as exeption:

            QMessageBox.warning(self, self.tr('Invalid Input'),
                                self.tr(str(exeption)))

        self.table_view.show_data(data)

    def closeEvent(self, a0: 'QCloseEvent') -> None:
        super().closeEvent(a0)


if __name__ == '__main__':
    import pandas as pd
    import numpy as np
    import datetime

    app = QApplication(sys.argv)
    table = PMGTableViewer(table_view=PMTableView())

    data = np.random.random((5, 3, 3, 3))
    data = pd.DataFrame([['aaa', 'bbb', 0.1, 0.0001, True, pd.Timestamp(datetime.datetime(2012, 5, 1))],
                         ['rrr', 'aaaaaa', False, pd.Timestamp(datetime.datetime(2012, 5, 1))]])
    table.show()

    table.set_data(data)

    app.exec_()
