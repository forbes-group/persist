import sys
import math

import os
import tempfile
import shutil

import nose.tools

import numpy as np
import scipy as sp

import mmf.objects
import mmf.interfaces

archive = sys.modules['mmf.archive._archive']

import mmf.utils.mmf_test

class A(object):
    """Example of a class with an archive function."""
    def __init__(self,d,l):
        self.d = d
        self.l = l
    def archive_1(self,env=None):
        """Example of an archive function."""
        imports = archive.get_imports(self)
        args = dict(d=self.d, l=self.l)
        rep = imports[0][-1] + '(d=d,l=l)'
        return (rep, args, imports)

class B(object):
    """Example of a class without an archive function but with a repr
    function."""
    def __init__(self,d,l):
        self.d = d
        self.l = l
    def __repr__(self):
        return "B(d=%r,l=%r)"%(self.d,self.l)

class C(mmf.objects.Archivable):
    """Example of a class inheriting from Archivable."""
    def __init__(self,d,l):
        self.d = d
        self.l = l
    def items(self):
        """This must be overloaded."""
        args = [('d',self.d),
                ('l',self.l)]
        return args

class Functions(object):
    """Example of a class with methods that are archivable.   This
    gives one way to use "archivable functions with associated
    data"."""
    def __init__(self, a):
        self.a = 2
    def __repr__(self):
        """Use repr to make `self` archivable."""
        return "Functions(a=%r)" % (self.a,)
    def f(self, x):
        """A function that depends on a."""
        return self.a*x

class NestedClasses(object):
    class NestedFunctions(Functions):
        """Example of a nested class."""

class TestException(Exception):
    pass

class MyDict(dict):
    """Class to test archiving of derived classes."""

class MyList(list):
    """Class to test archiving of derived classes."""

class MyTuple(tuple):
    """Class to test archiving of derived classes."""

class NoStrNoRepr(mmf.objects.Archivable):
    r"""This class provides its own archive_1 function, so __str__ and __repr__
    should never be called."""
    def archive_1(self, env):
        rep = 'NoStrNoRepr()'
        args = {}
        imports = []
        return (rep, args, imports)
    def __str__(self):
        import pdb;pdb.set_trace()
        raise NotImplementedError
    def __repr__(self):
        import pdb;pdb.set_trace()
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
        
