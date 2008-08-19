import inspect

import nose.tools

import numpy as np

import mmf.objects
import mmf.objects.interfaces as interfaces
import mmf.archive as archive

import mmf.utils.mmf_test

class A(object):
    """Example of a class with an archive function."""
    def __init__(self,d,l):
        self.d = d
        self.l = l
    def archive_1(self,env=None):
        """Example of an archive function."""
        imports = archive.get_imports(self)
        args = [('d',self.d),
                ('l',self.l)]
        rep = imports[0][-1] + '(d=d,l=l)'
        return (rep,args,imports)

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

class TestException(Exception):
    pass

class TestSuite(object):
    """Test the functionality of the archive module."""
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
        """Test archiving of class A()"""
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
        """Test archiving of class B()"""
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
        """Test archiving of class C()"""
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
        self._test_archiving([1,2])

    def test_numpy_types(self):
        """Test archiving of numpy types"""
        obj = dict(inf=np.inf,
                   neg_inf=-np.inf,
                   nan=np.nan,
                   array=np.array([1,np.inf,np.nan]))

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

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test_mutual_deps(self):
        """Test non-reduction of non-simple mutual dependence."""
        x = [1]
        y = [2]
        z = [x,y,x]
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

    @nose.tools.raises(archive.ArchiveError)
    def test_cyclic_exception(self):
        """Make sure cyclic deps raise an error."""
        A = []
        A.append(A)
        arch = archive.Archive()
        arch.insert(a=A)
        arch.make_persistent()

class TestCoverage(object):
    """Ensure coverage."""
    def test_repr(self):
        """Cover repr."""
        repr(archive.Archive())
    def test_expr(self):
        """Cover AST.expr"""
        s = '[1,2]'
        assert s == archive.AST(s).expr
    
