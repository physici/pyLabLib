from .widgets import edit
from PyQt4 import QtCore, QtGui
from ...utils import dictionary, py3, string


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


_default_getters=("get_value","get_all_values")
_default_setters=("set_value","set_all_values")
class IValueHandler(object):
    def __init__(self, widget, getters=None, setters=None):
        object.__init__(self)
        self.widget=widget
        self.getters=getters or _default_getters
        self.setters=setters or _default_setters
    def get_value(self):
        for g in self.getters:
            if hasattr(self.widget,g):
                return getattr(self.widget,g)()
        raise ValueError("can't find default getter for widget {}".format(self.widget))
    def set_value(self, value):
        for s in self.setters:
            if hasattr(self.widget,s):
                return getattr(self.widget,s)(value)
        raise ValueError("can't find default setter for widget {}".format(self.widget))
    def repr_value(self, value):
        if hasattr(self.widget,"repr_value"):
            return self.widget.repr_value(value)
        return str(value)
    def value_changed_signal(self):
        if hasattr(self.widget,"value_changed"):
            return self.widget.value_changed
        return None

class LineEditValueHandler(IValueHandler):
    def get_value(self):
        return str(self.widget.text())
    def set_value(self, value):
        return self.widget.setText(str(value))
    def value_changed_signal(self):
        return self.widget.textChanged
class LabelValueHandler(IValueHandler):
    def get_value(self):
        return str(self.widget.text())
    def set_value(self, value):
        return self.widget.setText(str(value))
class BoolValueHandler(IValueHandler):
    def __init__(self, widget, labels=("Off","On")):
        IValueHandler.__init__(self,widget)
        self.labels=labels
    def repr_value(self, value):
        return self.labels[value]
class CheckboxValueHandler(BoolValueHandler):
    def get_value(self):
        return self.widget.isChecked()
    def set_value(self, value):
        return self.widget.setChecked(value)
    def value_changed_signal(self):
        return self.widget.stateChanged
class PushButtonValueHandler(BoolValueHandler):
    def get_value(self):
        return self.widget.isChecked()
    def set_value(self, value):
        return self.widget.setChecked(value)
    def value_changed_signal(self):
        return self.widget.toggled
    def repr_value(self, value):
        if not self.widget.isCheckable():
            return ""
        return BoolValueHandler.repr_value(self,value)
class ComboBoxValueHandler(IValueHandler):
    def get_value(self):
        return self.widget.currentIndex()
    def set_value(self, value):
        return self.widget.setCurrentIndex(value)
    def value_changed_signal(self):
        return self.widget.currentIndexChanged
    def repr_value(self, value):
        if isinstance(value,py3.anystring):
            return value
        return self.widget.itemText(value)
class ProgressBarValueHandler(IValueHandler):
    def get_value(self):
        return self.widget.value()
    def set_value(self, value):
        return self.widget.setValue(int(value))

def is_handled_widget(widget):
    return has_methods(widget,[_default_getters,_default_setters])

def get_default_value_handler(widget):
    if is_handled_widget(widget):
        return IValueHandler(widget)
    if isinstance(widget,QtGui.QLineEdit):
        return LineEditValueHandler(widget)
    if isinstance(widget,QtGui.QLabel):
        return LabelValueHandler(widget)
    if isinstance(widget,QtGui.QCheckBox):
        return CheckboxValueHandler(widget)
    if isinstance(widget,QtGui.QPushButton):
        return PushButtonValueHandler(widget)
    if isinstance(widget,(QtGui.QComboBox)):
        return ComboBoxValueHandler(widget)
    if isinstance(widget,QtGui.QProgressBar):
        return ProgressBarValueHandler(widget)
    return IValueHandler(widget)



class ValuesTable(object):
    def __init__(self):
        object.__init__(self)
        self.handlers=dictionary.Dictionary()
        self.v=dictionary.ItemAccessor(self.get_value,self.set_value)

    def add_handler(self, name, handler):
        self.handlers[name]=handler
    def add_widget(self, name, widget):
        self.add_handler(name,get_default_value_handler(widget))
    _default_value_types=(edit.LVTextEdit,edit.LVNumEdit,QtGui.QLineEdit,QtGui.QCheckBox,QtGui.QPushButton,QtGui.QComboBox)
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
        return self.handlers[name].get_value()
    def get_all_values(self):
        values=dictionary.Dictionary()
        for n,_ in self.handlers.iternodes(include_path=True):
            values[n]=self.get_value(n)
        return values
    def set_value(self, name, value):
        return self.handlers[name].set_value(value)
    def set_all_values(self, values):
        for n,v in dictionary.as_dictionary(values).iternodes(to_visit="all",topdown=True,include_path=True):
            if self.handlers.has_entry(n,kind="leaf"):
                self.handlers[n].set_value(v)
    def repr_value(self, name, value):
        return self.handlers[name].repr_value(value)
    def changed_event(self, name):
        return self.handlers[name].changed_event()



_default_indicator_getters=("get_indicator",)
_default_indicator_setters=("set_indicator",)
class IIndicatorHandler(object):
    def __init__(self, widget, getters=None, setters=None):
        object.__init__(self)
        self.widget=widget
        self.getters=getters or _default_indicator_getters
        self.setters=setters or _default_indicator_setters
    def get_value(self):
        for g in self.getters:
            if hasattr(self.widget,g):
                return getattr(self.widget,g)()
        raise ValueError("can't find default getter for widget {}".format(self.widget))
    def set_value(self, value):
        for s in self.setters:
            if hasattr(self.widget,s):
                return getattr(self.widget,s)(value)
        raise ValueError("can't find default setter for widget {}".format(self.widget))
class LabelIndicatorHandler(IIndicatorHandler):
    def __init__(self, widget, label, widget_handler=None):
        IIndicatorHandler.__init__(self,widget)
        self.widget_handler=widget_handler or get_default_value_handler(widget)
        if not isinstance(label,IValueHandler):
            label=get_default_value_handler(label)
        self.label_handler=label
    def get_value(self):
        return self.label_handler.get_value()
    def set_value(self, value):
        return self.label_handler.set_value(self.widget_handler.repr_value(value))

def get_default_indicator_handler(widget, label=None):
    if label is not None:
        return LabelIndicatorHandler(widget,label)
    if has_methods(widget,[_default_indicator_getters,_default_indicator_setters]):
        return IIndicatorHandler(widget)
    return None


class IndicatorValuesTable(ValuesTable):
    def __init__(self):
        ValuesTable.__init__(self)
        self.indicator_handlers=dictionary.Dictionary()
        self.i=dictionary.ItemAccessor(self.get_indicator,self.set_indicator)
    def add_indicator_handler(self, name, handler):
        if handler is not None:
            self.indicator_handlers[name]=handler
            return True
        return False
    def add_indicator(self, name, widget, label=None):
        return self.add_indicator_handler(name,get_default_indicator_handler(widget,label))

    def set_indicator(self, name, value):
        return self.indicator_handlers[name].set_value(value)
    def get_indicator(self, name):
        return self.indicator_handlers[name].get_value()
    def update_indicators(self):
        for n in self.handlers:
            if n in self.handlers and n in self.indicator_handlers:
                self.set_indicator(n,self.get_value(n))