class TestSuite(object):
    """Test the functionality of the archive module."""
    def setUp(self):
        np.random.seed(3)
        
    def _test_archiving(self,obj):
        """Fail if obj does not acrhive properly."""
        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(1,len(ld))
        nose.tools.assert_equals(obj,ld['x'])

    def test_1(self):
        """Test archiving of instance A()"""
        l = [1,2,3]
        d = {'a':1.0,'b':2.0,'l':l}
        a = A(d=d,l=l)
        arch = archive.Archive()
        arch.insert(a=a)
        s = str(arch)
        ld = {}
        exec(s,ld)
        assert (ld['a'].l == a.l and id(ld['a'].l) != id(a.l))
        assert (ld['a'].d == a.d and id(ld['a'].d) != id(a.d))
        
    def test_2(self):
        """Test archiving of instance B()"""
        l = [1,2,3]
        d = {'a':1.0,'b':2.0,'l':l}
        a = B(d=d,l=l)
        arch = archive.Archive()
        arch.insert(a=a)
        s = str(arch)
        ld = {}
        exec(s,ld)
        assert (ld['a'].l == a.l and id(ld['a'].l) != id(a.l))
        assert (ld['a'].d == a.d and id(ld['a'].d) != id(a.d))

    def test_3(self):
        """Test archiving of instance C()"""
        l = [1,2,3]
        d = {'a':1.0,'b':2.0,'l':l}
        a = C(d=d,l=l)
        s = a.archive('a')
        ld = {}
        exec(s,ld)
        assert (ld['a'].l == a.l and id(ld['a'].l) != id(a.l))
        assert (ld['a'].d == a.d and id(ld['a'].d) != id(a.d))

    def test_4(self):
        """Test archiving of class C"""
        a = C
        arch = archive.Archive()
        arch.insert(a=a)
        s = str(arch)
        ld = {}
        exec(s,ld)
        assert (ld['a'] is C)
    
    def test_simple_types(self):
        """Test archiving of various simple types."""
        self._test_archiving(1)
        self._test_archiving(1.0)
        self._test_archiving(1.0+2j)
        self._test_archiving(True)
        self._test_archiving(False)
        self._test_archiving("asd")
        self._test_archiving((1,))
        self._test_archiving((1,2))
        self._test_archiving([1])
        self._test_archiving([1,2])
        self._test_archiving((1,1))
        self._test_archiving(np.sin)
        self._test_archiving(math.sin)
        self._test_archiving(None)
        self._test_archiving(type(None))

    def test_derived_types(self):
        """Test archiving of simple derived types..."""
        arch = archive.Archive()
        d = MyDict(a=1,b=2)
        l = MyList([1,2])
        t = MyTuple((1,2))
        arch.insert(d=d,l=l, t=t)
        s = str(arch)
        ld = {}
        exec(s,ld)
        assert (ld['d']['a'] == d['a'])
        assert isinstance(ld['d'], MyDict)
        assert (ld['l'] == l)
        assert isinstance(ld['l'], MyList)
        assert (ld['t'] == t)
        assert isinstance(ld['t'], MyTuple)

    def test_numpy_types(self):
        """Test archiving of numpy types"""
        obj = dict(inf=np.inf,
                   neg_inf=-np.inf,
                   nan=np.nan,
                   array=np.array([1,np.inf,np.nan]),
                   ndarray=np.array([[1,2],[3,4]]),
                   matrix=np.matrix([[1,2],[3,4]]))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(1,len(ld))
        nose.tools.assert_true(np.isnan(ld['x']['nan']))
        nose.tools.assert_equals(np.inf,(ld['x']['inf']))
        nose.tools.assert_equals(-np.inf,(ld['x']['neg_inf']))

        a0 = obj['array']
        a1 = ld['x']['array']
        
        nose.tools.assert_equals(a0[0],a1[0])
        nose.tools.assert_equals(a0[1],a1[1])
        nose.tools.assert_true(np.isnan(a1[2]))

        a0 = obj['ndarray']
        a1 = ld['x']['ndarray']
        
        nose.tools.assert_true((a0 == a1).all())
        nose.tools.assert_true(a0.shape == a1.shape)

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test_numpy_types2(self):
        """Test archiving of complex numpy types"""
        obj = dict(inf=1+1j*np.inf,
                   neg_inf=1-1j*np.inf,
                   nan=1-1j*np.nan,
                   array=np.array([1,1+1j*np.inf,1+1j*np.nan]))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(1,len(ld))
        nose.tools.assert_true(np.isnan(ld['x']['nan']))
        nose.tools.assert_equals(np.inf,(ld['x']['inf']))
        nose.tools.assert_equals(-np.inf,(ld['x']['neg_inf']))

        a0 = obj['array']
        a1 = ld['x']['array']
        
        nose.tools.assert_equals(a0[0],a1[0])
        nose.tools.assert_equals(a0[1],a1[1])
        nose.tools.assert_true(np.isnan(a1[2]))

    def test_spmatrix_types(self):
        """Test archiving of scipy.sparse.spmatrix types"""
        A = np.random.random((2,2))
        
        obj = dict(csr=sp.sparse.csr_matrix(A),
                   csc=sp.sparse.csc_matrix(A),
                   bsr=sp.sparse.bsr_matrix(A),
                   dia=sp.sparse.dia_matrix(A))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(1,len(ld))
        x = ld['x']
        nose.tools.assert_true(sp.sparse.isspmatrix_csr(x['csr']))
        nose.tools.assert_true(sp.sparse.isspmatrix_csc(x['csc']))
        nose.tools.assert_true(sp.sparse.isspmatrix_bsr(x['bsr']))
        nose.tools.assert_true(sp.sparse.isspmatrix_dia(x['dia']))
        
        nose.tools.assert_true((A - x['csr'] == 0).all())
        nose.tools.assert_true((A - x['csc'] == 0).all())
        nose.tools.assert_true((A - x['bsr'] == 0).all())
        nose.tools.assert_true((A - x['dia'] == 0).all())

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test_spmatrix_types2(self):
        """Test archiving of unsupported scipy.sparse.spmatrix
        types."""
        A = np.random.random((10,10))
        
        obj = dict(lil=sp.sparse.lil_matrix(A),
                   dok=sp.sparse.dok_matrix(A),
                   coo=sp.sparse.coo_matrix(A))

        arch = archive.Archive()
        arch.insert(x=obj)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(1,len(ld))
        x = ld['x']
        nose.tools.assert_true(sp.sparse.isspmatrix_lil(x['lil']))
        nose.tools.assert_true(sp.sparse.isspmatrix_dok(x['dok']))
        nose.tools.assert_true(sp.sparse.isspmatrix_coo(x['coo']))
        
        nose.tools.assert_true((A - x['lil'] == 0).all())
        nose.tools.assert_true((A - x['dok'] == 0).all())
        nose.tools.assert_true((A - x['coo'] == 0).all())

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test_mutual_deps(self):
        """Test non-reduction of non-simple mutual dependence."""
        x = [1]
        y = [2]
        z = [x, y, x]
        arch = archive.Archive()
        arch.insert(z=z)
        s = str(arch)
        ld = {}
        exec(s,ld)
        assert ld['z'][0] is ld['z'][2]
        

    @nose.tools.raises(ValueError)
    def test_insert_1(self):
        """Check for _name exception."""
        arch = archive.Archive()
        arch.insert(_a=1)

    @nose.tools.raises(TestException)
    def test_check_on_insert(self):
        """Make sure check_on_insert works."""
        class A():
            def archive_1(self,env=None):
                raise TestException()
        arch = archive.Archive()
        arch.check_on_insert = True
        arch.insert(a=A())

    @nose.tools.raises(archive.CycleError)
    def test_cyclic_exception(self):
        """Make sure cyclic deps raise an error."""
        A = []
        A.append(A)
        arch = archive.Archive()
        arch.insert(a=A)
        arch.make_persistent()

    def test_archivable_members(self):
        """Test the archiving of bound class members."""
        F = Functions(a=2)
        arch = archive.Archive()
        arch.insert(f=F.f, g=Functions.f)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(F.f(2), ld['f'](2))
        nose.tools.assert_equals(F.f(2), ld['g'](F, 2))

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test_nested_classes(self):
        """Test the archiving of nested classes."""
        F = NestedClasses.NestedFunctions(a=2)
        arch = archive.Archive()
        arch.insert(f=F.f, g=NestedClasses.NestedFunctions.f)
        s = str(arch)
        ld = {}
        exec(s,ld)
        nose.tools.assert_equals(F.f(2), ld['f'](2))
        nose.tools.assert_equals(F.f(2), ld['g'](F, 2))

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

    @nose.tools.raises(Exception)
    def test_archive_1_regression_1(self):
        r"""Regression for usage of archive_1().  Exceptions raised
        should not be ignored."""
        class A(object):
            mmf.interfaces.implements(mmf.interfaces.IArchivable)
            def archive_1(self, env=None):
                raise Exception()
        
        arch = mmf.archive.Archive()
        a = A()
        arch.insert(a=a)
        str(arch)

    def test__replace_rep_regression_1a(self):
        r"""Regression test of bad replacement in numpy array rep."""
        rep = "dict(Q=_Q, a=_numpy.fromstring('`\\xbf=_Q-\\xf2?', dtype='<f8'))"
        replacements = {'_Q': '1.0'}
        rep = archive._replace_rep(rep, replacements)
        assert (
            rep == 
            "dict(Q=1.0, a=_numpy.fromstring('`\\xbf=_Q-\\xf2?', dtype='<f8'))")

    def test__replace_rep_regression_1b(self):
        r"""Regression test of bad replacement in numpy array rep.

        This is the same example as test__replace_rep_regression_1a but shows
        how it comes about from a high level.
        """
        c = mmf.objects.Container(Q=1.0, alpha=np.array(1.1360639305457525))
        arch = mmf.archive.Archive()
        arch.insert(c=c)
        d = {}
        exec(str(arch), d)
        assert d['c'].alpha == c.alpha
        
    
