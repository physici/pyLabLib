from .param_table import ParamTable, FixedParamTable

from PyQt4 import QtGui, QtCore
import pyqtgraph
import numpy as np
import contextlib


class ImageViewController(QtGui.QWidget):
    def __init__(self, parent=None):
        super(ImageViewController, self).__init__(parent)

    def setupUi(self, name, view, display_table=None, display_table_root=None):
        self.name=name
        self.setObjectName(self.name)
        self.layout=QtGui.QHBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setObjectName("layout")
        self.view=view
        self.view.attach_controller(self)
        self.settings_table=ParamTable(self)
        self.settings_table.setObjectName("settings_table")
        self.layout.addWidget(self.settings_table)
        self.settings_table.setupUi("img_settings",add_indicator=True,display_table=display_table,display_table_root=display_table_root)
        self.settings_table.add_text_label("size",label="Image size:")
        self.settings_table.add_check_box("flip_x","Flip X",value=False)
        self.settings_table.add_check_box("flip_y","Flip Y",value=False)
        self.settings_table.add_check_box("transpose","Transpose",value=False)
        self.settings_table.add_check_box("normalize","Normalize",value=False)
        self.settings_table.add_num_edit("minlim",value=0,limiter=(0,16384,"coerce","int"),formatter=("int"),label="Minimal intensity:")
        self.settings_table.add_num_edit("maxlim",value=16384,limiter=(0,16384,"coerce","int"),formatter=("int"),label="Maximal intensity:")
        self.settings_table.add_check_box("show_lines","Show lines",value=True)
        self.settings_table.add_num_edit("vlinepos",value=0,limiter=(0,None,"coerce","float"),formatter=("float","auto",1,True),label="X line:")
        self.settings_table.add_num_edit("hlinepos",value=0,limiter=(0,None,"coerce","float"),formatter=("float","auto",1,True),label="Y line:")
        self.settings_table.add_button("center_lines","Center lines").clicked.connect(view.center_lines)
        self.settings_table.value_changed.connect(lambda: self.view.update_image(update_controls=False))
        self.settings_table.add_padding()

class ImageView(QtGui.QWidget):
    def __init__(self, parent=None):
        super(ImageView, self).__init__(parent)
        self.ctl=None

    def setupUi(self, name, img_size=(1024,1024), min_size=(512,512)):
        self.name=name
        self.setObjectName(self.name)
        self.layout=QtGui.QHBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setObjectName("layout")
        self.img=np.zeros(img_size)
        self.imageWindow=pyqtgraph.ImageView(self)
        if min_size:
            self.imageWindow.setMinimumSize(QtCore.QSize(*min_size))
        self.imageWindow.setObjectName("imageWindow")
        self.layout.addWidget(self.imageWindow)
        self.imageWindow.setColorMap(pyqtgraph.ColorMap([0,0.3,0.7,0.999,1.],[(0.,0.,0.),(1.,0.,0.),(1.,1.,0.),(1.,1.,1.),(0.,0.,1.)]))
        self.imageWindow.ui.roiBtn.hide()
        self.imageWindow.ui.menuBtn.hide()
        self.imgVLine=pyqtgraph.InfiniteLine(angle=90,movable=True,bounds=[0,None])
        self.imgHLine=pyqtgraph.InfiniteLine(angle=0,movable=True,bounds=[0,None])
        self.imageWindow.getView().addItem(self.imgVLine)
        self.imageWindow.getView().addItem(self.imgHLine)
        self.imgVLine.sigPositionChanged.connect(self.update_image_controls)
        self.imgHLine.sigPositionChanged.connect(self.update_image_controls)
        self.imageWindow.getHistogramWidget().sigLevelsChanged.connect(self.update_image_controls)

    def attach_controller(self, ctl):
        self.ctl=ctl
    def _get_params(self):
        if self.ctl is not None:
            return self.ctl.settings_table
        return FixedParamTable(v={"transpose":False,
                "flip_x":False,
                "flip_y":False,
                "normalize":True,
                "show_lines":False,
                "vlinepos":0,
                "hlinepos":0})
    
    @contextlib.contextmanager
    def no_events(self):
        self.imgVLine.sigPositionChanged.disconnect(self.update_image_controls)
        self.imgHLine.sigPositionChanged.disconnect(self.update_image_controls)
        self.imageWindow.getHistogramWidget().sigLevelsChanged.disconnect(self.update_image_controls)
        yield
        self.imgVLine.sigPositionChanged.connect(self.update_image_controls)
        self.imgHLine.sigPositionChanged.connect(self.update_image_controls)
        self.imageWindow.getHistogramWidget().sigLevelsChanged.connect(self.update_image_controls)


    def set_image(self, img):
        self.img=img
    def center_lines(self):
        self.imgVLine.setPos(self.img.shape[0]/2)
        self.imgHLine.setPos(self.img.shape[1]/2)
    # Update image controls based on PyQtGraph image window
    def update_image_controls(self):
        params=self._get_params()
        levels=self.imageWindow.getHistogramWidget().getLevels()
        params.v["minlim"],params.v["maxlim"]=levels
        params.v["vlinepos"]=self.imgVLine.getPos()[0]
        params.v["hlinepos"]=self.imgHLine.getPos()[1]
    # Update image plot
    def update_image(self, update_controls=False):
        with self.no_events():
            params=self._get_params()
            draw_img=self.img
            if params.v["transpose"]:
                draw_img=draw_img.transpose()
            if params.v["flip_x"]:
                draw_img=draw_img[::-1,:]
            if params.v["flip_y"]:
                draw_img=draw_img[:,::-1]
            autoscale=params.v["normalize"]
            if self.isVisible():
                self.imageWindow.setImage(draw_img,autoLevels=autoscale,autoHistogramRange=autoscale)
            if update_controls:
                self.update_image_controls()
            if not autoscale:
                levels=params.v["minlim"],params.v["maxlim"]
                self.imageWindow.setLevels(*levels)
                self.imageWindow.getHistogramWidget().setLevels(*levels)
                self.imageWindow.getHistogramWidget().autoHistogramRange()
            params.i["minlim"]=self.imageWindow.levelMin
            params.i["maxlim"]=self.imageWindow.levelMax
            params.v["size"]="{} x {}".format(*draw_img.shape)
            show_lines=params.v["show_lines"]
            for ln in [self.imgVLine,self.imgHLine]:
                ln.setPen("g" if show_lines else None)
                ln.setHoverPen("y" if show_lines else None)
                ln.setMovable(show_lines)
            self.imgVLine.setBounds([0,draw_img.shape[0]])
            self.imgHLine.setBounds([0,draw_img.shape[1]])
            self.imgVLine.setPos(params.v["vlinepos"])
            self.imgHLine.setPos(params.v["hlinepos"])
            return params