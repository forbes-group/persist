from __future__ import print_function

import glob
import math
import os.path
import shutil
import sys
import warnings

import pytest

from persist import objects
from persist import interfaces
from persist import archive


# This is needed until a later release of py.test.  See Issue #2430
# https://github.com/pytest-dev/pytest/issues/2430
warnings.simplefilter('always', UserWarning)


class A(object):
    """Example of a class with an archive function."""
    def __init__(self, d, l):
        self.d = d
        self.l = l

    def get_persistent_rep(self, env=None):
        """Example of an archive function."""
        imports = archive.get_imports(self)
        args = dict(d=self.d, l=self.l)
        rep = imports[0][-1] + '(d=d, l=l)'
        return (rep, args, imports)


class B(object):
    """Example of a class without an archive function but with a repr
    function."""
    def __init__(self, d, l):
        self.d = d
        self.l = l

    def __repr__(self):
        return "B(d=%r, l=%r)" % (self.d, self.l)


class C(objects.Archivable):
    """Example of a class inheriting from Archivable."""
    def __init__(self, d, l):
        self.d = d
        self.l = l

    def items(self):
        """This must be overloaded."""
        args = [('d', self.d),
                ('l', self.l)]
        return args


class Functions(object):
    """Example of a class with methods that are archivable.   This
    gives one way to use "archivable functions with associated
    data"."""
    def __init__(self, a):
        self.a = 2

    def __repr__(self):
        """Use repr to make `self` archivable."""
        return "Functions(a=%r)" % (self.a, )

    def f(self, x):
        """A function that depends on a."""
        return self.a*x


class NestedClasses(object):
    class NestedFunctions(Functions):
        """Example of a nested class."""


class TException(Exception):
    pass


class MyDict(dict):
    """Class to test archiving of derived classes."""


class MyList(list):
    """Class to test archiving of derived classes."""


class MyTuple(tuple):
    """Class to test archiving of derived classes."""


class NoStrNoRepr(objects.Archivable):
    r"""This class provides its own get_persistent_rep function, so __str__ and
    __repr__ should never be called."""
    def get_persistent_rep(self, env):
        rep = 'NoStrNoRepr()'
        args = {}
        imports = [
            (archive.get_module(self).__name__, 'NoStrNoRepr', 'NoStrNoRepr')]
        return (rep, args, imports)

    def __str__(self):
        raise NotImplementedError

    def __repr__(self):
        raise NotImplementedError


class Pickleable(object):
    def __init__(self, x):
        self.x = x
        self.pickled = False

    def __getstate__(self):
        return dict(x=self.x)

    def __setstate__(self, state):
        self.x = state['x']
        self.pickled = True


class ToolsMixin(object):
    """Some testing tools"""
    def _test_archiving(self, obj):
        """Fail if obj does not acrhive properly."""
        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec s in ld
        assert 1 == len(ld)
        assert obj == ld['x']


