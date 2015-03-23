import os
import shutil
import sys
import tempfile

import nose.tools

from test_archive import NoStrNoRepr, np  #, sp, h5py

archive = sys.modules['persist.archive']


class TestDataSet(object):
    def setUp(self):
        # Make a temporary directory for tests.
        self.ds_name = tempfile.mkdtemp(dir='.')[2:]
        os.rmdir(self.ds_name)

    def tearDown(self):
        if os.path.exists(self.ds_name):
            shutil.rmtree(self.ds_name)

    def test_failure1(self):
        r"""Regression test for a bug that left a DataSet in a bad
        state."""
        ds = archive.DataSet(self.ds_name, 'w')

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
        nose.tools.assert_equals(1, ds['x'])

    def test_no_str_no_repr(self):
        r"""Test that str and repr are not called unnecessarily."""
        ds = archive.DataSet(self.ds_name, 'w')
        ds.a = NoStrNoRepr()

    def test_large_array(self):
        """Test large array in dataset"""
        a = np.arange(1000, dtype=float)
        ds = archive.DataSet(self.ds_name, 'w')
        ds.a = a
        del ds
        ds = archive.DataSet(self.ds_name, 'r')
        assert np.allclose(a, ds.a)

    def test_import1(self):
        """Test import of dataset"""
        if np is None:
            raise nose.SkipTest, 'Skipping numpy dependent test'

        module_name = 'module'

        ds_name = os.path.join(self.ds_name, module_name)

        a = np.arange(1000, dtype=float)
        ds = archive.DataSet(ds_name, 'w')
        ds.a = a
        ds['b'] = 'b'
        ds.c = 1
        del ds

        # Try importing
        sys.path.append(self.ds_name)
        ds = __import__(module_name)

        assert ds._info_dict == dict(a=None, b='b', c=None)
        assert np.allclose(ds.a, np.arange(1000, dtype=float))
        assert ds.c == 1

    @nose.tools.raises(ValueError)
    def test_noclobber(self):
        """Test access to an existing non-dataset."""
        archive.DataSet('.')

    @nose.tools.raises(ValueError)
    def test_noexist(self):
        """Test access to a non-existing dataset."""
        archive.DataSet(self.ds_name, 'r')

    def test_non_synchronize(self):
        """Test non-sychronized access."""
        ds = archive.DataSet(self.ds_name, 'w', synchronize=False)
        a = np.arange(1000, dtype=float)
        ds.a = a
        ds['a'] = a.shape
        ds['b'] = 'b'
        ds.c = 1

        del ds

        ds = archive.DataSet(self.ds_name, 'r')

        assert ds._info_dict == dict(a=a.shape, b='b', c=None)
        assert np.allclose(ds.a, a)
        assert ds.c == 1

    @nose.tools.raises(IOError)
    def test_timeout1(self):
        """Test lock timeout."""
        ds = archive.DataSet(self.ds_name, 'w')
        ds.close()

        # Touch the lock-file
        open(os.path.join(self.ds_name, ds._lock_file_name), 'w').close()

        ds = archive.DataSet(self.ds_name, 'w', timeout=0)
        ds.x = 1
        del ds

    @nose.tools.raises(IOError)
    def test_timeout2(self):
        """Test lock timeout."""
        ds = archive.DataSet(self.ds_name, 'w')
        ds.close()

        # Touch the lock-file
        open(os.path.join(self.ds_name, ds._lock_file_name), 'w').close()

        ds = archive.DataSet(self.ds_name, 'w', synchronize=False, timeout=0)


class TestCoverage(object):
    def setUp(self):
        # Make a temporary directory for tests.
        self.ds_name = tempfile.mkdtemp(dir='.')[2:]
        os.rmdir(self.ds_name)

    def tearDown(self):
        if os.path.exists(self.ds_name):
            shutil.rmtree(self.ds_name)

    @nose.tools.raises(NotImplementedError)
    def test_bad_mode(self):
        archive.DataSet(self.ds_name, mode='oops')
