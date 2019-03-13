from ...core.utils import files

import platform
import ctypes
import sys
import os.path
import os


def get_default_lib_folder():
    """Get default DLL folder withing the package, depending on the Python bitness"""
    arch=platform.architecture()[0]
    if arch=="32bit":
        archfolder="x86"
    elif arch=="64bit":
        archfolder="x64"
    else:
        raise ImportError("Unexpected system architecture: {0}".format(arch))
    module_folder=os.path.split(files.normalize_path(sys.modules[__name__].__file__))[0]
    return os.path.join(module_folder,"libs",archfolder)
default_lib_folder=get_default_lib_folder()

def load_lib(path, locally=False, call_conv="cdecl", global_first=False):
    """
    Load DLL.

    Args:
        path: path to the library (usually, inside the path given by :func:`get_default_lib_folder`)
        locally(bool): if ``True``, change local path to allow loading of dependent DLLs
        call_conv(str): DLL call convention; can be either ``"cdecl"`` (corresponds to ``ctypes.cdll``) or ``"stdcall"`` (corresponds to ``ctypes.windll``)
        global_first(str): if ``True``, try load globablly-defined DLL (contained in ``System32`` folder) with this name
    """
    if platform.system()!="Windows":
        raise OSError("DLLs are not available on non-Windows platform")
    if global_first:
        name=os.path.split(path)[1]
        try:
            return load_lib(name,locally=False,global_first=False,call_conv=call_conv)
        except OSError:
            pass
    if locally:
        env_paths=os.environ["PATH"].split(";")
        folder,name=os.path.split(path)
        if not any([files.paths_equal(folder,ep) for ep in env_paths if ep]):
            os.environ["PATH"]=files.normalize_path(folder)+";"+os.environ["PATH"]
        path=name
    if call_conv=="cdecl":
        lib=ctypes.cdll.LoadLibrary(path)
    elif call_conv=="stdcall":
        lib=ctypes.windll.LoadLibrary(path)
    else:
        raise ValueError("unrecognized call convention: {}".format(call_conv))
    return lib