class TestSuite(ToolsMixin):
    """Test the functionality of the archive module."""
    def test_1(self):
        """Test archiving of instance A()"""
        l = [1, 2, 3]
        d = {'a': 1.0, 'b': 2.0, 'l': l}
        a = A(d=d, l=l)
        arch = archive.Archive()
        arch.insert(a=a)
        s = str(arch)
        ld = {}
        exec s in ld
        assert (ld['a'].l == a.l and id(ld['a'].l) != id(a.l))
        assert (ld['a'].d == a.d and id(ld['a'].d) != id(a.d))

    def test_2(self):
        """Test archiving of instance B()"""
        l = [1, 2, 3]
        d = {'a': 1.0, 'b': 2.0, 'l': l}
        a = B(d=d, l=l)
        arch = archive.Archive()
        arch.insert(a=a)
        s = str(arch)
        ld = {}
        exec s in ld
        assert (ld['a'].l == a.l and id(ld['a'].l) != id(a.l))
        assert (ld['a'].d == a.d and id(ld['a'].d) != id(a.d))

    def test_3(self):
        """Test archiving of instance C()"""
        l = [1, 2, 3]
        d = {'a': 1.0, 'b': 2.0, 'l': l}
        a = C(d=d, l=l)
        s = a.archive('a')
        ld = {}
        exec s in ld
        assert (ld['a'].l == a.l and id(ld['a'].l) != id(a.l))
        assert (ld['a'].d == a.d and id(ld['a'].d) != id(a.d))

    def test_4(self):
        """Test archiving of class C"""
        a = C
        arch = archive.Archive()
        arch.insert(a=a)
        s = str(arch)
        ld = {}
        exec s in ld
        assert (ld['a'] is C)

    def test_simple_types(self):
        """Test archiving of various simple types."""
        self._test_archiving(1)
        self._test_archiving(1.0)
        self._test_archiving(1.0+2j)
        self._test_archiving(True)
        self._test_archiving(False)
        self._test_archiving("asd")
        self._test_archiving((1, ))
        self._test_archiving((1, 2))
        self._test_archiving([1])
        self._test_archiving([1, 2])
        self._test_archiving((1, 1))
        self._test_archiving(math.sin)
        self._test_archiving(None)
        self._test_archiving(type(None))

    def test_derived_types(self):
        """Test archiving of simple derived types..."""
        arch = archive.Archive()
        d = MyDict(a=1, b=2)
        l = MyList([1, 2])
        t = MyTuple((1, 2))
        arch.insert(d=d, l=l, t=t)
        s = str(arch)
        ld = {}
        exec s in ld
        assert (ld['d']['a'] == d['a'])
        assert isinstance(ld['d'], MyDict)
        assert (ld['l'] == l)
        assert isinstance(ld['l'], MyList)
        assert (ld['t'] == t)
        assert isinstance(ld['t'], MyTuple)

    def test_mutual_deps(self):
        """Test non-reduction of non-simple mutual dependence."""
        x = [1]
        y = [2]
        z = [x, y, x]
        arch = archive.Archive()
        arch.insert(z=z)
        s = str(arch)
        ld = {}
        exec s in ld
        assert ld['z'][0] is ld['z'][2]

    def test_insert_1(self):
        """Check for _name exception."""
        arch = archive.Archive()
        with pytest.raises(ValueError):
            arch.insert(_a=1)

    def test_check_on_insert(self):
        """Make sure check_on_insert works."""
        class A():
            def get_persistent_rep(self, env=None):
                raise TException()
        arch = archive.Archive()
        arch.check_on_insert = True
        with pytest.raises(TException):
            arch.insert(a=A())

    def test_cyclic_exception(self):
        """Make sure cyclic deps raise an error."""
        A = []
        A.append(A)
        arch = archive.Archive()
        arch.insert(a=A)
        with pytest.raises(archive.CycleError):
            arch.make_persistent()

    def test_archivable_members(self):
        """Test the archiving of bound class members."""
        F = Functions(a=2)
        arch = archive.Archive()
        arch.insert(f=F.f, g=Functions.f)
        s = str(arch)
        ld = {}
        exec s in ld
        assert F.f(2) == ld['f'](2)
        assert F.f(2), ld['g'](F == 2)

    @pytest.mark.skip(reason="Known Failure")
    def test_nested_classes(self):  # pragma: nocover
        """Test the archiving of nested classes."""
        F = NestedClasses.NestedFunctions(a=2)
        arch = archive.Archive()
        arch.insert(f=F.f, g=NestedClasses.NestedFunctions.f)
        s = str(arch)
        ld = {}
        exec s in ld
        assert F.f(2) == ld['f'](2)
        assert F.f(2), ld['g'](F == 2)

    def test_builtins(self):
        arch = archive.Archive()
        arch.insert(m=math.sin, p=print)
        s = str(arch)
        ld = {}
        exec s in ld
        assert ld['m'] is math.sin
        assert ld['p'] is print

    def test_pickle(self):
        r"""Test archiving of picklable objects as a last resort."""
        arch = archive.Archive()
        p = Pickleable(x=2)
        arch.insert(p=p)
        s = str(arch)
        ld = {}
        exec s in ld
        p1 = ld['p']
        assert not p.pickled
        assert p1.pickled
        assert p.x == p1.x

    def test_get_persistent_rep_regression_1(self):
        r"""Regression for usage of get_persistent_rep().  Exceptions raised
        should not be ignored."""
        import zope.interface

        class A(object):
            zope.interface.implements(interfaces.IArchivable)

            def get_persistent_rep(self, env=None):
                raise Exception()

        arch = archive.Archive()
        a = A()
        arch.insert(a=a)
        with pytest.raises(Exception):
            str(arch)

    def test__replace_rep_regression_issue_11a(self):
        r"""Regression test of bad replacement in numpy array rep."""
        rep = ("dict(Q=_Q, a=_numpy.fromstring(" +
               "'`\\xbf=_Q-\\xf2?', dtype='<f8'))")
        replacements = {'_Q': '1.0'}
        rep = archive._replace_rep(rep, replacements)
        assert (rep ==
                "dict(Q=1.0, a=_numpy.fromstring(" +
                "'`\\xbf=_Q-\\xf2?', dtype='<f8'))")

    def test_scoped_too_many_args_issue_12(self):
        r"""Regression test for scoped representations with too many
        arguments."""
        arch = archive.Archive(scoped=True)
        ls = [[] for _n in xrange(500)]
        arch.insert(ls=ls)
        d = {}
        exec str(arch) in d
        assert len(d['ls']) == 500


