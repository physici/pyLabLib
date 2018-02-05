# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file './param_table.ui'
#
# Created by: PyQt4 UI code generator 4.11.4

from ....core.gui.qt.widgets import edit, label as widget_label
from ....core.gui.qt.thread import threadprop

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
    if hasattr(widget,"get_params"):
        return widget.get_params
    raise ValueError("can't find default getter for widget {}".format(widget))

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
    if hasattr(widget,"set_params"):
        return widget.set_params
    raise ValueError("can't find default setter for widget {}".format(widget))

class ParamTable(QtGui.QWidget):
    def __init__(self, parent=None):
        super(ParamTable, self).__init__()
        self.params={}
        self.v=self.ValueAccessor(self)

    def setupUi(self, name):
        self.name=name
        self.setObjectName(_fromUtf8(self.name))
        self.formLayout = QtGui.QFormLayout(self)
        self.formLayout.setFieldGrowthPolicy(QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))

    ParamRow=collections.namedtuple("ParamRow",["widget","label","getter","setter"])
    def add_widget(self, name, widget, label=None, getter=None, setter=None):
        if name in self.params:
            raise KeyError("widget {} already exists".format(name))
        row=self.formLayout.rowCount()
        if label is not None:
            wlabel=QtGui.QLabel(self)
            wlabel.setObjectName(_fromUtf8("{}__label".format(name)))
            self.formLayout.setWidget(row,QtGui.QFormLayout.LabelRole,wlabel)
            wlabel.setText(_translate(self.name,label,None))
        else:
            wlabel=None
        self.formLayout.setWidget(row,QtGui.QFormLayout.FieldRole,widget)
        self.params[name]=self.ParamRow(widget,wlabel,getter or _get_default_getter(widget),setter or _get_default_setter(widget))
        return widget

    def add_button(self, name, caption, checkable=False, value=False, label=None):
        widget=QtGui.QPushButton(self)
        widget.setText(_translate(self.name,caption,None))
        widget.setObjectName(_fromUtf8(name))
        widget.setCheckable(checkable)
        widget.setChecked(value)
        return self.add_widget(name,widget,label=label)
    def add_text_label(self, name, value=None, label=None):
        widget=QtGui.QLabel(self)
        widget.setObjectName(_fromUtf8(name))
        if value is not None:
            widget.setText(str(value))
        return self.add_widget(name,widget,label=label)
    def add_num_label(self, name, value=None, limiter=None, formatter=None, label=None):
        widget=widget_label.LVNumLabel(self,value=value,num_limit=limiter,num_format=formatter)
        widget.setObjectName(_fromUtf8(name))
        return self.add_widget(name,widget,label=label)
    def add_text_edit(self, name, value=None, label=None):
        widget=edit.LVTextEdit(self,value=value)
        widget.setObjectName(_fromUtf8(name))
        return self.add_widget(name,widget,label=label)
    def add_num_edit(self, name, value=None, limiter=None, formatter=None, label=None):
        widget=edit.LVNumEdit(self,value=value,num_limit=limiter,num_format=formatter)
        widget.setObjectName(_fromUtf8(name))
        return self.add_widget(name,widget,label=label)
    def add_progress_bar(self, name, value=None, label=None):
        widget=QtGui.QProgressBar(self)
        widget.setObjectName(_fromUtf8(name))
        if value is not None:
            widget.setValue(value)
        return self.add_widget(name,widget,label=label)

    def add_spacer(self, height):
        spacer=QtGui.QSpacerItem(1,height,QtGui.QSizePolicy.Minimum,QtGui.QSizePolicy.Expanding)
        self.formLayout.addItem(spacer)

    def get_all_params(self):
        values={}
        for n in self.params:
            values[n]=self.params[n].getter()
    def set_all_params(self, values):
        for n in values:
            if n in self.params:
                self.params[n].setter(values[n])

    def get_param(self, name):
        return self.params[name].getter()
    def set_param(self, name, value):
        return self.params[name].setter(value)
    class ValueAccessor(object):
        def __init__(self, parent):
            object.__init__(self)
            self.parent=parent
        def __getitem__(self, name): return self.parent.get_param(name)
        def __setitem__(self, name, value): return self.parent.set_param(name,value)
    
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