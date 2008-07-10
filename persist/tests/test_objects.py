import inspect

from copy import copy, deepcopy
import nose
import mmf.objects

class A(mmf.objects.Archivable):
    def __init__(self,x):
        self.x = x
    def _get_args(self):
        return self.__dict__.items()
    
class TestArchivable(object):
    """Test Archivable class."""
    def test_repr(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)",repr(a))
    def test_str(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)",str(a))

class TestStateVars(object):
    def test_ordering(self):
        """Test the inherited order of _state_vars."""
        class A(mmf.objects.StateVars):
            _state_vars = [('e',5),
                           ('f',6)]
            mmf.objects.process_vars()
        class B(A):
            _state_vars = [('c',3),
                           ('d',4)]
            mmf.objects.process_vars()
        class C(B):
            _state_vars = [('a',1),
                           ('b',2)]
            mmf.objects.process_vars()
    
        nose.tools.assert_equal(C.class_keys(),['a','b','c','d','e','f'])

    def test_replacement(self):
        """Test the replacement of _state_vars."""
        class A(mmf.objects.StateVars):
            _state_vars = [('a',5)]
            mmf.objects.process_vars()
        class B(A):
            _state_vars = [('a',1)]
            mmf.objects.process_vars()
        nose.tools.assert_equal(B().a,1)

    def test_copy1(self):
        """Test copy=False"""
        c = [1]
        class A(mmf.objects.StateVars):
            _state_vars = [('a',c),('b',c)]
            mmf.objects.process_vars(copy=False)
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0],1)
        nose.tools.assert_equal(b.c[0],1)
        a.c[0] = 2
        nose.tools.assert_equal(a.c[0],2)
        nose.tools.assert_equal(b.c[0],2)

    def test_copy2(self):
        """Test copy=copy"""
        c = [[1]]
        class A(mmf.objects.StateVars):
            _state_vars = [('a',c),('b',c)]
            mmf.objects.process_vars(copy=copy)
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0][0],1)
        nose.tools.assert_equal(b.c[0][0],1)
        a.c[0][0] = 2
        nose.tools.assert_equal(a.c[0][0],2)
        nose.tools.assert_equal(b.c[0][0],2)
        a.c[0] = 1
        nose.tools.assert_equal(a.c[0],1)
        nose.tools.assert_equal(b.c[0],[2])

    def test_copy3(self):
        """Test copy=deepcopy"""
        c = [[1]]
        class A(mmf.objects.StateVars):
            _state_vars = [('a',c),('b',c)]
            mmf.objects.process_vars(copy=deepcopy)
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0][0],1)
        nose.tools.assert_equal(b.c[0][0],1)
        a.c[0][0] = 2
        nose.tools.assert_equal(a.c[0][0],2)
        nose.tools.assert_equal(b.c[0][0],1)

    @nose.tools.raises(ValueError)
    def test_Required(self):
        """Test required keys"""
        class A(mmf.objects.StateVars):
            _state_vars = mmf.objects.state_var(
                copy=False,
                c=(mmf.objects.Required,'Required'))
            mmf.objects.process_vars()
        a = A()

    @nose.tools.raises(AttributeError)
    def test_NotImplemented(self):
        """Test NotImplemented keys"""
        class A(mmf.objects.StateVars):
            _state_vars = mmf.objects.state_var(
                copy=False,
                c=(NotImplemented,'Required'))
            mmf.objects.process_vars()
        a = A()
        c = a.c
        
    @nose.tools.raises(ValueError)
    def test_get_args(self):
        """Test get_args arg checking"""
        mmf.objects.StateVars.get_args(1,2)
            