class TestNumpy(ToolsMixin):
    """Run numpy specific tests"""
    def test_numpy_types(self, np):
        """Test archiving of numpy types"""
        self._test_archiving(np.sin)

        obj = dict(inf=np.inf,
                   neg_inf=-np.inf,
                   nan=np.nan,
                   array=np.array([1, np.inf, np.nan]),
                   ndarray=np.array([[1, 2], [3, 4]]),
                   matrix=np.matrix([[1, 2], [3, 4]]))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec s in ld
        assert 1 == len(ld)
        assert np.isnan(ld['x']['nan'])
        assert np.inf == (ld['x']['inf'])
        assert -np.inf == (ld['x']['neg_inf'])

        a0 = obj['array']
        a1 = ld['x']['array']

        assert a0[0] == a1[0]
        assert a0[1] == a1[1]
        assert np.isnan(a1[2])

        a0 = obj['ndarray']
        a1 = ld['x']['ndarray']

        assert (a0 == a1).all()
        assert a0.shape == a1.shape

    @pytest.mark.skip(reason="Known Failure")
    def test_numpy_types2(self, np):  # pragma: nocover
        """Test archiving of complex numpy types"""
        obj = dict(inf=1+1j*np.inf,
                   neg_inf=1-1j*np.inf,
                   nan=1-1j*np.nan,
                   array=np.array([1, 1+1j*np.inf, 1+1j*np.nan]))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec s in ld
        assert 1 == len(ld)
        assert np.isnan(ld['x']['nan'])
        assert np.inf == (ld['x']['inf'])
        assert -np.inf == (ld['x']['neg_inf'])

        a0 = obj['array']
        a1 = ld['x']['array']

        assert a0[0] == a1[0]
        assert a0[1] == a1[1]
        assert np.isnan(a1[2])

    def test__replace_rep_regression_issue_11b(self, np):
        r"""Regression test of bad replacement in numpy array rep.

        This is the same example as test__replace_rep_regression_1a but shows
        how it comes about from a high level.
        """
        c = objects.Container(Q=1.0, alpha=np.array(1.1360639305457525))
        arch = archive.Archive()
        arch.insert(c=c)
        d = {}
        exec str(arch) in d
        assert d['c'].alpha == c.alpha

    def test_data_duplicate_regression(self, np):
        """Regression against a bug where multiple calls to make_persistent()
        would insert multiple copies of data into self.data"""

        a = archive.Archive(array_threshold=2)
        M = np.random.rand(10)
        a.insert(M=M)
        s = str(a)
        with pytest.warns(UserWarning) as record:
            rep, files = a.save_data()
        assert len(record) == 1
        assert record[0].message.args[0] == (
            "Data arrays ['array_0'] exist but no datafile specified. " +
            "Save data manually and populate in _arrays dict.")

        assert len(a.data) == 1
        s = str(a)
        with pytest.warns(UserWarning) as record:
            rep, files = a.save_data()
        assert len(record) == 1
        assert record[0].message.args[0] == (
            "Data arrays ['array_0'] exist but no datafile specified. " +
            "Save data manually and populate in _arrays dict.")

        assert len(a.data) == 1

    def test_external_data_no_datafile(self, np, scoped):
        """Test archive without datafile."""

        # Archive without specified datafile will not save data.  This should
        # raise a warning.
        a = archive.Archive(scoped=scoped, array_threshold=2)
        np.random.seed(1)
        M = np.random.rand(10)
        a.insert(M=M)
        s = str(a)
        with pytest.warns(UserWarning) as record:
            rep, files = a.save_data()
        assert len(record) == 1
        assert record[0].message.args[0] == (
            "Data arrays ['array_0'] exist but no datafile specified. " +
            "Save data manually and populate in _arrays dict.")

        # Data must be provided when evaluated
        d = dict(_arrays=dict(array_0=M.copy()))
        exec s in d
        assert np.allclose(d['M'], M)

    def test_external_data(self, np, data_format, datafile):
        """Test saving external data."""
        a = archive.Archive(array_threshold=3)
        np.random.seed(1)
        M = np.random.rand(10)
        a.insert(M=M)
        s = str(a)
        rep, files = a.save_data(datafile=datafile, data_format=data_format)

        d = {a.data_name: archive.ArrayManager.load_arrays(rep)}
        exec s in d
        assert np.allclose(d['M'], M)
        map(os.remove, files)


