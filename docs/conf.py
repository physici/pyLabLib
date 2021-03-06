# -*- coding: utf-8 -*-
#
# pyLabLib documentation build configuration file, created by
# sphinx-quickstart on Tue Feb 20 00:07:50 2018.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from unittest import mock


# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = ['sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.coverage',
    'sphinx.ext.imgmath',
    'sphinx.ext.viewcode']

autodoc_mock_imports = ['nidaqmx', 'visa', 'serial', 'ft232', 'PyQt5', 'pywinusb', 'pyqtgraph', 'websocket', 'zhinst', 'matplotlib', 'sip', 'rpyc', 'numba']
sys.modules['visa']=mock.Mock(VisaIOError=object, __version__='1.9.0')
sys.modules['serial']=mock.Mock(SerialException=object)
sys.modules['ft232']=mock.Mock(Ft232Exception=object)
autodoc_member_order = 'bysource'

# nitpicky = True
nitpick_ignore=[ ("py:class","callable"),
                    ("py:class","socket.socket"),
                    ("py:class","sphinx.ext.autodoc.importer._MockObject"), ("py:class","_ctypes.Structure"), ("py:class","_ctypes.Union"),
                    ("py:class","builtins.object"), ("py:class","builtins.OSError"), ("py:class","builtins.RuntimeError"),
                    ("py:class","usb.core.USBError")]
intersphinx_mapping = {'python': ('https://docs.python.org/3', None),
                       'numpy': ('http://docs.scipy.org/doc/numpy/', None),
                       'scipy': ('http://docs.scipy.org/doc/scipy/reference/', None),
                       'matplotlib': ('http://matplotlib.org/', None),
                       'rpyc': ('https://rpyc.readthedocs.io/en/latest/', None),
                       'pyqtgraph': ("http://www.pyqtgraph.org/documentation/", None),
                       'pySerial': ("https://pythonhosted.org/pyserial/", None),
                       'PyVISA': ("https://pyvisa.readthedocs.io/en/master/", None),
                       'nidaqmx': ("https://nidaqmx-python.readthedocs.io/en/latest/", None),}


def no_namedtuple_attrib_docstring(app, what, name, obj, options, lines):
    if len(lines) == 1 and lines[0].startswith('Alias for field number'):
        # We don't return, so we need to purge in-place
        del lines[:]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'pyLabLib'
copyright = u'2019, Alexey Shkarin'
author = u'Alexey Shkarin'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = u'0.3'
# The full version, including alpha/beta/rc tags.
release = u'0.3.5'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False


# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

def setup(app):
    app.add_stylesheet('css/wide.css')
    app.connect('autodoc-process-docstring',no_namedtuple_attrib_docstring)


# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# This is required for the alabaster theme
# refs: http://alabaster.readthedocs.io/en/latest/installation.html#sidebars
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',  # needs 'show_related': True theme option to display
        'searchbox.html',
        'donate.html',
    ]
}


# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'pyLabLibdoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'pyLabLib.tex', u'pyLabLib Documentation',
     u'Alexey Shkarin', 'manual'),
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'pylablib', u'pyLabLib Documentation',
     [author], 1)
]


# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'pyLabLib', u'pyLabLib Documentation',
     author, 'pyLabLib', 'One line description of project.',
     'Miscellaneous'),
]



