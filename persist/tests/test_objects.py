import inspect

from copy import copy, deepcopy
import nose

import numpy as np

import mmf.objects
from mmf.objects import StateVars, Container, process_vars

class A(mmf.objects.Archivable):
    def __init__(self,x):
        self.x = x
    def items(self):
        return self.__dict__.items()
    
class TestArchivable(object):
    """Test Archivable class."""
    def test_repr(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)",repr(a))
    def test_str(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)",str(a))

class TestStateVars1(object):
    """Test StateVars processing without explicit calls to
    process_vars()"""
    def test1(self):
        """Test StateVars without process_vars call."""
        class StateVars1(StateVars):
            _dynamic = True
        a = StateVars1(a=1,b=2)
        nose.tools.assert_equal(a.a,1)
        nose.tools.assert_equal(a.b,2)

    def test2(self):
        """Test StateVars inheritance without process_vars call."""
        class StateVars1(StateVars):
            _state_vars = [('a',1)]
            process_vars()
        class StateVars2(StateVars1):
            pass

        a = StateVars2()
        nose.tools.assert_equal(a.a,1)

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test3(self):
        """Test StateVars multiple inheritance without process_vars call."""
        class StateVars1(StateVars):
            _state_vars = [('a',1)]
            process_vars()
        class StateVars2(StateVars):
            _state_vars = [('b',2)]
            process_vars()
        class StateVars3(StateVars1,StateVars2):
            pass

        a = StateVars3()
        nose.tools.assert_equal(a.a,1)
        nose.tools.assert_equal(a.b,2)

class TestStateVars(object):
    def test_ordering(self):
        """Test the inherited order of _state_vars."""
        class A(StateVars):
            _state_vars = [('a',1),
                           ('b',2)]
            process_vars()
        class B(A):
            _state_vars = [('c',3),
                           ('d',4)]
            process_vars()
        class C(B):
            _state_vars = [('e',5),
                           ('f',6)]
            process_vars()
    
        nose.tools.assert_equal(C.class_keys(),['a','b','c','d','e','f'])

    def test_replacement(self):
        """Test the replacement of _state_vars."""
        class A(StateVars):
            _state_vars = [('a',5)]
            process_vars()
        class B(A):
            _state_vars = [('a',1)]
            process_vars()
        nose.tools.assert_equal(B().a,1)

    def test_copy1(self):
        """Test copy=False"""
        c = [1]
        class A(StateVars):
            _state_vars = [('c',c)]
            process_vars(copy=False)
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
        class A(StateVars):
            _state_vars = [('c',c)]
            process_vars(copy=copy)
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
        class A(StateVars):
            _state_vars = [('c',c)]
            process_vars(copy=deepcopy)
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
        class A(StateVars):
            _state_vars = [('c',mmf.objects.Required,'Required')]
            process_vars()
        a = A()

    @nose.tools.raises(AttributeError)
    def test_NotImplemented(self):
        """Test NotImplemented keys"""
        class A(StateVars):
            _state_vars = [('c',NotImplemented,'NotImplemented')]
            process_vars()
        a = A()
        c = a.c
        
    @nose.tools.raises(ValueError)
    def test_get_args(self):
        """Test get_args arg checking"""
        StateVars.get_args(1,2)

    @nose.tools.raises(TypeError)
    def test_key_check_1(self):
        """Test exception for 1 extra kwarg."""
        class A(StateVars):
            _state_vars = ['x']
            process_vars()
        a = A(x=1,y=2)

    @nose.tools.raises(TypeError)
    def test_key_check_2(self):
        """Test exception for 2 extra kwarg."""
        class A(StateVars):
            _state_vars = ['x']
            process_vars()
        a = A(x=1,y=2,z=3)

    @nose.tools.raises(TypeError)
    def test_empty_state_vars1(self):
        """Test __init__ for _state_vars = []"""
        class A(StateVars):
            _state_vars = []
            process_vars()
        a = A(a=1)

    @nose.tools.raises(AttributeError)
    def test_empty_state_vars2(self):
        """Test assignment for _state_vars = []"""
        class A(StateVars):
            _state_vars = []
            process_vars()
        a = A()
        a.a = 1

    @nose.tools.raises(ValueError)
    def test_invalid_varargin1(self):
        """Test default __init__ for invalid varargins."""
        a = StateVars(1)

    @nose.tools.raises(ValueError)
    def test_invalid_varargin2(self):
        """Test default __init__ for invalid varargins."""
        a = StateVars(1,2)


    def test_compare_arrays(self):
        """Test that arrays can be compared."""
        class A(StateVars):
            _state_vars = [('a',np.array([1,2]))]
            process_vars()
        a = repr(A())

    def test_copy(self):
        """Test StateVars.__copy__"""
        l = [1]
        a = Container(l=l)
        b = copy(a)
        a.l[0] = 2
        nose.tools.assert_equal(b.l[0],a.l[0])

    def test_deepcopy(self):
        """Test StateVars.__deepcopy__"""
        l = [1]
        a = Container(l=l)
        b = deepcopy(a)
        a.l[0] = 2
        nose.tools.assert_not_equal(b.l[0],a.l[0])

    def test_exclude(self):
        """Tests a bug with _gather_vars."""
        class C(StateVars):
            _state_vars = ['a']
            _excluded_vars = ['_b']
            process_vars()
        C.b = 5
        nose.tools.assert_equals(C.b, 5)

