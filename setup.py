"""Persistent archival of python objects in an importable format.

The method of archival is essentially pickling to disk for long term storage in
a human readable format.  The archives use importable code and so are
relatively robust to code changes (in the event that an interface changes, one
can manually edit the archive making appropriate changes). Large binary data is
stored in hdf5 format for efficiency.
"""
import sys

from setuptools import setup, find_packages
from setuptools.command.test import test as original_test

import persist
VERSION = persist.__version__

# Remove mmfutils so that it gets properly covered in tests. See
# http://stackoverflow.com/questions/11279096
for mod in sys.modules.keys():
    if mod.startswith('persist'):
        del sys.modules[mod]
del mod


class test(original_test):
    description = "Run all tests and checks (customized for this project)"

    def finalize_options(self):
        # Don't actually run any "test" tests (we will use nosetest)
        self.test_suit = None

    def run(self):
        # Call this to do complicated distribute stuff.
        original_test.run(self)

        for cmd in ['nosetests', 'flake8', 'check']:
            try:
                self.run_command(cmd)
            except SystemExit, e:
                if e.code:
                    raise

setup(name='persist',
      version=VERSION,
      packages=find_packages(),
      cmdclass=dict(test=test),

      install_requires=[
          "zope.interface>=3.8.0"
      ],

      setup_requires=[
          'sphinx>=1.3.1',
          'nose>=1.3',
          'coverage',
          'flake8',
          'sphinxcontrib-zopeext'
      ],

      # Metadata
      author='Michael McNeil Forbes',
      author_email='michael.forbes+bitbucket@gmail.com',
      url='https://bitbucket.org/mforbes_pristine/persist',
      description="Persistent importable archival of python objects to disk",
      long_description=__doc__,
      license='LPGL',

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