class TestScipy(ToolsMixin):
    """Run scipy specific tests"""
    def test_spmatrix_types(self, np, sp):
        """Test archiving of scipy.sparse.spmatrix types"""
        A = np.random.random((2, 2))

        obj = dict(csr=sp.sparse.csr_matrix(A),
                   csc=sp.sparse.csc_matrix(A),
                   bsr=sp.sparse.bsr_matrix(A),
                   dia=sp.sparse.dia_matrix(A))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec s in ld
        assert 1 == len(ld)
        x = ld['x']
        assert sp.sparse.isspmatrix_csr(x['csr'])
        assert sp.sparse.isspmatrix_csc(x['csc'])
        assert sp.sparse.isspmatrix_bsr(x['bsr'])
        assert sp.sparse.isspmatrix_dia(x['dia'])

        assert (A - x['csr'] == 0).all()
        assert (A - x['csc'] == 0).all()
        assert (A - x['bsr'] == 0).all()
        assert (A - x['dia'] == 0).all()

    @pytest.mark.skip(reason="Known Failure")
    def test_spmatrix_types2(self, np, sp):  # pragma: nocover
        """Test archiving of unsupported scipy.sparse.spmatrix
        types."""
        A = np.random.random((10, 10))

        obj = dict(lil=sp.sparse.lil_matrix(A),
                   dok=sp.sparse.dok_matrix(A),
                   coo=sp.sparse.coo_matrix(A))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec s in ld
        assert 1 == len(ld)
        x = ld['x']
        assert sp.sparse.isspmatrix_lil(x['lil'])
        assert sp.sparse.isspmatrix_dok(x['dok'])
        assert sp.sparse.isspmatrix_coo(x['coo'])

        assert (A - x['lil'] == 0).all()
        assert (A - x['dok'] == 0).all()
        assert (A - x['coo'] == 0).all()


class TestDatafile(object):
    def test_datafile(self, hdf5_datafile, np, h5py):
        """Test saving large arrays to disk."""
        a = archive.Archive(array_threshold=2,
                            backup_data=False)
        M = np.random.rand(10)
        a.insert(M=M)
        a.make_persistent()
        rep, files = a.save_data(datafile=hdf5_datafile, data_format='hdf5')
        assert len(files) == 1
        assert files[0] == hdf5_datafile
        
        assert len(a.data) == 1
        array_name = a.data.keys()[0]
        with h5py.File(hdf5_datafile) as f:
            assert np.allclose(f[array_name], M)

        s = str(a)
        assert len(a.data) == 1

        ld = {a.data_name: {array_name: M}}
        exec s in ld
        assert np.allclose(ld['M'], M)


