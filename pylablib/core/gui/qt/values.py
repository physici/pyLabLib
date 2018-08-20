from .widgets import edit
from PyQt5 import QtCore, QtWidgets
from ...utils import dictionary, py3, string
from ...utils.functions import FunctionSignature


def build_children_tree(root, types_include, is_atomic=None, is_excluded=None, self_node="#"):
    is_atomic=is_atomic or (lambda _: False)
    is_excluded=is_excluded or (lambda _: False)
    children=dictionary.Dictionary()
    if not (is_atomic and is_atomic(root)):
        for ch in root.findChildren(QtCore.QObject):
            chn=str(ch.objectName())
            if (ch.parent() is root) and chn and not is_excluded(ch) and (chn not in children):
                children[str(ch.objectName())]=build_children_tree(ch,types_include,is_atomic,is_excluded,self_node)
        if isinstance(root,tuple(types_include)):
            children[self_node]=root
    else:
        children[self_node]=root
    return children


def has_methods(widget, methods_sets):
    for ms in methods_sets:
        if not any([hasattr(widget,m) for m in ms]):
            return False
    return True

def get_method_kind(method, add_args=0):
    if method is None:
        return None
    fsig=FunctionSignature.from_function(method)
    if len(fsig.arg_names)>=1+add_args and fsig.arg_names[0]=="name":
        return "named"
    else:
        return "simple"


class IValueHandler(object):
    def __init__(self, widget):
        object.__init__(self)
        self.widget=widget
    def get_value(self, name=None):
        raise NotImplementedError("IValueHandler.get_value")
    def set_value(self, value, name=None):
        raise NotImplementedError("IValueHandler.set_value")
    def repr_value(self, value, name=None):
        return str(value)
    def value_changed_signal(self):
        if hasattr(self.widget,"value_changed"):
            return self.widget.value_changed
        return None

_default_getters=("get_value","get_all_values")
_default_setters=("set_value","set_all_values")
class IDefaultValueHandler(IValueHandler):
    def __init__(self, widget, default_name=None):
        IValueHandler.__init__(self,widget)
        self.get_value_kind=get_method_kind(getattr(self.widget,"get_value",None))
        self.get_all_values_kind="simple" if hasattr(self.widget,"get_all_values") else None
        if not (self.get_value_kind or self.get_all_values_kind):
            raise ValueError("can't find default getter for widget {}".format(self.widget))
        self.set_value_kind=get_method_kind(getattr(self.widget,"set_value",None),add_args=1)
        self.set_all_values_kind="simple" if hasattr(self.widget,"set_all_values") else None
        if not (self.set_value_kind or self.set_all_values_kind):
            raise ValueError("can't find default setter for widget {}".format(self.widget))
        self.repr_value_kind=get_method_kind(getattr(self.widget,"repr_value",None),add_args=1)
        self.default_name=default_name
    def get_value(self, name=None):
        if not name:
            if self.get_value_kind=="simple":
                return self.widget.get_value()
            elif self.get_all_values_kind=="simple":
                return self.widget.get_all_values()
            elif self.get_value_kind=="named":
                return self.widget.get_value(self.default_name)
        else:
            if self.get_value_kind=="named":
                return self.widget.get_value(name)
            elif self.get_all_values_kind=="simple":
                return self.widget.get_all_values()[name]
        raise ValueError("can't find getter for widget {} with name {}".format(self.widget,name))
    def set_value(self, value, name=None):
        if not name:
            if self.set_value_kind=="simple":
                return self.widget.set_value(value)
            elif self.set_value_kind=="named":
                return self.widget.set_value(self.default_name,value)
            elif self.set_all_values_kind=="simple":
                return self.widget.set_all_values(value)
        else:
            if self.set_value_kind=="named":
                return self.widget.set_value(name,value)
            elif self.set_all_values_kind=="simple":
                if isinstance(name,list):
                    name="/".join(name)
                return self.widget.set_all_values({name:value})
        raise ValueError("can't find setter for widget {} with name {}".format(self.widget,name))
    def repr_value(self, value, name=None):
        if not name:
            if self.repr_value_kind=="simple":
                return self.widget.repr_value(value)
            elif self.repr_value_kind=="named":
                return self.widget.repr_value(self.default_name,value)
        else:
            if self.repr_value_kind=="named":
                return self.widget.repr_value(value)
        return str(value)

