from PyQt4 import QtCore, QtGui

from ...thread import threadprop, controller, sync_primitives
from ...utils import funcargparse
    
_depends_local=["...thread.controller"]


def get_app():
    """
    Get current application instance.
    """
    return QtCore.QCoreApplication.instance()
def is_gui_running():
    """
    Check if GUI is running.
    """
    return get_app() is not None
def is_gui_thread():
    """
    Check if the current thread is the one running the GUI loop.
    """
    app=get_app()
    return (app is not None) and (QtCore.QThread.currentThread() is app.thread())
def is_gui_controlled_thread():
    """
    Check if the current thread is controlled by a GUI controller.
    """
    return isinstance(threadprop.current_controller(),GUIThreadController)



class CallerObject(QtCore.QObject):
    """
    Auxiliary object for making remote calls in the GUI thread.
    """
    call_signal=QtCore.pyqtSignal("PyQt_PyObject")
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.call_signal.connect(self.on_call)
    def on_call(self, func):
        func()
    def call_after(self, func):
        self.call_signal.emit(func)
def setup_call_after(): # needs to be called from the main thread
    """
    Setup the :func:`call_after` functionality.

    Needs to be called once in the GUI thread.
    """
    app=get_app()
    if app is None:
        raise threadprop.NotRunningThreadError("GUI thread is not running")
    if not hasattr(app,"_caller_object"):
        app._caller_object=CallerObject()
def call_after(func, *args, **kwargs):
    """
    Call the function `func` with the given arguments in a GUI thread.

    Return immediately. If synchronization is needed, use :func:`call_in_gui_thread`.
    Analogue of ``wx.CallAfter``.
    """
    app=get_app()
    if app is None:
        raise threadprop.NotRunningThreadError("GUI thread is not running")
    app._caller_object.call_after(lambda: func(*args,**kwargs))

def call_in_gui_thread(func, args=None, kwargs=None, to_return="result", note=None, on_stopped="error"):
    """
    Call the function `func` with the given arguments in a GUI thread.

    `to_return` specifies the return value parameters:
        - ``"none"``: execute immediately, return nothing, no synchronization is performed;
        - ``"syncher"``: execute immediately, return a synchronizer object (:class:`.sync_primitives.ValueSynchronizer`),
            which can be used to check if the execution is done and to obtain the result.
        - ``"result"``: pause until the function has been executed, return the result. Mostly equivalent to a simple function call.

    If `note` is not ``None``, it specifiec a callback function to be called after the exectuion is done, or (if it's a string), a message tag which is sent after the execution is done.
    """
    funcargparse.check_parameter_range(to_return,"to_return",{"none","result","syncher"})
    if is_gui_thread():
        if to_return=="syncher":
            raise ValueError("can't return syncher for the gui thread")
        res=func(*(args or []),**(kwargs or {}))
        return res if to_return=="result" else True
    if to_return!="none" or note is not None:
        call=sync_primitives.SyncCall(func,args,kwargs,sync=(None if to_return=="none" else True),note=note)
        try:
            call_after(call)
        except threadprop.NotRunningThreadError:
            return bool(threadprop.on_error(on_stopped,threadprop.NotRunningThreadError("GUI thread is not running")))
        value=call.value(sync=(to_return=="result"),default=None if to_return=="result" else False)
        return value
    else:
        call_after(func,*(args or []),**(kwargs or {}))
    
def gui_func(to_return="result", note=None, on_stopped="error"): #decorator
    """
    Decorator for a function which makes it exectute through a :func:`call_in_gui_thread` call.

    Effectively, makes a GUI-realted function thread-safe (can be called from any thread, but the execution is done in the GUI thread).
    """
    def wrapper(func):
        def wrapped(*args, **kwargs):
            return call_in_gui_thread(func,args,kwargs,to_return=to_return,note=note,on_stopped=on_stopped)
        return wrapped
    return wrapper
gui_func_sync=gui_func()