from ...core.utils import files

import platform
import ctypes
import sys
import os.path
import os


def get_default_lib_folder():
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

def load_lib(path, locally=False, call_conv="cdecl"):
    if platform.system()!="Windows":
        raise OSError("DLLs are not available on non-Windows platform")
    if locally:
        env_paths=os.environ["PATH"].split(";")
        folder,name=os.path.split(path)
        if not any([files.paths_equal(folder,ep) for ep in env_paths if ep]):
            os.environ["PATH"]+=";"+files.normalize_path(folder)+";"
        path=name
    if call_conv=="cdecl":
        return ctypes.cdll.LoadLibrary(path)
    elif call_conv=="stdcall":
        return ctypes.windll.LoadLibrary(path)
    else:
        raise ValueError("unrecognized call convention: {}".format(call_conv))