class ISingleValueHandler(IValueHandler):
    def __init__(self, widget):
        IValueHandler.__init__(self,widget)
    def get_single_value(self):
        raise ValueError("can't find default getter for widget {}".format(self.widget))
    def get_value(self, name=None):
        if name:
            raise KeyError("no value with name {}".format(name))
        return self.get_single_value()
    def set_single_value(self, value):
        raise ValueError("can't find default setter for widget {}".format(self.widget))
    def set_value(self, value, name=None):
        if name:
            raise KeyError("no value with name {}".format(name))
        return self.set_single_value(value)
    def repr_single_value(self, value):
        if hasattr(self.widget,"repr_value"):
            return self.widget.repr_value(value)
        return str(value)
    def repr_value(self, value, name=None):
        if name:
            raise KeyError("no value with name {}".format(name))
        return self.repr_single_value(value)

class LineEditValueHandler(ISingleValueHandler):
    def get_single_value(self):
        return str(self.widget.text())
    def set_single_value(self, value):
        return self.widget.setText(str(value))
    def value_changed_signal(self):
        return self.widget.textChanged
class LabelValueHandler(ISingleValueHandler):
    def get_single_value(self):
        return str(self.widget.text())
    def set_single_value(self, value):
        return self.widget.setText(str(value))
class IBoolValueHandler(ISingleValueHandler):
    def __init__(self, widget, labels=("Off","On")):
        ISingleValueHandler.__init__(self,widget)
        self.labels=labels
    def repr_single_value(self, value):
        return self.labels[value]
class CheckboxValueHandler(IBoolValueHandler):
    def get_single_value(self):
        return self.widget.isChecked()
    def set_single_value(self, value):
        return self.widget.setChecked(value)
    def value_changed_signal(self):
        return self.widget.stateChanged
class PushButtonValueHandler(IBoolValueHandler):
    def get_single_value(self):
        return self.widget.isChecked()
    def set_single_value(self, value):
        return self.widget.setChecked(value)
    def value_changed_signal(self):
        return self.widget.toggled
    def repr_single_value(self, value):
        if not self.widget.isCheckable():
            return ""
        return IBoolValueHandler.repr_single_value(self,value)
class ToolButtonValueHandler(IBoolValueHandler):
    def get_single_value(self):
        return self.widget.isChecked()
    def set_single_value(self, value):
        return self.widget.setChecked(value)
    def value_changed_signal(self):
        return self.widget.triggered
    def repr_single_value(self, value):
        if not self.widget.isCheckable():
            return ""
        return IBoolValueHandler.repr_single_value(self,value)
class ComboBoxValueHandler(ISingleValueHandler):
    def get_single_value(self):
        return self.widget.currentIndex()
    def set_single_value(self, value):
        return self.widget.setCurrentIndex(value)
    def value_changed_signal(self):
        return self.widget.currentIndexChanged
    def repr_single_value(self, value):
        if isinstance(value,py3.anystring):
            return value
        return self.widget.itemText(value)
class ProgressBarValueHandler(ISingleValueHandler):
    def get_single_value(self):
        return self.widget.value()
    def set_single_value(self, value):
        return self.widget.setValue(int(value))

def is_handled_widget(widget):
    return has_methods(widget,[_default_getters,_default_setters])

def get_default_value_handler(widget):
    if is_handled_widget(widget):
        return IDefaultValueHandler(widget)
    if isinstance(widget,QtWidgets.QLineEdit):
        return LineEditValueHandler(widget)
    if isinstance(widget,QtWidgets.QLabel):
        return LabelValueHandler(widget)
    if isinstance(widget,QtWidgets.QCheckBox):
        return CheckboxValueHandler(widget)
    if isinstance(widget,QtWidgets.QPushButton):
        return PushButtonValueHandler(widget)
    if isinstance(widget,(QtWidgets.QComboBox)):
        return ComboBoxValueHandler(widget)
    if isinstance(widget,QtWidgets.QProgressBar):
        return ProgressBarValueHandler(widget)
    return IValueHandler(widget)



