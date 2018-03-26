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
In addition :mod:`PyVISA` and :mod:`pySerial` modules are used for the device communication.

Some data processing functionality is written in C. The package is distributed with precompiled Windows binaries for 32 and 64 bit version for Python 2.7 and 3.6. If you see a message ``Couldn't find appropriate precompiled IIR filter implementation, using pure Python fallback instead; expect sever performance drop.`` on the package import, it means that these libraries could not be accessed, and the related function can be severely slowed down. To build the required modules for your system, go into ``core\dataproc`` folder inside the package and run ``python iir_transform_setup.py build`` (it requires configured C compiler for Python and installed NumPy). After that, copy the compiled module from the ``build`` subfolder into the main ``dataproc`` folder.

The package has been tested with Python 2.7 and Python 3.6 (not extensively).