"""Persistent archival of python objects in an importable format.

The method of archival is essentially pickling to disk for long term storage in
a human readable format.  The archives use importable code and so are
relatively robust to code changes (in the event that an interface changes, one
can manually edit the archive making appropriate changes). Large binary data is
stored in hdf5 format for efficiency.

**Source:**
  https://bitbucket.org/mforbes/persist
**Issues:**
  https://bitbucket.org/mforbes/persist/issues

"""
import sys

from setuptools import setup, find_packages

NAME = "persist"

install_requires = [
    'zope.interface>=3.8.0',
    'six',
]

test_requires = [
    'pytest>=2.8.1',
    'pytest-cov>=2.2.0',
    'pytest-flake8',
    'coverage',
    'flake8',
    'pep8',     # Needed by flake8: dependency resolution issue if not pinned
    'numpy>=1.16',
    'scipy',
    'h5py',
]

extras_require = dict(
    doc=['mmf_setup',
         'sphinx>=1.3.1',
         'sphinxcontrib-zopeext',
         'nbsphinx>=0.2.13',
    ]
)

# Remove NAME from sys.modules so that it gets covered in tests. See
# http://stackoverflow.com/questions/11279096
for mod in sys.modules.keys():
    if mod.startswith(NAME):
        del sys.modules[mod]
del mod


setup(name=NAME,
      version='3.0',
      packages=find_packages(),

      install_requires=install_requires,
      tests_require=test_requires,
      extras_require=extras_require,

      # Metadata
      author='Michael McNeil Forbes',
      author_email='michael.forbes+bitbucket@gmail.com',
      url='https://bitbucket.org/mforbes/persist',
      description="Persistent importable archival of python objects to disk",
      long_description=__doc__,
      license='BSD',

      classifiers=[
          # How mature is this project? Common values are
          #   3 - Alpha
          #   4 - Beta
          #   5 - Production/Stable
          'Development Status :: 4 - Beta',

          # Indicate who your project is intended for
          'Intended Audience :: Developers',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: Utilities',

          # Pick your license as you wish (should match "license" above)
          'License :: OSI Approved :: BSD License',

          # Specify the Python versions you support here. In particular, ensure
          # that you indicate whether you support Python 2, Python 3 or both.
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
      ],
      )
