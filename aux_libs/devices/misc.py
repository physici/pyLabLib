from ...core.utils import files

import platform
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
    module_folder=os.path.split(files.normalize_path(sys.modules[__name__].__path__))[0]
    return os.path.join(module_folder,"libs",archfolder)
default_lib_folder=get_default_lib_folder()