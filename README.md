# Persistent Archival of Python Objects

[![Documentation Status](https://readthedocs.org/projects/persist/badge/?version=latest)](https://persist.readthedocs.io/en/latest/?badge=latest)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/forbes-group/persist.svg)](https://lgtm.com/projects/g/forbes-group/persist/context:python)
[![Tests](https://github.com/forbes-group/persist/actions/workflows/tests.yml/badge.svg)](https://github.com/forbes-group/persist/actions/workflows/tests.yml)
[![Pypi](https://img.shields.io/pypi/v/persist.svg)](https://pypi.python.org/pypi/persist)
[![pyversions](https://img.shields.io/pypi/pyversions/persist.svg)](https://pypi.python.org/pypi/persist)[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Persistent archival of python objects in an importable format.

This package provides a method for archiving python objects to disk for long-term persistent storage.  The archives are importable python packages with large data stored in the [npy](https://docs.scipy.org/doc/numpy/neps/npy-format.html) numpy data format, or [HDF5](http://www.hdfgroup.org/HDF5/) files using the [h5py](http://www.h5py.org) package (if it is installed). The original goal was to overcomes several disadvatages of pickles:

1. Archives are relatively stable to code changes.  Unlike pickles, changing the underlying code for a class will not change the ability to read an archive if the API does not change.
2. In the presence of API changes, the archives can be edited by hand to fix them since they are simply python code.  (Note: for reliability, the generated code is highly structured and not so "pretty", but can still be edited or debugged in the case of errors due to API changes.)
3. Efficient storage of large arrays.
4. Safe for concurrent access by multiple processes.

**Documentation:**
   http://persist.readthedocs.org

**Source:**
   https://alum.mit.edu/www/mforbes/hg/forbes-group/persist
   
**Issues:**
   https://alum.mit.edu/www/mforbes/hg/forbes-group/issues

## Installing

This package can be installed from [PyPI](https://pypi.org/project/persist/):

```bash
python3 -m pip install persist
```

or from source:

```bash
python3 -m pip install hg+https://alum.mit.edu/www/mforbes/hg/forbes-group/persist
```
