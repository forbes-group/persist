Persistent Archival of Python Objects
=====================================

|Documentation Status| |Language grade: Python| |Tests| |Pypi|
|pyversions|\ |Code style: black|

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
   the generated code is highly structured and not so "pretty", but can
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

As of version 3.1, we release only to PyPI using
```poetry`` <https://python-poetry.org/>`__. Here is the typical
development/release cycle.

-  First make sure you have a development environment with Mercurial,
   the evolve extension, topics enabled, [Black], [Nox], and
   [nbconvert].

-  Set your virtual environment and run a shell to work in:

``bash    poetry env use python3.8    poetry shell    poetry install -E doc -E test``

-  Start a development branch, i.e.:

   .. code:: bash

       hg branch 3.2

-  Change version to ``'3.2.dev0'`` in ``pyproject.toml`` and commit
   this changes:

   .. code:: bash

       hg com -m "BRN: Start working on branch 3.2"
       hg push --new-branch -r . 

-  Complete your changes making sure code is well tested etc. While
   working on specific features, you should always use topics:

   .. code:: bash

       hg topic new-feature

   When you push to Heptapod, the commits in these topics will remain in
   the draft phase, allowing you to rebase, etc. as needed to clean the
   history. We have setup automatic pushes to
   `GitHub <https://github.com/forbes-group/persist>`__ and you can see
   the status of the tests with the badge: |Github Tests|.

   To run the tests locally, you should be able to just run:

   .. code:: bash

       nox

-  Once everything is working and tested, push it to Heptapod and create
   Merge Requests:

-  First merge all open topics to the development branch.

-  Then change the revision in ``pyproject.toml`` to ``'3.2'``, dropping
   the ``'.dev'``. Push this to Heptapod and create a merge request to
   merge this to the default branch. Review the changes, and complete
   the Merge. Unlike previously, **do not close the branch.** Just leave
   it.

-  Start work on next branch::

   .. code:: bash

       hg up 3.2
       hg branch 3.3

PyPI
----

To release on PyPI:

\`\`\`bash poetry build poetry

::

    hg up 3.2
    poetry build

    python setup.py sdist bdist_wheel
    twine upload dist/persist-3.2*

Anaconda Cloud
--------------

To release on Anaconda Cloud (replace the filename as appropriate):

::

    conda build meta.yaml
    anaconda upload --all /data/apps/conda/conda-bld/osx-64/persist-3.0-py37_0.tar.bz2

.. |Github Tests| image:: https://github.com/forbes-group/persist/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/forbes-group/persist/actions/workflows/tests.yml

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
