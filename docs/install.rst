.. _install:

============
Installation
============

You can install the library using pip::

    pip install pylablib

-----
Usage
-----

To access to the most common functions simply import the library::

    import pylablib as pll
    data = pll.load("data.csv","csv")

------------
Requirements
------------

The package requires :mod:`NumPy`, :mod:`SciPy` and :mod:`Matplotlib` modules for computations. Since getting them directly from pip might not be optimal, it is a good idea to have them already installed before installing pyLabLib.
:mod:`PyVISA` and :mod:`pySerial` are the main packages used for the device communication. For some specific devices you might require :mod:`pyft232`, :mod:`pywinusb`, :mod:`websocket-client`, or :mod:`pynidaqmx` (keep in mind that it's different from the :mod:`PyDAQmx` package). Some devices have additional requirements (devices software or drivers installed, or some particular dlls), which are specified in their description.

Some data processing functionality is written in C. The package is distributed with precompiled Windows binaries for 32 and 64 bit version for Python 2.7 and 3.6. If you see a message ``Couldn't find appropriate precompiled IIR filter implementation, using pure Python fallback instead; expect sever performance drop.`` on the package import, it means that these libraries could not be accessed, and the related function can be severely slowed down. To build the required modules for your system, go into ``core\dataproc`` folder inside the package and run ``python iir_transform_setup.py build`` (it requires configured C compiler for Python and installed NumPy). After that, copy the compiled module from the ``build`` subfolder into the main ``dataproc`` folder.

The package has been tested with Python 2.7 and Python 3.6 (not extensively).

.. _install-github:

-----------------------
Installing from  GitHub
-----------------------

The most recent and extensive, but less documented, version of this library is available in the `dev` branch on GitHub at https://github.com/AlexShkarin/pyLabLib/tree/dev. To simply get the most recent version, you can download it as a zip-file (make sure `dev` branch is selected in the dropdown branch menu, so the file is called `pyLabLib-dev.zip`) and unpack it into any appropriate place (can be folder of the project you're working on, Python site-packages folder, or any folder added to Python path variable). In order to easily get updates, you can instead clone the repository to your computer. For that, you need to install Git (https://git-scm.com/), and use the following commands in the command line (in the folder where you want to store the library)::

    git clone https://github.com/AlexShkarin/pyLabLib
    cd ./pyLabLib
    git checkout dev

Whenever you want to update to the most recent version, simply type ::
    
    git pull

in the library folder. Keep in mind that any changes that you make to the library code might conflict with the new version that you pull from GitHub, so you should not modify anything in this folder if possible.