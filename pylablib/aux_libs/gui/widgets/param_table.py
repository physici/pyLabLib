from ....core.gui.qt.widgets import edit, label as widget_label
from ....core.gui.qt.thread import threadprop
from ....core.gui.qt import values as values_module
from ....core.utils import py3, dictionary

from PyQt4 import QtCore, QtGui

import collections

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)


class ParamTable(QtGui.QWidget):
    def __init__(self, parent=None):
        super(ParamTable, self).__init__(parent)
        self.params={}
        self.v=dictionary.ItemAccessor(self.get_param,self.set_param)
        self.i=dictionary.ItemAccessor(self.get_indicator,self.set_indicator)

    def setupUi(self, name, add_indicator=False, display_table=None, display_table_root=None):
        self.name=name
        self.setObjectName(_fromUtf8(self.name))
        self.formLayout = QtGui.QGridLayout(self)
        self.formLayout.setSizeConstraint(QtGui.QLayout.SetDefaultConstraint)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))
        self.add_indicator=add_indicator
        self.change_focused_control=False
        self.display_table=display_table
        self.display_table_root=display_table_root or self.name

    value_changed=QtCore.pyqtSignal("PyQt_PyObject","PyQt_PyObject")

    ParamRow=collections.namedtuple("ParamRow",["widget","label","value_handler","indicator_handler"])
    def _add_widget(self, name, params):
        self.params[name]=params
        if self.display_table:
            path=(self.display_table_root,name)
            self.display_table.add_handler(path,params.value_handler)
            self.display_table.add_indicator_handler(path,params.indicator_handler)
        changed_signal=params.value_handler.value_changed_signal()
        if changed_signal:
            changed_signal.connect(lambda value: self.value_changed.emit(name,value))
    def add_simple_widget(self, name, widget, label=None, value_handler=None):
        if name in self.params:
            raise KeyError("widget {} already exists".format(name))
        row=self.formLayout.rowCount()
        if label is not None:
            wlabel=QtGui.QLabel(self)
            wlabel.setObjectName(_fromUtf8("{}__label".format(name)))
            self.formLayout.addWidget(wlabel,row,0)
            wlabel.setText(_translate(self.name,label,None))
        else:
            wlabel=None
        value_handler=value_handler or values_module.get_default_value_handler(widget)
        if self.add_indicator:
            windicator=QtGui.QLabel(self)
            windicator.setObjectName(_fromUtf8("{}__indicator".format(name)))
            self.formLayout.addWidget(windicator,row,2)
            indicator_handler=values_module.WidgetLabelIndicatorHandler(windicator,widget=value_handler)
        else:
            indicator_handler=None
        if wlabel is None:
            self.formLayout.addWidget(widget,row,0,1,2)
        else:
            self.formLayout.addWidget(widget,row,1)
        self._add_widget(name,self.ParamRow(widget,wlabel,value_handler,indicator_handler))
        return widget

    def add_custom_widget(self, name, widget, value_handler=None, indicator_handler=None, location=(None,0,1,None)):
        if name in self.params:
            raise KeyError("widget {} already exists".format(name))
        row,col,rowspan,colspan=location
        row=self.formLayout.rowCount() if row is None else row
        rowspan=1 if rowspan is None else rowspan
        col=0 if col is None else col
        if colspan is None:
            colspan=3 if self.add_indicator else 2
        self.formLayout.addWidget(widget,row,col,rowspan,colspan)
        value_handler=value_handler or values_module.get_default_value_handler(widget)
        indicator_handler=indicator_handler or values_module.get_default_indicator_handler(widget)
        self._add_widget(name,self.ParamRow(widget,None,value_handler,indicator_handler))
        return widget

    def add_button(self, name, caption, checkable=False, value=False, label=None):
        widget=QtGui.QPushButton(self)
        widget.setText(_translate(self.name,caption,None))
        widget.setObjectName(_fromUtf8(name))
        widget.setCheckable(checkable)
        widget.setChecked(value)
        return self.add_simple_widget(name,widget,label=label)
    def add_check_box(self, name, caption, value=False, label=None):
        widget=QtGui.QCheckBox(self)
        widget.setText(_translate(self.name,caption,None))
        widget.setObjectName(_fromUtf8(name))
        widget.setChecked(value)
        return self.add_simple_widget(name,widget,label=label)
    def add_text_label(self, name, value=None, label=None):
        widget=QtGui.QLabel(self)
        widget.setObjectName(_fromUtf8(name))
        if value is not None:
            widget.setText(str(value))
        return self.add_simple_widget(name,widget,label=label)
    def add_num_label(self, name, value=None, limiter=None, formatter=None, label=None):
        widget=widget_label.LVNumLabel(self,value=value,num_limit=limiter,num_format=formatter)
        widget.setObjectName(_fromUtf8(name))
        return self.add_simple_widget(name,widget,label=label)
    def add_text_edit(self, name, value=None, label=None):
        widget=edit.LVTextEdit(self,value=value)
        widget.setObjectName(_fromUtf8(name))
        return self.add_simple_widget(name,widget,label=label)
    def add_num_edit(self, name, value=None, limiter=None, formatter=None, label=None):
        widget=edit.LVNumEdit(self,value=value,num_limit=limiter,num_format=formatter)
        widget.setObjectName(_fromUtf8(name))
        return self.add_simple_widget(name,widget,label=label)
    def add_progress_bar(self, name, value=None, label=None):
        widget=QtGui.QProgressBar(self)
        widget.setObjectName(_fromUtf8(name))
        if value is not None:
            widget.setValue(value)
        return self.add_simple_widget(name,widget,label=label)
    def add_combo_box(self, name, value=None, options=None, label=None):
        widget=QtGui.QComboBox(self)
        widget.setObjectName(_fromUtf8(name))
        if options is not None:
            widget.addItems(options)
        if value is not None:
            widget.setCurrentIndex(value)
        return self.add_simple_widget(name,widget,label=label)

    def add_spacer(self, height):
        spacer=QtGui.QSpacerItem(1,height,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)
        self.formLayout.addItem(spacer)
        return spacer
    def add_padding(self, prop=1):
        self.add_spacer(0)
        self.formLayout.setRowStretch(self.formLayout.rowCount(),prop)

    def _set_enabled(self, names=None, enabled=True):
        if isinstance(names,py3.anystring):
            names=[names]
        if names is None:
            names=self.params.keys()
        for name in names:
            self.params[name].widget.setEnabled(enabled)
    def lock(self, names=None):
        self._set_enabled(names,enabled=False)
    def unlock(self, names=None):
        self._set_enabled(names,enabled=True)

    def get_param(self, name):
        return self.params[name].value_handler.get_value()
    def set_param(self, name, value):
        par=self.params[name]
        if self.change_focused_control or not par.widget.hasFocus():
            return par.value_handler.set_value(value)
    def get_all_values(self):
        values={}
        for n in self.params:
            values[n]=self.params[n].value_handler.get_value()
        return values
    def set_all_values(self, values):
        for n in values:
            if n in self.params:
                self.params[n].value_handler.set_value(values[n])

    def get_indicator(self, name):
        indicator_handler=self.params[name].indicator_handler
        if indicator_handler:
            return indicator_handler.get_value()
    def set_indicator(self, name, value):
        indicator_handler=self.params[name].indicator_handler
        if indicator_handler:
            return indicator_handler.set_value(value)
    def update_indicators(self):
        for name in self.params:
            value=self.get_param(name)
            self.set_indicator(name,value)
    
    def __getitem__(self, name):
        return self.params[name].widget
    def __contains__(self, name):
        return name in self.params

TFixedParamTable=collections.namedtuple("FixedParamTable",["v","i"])
def FixedParamTable(v=None,i=None):
    return TFixedParamTable(v=v or {}, i=i or {})


class StatusTable(ParamTable):
    def __init__(self, parent=None):
        ParamTable.__init__(self,parent=parent)

    def add_status_line(self, name, label=None, srcs=None, tags=None, filt=None, make_status=None):
        self.add_text_label(name,label=label)
        def update_text(src, tag, value):
            if make_status is not None:
                text=make_status(src,tag,value)
            else:
                text=value
            self.v[name]=text
        threadprop.current_controller().subscribe(update_text,srcs=srcs,dsts="any",tags=tags,filt=filt,limit_queue=10)