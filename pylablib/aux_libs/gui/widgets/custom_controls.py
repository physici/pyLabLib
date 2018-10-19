from PyQt5 import QtCore, QtWidgets

from ....core.gui.qt.widgets.edit import LVNumEdit
from ....core.utils.numerical import limit_to_range

import collections

class BinROICtl(QtWidgets.QWidget):
    AxisParams=collections.namedtuple("AxisParams",["min","max","bin"])
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self,parent)
        self.xparams=self.AxisParams(0,1,1)
        self.yparams=self.AxisParams(0,1,1)
        self.validate=None
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
        return self.AxisParams(int(vmin),int(vmax),int(vbin))
    def validateROI(self, xparams, yparams):
        xparams=self._limit_range(xparams,self.xlim,self.maxbin,self.minsize)
        yparams=self._limit_range(yparams,self.ylim,self.maxbin,self.minsize)
        if self.validate:
            xparams,yparams=self.validate((xparams,yparams))
            xparams=self.AxisParams(*xparams)
            yparams=self.AxisParams(*yparams)
        return xparams,yparams
    def setupUi(self, name, xlim=(0,None), ylim=None, maxbin=None, minsize=0, validate=None):
        self.name=name
        self.setObjectName(self.name)
        self.setMinimumSize(QtCore.QSize(232, 83))
        self.setMaximumSize(QtCore.QSize(16777215, 83))
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setObjectName("gridLayout")
        self.labelROI = QtWidgets.QLabel(self)
        self.labelROI.setObjectName("labelROI")
        self.labelROI.setText("ROI")
        self.gridLayout.addWidget(self.labelROI, 0, 0, 1, 1)
        self.labelMin = QtWidgets.QLabel(self)
        self.labelMin.setObjectName("labelMin")
        self.labelMin.setText("Min")
        self.gridLayout.addWidget(self.labelMin, 0, 1, 1, 1)
        self.labelMax = QtWidgets.QLabel(self)
        self.labelMax.setObjectName("labelMax")
        self.labelMax.setText("Max")
        self.gridLayout.addWidget(self.labelMax, 0, 2, 1, 1)
        self.labelBin = QtWidgets.QLabel(self)
        self.labelBin.setObjectName("labelBin")
        self.labelBin.setText("Bin")
        self.gridLayout.addWidget(self.labelBin, 0, 3, 1, 1)
        self.labelX = QtWidgets.QLabel(self)
        self.labelX.setObjectName("labelX")
        self.labelX.setText("X")
        self.gridLayout.addWidget(self.labelX, 1, 0, 1, 1)
        self.labelY = QtWidgets.QLabel(self)
        self.labelY.setObjectName("labelY")
        self.labelY.setText("Y")
        self.gridLayout.addWidget(self.labelY, 2, 0, 1, 1)
        self.x_min = LVNumEdit(self)
        self.x_min.setObjectName("x_min")
        self.gridLayout.addWidget(self.x_min, 1, 1, 1, 1)
        self.x_max = LVNumEdit(self)
        self.x_max.setObjectName("x_max")
        self.gridLayout.addWidget(self.x_max, 1, 2, 1, 1)
        self.x_bin = LVNumEdit(self)
        self.x_bin.setObjectName("x_bin")
        self.gridLayout.addWidget(self.x_bin, 1, 3, 1, 1)
        self.y_min = LVNumEdit(self)
        self.y_min.setObjectName("y_min")
        self.gridLayout.addWidget(self.y_min, 2, 1, 1, 1)
        self.y_max = LVNumEdit(self)
        self.y_max.setObjectName("y_max")
        self.gridLayout.addWidget(self.y_max, 2, 2, 1, 1)
        self.y_bin = LVNumEdit(self)
        self.y_bin.setObjectName("y_bin")
        self.gridLayout.addWidget(self.y_bin, 2, 3, 1, 1)
        self.gridLayout.setContentsMargins(0,0,0,0)
        self.gridLayout.setColumnStretch(1, 2)
        self.gridLayout.setColumnStretch(2, 2)
        self.gridLayout.setColumnStretch(3, 1)
        self.validate=validate
        for v in [self.x_min,self.y_min]:
            v.set_number_format("int")
            v.set_number_limit(value_type="int")
            v.set_value(0)
        for v in [self.x_max,self.x_bin,self.y_max,self.y_bin]:
            v.set_number_format("int")
            v.set_number_limit(value_type="int")
            v.set_value(1)
        for v in [self.x_min,self.x_max,self.x_bin,self.y_min,self.y_max,self.y_bin]:
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





