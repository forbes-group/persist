"""Persistent archival of python objects in an importable format.

The method of archival is essentially pickling to disk for long term storage in
a human readable format.  The archives use importable code and so are
relatively robust to code changes (in the event that an interface changes, one
can manually edit the archive making appropriate changes). Large binary data is
stored in hdf5 format for efficiency.
"""

# Author: Michael McNeil Forbes <mforbes@physics.ubc.ca>

#from distribute_setup import use_setuptools
#use_setuptools()

dependencies = []

if __name__ == "__main__":
    from setuptools import setup, find_packages

setup(name='persist',
      version='1.0',
      packages=find_packages(),

      # Project uses sphinx for documentation, so ensure that we have
      # docutils:
      install_requires=["zope.interface>=3.8.0"],

      extras_require={
          'doc': ["Sphinx>=1.1.2",
                  "sphinxcontrib-zopeext>=0.2"],
      },

      # Metadata
      author='Michael McNeil Forbes',
      author_email='michael.forbes+bitbucket@gmail.com',
      url='http://alum.mit.edu/www/mforbes',
      description="Persistent archival of python objects to disk",
      long_description=__doc__,
      )
