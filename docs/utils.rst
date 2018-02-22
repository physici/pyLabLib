===============
Dictionary module
===============

:class:`Dictionary` is an expansion of the standard `dict` class which supports tree structures (nested dictionaries). The extensions include:

- handling multi-level paths and nested dictionaries, with several different indexing methods
- iteration over the immediate branches, or over the whole tree structure
- some additional methods: mapping, filtering, finding difference between two dictionaries
- combined with :mod:`pylablib.core.fileio` allows to save and load the content in a human-readable fromat.