import os
import sys
import threading
import time

import pytest

from test_archive import NoStrNoRepr

from persist import archive

if sys.version_info >= (3, 0):
    from importlib import reload


def test_1():
    import tempfile, shutil, os

    t = tempfile.mkdtemp(dir=".")
    os.rmdir(t)
    modname = t[2:]
    ds = archive.DataSet(modname, "w")
    ds.d = dict(a=1, b=2)  # Will write to disk
    ds1 = archive.DataSet(modname, "r")
    assert ds1.d == {"a": 1, "b": 2}

    ds.d["a"] = 6  # No write!
    assert ds1.d["a"] == 1

    import time

    d = ds.d
    d["a"] = 6
    time.sleep(1)
    ds.d = d  # This assignment will write
    assert ds1.d["a"] == 6

    shutil.rmtree(t)


class TestDataSet(object):
    def test_failure1(self, ds_name):
        r"""Regression test for a bug that left a DataSet in a bad
        state."""
        ds = archive.DataSet(ds_name, "w")

        class A(object):
            def __repr__(self):
                raise Exception()

        a = A()
        try:
            ds["a"] = a
        except Exception:
            pass

        # Archive should still be in an okay state
        ds["x"] = 1
        assert ds["x"] == 1

    def test_no_str_no_repr(self, ds_name):
        r"""Test that str and repr are not called unnecessarily."""
        ds = archive.DataSet(ds_name, "w")
        ds.a = NoStrNoRepr()

    def test_large_array(self, ds_name, np, data_format):
        """Test large array in dataset"""
        a = np.arange(1000, dtype=float)
        ds = archive.DataSet(ds_name, "w", data_format=data_format)
        ds.a = a
        del ds
        ds = archive.DataSet(ds_name, "r")
        assert np.allclose(a, ds.a)

    def test_import1(self, ds_name, np, data_format):
        """Test import of dataset"""
        module_name = "module"

        ds_name_ = os.path.join(ds_name, module_name)

        a = np.arange(1000, dtype=float)
        ds = archive.DataSet(ds_name_, "w", data_format=data_format)
        ds.a = a
        ds["b"] = "b"
        ds.c = 1
        del ds

        # Try importing
        sys.path.append(ds_name)
        ds_mod = __import__(module_name)
        reload(ds_mod)
        assert ds_mod._info_dict == dict(a=None, b="b", c=None)

        # We have not imported a yet, so it should not be there
        assert not hasattr(ds_mod, "a")
        __import__(module_name + ".a")

        # Now it should be there
        assert np.allclose(ds_mod.a, np.arange(1000, dtype=float))

        __import__(module_name + ".c")
        assert ds_mod.c == 1

    def test_noclobber(self):
        """Test access to an existing non-dataset."""
        with pytest.raises(ValueError):
            archive.DataSet(".")

    def test_noexist(self, ds_name):
        """Test access to a non-existing dataset."""
        with pytest.raises(ValueError):
            archive.DataSet(ds_name, "r")

    def test_non_synchronize(self, ds_name, np, data_format):
        """Test non-sychronized access."""
        ds = archive.DataSet(ds_name, "w", synchronize=False, data_format=data_format)
        a = np.arange(1000, dtype=float)
        ds.a = a
        ds["a"] = a.shape
        ds["b"] = "b"
        ds.c = 1

        del ds

        ds = archive.DataSet(ds_name, "r")

        assert ds._info_dict == dict(a=a.shape, b="b", c=None)
        assert np.allclose(ds.a, a)
        assert ds.c == 1

    def test_non_scoped(self, ds_name, np, data_format):
        ds = archive.DataSet(ds_name, "w", scoped=False, data_format=data_format)
        a = np.arange(1000, dtype=float)
        ds.a = a
        ds["a"] = a.shape
        ds["b"] = "b"
        ds.c = 1

        del ds

        ds = archive.DataSet(ds_name, "r")

        assert ds._info_dict == dict(a=a.shape, b="b", c=None)
        assert np.allclose(ds.a, a)
        assert ds.c == 1

    def test_timeout1(self, ds_name):
        """Test lock timeout."""
        ds = archive.DataSet(ds_name, "w")
        ds.close()

        # Touch the lock-file
        open(os.path.join(ds_name, ds._lock_file_name), "w").close()

        ds = archive.DataSet(ds_name, "w", timeout=0)
        with pytest.raises(IOError):
            ds.x = 1
        del ds

    def test_timeout2(self, ds_name):
        """Test lock timeout."""
        ds = archive.DataSet(ds_name, "w")
        ds.close()

        # Touch the lock-file
        open(os.path.join(ds_name, ds._lock_file_name), "w").close()

        with pytest.raises(IOError):
            ds = archive.DataSet(ds_name, "w", synchronize=False, timeout=0)
        del ds

    def test_timeout3(self, ds_name):
        """Test lock timeout, but with lockfile released during timeout."""
        ds = archive.DataSet(ds_name, "w")
        ds.close()

        # Touch the lock-file
        lockfile = os.path.join(ds_name, ds._lock_file_name)
        open(lockfile, "w").close()

        def release(lockfile=lockfile, wait=0.1):
            time.sleep(wait)
            os.remove(lockfile)

        threading.Thread(target=release).start()

        # The lockfile should be released before the timeout, allowing the dataset to
        # be accessed.
        ds = archive.DataSet(ds_name, "w", timeout=2)
        ds.x = 1
        del ds


class TestCoverage(object):
    """
    >>> ds = archive.DataSet(getfixture('ds_name'), "w")
    >>> ds._insert(a=1.0, info={"a": "A lovely variable"})
    ['a']
    >>> ds._insert(x_0=1.0)
    ['x_0']
    >>> ds._insert({})
    ['x_1']
    >>> list(ds)
    ['a', 'x_0', 'x_1']
    >>> ds
    DataSet(module_name='...', path='.', synchronize=True, array_threshold=100,
    backup_data=False, name_prefix='x_')
    """

    def test_bad_mode(self, ds_name):
        with pytest.raises(NotImplementedError):
            archive.DataSet(ds_name, mode="oops")

    def test__insert(self, ds_name):
        ds = archive.DataSet(ds_name, "w")
        ds._insert({})
        ds.close()
        with pytest.raises(IOError):
            ds._lock()

        ds = archive.DataSet(ds_name, "r")
        with pytest.raises(ValueError):
            ds._insert(c=3.0)
        ds.close()

    def test__keys(self, ds_name):
        ds = archive.DataSet(ds_name, "w")
        ds._insert(a=1.0, info={"a": "A lovely variable"})
        assert ds._keys() == ["a"]

    def test_read_only(self, ds_name):
        ds = archive.DataSet(ds_name, "w")
        ds._insert(a=1.0)
        ds.close()

        ds = archive.DataSet(ds_name, "r")
        with pytest.raises(ValueError):
            ds["a"] = "A lovely variable"


def test_issue_10(ds_name, np):
    """Regression for issue 10 that __init__.py backup files stick arround."""
    ds = archive.DataSet(ds_name, mode="w", backup_data=False)
    ds.a = np.ones(10)
    ds.x = np.ones(100)
    for f in os.listdir(ds_name):
        assert not f.endswith(".bak")