class TestImportableArchive(object):
    """Tests for the importable archive format provided in version 1.0"""

    def run_test(self, datadir, np, package, data_format,
                 force=False, **kw):
        a = archive.Archive(array_threshold=2, **kw)
        M = np.random.rand(10)
        N = np.random.rand(10)
        x = [M, N]
        a.insert(M=M, N=N, x=x)
        
        a.save(dirname=datadir, name='my_archive', package=package,
               data_format=data_format, force=force)
        sys.path.append(datadir)
        import my_archive
        reload(my_archive)  # Might have been imported before
        sys.path.pop()
        if package:
            package_file = os.path.join(datadir, 'my_archive', '__init__.py')
        else:
            package_file = os.path.join(datadir, 'my_archive.py')

        assert os.path.isfile(package_file)
        assert np.allclose(my_archive.M, M)
        assert np.allclose(my_archive.N, N)
        assert my_archive.x[0] is my_archive.M
        assert my_archive.x[1] is my_archive.N
        
    def test_save(self, data_format, datadir, np, package):
        """Test saving to an importable package"""
        args = dict(data_format=data_format, datadir=datadir, np=np,
                    package=package)
        
        # Test case where datadir exists
        self.run_test(**args)

        # Test case where datadir does not exist
        shutil.rmtree(datadir)
        self.run_test(**args)

    def test_save_force(self, data_format, datadir, np, package, backup_data,
                        arrays_name='_arrays'):
        """Test forced saving to an importable package."""
        args = dict(datadir=datadir, np=np, 
                    package=package, backup_data=backup_data,
                    data_format=data_format, force=True)

        name = 'my_archive'
        arrays_file = arrays_name + archive._EXTS[data_format]
        if package:
            init_file = os.path.join(datadir, name, '__init__.py')
            arrays_file = os.path.join(datadir, name, arrays_file)
            package_dir = os.path.join(datadir, name)
        else:
            init_file = os.path.join(datadir, name + '.py')
            arrays_file = os.path.join(datadir, name + arrays_file)
            package_dir = datadir
            
        # Test case where datadir exists
        self.run_test(**args)
        assert not os.path.exists(init_file + '.bak')
        if data_format == 'npy':
            assert not glob.glob(os.path.join(arrays_file, '*.bak'))
        else:
            assert not os.path.exists(arrays_file + '.bak')
            
        self.run_test(**args)
        if backup_data:
            assert os.path.exists(init_file + '.bak')
            if data_format == 'npy':
                assert os.path.exists(os.path.join(arrays_file, 'array_0.npy.bak'))
                assert os.path.exists(os.path.join(arrays_file, 'array_1.npy.bak'))
            else:
                assert os.path.exists(arrays_file + '.bak')
        else:
            if data_format == 'npy':
                assert not glob.glob(os.path.join(arrays_file, '*.bak'))
            else:
                assert not os.path.exists(arrays_file + '.bak')

        # Case where package_dir is a file
        if package:
            shutil.rmtree(package_dir)
            with open(package_dir, 'w') as f:
                f.write("noop")
            self.run_test(**args)

            # This backup is always made...
            assert os.path.exists(package_dir + '.bak')
        
    def test_save_errors(self, data_format, datadir, np, package):
        """Test error handling with saving"""
        args = dict(data_format=data_format, datadir=datadir, np=np,
                    package=package)
        # Test case where datadir exists
        self.run_test(**args)

        # Test case where datadir/my_archive is a file
        if package:
            _file = os.path.join(datadir, 'my_archive')
            shutil.rmtree(_file)
            with open(_file, 'w') as f:
                f.write("noop")
            with pytest.raises(ValueError) as e:
                self.run_test(**args)
            msg = e.value.message
            assert msg.startswith('File dirname/name=')
            assert msg.endswith(' exists and is not a directory.')

        # Test case where datadir is a file
        shutil.rmtree(datadir)
        for force in [True, False]:
            with open(datadir, 'w') as f:
                f.write("noop")
            with pytest.raises(ValueError) as e:
                self.run_test(force=force, **args)
            msg = e.value.message
            assert msg.startswith('File dirname=')
            assert msg.endswith(' exists and is not a directory.')
            os.remove(datadir)

        # Test case where datadir and files exist
        self.run_test(**args)
        with pytest.raises(ValueError) as e:
            self.run_test(**args)
        msg = e.value.message
        assert msg.startswith('File ')
        if package:
            assert msg.endswith('/my_archive/__init__.py exists and force=False.')
        else:
            assert msg.endswith('/my_archive.py exists and force=False.')
        
        # Test case where datadir and only arrays_file exist
        if package:
            os.remove(os.path.join(datadir, 'my_archive', '__init__.py'))
        else:
            os.remove(os.path.join(datadir, 'my_archive.py'))
        with pytest.raises(ValueError) as e:
            self.run_test(**args)
        msg = e.value.message
        assert msg.startswith('File ')
        assert msg.endswith(' exists and force=False.')
        if package:
            assert "/my_archive/_arrays" in msg
        else:
            assert "/my_archive_arrays" in msg

    def test_save_no_name(self, datadir):
        """Test error handling with saving with no name"""
        a = archive.Archive(array_threshold=2)
        a.insert(x=1)
        with pytest.raises(ValueError) as e:
            a.save(dirname=datadir, name=None)
        msg = e.value.message
        assert msg == 'Must provide name unless single_item_mode=True'
        
            
