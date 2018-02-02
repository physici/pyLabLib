from PyQt4 import QtGui,QtCore
from ... import format,limit

class LVNumLabel(QtGui.QLabel):
    def __init__(self, parent, value=None, num_limit=None, num_format=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.num_limit=limit.as_limiter(num_limit) if num_limit is not None else limit.NumberLimit()
        self.num_format=format.as_formatter(num_format) if num_format is not None else format.FloatFormatter()
        self._value=None
        if value is not None:
            self.set_value(None)
        # self.textChanged.connect(self._on_change_text)
    def _on_change_text(self, text):
        if not self.isModified():
            try:
                value=format.str_to_float(str(self.text()))
                self.set_value(value)
            except ValueError:
                pass

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

    def get_value(self):
        return self._value
    def set_value(self, value):
        if value is not None:
            try:
                value=self.num_limit(value)
                self._value=value
                self.setText(self.num_format(self._value))
                return True
            except limit.LimitError:
                pass
        if self._value is not None:
            self.setText(self.num_format(self._value))
        return False