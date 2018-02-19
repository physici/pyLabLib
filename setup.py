"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pylablib',
    version='0.2.0',
    description='Collection of Python code for using in lab environment (data acquisition, device communication, data analysis)',
    long_description=long_description,
    url='https://github.com/AlexShkarin/pyLabLib',
    author='Alexey Shkarin',
    author_email='alex.shkarin@gmail.com',
    license='MIT',
    classifiers=[
    'Development Status :: 3 - Alpha',
    'Environment :: Win32 (MS Windows)',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering :: Physics',
     'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Operating System :: Microsoft :: Windows'
    ],
    packages=find_packages(exclude=['docs']),
    package_data={'pylablib.core.dataproc': ['*.c','*.pyd']},
    install_requires=['future','numpy','scipy','matplotlib','pyvisa','pyserial'],
)