class TestArchiveSingleItemMode(object):
    """Tests single_item_mode."""
    def test_1(self, data_format, datadir, np, package):
        a = archive.Archive(single_item_mode=True)
        y = [1, 2, 3]
        x = [y, y]
        a.insert(my_x=x)
        
        a.save(dirname=datadir, name=None, package=package)
        sys.path.append(datadir)
        if 'my_x' in sys.modules:
            del sys.modules['my_x']
        import my_x
        sys.path.pop()
        if package:
            package_file = os.path.join(datadir, 'my_x', '__init__.py')
        else:
            package_file = os.path.join(datadir, 'my_x.py')

        assert os.path.isfile(package_file)
        assert my_x == x
        assert my_x[0] is my_x[1]

    def test_err(self, data_format, datadir, np, package):
        a = archive.Archive(single_item_mode=True)
        with pytest.raises(ValueError) as e:
            a.insert(x=1, y=2)
        msg = e.value.message
        assert msg == "Can't insert 2 items when single_item_mode=True"

        a.insert(x=1)
        a.insert(x=1)
        with pytest.raises(ValueError) as e:
            a.insert(y=2)
        msg = e.value.message
        assert msg == "Can't insert 'y' into single_item_mode=True archive with 'x'."
        

class TestDeprecationWarning(object):
    def test_deprecation_warning(self):
        """Test archive_1 deprecation warning"""
        class A():
            def archive_1(self, env=None):
                return ('A', {}, [])
        arch = archive.Archive()
        arch.insert(a=A())
        with pytest.deprecated_call():
            str(arch)


class A_archive_1():
    """Class with deprecated and erroneous form of archive_1."""
    def archive_1(self):        # pragma: nocover
        return ('A', {}, [])


class A_get_persistent_rep():
    def get_persistent_rep(self):  # pragma: nocover
        return ('A', {}, [])


class TestWarnings(object):
    def test_archive_1_warning(self):
        """Test archive_1 warning"""
        arch = archive.Archive()
        arch.insert(a=A_archive_1())
        with pytest.deprecated_call() as w:
            str(arch)
        assert len(w) == 2
        assert w[0].message[0] == (
            'archive_1 is deprecated: use get_persistent_rep')
        assert w[1].message[0] == (
            '\n'.join(['Found archive_1() but got TypeError:',
                       'archive_1() takes exactly 1 argument (2 given)']))

    def test_get_persistent_rep_warning(self):
        """Test get_persistent_rep warning"""
        arch = archive.Archive()
        arch.insert(a=A_get_persistent_rep())
        with pytest.warns(UserWarning) as w:
            str(arch)
        assert len(w) == 1
        assert w[0].message[0] == (
            '\n'.join(['Found get_persistent_rep() but got TypeError:',
                       'get_persistent_rep() takes exactly 1 argument (2 given)']))

    def test_nested_class(self):
        """Can't pickle nested classes."""
        class A():
            def archive_1(self):  # pragma: nocover
                return ('A', {}, [])
        arch = archive.Archive()
        arch.insert(a=A())
        with pytest.warns(UserWarning) as w:
            with pytest.raises(archive.ArchiveError) as e:
                str(arch)

        assert len(w) == 2
        assert w[0].message[0] == (
            'archive_1 is deprecated: use get_persistent_rep')
        assert w[1].message[0] == (
            '\n'.join(['Found archive_1() but got TypeError:',
                       'archive_1() takes exactly 1 argument (2 given)']))
        assert e.value[0].startswith(
            'Could not archive object <')
        assert e.value[0].endswith('>.  Even tried pickling!')