class ValuesTable(object):
    def __init__(self):
        object.__init__(self)
        self.handlers=dictionary.Dictionary()
        self.v=dictionary.ItemAccessor(self.get_value,self.set_value)

    def add_handler(self, name, handler):
        self.handlers[name]=handler
        return handler
    def remove_handler(self, name):
        del self.handlers[name]
    def add_widget(self, name, widget):
        return self.add_handler(name,get_default_value_handler(widget))
    def add_table(self, name, table):
        return self.add_handler(name,IDefaultValueHandler(table))
    _default_value_types=(edit.LVTextEdit,edit.LVNumEdit,QtWidgets.QLineEdit,QtWidgets.QCheckBox,QtWidgets.QPushButton,QtWidgets.QComboBox)
    def add_all_children(self, root, root_name=None, types_include=None, types_exclude=(), names_exclude=None):
        name_filt=string.sfregex(exclude=names_exclude)
        def is_excluded(w):
            return isinstance(w,types_exclude) or not name_filt(str(w.objectName()))
        types_include=types_include or self._default_value_types
        tree=build_children_tree(root,types_include,is_atomic=is_handled_widget,is_excluded=is_excluded)
        for path,widget in tree.iternodes(include_path=True):
            if path[-1]=="#":
                path=path[:-1]
                if root_name is not None:
                    path=[root_name]+path[1:]
                name="/".join([p for p in path if p])
                self.add_widget(name,widget)

    def get_value(self, name):
        path,subpath=self.handlers.get_max_prefix(name,kind="leaf")
        if path is None:
            raise KeyError("missing handler {}".format(name))
        return self.handlers[path].get_value(subpath)
    def get_all_values(self):
        values=dictionary.Dictionary()
        for n in self.handlers.paths():
            values[n]=self.get_value(n)
        return values
    def set_value(self, name, value):
        path,subpath=self.handlers.get_max_prefix(name,kind="leaf")
        if path is None:
            raise KeyError("missing handler {}".format(name))
        return self.handlers[path].set_value(value,subpath)
    def set_all_values(self, values):
        for n,v in dictionary.as_dictionary(values).iternodes(to_visit="all",topdown=True,include_path=True):
            if self.handlers.has_entry(n,kind="leaf"):
                self.handlers[n].set_value(v)
            
    def repr_value(self, name, value):
        path,subpath=self.handlers.get_max_prefix(name,kind="leaf")
        if path is None:
            raise KeyError("missing handler {}".format(name))
        return self.handlers[path].repr_value(value,subpath)
    def changed_event(self, name):
        return self.handlers[name].value_changed_signal()
    def update_value(self, name):
        changed_event=self.handlers[name].value_changed_signal()
        if changed_event:
            changed_event.emit(self.get_value(name))



class IIndicatorHandler(object):
    def get_value(self, name=None):
        raise NotImplementedError("IIndicatorHandler.get_value")
    def set_value(self, value, name=None):
        raise NotImplementedError("IIndicatorHandler.set_value")
_default_indicator_getters=("get_indicator",)
_default_indicator_setters=("set_indicator",)
class IDefaultIndicatorHandler(IIndicatorHandler):
    def __init__(self, widget, default_name=None):
        IIndicatorHandler.__init__(self)
        self.widget=widget
        self.get_indicator_kind=get_method_kind(getattr(self.widget,"get_indicator",None))
        if not self.get_indicator_kind:
            raise ValueError("can't find default indicator getter for widget {}".format(self.widget))
        self.set_indicator_kind=get_method_kind(getattr(self.widget,"get_indicator",None),add_args=1)
        if not self.set_indicator_kind:
            raise ValueError("can't find default indicator setter for widget {}".format(self.widget))
        self.default_name=default_name
    def get_value(self, name=None):
        if not name:
            if self.get_indicator_kind=="simple":
                return self.widget.get_indicator()
            elif self.get_indicator_kind=="named":
                return self.widget.get_indicator(self.default_name)
        else:
            if self.get_indicator_kind=="named":
                return self.widget.get_indicator()
        raise ValueError("can't find indicator getter for widget {} with name {}".format(self.widget,name))
    def set_value(self, value, name=None):
        if not name:
            if self.set_indicator_kind=="simple":
                return self.widget.set_indicator(value)
            elif self.set_indicator_kind=="named":
                return self.widget.set_indicator(self.default_name,value)
        else:
            if self.set_indicator_kind=="named":
                return self.widget.set_indicator(name,value)
        raise ValueError("can't find indicator setter for widget {} with name {}".format(self.widget,name))
