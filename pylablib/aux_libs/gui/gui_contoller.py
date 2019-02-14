from ...core.gui.qt.thread import controller, threadprop
from ...core.gui.qt import values as values_module

from PyQt5 import QtCore

import collections

class IGUIController(QtCore.QObject):
    def __init__(self):
        super(IGUIController, self).__init__()
        self.widgets_desc={}
        self.widgets={}
        self.ctl=controller.get_gui_controller()
        self.params_table=values_module.ValuesTable()

    TWidget=collections.namedtuple("TWidget",["params_path"])
    def add_widget_desc(self, name, params_path=None):
        self.widgets_desc[name]=self.TWidget(params_path)
    def set_widget(self, name, widget):
        self.widgets[name]=widget
        desc=self.widgets_desc.setdefault(name,self.TWidget(None))
        if desc.params_path is not None:
            self.params_table.add_widget(desc.params_path,widget)
    def get_widget(self, name, default=None):
        return self.widgets.get(name,default)
    __getitem__=get_widget
    def __contains__(self, name):
        return name in self.widgets
    
    def get_all_values(self):
        return self.params_table.get_all_values()
    def set_all_values(self, params):
        return self.params_table.set_all_values(params)