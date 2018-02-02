from PyQt4 import QtGui,QtCore
from ... import format, limit

class LVTextEdit(QtGui.QLineEdit):
    def __init__(self, parent, value=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.returnPressed.connect(self._on_enter)
        self.editingFinished.connect(self._on_edit_done)
        self._value=None
        if value is not None:
            self.set_value(None)
        self.textChanged.connect(self._on_change_text)
    def _on_edit_done(self):
        self.set_value(self.text())
        self.value_entered.emit(self._value)
    def _on_enter(self):
        self._on_edit_done()
        self.clearFocus()
    def _on_change_text(self, text):
        if not self.isModified():
            self.set_value(text)
    def keyPressEvent(self, event):
        if event.key()==QtCore.Qt.Key_Escape:
            self.set_value(None)
            self.clearFocus()
        else:
            QtGui.QLineEdit.keyPressEvent(self,event)

    value_entered=QtCore.pyqtSignal("PyQt_PyObject")
    value_changed=QtCore.pyqtSignal("PyQt_PyObject")
    def get_value(self):
        return self._value
    def set_value(self, value, notify_value_change=True):
        if value is None:
            self.setText(self._value)
        else:
            value=str(value)
            if self._value!=value:
                self._value=value
                if notify_value_change:
                    self.value_changed.emit(self._value)
                self.setText(value)
                return True
        return False

class LVNumEdit(QtGui.QLineEdit):
    def __init__(self, parent, value=None, num_limit=None, num_format=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.num_limit=limit.as_limiter(num_limit) if num_limit is not None else limit.NumberLimit()
        self.num_format=format.as_formatter(num_format) if num_format is not None else format.FloatFormatter()
        self.returnPressed.connect(self._on_enter)
        self.editingFinished.connect(self._on_edit_done)
        self._value=None
        if value is not None:
            self.set_value(value)
        self.textChanged.connect(self._on_change_text)
    def _on_edit_done(self):
        self.set_value(self._read_input())
        self.value_entered.emit(self._value)
    def _on_enter(self):
        self._on_edit_done()
        self.clearFocus()
    def _on_change_text(self, text):
        if not self.isModified():
            try:
                value=format.str_to_float(str(self.text()))
                self.set_value(value)
            except ValueError:
                pass
    def keyPressEvent(self, event):
        k=event.key()
        if k==QtCore.Qt.Key_Escape:
            self.set_value(None)
            self.clearFocus()
        elif k in [QtCore.Qt.Key_Up,QtCore.Qt.Key_Down]:
            try:
                str_value=str(self.text())
                num_value=format.str_to_float(str_value)
                cursor_order=self.get_cursor_order()
                if cursor_order!=None:
                    step=10**(cursor_order)
                    if k==QtCore.Qt.Key_Up:
                        self.set_value(num_value+step,preserve_cursor_order=False)
                    else:
                        self.set_value(num_value-step,preserve_cursor_order=False)
                    self.set_cursor_order(cursor_order)
            except ValueError:
                self.set_value(None)
        else:
            QtGui.QLineEdit.keyPressEvent(self,event)
    def _read_input(self):
        try:
            return format.str_to_float(str(self.text()))
        except ValueError:
            return self._value

    def change_limiter(self, limiter):
        self.num_limit=limit.as_limiter(limiter)
        self.set_value(self._value)
    def set_number_limit(self, lower_limit=None, upper_limit=None, action="ignore", value_type=None):
        limiter=limit.NumberLimit(lower_limit=lower_limit,upper_limit=upper_limit,action=action,value_type=value_type)
        self.change_limiter(limiter)
    def change_formatter(self, formatter):
        self.num_format=formatter
        self.set_value(None)
    def set_number_format(self, kind="float", *args, **kwargs):
        if kind=="float":
            formatter=format.FloatFormatter(*args,**kwargs)
        elif kind=="int":
            formatter=format.IntegerFormatter()
        else:
            raise ValueError("unknown format: {}".format(kind))
        self.change_formatter(formatter)

    def get_cursor_order(self):
        str_value=str(self.text())
        cursor_pos=self.cursorPosition()
        return format.pos_to_order(str_value,cursor_pos)
    def set_cursor_order(self, order):
        if order is not None:
            new_cursor_pos=format.order_to_pos(str(self.text()),order)
            self.setCursorPosition(new_cursor_pos)

    value_entered=QtCore.pyqtSignal("PyQt_PyObject")
    value_changed=QtCore.pyqtSignal("PyQt_PyObject")
    def get_value(self):
        return self._value
    def set_value(self, value, notify_value_change=True, preserve_cursor_order=True):
        if value is not None:
            try:
                value=self.num_limit(value)
                if self._value!=value:
                    self._value=value
                    if notify_value_change:
                        self.value_changed.emit(self._value)
                    if preserve_cursor_order and self.hasFocus():
                        cursor_order=self.get_cursor_order()
                        self.setText(self.num_format(self._value))
                        if cursor_order is not None:
                            self.set_cursor_order(cursor_order)
                    else:
                        self.setText(self.num_format(self._value))
                    return True
            except limit.LimitError:
                pass
        if self._value is not None:
            self.setText(self.num_format(self._value))
        return False