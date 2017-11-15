from distutils.core import setup, Extension
from distutils.sysconfig import get_python_lib
import os.path

import platform
arch=platform.architecture()
if arch[0]=="32bit":
    module_name='iir_transform_32'
elif arch[0]=="64bit":
    module_name='iir_transform_64'
else:
    raise ImportError("Unexpected system architecture: {0}".format(arch))

numpy_dir=os.path.join(get_python_lib(),'numpy')
numpy_include_dir=os.path.join(numpy_dir,'core','include','numpy')
numpy_lib_dir=os.path.join(numpy_dir,'core','lib')

module = Extension(module_name,
                    sources = ['iir_transform.c'],
                    include_dirs=[numpy_include_dir],
                    library_dirs=[numpy_lib_dir])

setup(name = 'IIR transform',
       description = 'Digital filters package.',
       ext_modules = [module])