from PyQt4 import QtCore, QtGui

from ....core.gui.qt.widgets.edit import LVNumEdit
from ....core.utils.numerical import limit_to_range

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



class ROICtl(QtGui.QWidget):
    AxisParams=collections.namedtuple("AxisParams",["min","max","bin"])
    def __init__(self, parent=None):
        super(ROICtl, self).__init__(parent)
        self.xparams=self.AxisParams(0,1,1)
        self.yparams=self.AxisParams(0,1,1)
        self.xlim=(0,None)
        self.ylim=(0,None)
        self.maxbin=None
        self.minsize=0

    def _limit_range(self, rng, lim, maxbin, minsize):
        vmin=limit_to_range(rng.min,*lim)
        vmax=limit_to_range(rng.max,*lim)
        vmin,vmax=min(vmin,vmax),max(vmin,vmax)
        if vmax-vmin<minsize: # try increase upper limit
            vmax=limit_to_range(vmin+minsize,*lim)
        if vmax-vmin<minsize: # try decrease lower limit
            vmin=limit_to_range(vmax-minsize,*lim)
        vbin=limit_to_range(rng.bin,1,maxbin)
        return self.AxisParams(vmin,vmax,vbin)
    def validateROI(self, xparams, yparams):
        xparams=self._limit_range(xparams,self.xlim,self.maxbin,self.minsize)
        yparams=self._limit_range(yparams,self.ylim,self.maxbin,self.minsize)
        return xparams,yparams
    def setupUi(self, name, xlim=(0,None), ylim=None, maxbin=None, minsize=0):
        self.name=name
        self.setObjectName(_fromUtf8(self.name))
        self.setMinimumSize(QtCore.QSize(232, 83))
        self.setMaximumSize(QtCore.QSize(16777215, 83))
        self.gridLayout = QtGui.QGridLayout(self)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.labelROI = QtGui.QLabel(self)
        self.labelROI.setObjectName(_fromUtf8("labelROI"))
        self.labelROI.setText(_translate(self.name, "ROI", None))
        self.gridLayout.addWidget(self.labelROI, 0, 0, 1, 1)
        self.labelMin = QtGui.QLabel(self)
        self.labelMin.setObjectName(_fromUtf8("labelMin"))
        self.labelMin.setText(_translate(self.name, "Min", None))
        self.gridLayout.addWidget(self.labelMin, 0, 1, 1, 1)
        self.labelMax = QtGui.QLabel(self)
        self.labelMax.setObjectName(_fromUtf8("labelMax"))
        self.labelMax.setText(_translate(self.name, "Max", None))
        self.gridLayout.addWidget(self.labelMax, 0, 2, 1, 1)
        self.labelBin = QtGui.QLabel(self)
        self.labelBin.setObjectName(_fromUtf8("labelBin"))
        self.labelBin.setText(_translate(self.name, "Bin", None))
        self.gridLayout.addWidget(self.labelBin, 0, 3, 1, 1)
        self.labelX = QtGui.QLabel(self)
        self.labelX.setObjectName(_fromUtf8("labelX"))
        self.labelX.setText(_translate(self.name, "X", None))
        self.gridLayout.addWidget(self.labelX, 1, 0, 1, 1)
        self.labelY = QtGui.QLabel(self)
        self.labelY.setObjectName(_fromUtf8("labelY"))
        self.labelY.setText(_translate(self.name, "Y", None))
        self.gridLayout.addWidget(self.labelY, 2, 0, 1, 1)
        self.x_max = LVNumEdit(self)
        self.x_max.setObjectName(_fromUtf8("x_max"))
        self.gridLayout.addWidget(self.x_max, 1, 2, 1, 1)
        self.x_min = LVNumEdit(self)
        self.x_min.setObjectName(_fromUtf8("x_min"))
        self.gridLayout.addWidget(self.x_min, 1, 1, 1, 1)
        self.x_bin = LVNumEdit(self)
        self.x_bin.setObjectName(_fromUtf8("x_bin"))
        self.gridLayout.addWidget(self.x_bin, 1, 3, 1, 1)
        self.y_min = LVNumEdit(self)
        self.y_min.setObjectName(_fromUtf8("y_min"))
        self.gridLayout.addWidget(self.y_min, 2, 1, 1, 1)
        self.y_max = LVNumEdit(self)
        self.y_max.setObjectName(_fromUtf8("y_max"))
        self.gridLayout.addWidget(self.y_max, 2, 2, 1, 1)
        self.y_bin = LVNumEdit(self)
        self.y_bin.setObjectName(_fromUtf8("y_bin"))
        self.gridLayout.addWidget(self.y_bin, 2, 3, 1, 1)
        self.gridLayout.setColumnStretch(1, 2)
        self.gridLayout.setColumnStretch(2, 2)
        self.gridLayout.setColumnStretch(3, 1)
        for v in [self.x_min,self.x_max,self.x_bin,self.y_min,self.y_max,self.y_bin]:
            v.set_number_format("int")
            v.value_changed.connect(self._on_edit)
        self.set_limits(xlim,ylim,maxbin=maxbin,minsize=minsize)


    def set_limits(self, xlim="keep", ylim="keep", maxbin="keep", minsize="keep"):
        if xlim!="keep":
            self.xlim=xlim
        if ylim!="keep":
            self.ylim=ylim or xlim
        if maxbin!="keep":
            self.maxbin=maxbin
        if minsize!="keep":
            self.minsize=minsize
        for v in [self.x_min,self.x_max]:
            v.set_number_limit(self.xlim[0],self.xlim[1],"coerce","int")
        for v in [self.y_min,self.y_max]:
            v.set_number_limit(self.ylim[0],self.ylim[1],"coerce","int")
        for v in [self.x_bin,self.y_bin]:
            v.set_number_limit(1,self.maxbin,"coerce","int")
        self._show_values(*self.get_value())

    value_changed=QtCore.pyqtSignal("PyQt_PyObject")
    def _on_edit(self):
        params=self.get_value()
        self._show_values(*params)
        self.value_changed.emit(params)

    def get_value(self):
        xparams=self.AxisParams(self.x_min.get_value(),self.x_max.get_value(),self.x_bin.get_value())
        yparams=self.AxisParams(self.y_min.get_value(),self.y_max.get_value(),self.y_bin.get_value())
        return self.validateROI(xparams,yparams)
    def _show_values(self, xparams, yparams):
        self.x_min.set_value(xparams.min,notify_value_change=False)
        self.x_max.set_value(xparams.max,notify_value_change=False)
        self.x_bin.set_value(xparams.bin,notify_value_change=False)
        self.y_min.set_value(yparams.min,notify_value_change=False)
        self.y_max.set_value(yparams.max,notify_value_change=False)
        self.y_bin.set_value(yparams.bin,notify_value_change=False)
    def set_value(self, roi, notify_value_change=True):
        roi=self.AxisParams(*roi[0]),self.AxisParams(*roi[1])
        params=self.validateROI(*roi)
        self._show_values(*params)
        if notify_value_change:
            self.value_changed.emit(params)