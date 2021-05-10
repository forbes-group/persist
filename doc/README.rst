Persistent Archival of Python Objects
=====================================

|Documentation Status| |Language grade: Python| |Tests| |Pypi|
|pyversions|\ |black_img| |Code style: black|

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

**Source:** https://alum.mit.edu/www/mforbes/hg/forbes-group/persist

**Issues:** https://alum.mit.edu/www/mforbes/hg/forbes-group/issues

.. |Documentation Status| image:: https://readthedocs.org/projects/persist/badge/?version=latest
   :target: https://persist.readthedocs.io/en/latest/?badge=latest
.. |Language grade: Python| image:: https://img.shields.io/lgtm/grade/python/g/forbes-group/persist.svg
   :target: https://lgtm.com/projects/g/forbes-group/persist/context:python
.. |Tests| image:: https://github.com/forbes-group/persist/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/forbes-group/persist/actions/workflows/tests.yml
.. |Pypi| image:: https://img.shields.io/pypi/v/persist.svg
   :target: https://pypi.python.org/pypi/persist
.. |pyversions| image:: https://img.shields.io/pypi/pyversions/persist.svg
   :target: https://pypi.python.org/pypi/persist
.. |black_img| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
.. |Code style: black| image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black

Installing
----------

This package can be installed from
`PyPI <https://pypi.org/project/persist/>`__:

.. code:: bash

   python3 -m pip install persist

or from source:

.. code:: bash

   python3 -m pip install hg+https://alum.mit.edu/www/mforbes/hg/forbes-group/persist

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

Release Notes
=============

As of version 3.0, we now provide a conda ``meta.yaml`` file. Here are
the instructions for releasing on PyPI and Anaconda Cloud:

-  Start a development branch:

   .. code:: bash

      hg branch 3.0

-  Change version to ``'3.0dev1'`` in ``setup.py``, ``meta.yaml``, and
   ``persist/__init__.py`` and commit these changes:

   .. code:: bash

      hg com -m "BRN: Start working on branch 3.0"

-  Complete your changes making sure code is well tested etc.

-  Change version to ``'3.0'`` in ``setup.py``, ``meta.yaml``, and
   ``persist/__init__.py`` and commit these changes:

   .. code:: bash

      hg com -m "REL: 3.0"

-  Push your work to bitbucket:

   .. code:: bash

      hg push --new-branch -r . 

-  (Optional) Create a PR and merge::

   .. code:: bash

      open https://bitbucket.org/mforbes/persist/pull-requests/new?source=3.0&t=1

-  (Optional) Manually close branch and merge into default (this is what
   accepting the the PR above would do)::

   .. code:: bash

      hg up 3.0
      hg com --close-branch -m "Close branch 3.0"
      hg up default
      hg merge 3.0
      hg com -m "Merge in 3.0"

-  Start work on next branch::

   .. code:: bash

      hg up 3.0
      hg branch 3.1

-  Change version to ``'3.1dev1'`` in ``setup.py``, ``meta.yaml``, and
   ``persist/__init__.py`` and commit these changes:

   .. code:: bash

      hg com -m "BRN: Start working on branch 3.1"

PyPI
----

To release on PyPI:

::

   hg up 3.0
   python setup.py sdist bdist_wheel
   twine upload dist/persist-3.0*

Anaconda Cloud
--------------

To release on Anaconda Cloud (replace the filename as appropriate):

::

   conda build meta.yaml
   anaconda upload --all /data/apps/conda/conda-bld/osx-64/persist-3.0-py37_0.tar.bz2

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
