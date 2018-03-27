Overview
=======================

PyLabLib is a collection of code intended to simplify some of the coding tasks encountered in a physics laboratory.

Some major parts include:
    - Simpler loading and saving of data in text or binary files.
    - Data tables with heterogeneous columns and more universal indexing (heavy overlap with pandas).
    - Some data processing utilities: filtering, decimating, peak detection, FFT (mostly wrappers around NumPy and SciPy).
    - Classes for device control (universal wrapper for pyVISA, pySerial and network backends).
    - More user-friendly fitting interface.
    - Multi-level dictionaries which are convenient for storing heterogeneous data and settings in human-readable format.
    - A bunch more utilities dealing with file system (creating, moving and removing folders, zipping/unzipping, path normalization), network (simplified interface for client and server sockets), strings (serializing and de-serializing values), function introspection, and more. 

The most recent version library is available on GitHub (https://github.com/AlexShkarin/pyLabLib), and the documentation can be found at http://pylablib.readthedocs.io/ .

For a more comprehensive, specialized (classes for certain equipment, GUI building, multithreading, specific computational tasks), and recent version of the library, check out dev branch of the GitHub repository