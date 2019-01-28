from ....core.gui.qt.widgets import edit, label as widget_label
from ....core.gui.qt.thread import threadprop
from ....core.gui.qt import values as values_module, utils
from ....core.utils import py3, dictionary

from PyQt5 import QtCore, QtWidgets

import collections

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtWidgets.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtWidgets.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtWidgets.QApplication.translate(context, text, disambig)


class ParamTable(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ParamTable, self).__init__(parent)
        self.params={}
        self.v=dictionary.ItemAccessor(self.get_value,self.set_value)
        self.i=dictionary.ItemAccessor(self.get_indicator,self.set_indicator)
        self.w=dictionary.ItemAccessor(self.get_widget)

    def setupUi(self, name, add_indicator=False, display_table=None, display_table_root=None):
        self.name=name
        self.setObjectName(_fromUtf8(self.name))
        self.formLayout = QtWidgets.QGridLayout(self)
        self.formLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.formLayout.setContentsMargins(5,5,5,5)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))
        self.add_indicator=add_indicator
        self.change_focused_control=False
        if display_table is None:
            self.display_table=values_module.IndicatorValuesTable()
            self.display_table_root=""
        else:
            self.display_table=display_table
            self.display_table_root=display_table_root if display_table_root is not None else self.name

    value_changed=QtCore.pyqtSignal("PyQt_PyObject","PyQt_PyObject")

    def _normalize_location(self, location, default=(None,0,1,1)):
        location+=(None,)*(4-len(location))
        location=[d if l is None else l for (l,d) in zip(location,default)]
        row,col,rowspan,colspan=location
        row_cnt=self.formLayout.rowCount()
        row=row_cnt if row is None else (row%row_cnt)
        return row,col,rowspan,colspan
    ParamRow=collections.namedtuple("ParamRow",["widget","label","value_handler","indicator_handler"])
    def _add_widget(self, name, params):
        self.params[name]=params
        path=(self.display_table_root,name)
        self.display_table.add_handler(path,params.value_handler)
        self.display_table.add_indicator_handler(path,params.indicator_handler)
        changed_signal=params.value_handler.value_changed_signal()
        if changed_signal:
            changed_signal.connect(lambda value: self.value_changed.emit(name,value))
    def add_simple_widget(self, name, widget, label=None, value_handler=None, add_indicator=None, location=(None,0)):
        if name in self.params:
            raise KeyError("widget {} already exists".format(name))
        row,col,rowspan,_=self._normalize_location(location)
        if label is not None:
            wlabel=QtWidgets.QLabel(self)
            wlabel.setObjectName(_fromUtf8("{}__label".format(name)))
            self.formLayout.addWidget(wlabel,row,col,rowspan,1)
            wlabel.setText(_translate(self.name,label,None))
        else:
            wlabel=None
        value_handler=value_handler or values_module.get_default_value_handler(widget)
        if add_indicator is None:
            add_indicator=self.add_indicator
        if add_indicator:
            windicator=QtWidgets.QLabel(self)
            windicator.setObjectName(_fromUtf8("{}__indicator".format(name)))
            self.formLayout.addWidget(windicator,row,col+2,rowspan,1)
            indicator_handler=values_module.WidgetLabelIndicatorHandler(windicator,widget=value_handler)
        else:
            indicator_handler=None
        if wlabel is None:
            self.formLayout.addWidget(widget,row,col,rowspan,2 if add_indicator else 3)
        else:
            self.formLayout.addWidget(widget,row,col+1,rowspan,1 if add_indicator else 2)
        self._add_widget(name,self.ParamRow(widget,wlabel,value_handler,indicator_handler))
        return value_handler

    def add_custom_widget(self, name, widget, value_handler=None, indicator_handler=None, location=(None,0,1,None)):
        if name in self.params:
            raise KeyError("widget {} already exists".format(name))
        location=self._normalize_location(location,default=(None,0,1,3))
        self.formLayout.addWidget(widget,*location)
        value_handler=value_handler or values_module.get_default_value_handler(widget)
        indicator_handler=indicator_handler or values_module.get_default_indicator_handler(widget)
        self._add_widget(name,self.ParamRow(widget,None,value_handler,indicator_handler))
        return value_handler

    def add_button(self, name, caption, checkable=False, value=False, label=None, add_indicator=None, location=(None,0)):
        widget=QtWidgets.QPushButton(self)
        widget.setText(_translate(self.name,caption,None))
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        widget.setCheckable(checkable)
        widget.setChecked(value)
        return self.add_simple_widget(name,widget,label=label,add_indicator=add_indicator,location=location)
    def add_check_box(self, name, caption, value=False, label=None, add_indicator=None, location=(None,0)):
        widget=QtWidgets.QCheckBox(self)
        widget.setText(_translate(self.name,caption,None))
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        widget.setChecked(value)
        return self.add_simple_widget(name,widget,label=label,add_indicator=add_indicator,location=location)
    def add_text_label(self, name, value=None, label=None, location=(None,0)):
        widget=QtWidgets.QLabel(self)
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        if value is not None:
            widget.setText(str(value))
        return self.add_simple_widget(name,widget,label=label,add_indicator=False,location=location)
    def add_num_label(self, name, value=None, limiter=None, formatter=None, label=None, location=(None,0)):
        widget=widget_label.LVNumLabel(self,value=value,num_limit=limiter,num_format=formatter)
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        return self.add_simple_widget(name,widget,label=label,add_indicator=False,location=location)
    def add_text_edit(self, name, value=None, label=None, add_indicator=None, location=(None,0)):
        widget=edit.LVTextEdit(self,value=value)
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        return self.add_simple_widget(name,widget,label=label,add_indicator=add_indicator,location=location)
    def add_num_edit(self, name, value=None, limiter=None, formatter=None, label=None, add_indicator=None, location=(None,0)):
        widget=edit.LVNumEdit(self,value=value,num_limit=limiter,num_format=formatter)
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        return self.add_simple_widget(name,widget,label=label,add_indicator=add_indicator,location=location)
    def add_progress_bar(self, name, value=None, label=None):
        widget=QtWidgets.QProgressBar(self)
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        if value is not None:
            widget.setValue(value)
        return self.add_simple_widget(name,widget,label=label)
    def add_combo_box(self, name, value=None, options=None, label=None, add_indicator=None):
        widget=QtWidgets.QComboBox(self)
        widget.setObjectName(_fromUtf8(self.name+"_"+name))
        if options is not None:
            widget.addItems(options)
        if value is not None:
            widget.setCurrentIndex(value)
        return self.add_simple_widget(name,widget,label=label,add_indicator=add_indicator)

    def add_spacer(self, height, width=1, location=(None,0)):
        spacer=QtWidgets.QSpacerItem(width,height,QtWidgets.QSizePolicy.Minimum,QtWidgets.QSizePolicy.Minimum)
        location=self._normalize_location(location)
        self.formLayout.addItem(spacer,*location)
        return spacer
    def add_label(self, text, location=(None,0)):
        label=QtWidgets.QLabel(self)
        label.setText(str(text))
        label.setAlignment(QtCore.Qt.AlignLeft)
        location=self._normalize_location(location)
        self.formLayout.addWidget(label,*location)
        return label
    def add_padding(self, prop=1):
        self.add_spacer(0)
        self.formLayout.setRowStretch(self.formLayout.rowCount(),prop)

    def lock(self, names=None, locked=True):
        if isinstance(names,py3.anystring):
            names=[names]
        if names is None:
            names=self.params.keys()
        for name in names:
            self.params[name].widget.setEnabled(not locked)

    def get_value(self, name):
        return self.display_table.get_value((self.display_table_root,name))
    def set_value(self, name, value):
        par=self.params[name]
        if self.change_focused_control or not par.widget.hasFocus():
            return self.display_table.set_value((self.display_table_root,name),value)
    def get_all_values(self):
        return self.display_table.get_all_values(root=self.display_table_root)
    def set_all_values(self, values):
        return self.display_table.set_all_values(values,root=self.display_table_root)

    def get_handler(self, name):
        return self.params[name].value_handler
    def get_widget(self, name):
        return self.params[name].widget
    def changed_event(self, name):
        return self.params[name].value_handler.value_changed_signal()

    def get_indicator(self, name):
        return self.display_table.get_indicator((self.display_table_root,name))
    def set_indicator(self, name, value):
        return self.display_table.set_indicator((self.display_table_root,name),value)
    def update_indicators(self):
        return self.display_table.update_indicators(root=self.display_table_root)

    def clear(self):
        for name in self.params:
            path=(self.display_table_root,name)
            self.display_table.remove_handler(path)
            self.display_table.remove_indicator_handler(path)
        self.params={}
        utils.clean_layout(self.formLayout,delete_layout=True)
        self.formLayout = QtWidgets.QGridLayout(self)
        self.formLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.formLayout.setContentsMargins(5,5,5,5)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))

    
    def __getitem__(self, name):
        return self.get_handler(name)
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