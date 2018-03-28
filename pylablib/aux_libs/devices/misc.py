from ...core.utils import files

import platform
import ctypes
import sys
import os.path


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

def load_lib(path, locally=False):
    if platform.system()!="Windows":
        raise OSError("DLLs are not available on non-Windows platform")
    if not locally:
        return ctypes.cdll.LoadLibrary(path)
    folder,name=os.path.split(path)
    cur_folder=files.normalize_path(os.path.curdir)
    os.chdir(folder)
    try:
        lib=load_lib(name,locally=False)
        return lib
    finally:
        os.chdir(cur_folder)