class DocTests(object):    
    def regression_1(self):
        """Regression Test 1.
        >>> a = archive.Archive()
        >>> a.insert(x_1=None)
        'x_1'
        >>> a.insert(x_2=None)
        'x_2'
        >>> print a
        x_2 = None
        x_1 = x_2
        try: del __builtins__
        except NameError: pass
        """
    def regression_2(self):
        r"""Here is a regression test for an old bug.  Sometimes the member
        `_` of the `__builtins__` model can have an array in it which
        causes tests like `if obj in vals` to fail.  Fix is to use
        `id()`.
        
        >>> import __builtin__
        >>> __builtin__._ = np.array([1,2])
        >>> archive.archive_1_type(type(None), {})
        ('NoneType', {}, [('types', 'NoneType', 'NoneType')])
        """

class TestDataSet(object):
    def setUp(self):
        # Make a temporary directory for tests.
        self.ds_name = tempfile.mkdtemp(dir='.')[2:]
        os.rmdir(self.ds_name)

    def tearDown(self):
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
                    rep="numpy.array([" + " ".join(("0.,",)*1000000) + "0])")
        archive._replace_rep(**args)
    def test_no_str_no_repr(self):
        r"""Test that str and repr are not called unnecessarily."""
        arch = archive.Archive()
        arch.insert(a=NoStrNoRepr())
        s = str(arch)
        del s

    def _test_large_array(self):
        r"""Test archiving a large list.  This was giving some performance
        issues."""
        #c = mmf.objects.Container(x=[1 for _l in xrange(820*6)])
        #ds = archive.DataSet(self.ds_name, 'w')
        #ds.c = c
        


class TestCoverage(object):
    """Ensure coverage."""
    def test_repr(self):
        """Cover repr."""
        repr(archive.Archive())
    def test_expr(self):
        """Cover AST.expr"""
        s = '[1,2]'
        assert s == archive.AST(s).expr
    
