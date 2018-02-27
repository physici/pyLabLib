# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './param_table.ui'
#
# Created by: PyQt4 UI code generator 4.11.4

from ....core.gui.qt.widgets import edit, label as widget_label
from ....core.gui.qt.thread import threadprop
from ....core.utils import py3

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


def _get_default_getter(widget):
    if isinstance(widget,(edit.LVNumEdit,edit.LVTextEdit,widget_label.LVNumLabel)):
        return widget.get_value
    if isinstance(widget,(QtGui.QLineEdit,QtGui.QLabel)):
        return lambda: str(widget.text())
    if isinstance(widget,(QtGui.QCheckBox,QtGui.QPushButton)):
        return widget.isChecked
    if isinstance(widget,(QtGui.QProgressBar)):
        return widget.value
    if isinstance(widget,(QtGui.QComboBox)):
        return widget.currentIndex
    if hasattr(widget,"get_value"):
        return widget.get_value
    if hasattr(widget,"get_all_params"):
        return widget.get_all_params
    raise ValueError("can't find default getter for widget {}".format(widget))

def _get_default_presenter(widget):
    if isinstance(widget,(edit.LVNumEdit,edit.LVTextEdit,widget_label.LVNumLabel)):
        return lambda v: widget.num_format(v)
    if isinstance(widget,QtGui.QCheckBox):
        return lambda v: "On" if v else "Off"
    if isinstance(widget,QtGui.QPushButton):
        def presenter(v):
            if widget.isCheckable():
                return "On" if v else "Off"
            else:
                return ""
        return presenter
    if isinstance(widget,(QtGui.QComboBox)):
        return lambda v: str(widget.itemText(v))
    return lambda v: str(v)

def _get_default_setter(widget):
    if isinstance(widget,(edit.LVNumEdit,edit.LVTextEdit,widget_label.LVNumLabel)):
        return widget.set_value
    if isinstance(widget,(QtGui.QLineEdit,QtGui.QLabel)):
        return lambda x: widget.setText(str(x))
    if isinstance(widget,(QtGui.QCheckBox,QtGui.QPushButton)):
        return widget.setChecked
    if isinstance(widget,(QtGui.QProgressBar)):
        return lambda x: widget.setValue(int(x))
    if isinstance(widget,(QtGui.QComboBox)):
        return widget.setCurrentIndex
    if hasattr(widget,"set_value"):
        return widget.set_value
    if hasattr(widget,"set_all_params"):
        return widget.set_all_params
    raise ValueError("can't find default setter for widget {}".format(widget))

def _get_changed_event(widget):
    if isinstance(widget,(edit.LVNumEdit,edit.LVTextEdit)):
        return widget.value_changed
    if isinstance(widget,QtGui.QLineEdit):
        return widget.textChanged
    if isinstance(widget,QtGui.QCheckBox):
        return widget.stateChanged
    if isinstance(widget,QtGui.QPushButton):
        return widget.clicked
    if isinstance(widget,(QtGui.QComboBox)):
        return widget.currentIndexChanged
    return None

class ParamTable(QtGui.QWidget):
    def __init__(self, parent=None):
        super(ParamTable, self).__init__()
        self.params={}
        self.v=self.ValueAccessor(self)
        self.i=self.IndicatorAccessor(self)

    def setupUi(self, name, add_indicator=False, change_focused_control=False):
        self.name=name
        self.setObjectName(_fromUtf8(self.name))
        self.formLayout = QtGui.QGridLayout(self)
        self.formLayout.setSizeConstraint(QtGui.QLayout.SetDefaultConstraint)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))
        self.add_indicator=add_indicator
        self.change_focused_control=change_focused_control

    changed=QtCore.pyqtSignal("PyQt_PyObject","PyQt_PyObject")

    ParamRow=collections.namedtuple("ParamRow",["widget","label","indicator","getter","setter","presenter"])
    def add_simple_widget(self, name, widget, label=None, getter=None, setter=None, presenter=None):
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
        if self.add_indicator:
            windicator=QtGui.QLabel(self)
            windicator.setObjectName(_fromUtf8("{}__indicator".format(name)))
            self.formLayout.addWidget(windicator,row,2)
        else:
            windicator=None
        if wlabel is None:
            self.formLayout.addWidget(widget,row,0,1,2)
        else:
            self.formLayout.addWidget(widget,row,1)
        getter=getter or _get_default_getter(widget)
        setter=setter or _get_default_setter(widget)
        presenter=presenter or _get_default_presenter(widget)
        self.params[name]=self.ParamRow(widget,wlabel,windicator,getter,setter,presenter)
        changed_event=_get_changed_event(widget)
        if changed_event:
            changed_event.connect(lambda value: self.changed.emit(name,value))
        return widget

    # def add_custom_widget(self, name, widget, getter=None, setter=None, location=(None,0,1,None)):
    #     if name in self.params:
    #         raise KeyError("widget {} already exists".format(name))
    #     row,col,rowspan,colspan=location
    #     row=self.formLayout.rowCount() if row is None else row
    #     rowspan=1 if rowspan is None else rowspan
    #     col=0 if col is None else col
    #     colspan=3 if self.add_indicator else 2
    #     self.formLayout.addWidget(widget,row,col,rowspan,colspan)
    #     getter=getter or _get_default_getter(widget)
    #     setter=setter or _get_default_setter(widget)
    #     presenter=None
    #     self.params[name]=self.ParamRow(widget,None,None,getter,setter,presenter)
    #     changed_event=_get_changed_event(widget)
    #     if changed_event:
    #         changed_event.connect(lambda value: self.changed.emit(name,value))
    #     return widget

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
        return self.params[name].getter()
    def set_param(self, name, value):
        par=self.params[name]
        if self.change_focused_control or not par.widget.hasFocus():
            return par.setter(value)
    def get_all_params(self):
        values={}
        for n in self.params:
            values[n]=self.params[n].getter()
        return values
    def set_all_params(self, values):
        for n in values:
            if n in self.params:
                self.params[n].setter(values[n])

    def get_indicator(self, name):
        indicator=self.params[name].indicator
        if indicator:
            return str(indicator.text())
    def set_indicator(self, name, value):
        par=self.params[name]
        indicator,presenter=par.indicator,par.presenter
        if indicator:
            indicator.setText(str(presenter(value)))
    def update_indicators(self):
        for name in self.params:
            value=self.get_param(name)
            self.set_indicator(name,value)
    

    class ValueAccessor(object):
        def __init__(self, parent):
            object.__init__(self)
            self.parent=parent
        def __getitem__(self, name): return self.parent.get_param(name)
        def __setitem__(self, name, value): return self.parent.set_param(name,value)
    class IndicatorAccessor(object):
        def __init__(self, parent):
            object.__init__(self)
            self.parent=parent
        def __getitem__(self, name): return self.parent.get_indicator(name)
        def __setitem__(self, name, value): return self.parent.set_indicator(name,value)
    
    def __getitem__(self, name):
        return self.params[name].widget
    def __contains__(self, name):
        return name in self.params




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