class DocTests(object):
    def regression_1(self):
        """Regression Test 1.
        >>> a = archive.Archive()
        >>> a.insert(x_1=None)
        >>> a.insert(x_2=None)
        >>> print(a)
        x_2 = None
        x_1 = x_2
        try: del __builtins__, _arrays
        except NameError: pass
        >>> a.names()
        ['x_1', 'x_2']
        """


class TestRegression(object):
    def test_regression_1(self, np):
        r"""Here is a regression test for an old bug.  Sometimes the member
        `_` of the `__builtins__` model can have an array in it which
        causes tests like `if obj in vals` to fail.  Fix is to use
        `id()`.
        """
        import __builtin__
        __builtin__._ = np.array([1, 2])
        rep = archive.get_persistent_rep_type(type(None), {})
        assert rep == ('NoneType', {}, [('types', 'NoneType', 'NoneType')])

    def test_regression_11a(self, scoped):
        "Regression test for issue 11: duplicated data in non-scoped archive."
        x = [1, 2, 3]
        y = [x, x]
        a = archive.Archive(scoped=scoped)
        a.insert(y=y)
        s = str(a)
        d = {}
        exec(s, d)
        y_ = d['y']
        assert y[0] is y[1]
        assert y_[0] is y_[1]


class TestPerformance(object):
    """Tests that could illustrate bad performance."""
    def test_1(self):
        args = dict(replacements={'infty': '_inf',
                                  'Infinity': '_inf',
                                  'NaN': '_nan',
                                  'nan': '_nan',
                                  'inf': '_inf',
                                  'numpy': '_numpy',
                                  'Inf': '_inf',
                                  'NAN': '_nan'},
                    rep="numpy.array([" + " ".join(("0., ", )*1000000) + "0])",
                    robust=False)
        archive._replace_rep(**args)

    def test_no_str_no_repr(self):
        r"""Test that str and repr are not called unnecessarily."""
        arch = archive.Archive()
        arch.insert(a=NoStrNoRepr())
        s = str(arch)
        ld = {}
        exec s in ld
        assert isinstance(ld['a'], NoStrNoRepr)
        with pytest.raises(NotImplementedError):
            str(ld['a'])
        with pytest.raises(NotImplementedError):
            repr(ld['a'])
        del s


    def _test_large_array(self):
        r"""Test archiving a large list.  This was giving some performance
        issues."""
        #c = objects.Container(x=[1 for _l in xrange(820*6)])
        #ds = archive.DataSet(self.ds_name, 'w')
        #ds.c = c


def coverage_doctests():
    """Ensure coverage.

    >>> a = archive.Archive()
    >>> a.insert(x=1)
    >>> a.insert(y=2)
    >>> a.names()
    ['x', 'y']

    >>> class A(object):
    ...     "Class with a bad repr to trigger exception."
    ...     def __repr__(self):
    ...         return "<object>"
    >>> a = archive.Archive()
    >>> a.insert(a=A())
    >>> a
    Traceback (most recent call last):
    ...
    ArchiveError: Could not archive object <object>.  Even tried pickling!

    >>> archive.get_persistent_rep_repr(1, {})
    ('1', {}, [])

    >>> archive._replace_rep_robust('1', dict(a="c"))
    '1'

    >>> type(archive.AST('[1,2,3]').ast)
    <class '_ast.Module'>
    """


