import os
import shutil
import sys
import tempfile

import pytest

from test_archive import NoStrNoRepr

archive = sys.modules['persist.archive']


@pytest.fixture
def ds_name():
    ds_name = tempfile.mkdtemp(dir='.')[2:]
    os.rmdir(ds_name)
    yield ds_name
    if os.path.exists(ds_name):
        shutil.rmtree(ds_name)


@pytest.fixture
def np():
    try:
        import numpy
        numpy.random.seed(3)
        return numpy
    except ImportError:         # pragma: nocover
        pytest.skip("Skipping test that depends on numpy")


class TestDataSet(object):
    def test_failure1(self, ds_name):
        r"""Regression test for a bug that left a DataSet in a bad
        state."""
        ds = archive.DataSet(ds_name, 'w')

        class A(object):
            def __repr__(self):
                raise Exception()

        a = A()
        try:
            ds['a'] = a
        except:
            pass

        # Archive should still be in an okay state
        ds['x'] = 1
        assert ds['x'] == 1

    def test_no_str_no_repr(self, ds_name):
        r"""Test that str and repr are not called unnecessarily."""
        ds = archive.DataSet(ds_name, 'w')
        ds.a = NoStrNoRepr()

    def test_large_array(self, ds_name, np):
        """Test large array in dataset"""
        a = np.arange(1000, dtype=float)
        ds = archive.DataSet(ds_name, 'w')
        ds.a = a
        del ds
        ds = archive.DataSet(ds_name, 'r')
        assert np.allclose(a, ds.a)

    def test_import1(self, ds_name, np):
        """Test import of dataset"""
        module_name = 'module'

        ds_name_ = os.path.join(ds_name, module_name)

        a = np.arange(1000, dtype=float)
        ds = archive.DataSet(ds_name_, 'w')
        ds.a = a
        ds['b'] = 'b'
        ds.c = 1
        del ds

        # Try importing
        sys.path.append(ds_name)
        ds = __import__(module_name)

        assert ds._info_dict == dict(a=None, b='b', c=None)
        assert np.allclose(ds.a, np.arange(1000, dtype=float))
        assert ds.c == 1

    def test_noclobber(self):
        """Test access to an existing non-dataset."""
        with pytest.raises(ValueError):
            archive.DataSet('.')

    def test_noexist(self, ds_name):
        """Test access to a non-existing dataset."""
        with pytest.raises(ValueError):
            archive.DataSet(ds_name, 'r')

    def test_non_synchronize(self, ds_name, np):
        """Test non-sychronized access."""
        ds = archive.DataSet(ds_name, 'w', synchronize=False)
        a = np.arange(1000, dtype=float)
        ds.a = a
        ds['a'] = a.shape
        ds['b'] = 'b'
        ds.c = 1

        del ds

        ds = archive.DataSet(ds_name, 'r')

        assert ds._info_dict == dict(a=a.shape, b='b', c=None)
        assert np.allclose(ds.a, a)
        assert ds.c == 1

    def test_non_scoped(self, ds_name, np):
        ds = archive.DataSet(ds_name, 'w', scoped=False)
        a = np.arange(1000, dtype=float)
        ds.a = a
        ds['a'] = a.shape
        ds['b'] = 'b'
        ds.c = 1

        del ds

        ds = archive.DataSet(ds_name, 'r')

        assert ds._info_dict == dict(a=a.shape, b='b', c=None)
        assert np.allclose(ds.a, a)
        assert ds.c == 1

    def test_timeout1(self, ds_name):
        """Test lock timeout."""
        ds = archive.DataSet(ds_name, 'w')
        ds.close()

        # Touch the lock-file
        open(os.path.join(ds_name, ds._lock_file_name), 'w').close()

        ds = archive.DataSet(ds_name, 'w', timeout=0)
        with pytest.raises(IOError):
            ds.x = 1
        del ds

    def test_timeout2(self, ds_name):
        """Test lock timeout."""
        ds = archive.DataSet(ds_name, 'w')
        ds.close()

        # Touch the lock-file
        open(os.path.join(ds_name, ds._lock_file_name), 'w').close()

        with pytest.raises(IOError):
            ds = archive.DataSet(ds_name, 'w', synchronize=False, timeout=0)
        del ds


class TestCoverage(object):
    def test_bad_mode(self, ds_name):
        with pytest.raises(NotImplementedError):
            archive.DataSet(ds_name, mode='oops')
