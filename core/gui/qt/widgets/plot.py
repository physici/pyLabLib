from matplotlib.backends.qt_compat import is_pyqt5
if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
else:
    from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar

import matplotlib.pyplot as mpl
import time

class MPLFigureCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        FigureCanvasQTAgg.__init__(self,mpl.Figure())
        if parent:
            self.setParent(parent)
        self.redraw_period=0.
        self._last_draw_time=None

    def redraw(self, force=False):
        t=time.time()
        if force or (not self._last_draw_time) or (self._last_draw_time+self.redraw_period<=t):
            self.draw_idle()
            self._last_draw_time=t