class RangeCtl(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(RangeCtl, self).__init__(parent)
        self.rng=(0,0,0)

    def setupUi(self, name, lim=(None,None), order=True, formatter="float", labels=("Min","Max","Center","Span","Step"), elements=("minmax","cspan","step")):
        self.name=name
        self.order=order
        self.setObjectName(self.name)
        # self.setMinimumSize(QtCore.QSize(232, 83))
        # self.setMaximumSize(QtCore.QSize(16777215, 83))
        self.gridLayout = QtWidgets.QGridLayout(self)
        self.gridLayout.setObjectName("gridLayout")
        row=0
        if "minmax" in elements:
            self.labelMin = QtWidgets.QLabel(self)
            self.labelMin.setObjectName("labelMin")
            self.labelMin.setText(labels[0])
            self.gridLayout.addWidget(self.labelMin, row, 0, 1, 1)
            self.labelMax = QtWidgets.QLabel(self)
            self.labelMax.setObjectName("labelMax")
            self.labelMax.setText(labels[1])
            self.gridLayout.addWidget(self.labelMax, row, 2, 1, 1)
            self.e_min = LVNumEdit(self)
            self.e_min.setObjectName("e_min")
            self.gridLayout.addWidget(self.e_min, row, 1, 1, 1)
            self.e_max = LVNumEdit(self)
            self.e_max.setObjectName("e_max")
            self.gridLayout.addWidget(self.e_max, row, 3, 1, 1)
            self.e_min.value_changed.connect(self._minmax_changed)
            self.e_max.value_changed.connect(self._minmax_changed)
            row+=1
        else:
            self.e_min=None
            self.e_max=None
        if "cspan" in elements:
            self.labelCent = QtWidgets.QLabel(self)
            self.labelCent.setObjectName("labelCent")
            self.labelCent.setText(labels[2])
            self.gridLayout.addWidget(self.labelCent, row, 0, 1, 1)
            self.labelSpan = QtWidgets.QLabel(self)
            self.labelSpan.setObjectName("labelSpan")
            self.labelSpan.setText(labels[3])
            self.gridLayout.addWidget(self.labelSpan, row, 2, 1, 1)
            self.e_cent = LVNumEdit(self)
            self.e_cent.setObjectName("e_cent")
            self.gridLayout.addWidget(self.e_cent, row, 1, 1, 1)
            self.e_span = LVNumEdit(self)
            self.e_span.setObjectName("e_span")
            self.gridLayout.addWidget(self.e_span, row, 3, 1, 1)
            self.e_cent.value_changed.connect(self._cspan_changed)
            self.e_span.value_changed.connect(self._cspan_changed)
            row+=1
        else:
            self.e_cent=None
            self.e_span=None
        if "step" in elements:
            self.labelStep = QtWidgets.QLabel(self)
            self.labelStep.setObjectName("labelStep")
            self.labelStep.setText(labels[4])
            self.gridLayout.addWidget(self.labelStep, row, 0, 1, 1)
            self.e_step = LVNumEdit(self)
            self.e_step.setObjectName("e_step")
            self.gridLayout.addWidget(self.e_step, row, 1, 1, 1)
            self.e_step.value_changed.connect(self._step_changed)
            self.e_step.set_number_limit(0,None)
            row+=1
        else:
            self.e_step=None
        self.gridLayout.setContentsMargins(2,2,2,2)
        for v in [self.e_min,self.e_max,self.e_cent,self.e_span,self.e_step]:
            if v:
                v.change_formatter(formatter)
        self._show_values(self.rng)
        self.set_limit(lim)

    def _limit_range(self, rng):
        vmin=limit_to_range(rng[0],*self.lim)
        vmax=limit_to_range(rng[1],*self.lim)
        if self.order:
            vmin,vmax=min(vmin,vmax),max(vmin,vmax)
        step=max(0,rng[2])
        return (vmin,vmax,step)
    def _minmax_changed(self):
        rng=self.e_min.get_value(),self.e_max.get_value(),self.rng[2]
        self.set_value(rng)
    def _cspan_changed(self):
        cent,span=self.e_cent.get_value(),self.e_span.get_value()
        rng=(cent-span/2.),(cent+span/2.),self.rng[2]
        self.set_value(rng)
    def _step_changed(self):
        rng=self.rng[0],self.rng[1],self.e_step.get_value()
        self.set_value(rng)

    def set_limit(self, lim):
        self.lim=lim
        self.set_value(self.rng)

    value_changed=QtCore.pyqtSignal("PyQt_PyObject")
    def get_value(self):
        return self.rng
    def _show_values(self, rng):
        if self.e_min:
            self.e_min.set_value(rng[0],notify_value_change=False)
            self.e_max.set_value(rng[1],notify_value_change=False)
        if self.e_cent:
            self.e_cent.set_value((rng[0]+rng[1])/2.,notify_value_change=False)
            self.e_span.set_value(rng[1]-rng[0],notify_value_change=False)
        if self.e_step:
            self.e_step.set_value(rng[2],notify_value_change=False)
    def set_value(self, rng, notify_value_change=True):
        rng=self._limit_range(rng)
        if self.rng!=rng:
            self.rng=rng
            self._show_values(rng)
            if notify_value_change:
                self.value_changed.emit(rng)