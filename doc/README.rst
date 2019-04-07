
Persistent Archival of Python Objects
=====================================

Persistent archival of python objects in an importable format.

This package provides a method for archiving python objects to disk for
long-term persistent storage. The archives are importable python
packages with large data stored in the
`npy <https://docs.scipy.org/doc/numpy/neps/npy-format.html>`__ numpy
data format, or `HDF5 <http://www.hdfgroup.org/HDF5/>`__ files using the
`h5py <http://www.h5py.org>`__ package (if it is installed). The
original goal was to overcomes several disadvatages of pickles:

1. Archives are relatively stable to code changes. Unlike pickles,
   changing the underlying code for a class will not change the ability
   to read an archive if the API does not change.
2. In the presence of API changes, the archives can be edited by hand to
   fix them since they are simply python code. (Note: for reliability,
   the generated code is highly structured and not so “pretty”, but can
   still be edited or debugged in the case of errors due to API
   changes.)
3. Efficient storage of large arrays.
4. Safe for concurrent access by multiple processes.

**Documentation:** http://persist.readthedocs.org

**Source:** https://bitbucket.org/mforbes/persist

**Issues:** https://bitbucket.org/mforbes/persist/issues

Installing
----------

This package can be installed from `from the bitbucket
project <https://bitbucket.org/mforbes/persist>`__:

.. code:: bash

   pip install hg+https://bitbucket.org/mforbes/persist

DataSet Format
==============

.. toctree::
   :maxdepth: 1
   
   notebooks/DataSet Format

API
===

.. toctree::
   :maxdepth: 3

   api/persist

Developer Notes
===============

.. toctree::
   :maxdepth: 1

   notebooks/Pickle
   notebooks/Dev Notes

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
