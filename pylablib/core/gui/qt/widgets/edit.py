from PyQt4 import QtGui,QtCore
from ... import format, limit

class LVTextEdit(QtGui.QLineEdit):
    def __init__(self, parent, value=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.returnPressed.connect(self._on_enter)
        self.editingFinished.connect(self._on_edit_done)
        self._value=None
        if value is not None:
            self.set_value(value)
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
            self.clearFocus()
            self.show_value()
        else:
            QtGui.QLineEdit.keyPressEvent(self,event)

    value_entered=QtCore.pyqtSignal("PyQt_PyObject")
    value_changed=QtCore.pyqtSignal("PyQt_PyObject")
    def get_value(self):
        return self._value
    def show_value(self, interrupt_edit=False):
        if (not self.hasFocus()) or interrupt_edit:
            self.setText(self._value)
    def set_value(self, value, notify_value_change=True, interrupt_edit=False):
        value_changed=False
        value=str(value)
        if self._value!=value:
            self._value=value
            if notify_value_change:
                self.value_changed.emit(self._value)
            value_changed=True
        self.show_value(interrupt_edit=interrupt_edit)
        return value_changed

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
            self.show_value(interrupt_edit=True)
            self.clearFocus()
        elif k in [QtCore.Qt.Key_Up,QtCore.Qt.Key_Down]:
            try:
                str_value=str(self.text())
                num_value=format.str_to_float(str_value)
                cursor_order=self.get_cursor_order()
                if cursor_order!=None:
                    step=10**(cursor_order)
                    if k==QtCore.Qt.Key_Up:
                        self.set_value(num_value+step,interrupt_edit=True)
                    else:
                        self.set_value(num_value-step,interrupt_edit=True)
            except ValueError:
                self.show_value(interrupt_edit=True)
        else:
            QtGui.QLineEdit.keyPressEvent(self,event)
    def _read_input(self):
        try:
            return format.str_to_float(str(self.text()))
        except ValueError:
            return self._value

    def change_limiter(self, limiter):
        self.num_limit=limit.as_limiter(limiter)
        if self._value is not None:
            new_value=self._coerce_value(self._value)
            if new_value!=self._value:
                self.set_value(new_value)
    def set_number_limit(self, lower_limit=None, upper_limit=None, action="ignore", value_type=None):
        limiter=limit.NumberLimit(lower_limit=lower_limit,upper_limit=upper_limit,action=action,value_type=value_type)
        self.change_limiter(limiter)
    def change_formatter(self, formatter):
        self.num_format=formatter
        if self._value is not None:
            self.show_value()
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

    def _coerce_value(self, value):
        while True:
            str_value=self.num_format(value)
            try:
                new_value=self.num_limit(format.str_to_float(str_value))
            except limit.LimitError:
                return value
            if new_value==value:
                return new_value
            value=new_value
    def repr_value(self, value):
        return self.num_format(value)

    value_entered=QtCore.pyqtSignal("PyQt_PyObject")
    value_changed=QtCore.pyqtSignal("PyQt_PyObject")
    def get_value(self):
        return self._value
    def show_value(self, interrupt_edit=False, preserve_cursor_order=True):
        if (not self.hasFocus()) or interrupt_edit:
            if preserve_cursor_order and self.hasFocus():
                cursor_order=self.get_cursor_order()
                self.setText(self.num_format(self._value))
                if cursor_order is not None:
                    self.set_cursor_order(cursor_order)
            else:
                self.setText(self.num_format(self._value))
    def set_value(self, value, notify_value_change=True, interrupt_edit=False, preserve_cursor_order=True):
        value_changed=False
        try:
            value=self._coerce_value(value)
            if self._value!=value:
                self._value=value
                if notify_value_change:
                    self.value_changed.emit(self._value)
                value_changed=True
        except limit.LimitError:
            pass
        self.show_value(interrupt_edit=interrupt_edit,preserve_cursor_order=preserve_cursor_order)
        return value_changed