class FuncLabelIndicatorHandler(IIndicatorHandler):
    def __init__(self, label, repr_func=None, repr_value_name=None):
        IIndicatorHandler.__init__(self)
        if not isinstance(label,IValueHandler):
            label=get_default_value_handler(label)
        self.label_handler=label
        self.repr_func=repr_func
        self.repr_func_kind=get_method_kind(repr_func,add_args=1)
        self.repr_value_name=repr_value_name
    def get_value(self, name=None):
        if name:
            raise KeyError("no indicator value with name {}".format(name))
        return self.label_handler.get_value()
    def repr_value(self, value, name=None):
        if name is None:
            if self.repr_func_kind is None:
                return str(value)
            elif self.repr_func_kind=="simple":
                return self.repr_func(value)
            else:
                return self.repr_func(self.repr_value_name,value)
        elif self.repr_func_kind=="named":
            return self.repr_func(name,value)
        raise KeyError("no indicator value with name {}".format(name))
    def set_value(self, value, name=None):
        return self.label_handler.set_value(self.repr_value(value,name=name))
class WidgetLabelIndicatorHandler(IIndicatorHandler):
    def __init__(self, label, widget=None, repr_value_name=None):
        IIndicatorHandler.__init__(self)
        if not isinstance(label,IValueHandler):
            label=get_default_value_handler(label)
        self.label_handler=label
        if widget and not isinstance(widget,IValueHandler):
            widget=get_default_value_handler(widget)
        self.widget_handler=widget
        self.repr_value_name=repr_value_name
    def get_value(self, name=None):
        if name:
            raise KeyError("no indicator value with name {}".format(name))
        return self.label_handler.get_value()
    def repr_value(self, value, name=None):
        if self.widget_handler:
            return self.widget_handler.repr_value(value,name=self.repr_value_name if name is None else name)
        if name:
            raise KeyError("no indicator value with name {}".format(name))
        return str(value)
    def set_value(self, value, name=None):
        return self.label_handler.set_value(self.repr_value(value,name=name))

def get_default_indicator_handler(widget, label=None):
    if label is not None:
        return WidgetLabelIndicatorHandler(label,widget)
    if has_methods(widget,[_default_indicator_getters,_default_indicator_setters]):
        return IDefaultIndicatorHandler(widget)
    return None


class IndicatorValuesTable(ValuesTable):
    def __init__(self):
        ValuesTable.__init__(self)
        self.indicator_handlers=dictionary.Dictionary()
        self.i=dictionary.ItemAccessor(self.get_indicator,self.set_indicator)
    def add_indicator_handler(self, name, handler, ind_name="__default__"):
        if handler is not None:
            self.indicator_handlers[name,ind_name]=handler
            return handler
        return None
    def remove_indicator_handler(self, name):
        del self.indicator_handlers[name]
    def add_widget_indicator(self, name, widget, label=None):
        return self.add_indicator_handler(name,get_default_indicator_handler(widget,label))
    def add_label_indicator(self, name, label, repr_func=None):
        return self.add_indicator_handler(name,FuncLabelIndicatorHandler(label,repr_func=repr_func))

    def set_indicator(self, name, value, ind_name=None):
        path,subpath=self.indicator_handlers.get_max_prefix(name)
        if path is None:
            raise KeyError("missing handler {}".format(name))
        if len(subpath)>0:
            return self.indicator_handlers[path].set_indicator(subpath,value,ind_name=ind_name)
        if ind_name is None:
            for i in self.indicator_handlers[path].iternodes():
               i.set_value(value) 
        else:
            return self.indicator_handlers[path][ind_name].set_value(value)
    def get_indicator(self, name, ind_name="__default__"):
        path,subpath=self.indicator_handlers.get_max_prefix(name)
        if path is None:
            raise KeyError("missing handler {}".format(name))
        if len(subpath)>0:
            return self.indicator_handlers[path].get_indicator(subpath,ind_name=ind_name)
        return self.indicator_handlers[path][ind_name].get_value()
    def update_indicators(self):
        for n in self.handlers.paths():
            if n in self.indicator_handlers:
                self.set_indicator(n,self.get_value(n))