class TestCoverage(object):
    def test_repr(self):
        """Cover repr."""
        repr(archive.Archive())

    def test_expr(self):
        """Cover AST.expr"""
        s = '[1, 2]'
        assert s == archive.AST(s).expr

    def test_array_name_clash(self, np):
        a = archive.Archive()
        with pytest.raises(ValueError) as e:
            a.insert(np.zeros(2))
        assert e.value[0] == (
            'Insert objects with a key: insert(x=3), not insert([ 0.  0.])')

    def test_array_name_clash2(self, np, hdf5_datafile):
        a = archive.Archive(array_threshold=2)
        a.data['array_0'] = np.zeros(2)
        a.insert(x=np.zeros(5), env={})
        s = str(a)
        assert s == "\n".join(["x = _arrays['array_1']",
                               "try: del __builtins__, _arrays",
                               "except NameError: pass"])

    def test_datafile_nohdf5_1(self, np, datadir):
        """Test saving large arrays to disk without hdf5."""
        a = archive.Archive(array_threshold=2)
        M = np.random.rand(10)
        a.insert(M=M)
        s = str(a)
        rep, files = a.save_data(datafile=datadir)
        ld = dict(_arrays=archive.ArrayManager.load_arrays(rep))
        exec s in ld
        assert np.allclose(ld['M'], M)

    def test_datafile_nohdf5_2(self, np, datadir):
        """Test saving large arrays to disk without hdf5."""
        a = archive.Archive(array_threshold=2)
        M = np.random.rand(10)
        a.insert(M=M)
        s = a.scoped__str__()
        rep, files = a.save_data(datafile=datadir)
        ld = dict(_arrays=archive.ArrayManager.load_arrays(rep))
        exec s in ld
        assert np.allclose(ld['M'], M)

    def test_get_persistent_rep_repr(self):
        rep = archive.get_persistent_rep_repr(1, {}, rep=None)
        assert rep == ('1', {}, [])

    def test_gname(self):
        a = archive.Archive()
        g0 = a.gname_prefix + '0'
        a.allowed_names.append(g0)
        a.insert(**{g0: 1})
        a.insert(a={'a': 1})
        s = str(a)
        ld = {}
        exec s in ld
        assert ld['a'] == {'a': 1}
        assert ld[g0] == 1


class TestArrayManager(object):
    """Test the ArrayManager class"""
    def test_save_no_filename(self, datafile):
        arrays = dict(x=range(10))
        
        with pytest.raises(ValueError) as e:
            archive.ArrayManager.save_arrays(
                arrays, filename=None, data_format='npz')
        msg = e.value.message
        assert msg == "Must specify filename for data_format='npz'"

    def test_save_arrays(self, np, datadir, data_format):
        """Test saving and loading arrays."""
        M = np.random.rand(10)
        arrays = dict(M=M)
        rep, files = archive.ArrayManager.save_arrays(
            arrays=arrays, dirname=datadir, filename='M', data_format=data_format)

    def test_unknown_format(self, datafile):
        with pytest.raises(NotImplementedError) as e:
            archive.ArrayManager.save_arrays({}, data_format='???')
        msg = e.value.message
        assert msg == "Expected data_format in ['hdf5', 'npz', 'npy'], got '???'"


class TestGraph(object):
    def test_graph(self):
        """Example graph from docs."""
        objs = 'A,B,C,D,E,F,G'.split(',')
        A, B, C, D, E, F, G = objs

        deps = dict(A=[B, C], B=[F], C=[F, D, E], D=[G], E=[G], F=[], G=[])

        def get_persistent_rep(obj, env={}):
            args = dict(zip(deps[obj], deps[obj]))
            return (obj, args, [])

        ids = dict((id(_obj), _obj) for _obj in objs)

        graph = archive.Graph([('A', A, {})], get_persistent_rep)
        paths = graph.paths()

        # Convert to simple strings
        paths = set([''.join(map(ids.__getitem__, _p)) for _p in paths])
        _paths = set(['ABF', 'ACF', 'ACDG', 'ACEG'])
        assert _paths == paths

        graph = archive._Graph([('A', A, {})], get_persistent_rep)
        paths = graph.paths()

        # Convert to simple strings
        paths = set([''.join(map(ids.__getitem__, _p)) for _p in paths])
        _paths = set(['ABF', 'ACF', 'ACDG', 'ACEG'])
        assert _paths == paths
