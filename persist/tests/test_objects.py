import inspect
import warnings

from copy import copy, deepcopy

import nose

import numpy as np

import mmf.utils.mmf_test

import mmf.objects
from mmf.objects import StateVars, Container, process_vars
from mmf.objects import ClassVar, Required, Computed, NoCopy, Deleted
from mmf.objects import Excluded, Delegate, Ref


class A(mmf.objects.Archivable):
    def __init__(self, x):
        self.x = x
    def items(self):
        return self.__dict__.items()

class WithProperty(StateVars):
    """Test required attributes specified by proprties."""
    _ignore_name_clash = set(['x'])
    _state_vars = [('x', Required),
                   ('_x', Computed)]
    process_vars()

    def __init__(self):
        self._x = 1

    @property
    def x(self):
        """Only valid after initialization (which can cause a bug in
        the __new__ checking of Required attributes)."""
        return self._x
    

class MyFloat(StateVars, float):
    """Overloading builtin type with extra data members."""
    _state_vars = [
        ('min', Required, "Minimum range"),
        ('max', Required, "Maximum range")]
    process_vars()
    def __new__(cls, *v, **kw):
        self = float.__new__(cls, v[0])
        return StateVars.__new__(cls, self=self, *v[1:], **kw)
    def __init__(self, *v, **kw):
        if self < self.min or self.max < self:
            raise ValueError(
                "Value must be between self.min and self.max")

def test_MyFloat():
    """Test the subclassing of a builtin as a StateVar."""
    f = MyFloat(3, min=2.0, max=4.0)
    nose.tools.assert_equals(f, 3)

class TestArchivable(object):
    """Test Archivable class."""
    def test_repr(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)", repr(a))
    def test_str(self):
        a = A(x=1)
        nose.tools.assert_equal("A(x=1)", str(a))
    def test_archive(self):
        """Test the archive method."""
        a = A(6)            # Create an instance
        s = a.archive('n')  # Get string archive
        env = {}            # Define an environment
        exec(s, env)        # Evaluate the string in env
        o = env['n']        # Access the object from env
        nose.tools.assert_equals(o.x, a.x)


class TestStateVars(object):

    def setUp(self):
        warnings.simplefilter('error', UserWarning)

    def tearDown(self):
        warnings.resetwarnings()

    def test_ordering(self):
        """Test the inherited order of _state_vars."""
        class A(StateVars):
            _state_vars = [('a', 1),
                           ('b', 2)]
            process_vars()
        class B(A):
            _state_vars = [('c', 3),
                           ('d', 4)]
            process_vars()
        class C(B):
            _state_vars = [('e', 5),
                           ('f', 6)]
            process_vars()
    
        nose.tools.assert_equal(C.class_keys(), 
                                ['a', 'b', 'c', 'd', 'e', 'f'])

    def test_replacement(self):
        """Test the replacement of _state_vars."""
        mmf.objects.NameClashWarning.simplefilter('ignore')
        class A(StateVars):
            _state_vars = [('a', 5)]
            process_vars()
        class B(A):
            _state_vars = [('a', 1)]
            process_vars()
        nose.tools.assert_equal(B().a, 1)

    def test_copy0a(self):
        """Test default copy semantics"""
        c0 = [1]
        c1 = [c0]
        class A(StateVars):
            _state_vars = [('c', c1)]
            process_vars()
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0][0], 1)
        nose.tools.assert_equal(b.c[0][0], 1)
        nose.tools.assert_not_equal(id(a.c), id(b.c))
        nose.tools.assert_not_equal(id(a.c[0]), id(b.c[0]))

    def test_copy1(self):
        """Test copy=False"""
        # This should not raise a warning but it does.  See
        # test_local_scope
        mmf.objects.NameClashWarning.simplefilter('ignore')        
        c = [1]
        class A(StateVars):
            _state_vars = [('c', c)]
            process_vars(copy=False)
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0], 1)
        nose.tools.assert_equal(b.c[0], 1)
        a.c[0] = 2
        nose.tools.assert_equal(a.c[0], 2)
        nose.tools.assert_equal(b.c[0], 2)

    @mmf.utils.mmf_test.dec.skipknownfailure
    @nose.tools.raises(AttributeError)
    def test_local_scope(self):
        """Test the spurious assignment of attributes."""
        def f():
            c = [1]
            class A(StateVars):
                _state_vars = [('a', c)]
                process_vars(copy=False)
            return A
        A = f()
        a = A()
        a.c

    def test_copy1a(self):
        """Test NoCopy"""
        # This should not raise a warning but it does.  See
        # test_local_scope
        mmf.objects.NameClashWarning.simplefilter('ignore')        
        c = [1]
        class A(StateVars):
            _state_vars = [('c', NoCopy(c))]
            process_vars()
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0], 1)
        nose.tools.assert_equal(b.c[0], 1)
        a.c[0] = 2
        nose.tools.assert_equal(a.c[0], 2)
        nose.tools.assert_equal(b.c[0], 2)

    def test_copy1b(self):
        """Test NoCopy(Required)"""
        c = [1]
        class A(StateVars):
            _state_vars = [('c', NoCopy(Required))]
            process_vars()
        nose.tools.assert_raises(ValueError, A)
        a = A(c=c)
        b = A(c=c)
        nose.tools.assert_equal(a.c[0], 1)
        nose.tools.assert_equal(b.c[0], 1)
        a.c[0] = 2
        nose.tools.assert_equal(a.c[0], 2)
        nose.tools.assert_equal(b.c[0], 2)

    def test_copy2(self):
        """Test copy=copy"""
        c = [[1]]
        class A(StateVars):
            _state_vars = [('c', c)]
            process_vars(copy=copy)
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0][0], 1)
        nose.tools.assert_equal(b.c[0][0], 1)
        a.c[0][0] = 2
        nose.tools.assert_equal(a.c[0][0], 2)
        nose.tools.assert_equal(b.c[0][0], 2)
        a.c[0] = 1
        nose.tools.assert_equal(a.c[0], 1)
        nose.tools.assert_equal(b.c[0], [2])

    def test_copy3(self):
        """Test copy=deepcopy"""
        c = [[1]]
        class A(StateVars):
            _state_vars = [('c', c)]
            process_vars(copy=deepcopy)
        a = A()
        b = A()
        nose.tools.assert_equal(a.c[0][0], 1)
        nose.tools.assert_equal(b.c[0][0], 1)
        a.c[0][0] = 2
        nose.tools.assert_equal(a.c[0][0], 2)
        nose.tools.assert_equal(b.c[0][0], 1)

    def test_copy4(self):
        """Test copying and init."""
        class A(StateVars):
            _state_vars = [('x', 5),
                           ('y', Computed)]
            process_vars()
            def __init__(self, *v, **kw):
                self.y = 6
        a = A()
        l = [3]
        a.__dict__['y'] = l
        b = copy(a)
        c = deepcopy(a)

        nose.tools.assert_equal(b.y, l)
        nose.tools.assert_equal(c.y, l)
        nose.tools.assert_equal(id(b.y), id(l))
        nose.tools.assert_not_equal(id(c.y), id(l))

    def test_copy4a(self):
        """Test Computed.save."""
        class A(StateVars):
            _state_vars = [('a', Required),
                           ('b', Computed),
                           ('c', Computed(save=True)),
                           ('_computed_c', ClassVar)]
            process_vars()
            def __init__(self, *v, **kw):
                self.b = 2*self.a
                if 'c' not in kw:
                    self.c = self.a**2
                    A._computed_c = True

        A._computed_c = False
        a = A(a=10)
        nose.tools.ok_(A._computed_c)

        A._computed_c = False
        b = A(**dict(a.items(archive=True)))
        nose.tools.ok_(not A._computed_c)

        A._computed_c = False
        b = copy(a)
        nose.tools.ok_(not b._computed_c)

        A._computed_c = False
        rep, args, imps = a.archive_1('obj')
        d = dict(args)
        d['A'] = A
        b = eval(rep, d)
        nose.tools.ok_(not A._computed_c)

        nose.tools.assert_equal(a.a, 10)
        nose.tools.assert_equal(a.b, 20)
        nose.tools.assert_equal(a.c, 100)
        nose.tools.assert_equal(b.a, 10)
        nose.tools.assert_equal(b.b, 20)
        nose.tools.assert_equal(b.c, 100)        


    def test_copy5(self):
        """Test bug with copy constructing not resetting
        `_constructing` flag."""
        class A(StateVars):
            _state_vars = [('x', 5)]
            process_vars()

        a = A()
        b = A(copy(a))

        nose.tools.ok_('_constructing' not in a.__dict__)
        nose.tools.ok_('_constructing' not in b.__dict__)

    def test_copy6(self):
        """Test copy construction with new values."""
        class A(StateVars):
            _state_vars = [('a', 5),
                           ('b', 6)]
            process_vars()
        a = A()
        b = A(a)
        c = A(a,b=7)
        nose.tools.assert_equal(a.items(), b.items())
        nose.tools.assert_equal(c.a, 5)
        nose.tools.assert_equal(c.b, 7)
        

    @nose.tools.raises(ValueError)
    def test_Required(self):
        """Test required keys"""
        class A(StateVars):
            _state_vars = [('x', mmf.objects.Required, 'Required')]
            process_vars()
        a = A()

    def test_Required2(self):
        """Test providing required keys with class variables"""
        mmf.objects.NameClashWarning.simplefilter('ignore')
        class A(StateVars):
            _state_vars = [('x', mmf.objects.Required, 'Required')]
            process_vars()
        class B(A):
            process_vars()
            x = 2
        class C(A):
            process_vars()
            @property
            def x(self): return 5

        b = B()
        nose.tools.assert_equal(b.x, 2)
        c = C()
        nose.tools.assert_equal(c.x, 5)

        b1 = B(x=3)
        nose.tools.assert_equal(b1.x, 3)
        nose.tools.assert_equal(b.x, 2)
        nose.tools.assert_equal(B.x, 2)

    @nose.tools.raises(ValueError)
    def test_Required3(self):
        """Test Required(arg) error."""
        class A(StateVars):
            _state_vars = [('x', mmf.objects.Required('Required'))]
            process_vars()

    @nose.tools.raises(AttributeError)
    def test_NotImplemented(self):
        """Test NotImplemented keys"""
        class A(StateVars):
            _state_vars = [('c', NotImplemented, 'NotImplemented')]
            process_vars()
        a = A()
        c = a.c
        
    @nose.tools.raises(ValueError)
    def test_get_args(self):
        """Test get_args arg checking"""
        StateVars.get_args(1, 2)

    @nose.tools.raises(TypeError)
    def test_key_check_1(self):
        """Test exception for 1 extra kwarg."""
        class A(StateVars):
            _state_vars = ['x']
            process_vars()
        a = A(x=1, y=2)

    @nose.tools.raises(TypeError)
    def test_key_check_2(self):
        """Test exception for 2 extra kwarg."""
        class A(StateVars):
            _state_vars = ['x']
            process_vars()
        a = A(x=1, y=2, z=3)

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
        a = StateVars(1, 2)

    def test_compare_arrays(self):
        """Test that arrays can be compared."""
        class A(StateVars):
            _state_vars = [('a', np.array([1, 2]))]
            process_vars()
        a = repr(A())

    def test_copy(self):
        """Test StateVars.__copy__"""
        l = [1]
        a = Container(l=l)
        b = copy(a)
        a.l[0] = 2
        nose.tools.assert_equal(b.l[0], a.l[0])

    def test_deepcopy(self):
        """Test StateVars.__deepcopy__"""
        l = [1]
        a = Container(l=l)
        b = deepcopy(a)
        a.l[0] = 2
        nose.tools.assert_not_equal(b.l[0], a.l[0])

    def test_exclude(self):
        """Tests a bug with _gather_vars."""
        class C(StateVars):
            _state_vars = ['a']
            _excluded_vars = ['b']
            process_vars()
        C.b = 5
        nose.tools.assert_equals(C.b, 5)

    def test_excluded(self):
        """Tests Excluded attribute definition."""
        class C(StateVars):
            _state_vars = [('a', Excluded),
                           ('b', Excluded(3))]
            process_vars()
        c = C()
        nose.tools.assert_equals(c.b, 3)
        

    def test_class_vars(self):
        """Test ClassVars attribute bug with __new__ overwriting with
        default values."""
        mmf.objects.NameClashWarning.simplefilter('ignore')
        class F(StateVars):
            _state_vars = [('A', ClassVar(Required))]
            process_vars()
        class G(F):
            _state_vars = [('A', ClassVar(1))]
            process_vars()
        g = G()
        nose.tools.assert_equal(g.A, 1)

    @nose.tools.raises(AttributeError)
    def test_class_vars2(self):
        """Test that ClassVars cannot be initialized."""
        class F(StateVars):
            _state_vars = [('A', ClassVar(1))]
            process_vars()
        g = F(A=3)

    def test_ClassVar_overriding(self):
        """Test that subclasses can properly override a ClassVar."""
        mmf.objects.NameClashWarning.simplefilter('ignore')        
        class A(StateVars):
            _state_vars = [('a', ClassVar(0))]
            process_vars()

        class B(A):
            _state_vars = [('a', ClassVar(1))]
            process_vars()

        b = B()
        nose.tools.assert_equal(1, b.a)

    def test_overriding_ClassVar(self):
        """Test that overriding ClassVar works with archiving.

        Normally a ClassVar would not be archived because it is a
        property of a class.  A subclass might want this property to
        become and instance var, so it might override this."""
        mmf.objects.NameClashWarning.simplefilter('ignore')
        class A(StateVars):
            _state_vars = [('x', ClassVar(1))]
            process_vars()

        class B(A):
            _state_vars = [('x', 2)]
            process_vars()
        
        b = B(x=4)
        nose.tools.assert_equal(b.x, 4)


    def test_changing_defaults(self):
        """Test StateVars to see if changing default values preserves
        the documentation."""
        mmf.objects.NameClashWarning.simplefilter('ignore')
        class A(StateVars):
            _state_vars = [('a', 1, "Documentation for A")]
            process_vars()

        class B(A):
            _state_vars = [('a', 2)]
            process_vars()

        doc_A = [doc for (name, default, doc) in A._state_vars]
        doc_B = [doc for (name, default, doc) in B._state_vars]
        nose.tools.assert_equals(doc_A, doc_B)
        nose.tools.assert_not_equals(A().a, B().a)

    class HookException(Exception):
        pass

    @nose.tools.raises(HookException)
    def test__pre_hook__new__(self_):
        """Test _pre_hook__new__"""
        class A(StateVars):
            process_vars()
            def _pre_hook__new__(self, *varargin, **kwargs):
                raise self_.HookException()
        a = A()

    @nose.tools.raises(HookException)
    def test__post_hook__new__(self_):
        """Test _post_hook__new__"""
        class A(StateVars):
            _state_vars = [('x', 1), ('y', None)]
            process_vars()
            def _pre_hook__new__(self, *varargin, **kwargs):
                self.__dict__['_private'] = 2
            def _post_hook__new__(self, *varargin, **kwargs):
                nose.tools.assert_equals(self._private, 2)
                raise self_.HookException()
        a = A()

    def test__pre_post_hook_process_vars(self_):
        """Test _pre_hook_process_vars and _post_hook_process_vars.

        This might be used to set class variables based on the defined
        class properties.
        """
        class A(StateVars):
            _state_vars = [
                ('has_F', ClassVar(False), "True if F is redefined.")]
            process_vars()

            def F(self):
                raise NotImplementedError

            @classmethod
            def _pre_hook_process_vars(cls):
                # This is called before the vars are processed.
                nose.tools.assert_false('has_F' in cls.__dict__)

            @classmethod
            def _post_hook_process_vars(cls, results, _F=F):
                # This is called before the vars are processed.
                nose.tools.ok_('has_F' in results)
                if cls.F.im_func is not _F:
                    results['has_F'] = True

        class B(A):
            process_vars()
            pass

        class C(A):
            process_vars()            
            def F(self):
                return 1

        nose.tools.assert_false(A.has_F)
        nose.tools.assert_false(B.has_F)
        nose.tools.assert_true(C.has_F)

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test_get(self):
        """Test for uneeded getattr calls."""
        okay = True
        class E(StateVars):
            _state_vars = ['x', 'y']
            process_vars()
            def get_x(self):
                okay = False
                return self.__dict__['x']
            x = property(get_x)
        
        e = E(y=1)
        nose.tools.ok_(okay)

    @nose.tools.raises(UserWarning)
    def test_hiding_warning(self):
        """Test attribute hiding warning."""
        class A(StateVars):
            _state_vars = [('x', 1)]
            x = 3
            process_vars()
        
        a = A()
        nose.tools.assert_equals(a.x, 1)

    def test_properties(self):
        """Makes sure that properties can provide for Required
        values."""
        a = WithProperty()
        nose.tools.assert_equals(a.x, 1)

    def test_inherited_properties(self):
        """Make sure that __setattr__ finds inherited properties.

        (These are not in the class __dict__ but rather the base
        class's __dict__ and hence __setattr__ gets called by
        mistake)."""

        class A(StateVars):
            _state_vars = [('_x', 1)]
            process_vars()
            def get_x(self):
                return self._x
            def set_x(self, x):
                self._x = x
            x = property(get_x, set_x)
            
        class B(A):
            _state_vars = []
            process_vars()

        b = B()
        b.x = 2
        nose.tools.assert_equal(b._x, 2)

    def test_inherited_properties2(self):
        """Regression test for a bug with properties and _dynamic
        flag."""

        class A(StateVars):
            _state_vars = [('_x', 1)]
            _dynamic = True
            process_vars()
            def get_x(self):
                return self._x
            def set_x(self, x):
                self._x = x
            x = property(get_x, set_x)
            
        class B(A):
            _state_vars = []
            process_vars()

        b = B()
        b.x = 2
        nose.tools.assert_equal(b._x, 2)

    @nose.tools.raises(ValueError)
    def test_invalid_nodeps1(self):
        """Test invalid _nodeps."""
        class A(StateVars):
            _nodeps = [('x', 1)]
            process_vars()

    @nose.tools.raises(ValueError)
    def test_invalid_nodeps2(self):
        """Test _nodeps missing in _vars."""
        class A(StateVars):
            _state_vars = []
            _nodeps = ['x']
            process_vars()
        
class TestStateVars1(object):
    """Test StateVars processing without explicit calls to
    process_vars()"""
    def setUp(self):
        warnings.simplefilter('error', UserWarning)

    def tearDown(self):
        warnings.resetwarnings()
    
    def test1(self):
        """Test StateVars without process_vars call."""
        class StateVars1(StateVars):
            _dynamic = True
        a = StateVars1(a=1, b=2)
        nose.tools.assert_equal(a.a, 1)
        nose.tools.assert_equal(a.b, 2)

    def test2(self):
        """Test StateVars inheritance without process_vars call."""
        # This triggers a warning... Not an appropriate message, but
        # the warning is okay!
        mmf.objects.NameClashWarning.simplefilter('ignore')
        class StateVars1(StateVars):
            _state_vars = [('a', 1)]
            process_vars()
        class StateVars2(StateVars1):
            pass

        a = StateVars2()
        nose.tools.assert_equal(a.a, 1)

    @mmf.utils.mmf_test.dec.skipknownfailure
    def test3(self):
        """Test StateVars multiple inheritance without process_vars call."""
        class StateVars1(StateVars):
            _state_vars = [('a', 1)]
            process_vars()
        class StateVars2(StateVars):
            _state_vars = [('b', 2)]
            process_vars()
        class StateVars3(StateVars1, StateVars2):
            pass

        a = StateVars3()
        nose.tools.assert_equal(a.a, 1)
        nose.tools.assert_equal(a.b, 2)

class TestStateVars2(object):
    """Test changing initialization format."""
    def setUp(self):
        warnings.simplefilter('error', UserWarning)

    def tearDown(self):
        warnings.resetwarnings()

    class AA(StateVars):
        _state_vars = [('a', Required),
                       ('b', Computed)]
        process_vars()
        def __init__(self, *v, **k):
            self.b = self.a*self.a

    class BB(AA):
        _ignore_name_clash = set(['a'])
        _state_vars = [('x', Required),
                       ('a', Computed)]
        process_vars()
        def __init__(self, *v, **k):
            self.a = 2*self.x
            TestStateVars2.AA.__init__(self, *v, **k)

    def test1(self):
        """Testing inherited overriding of __init__"""
        a = self.AA(a=2)
        nose.tools.assert_equal(a.b, 4)
        b = self.BB(x=2)
        nose.tools.assert_equal(b.a, 4)
        nose.tools.assert_equal(b.b, 16)

class TestStateVarsDelegate(object):
    """Test new delegation functionality."""
    def setUp(self):
        warnings.simplefilter('error', UserWarning)

    def tearDown(self):
        warnings.resetwarnings()
    
    class BB(StateVars):
        _state_vars = [('a', Container(x=3)),
                       'c=a.b']
        process_vars()
        
    def test1(self):
        """Testing setattr with chains."""
        a = self.BB(a=Container())
        a.c = 1
        nose.tools.assert_equal(a.a.b, 1)

    def test2(self):
        """Testing that setattr with refs calls `__init__`."""
        class A(StateVars):
            _state_vars = [('x', Container()),
                           'y=x.y']
            process_vars()
            def __init__(self, *v, **kw):
                if 'y' in kw:
                    self.x.called = True
        a = A(y=1)
        a.x.called = False
        a.y = 2
        nose.tools.assert_equal(a.x.y, 2)
        nose.tools.assert_equal(a.x.called, True)

    def test3(self):
        """Test that Excluded and private vars are not delegated."""
        class A(StateVars):
            _state_vars = [('x', Excluded(2)),
                           ('_y', 4)]
            process_vars()

        class B(StateVars):
            _state_vars = [('a', Delegate(A))]
            process_vars()

        nose.tools.ok_('x' not in B._vars)
        nose.tools.ok_('_y' not in B._vars)

    def test4(self):
        """Test that assignment works."""
        class A(object):
            def __init__(self):
                raise Exception("Init Called!")

        class B(A):
            def __init__(self):
                pass
        
        class C(StateVars):
            _state_vars = [('a', Delegate(A))]
            process_vars()

        b = B()
        c = C(a=b)

    def test5(self):
        """Test that copy construction works."""
        class A(StateVars):
            _state_vars = [
                ('a', 3),
                ('b', Computed)]
            process_vars()
            def __init__(self, *v, **kw):
                self.b = self.a*2

        class B(StateVars):
            _state_vars = [
                ('A_', Delegate(A))]
            process_vars()

        class C(StateVars):
            _state_vars = ['a', 'b', 'A_']
            process_vars()

        a1 = A()
        a2 = A(a1)
        b1 = B(a=6)
        b2 = B(b1)
        c2 = C(b2)
        nose.tools.assert_equal(a2.a, a1.a)
        nose.tools.assert_equal(a2.b, a1.b)
        nose.tools.assert_equal(b2.a, b1.a)
        nose.tools.assert_equal(b2.b, b1.b)
        nose.tools.assert_equal(c2.a, b2.a)
        nose.tools.assert_equal(c2.b, b2.b)

    def test6(self):
        """Test bug with defaults overwriting specified objects."""
        class A(StateVars):
            _state_vars = [('a', 5)]
            process_vars()
        class B(StateVars):
            _state_vars = [('A_', Delegate(A))]
            process_vars()
        class C(StateVars):
            _state_vars = [('A_', Delegate(A)), ('A_.a',8)]
            process_vars()

        A_ = A(a=10)
        b = B(A_=A_)
        c = C(A_=A_)
        nose.tools.assert_equal(b.a, 10)
        nose.tools.assert_equal(c.a, 10)

    def test7(self):
        """Test copying semantics."""
        class A(StateVars):
            _state_vars = [('a', 5)]
            process_vars()
        class B(StateVars):
            _state_vars = [('A_', Delegate(A))]
            process_vars()
        class C(B):
            _state_vars = []
            process_vars()

        b1 = B(a=10)
        b2 = B(b1)
        c = C(b1)
        
        nose.tools.assert_not_equal(id(b2.A_), id(b1.A_))
        nose.tools.assert_not_equal(id(c.A_), id(b1.A_))
        nose.tools.assert_equal(c.a, 10)
        nose.tools.assert_equal(b2.a, 10)

    def test8(self):
        """Test copying semantics."""
        class A(StateVars):
            _state_vars = [('a', 5)]
            process_vars()
        class B(StateVars):
            _state_vars = [('A_', Delegate(A))]
            process_vars()

        b = B(a=10)
        b1 = B(b, a=1)

        nose.tools.assert_equal(b1.a, 1)

class TestStateVarsCached(object):
    r"""Test cached reference optimization functionality."""
    def setUp(self):
        warnings.simplefilter('error', UserWarning)

    def tearDown(self):
        warnings.resetwarnings()
    
    def test_cached(self):
        r"""Test cached references."""
        class A(StateVars):
            _state_vars = [
                ('a', 4),
                ('b', 5)]
            process_vars()

        class B(StateVars):
            _state_vars = [
                ('A_', Delegate(A, cached=True))]
            process_vars()

        b = B(a=7, b=8)
        nose.tools.assert_true('a' in b.__dict__)
        nose.tools.assert_true('b' in b.__dict__)
        nose.tools.assert_equal(b.a, 7)
        nose.tools.assert_equal(b.b, 8)

        b.a = 10
        nose.tools.assert_equal(b.a, 10)
        nose.tools.assert_equal(b.A_.a, 10)

        b.A_ = A(a=0,b=1)

        nose.tools.assert_equal(b.a, 0)
        nose.tools.assert_equal(b.b, 1)


class TestStateVarsDelete(object):
    """Test new deletion functionality."""
    def setUp(self):
        warnings.simplefilter('error', UserWarning)

    def tearDown(self):
        warnings.resetwarnings()

    def test_delete_1(self):
        """Test deleting a variable"""
        class A(StateVars):
            _state_vars = [('a', ClassVar(1))]
            process_vars()

        class B(A):
            _state_vars = [('a', Deleted)]
            process_vars()

        
        nose.tools.ok_('a' in A._vars)
        nose.tools.ok_('a' not in B._vars)

    @nose.tools.raises(ValueError)
    def test_delete_2(self):
        """Test exception for deleting a non-existent variable"""
        class A(StateVars):
            _state_vars = [('a', ClassVar(1))]
            process_vars()

        class B(A):
            _state_vars = [('b', Deleted)]
            process_vars()

    
class TestCoverage(object):
    """Some tests of special cases to force code coverage."""
    def setUp(self):
        mmf.objects.NameClashWarning.simplefilter('error')

    def tearDown(self):
        mmf.objects.NameClashWarning.simplefilter('ignore')

    def test_normalize_state_vars_1(self):
        """Test state var `('a', )`."""
        sv = mmf.objects.objects_._normalize_state_vars([('a',)])
        nose.tools.assert_equal(sv, [
                ('a', NotImplemented, mmf.objects.objects_._NO_DESCRIPTION)])

    @nose.tools.raises(TypeError)
    def test_normalize_state_vars_2(self):
        """Test state var exception on ('a',,,,)."""
        sv = mmf.objects.objects_._normalize_state_vars([
                ('a',None, None, None)])
        
    @nose.tools.raises(ValueError)
    def test_normalize_state_vars_3(self):
        """Test state var exception on ('a',,,,)."""
        sv = mmf.objects.objects_._normalize_state_vars([
                ('a',1),
                ('b=a', 2, 'doc b')])
        
    @nose.tools.raises(TypeError)
    def test_normalize_state_vars_4(self):
        """Test state var exception on ('a',,,,)."""
        sv = mmf.objects.objects_._normalize_state_vars([
                ('a=b',1,1,1,1)])
        
    @nose.tools.raises(ValueError)
    def test_normalize_state_vars_5(self):
        """Coverage of ('a=b',1,'doc')"""
        sv = mmf.objects.objects_._normalize_state_vars([
                ('a=b',1,'doc')])
        
    @mmf.utils.mmf_test.dec.skipknownfailure
    @nose.tools.raises(mmf.objects.NameClashWarning)
    def test_normalize_state_vars_6(self):
        """Test conflicting defaults

        This should raise an exception because the defaults are different.
        ."""
        sv = mmf.objects.objects_._normalize_state_vars([
                ('x=b.x', 1),
                ('y=b.x', 1)])

    @nose.tools.raises(mmf.objects.NameClashWarning1)
    def test_nameclash_1(self):
        """Test nameclash error."""
        class A(object):
            a = 6
        class B(StateVars, A):
            _state_vars = [
                ('a', 5)]
            process_vars()
        b = B()

    def test_no_nameclash_1(self):
        """This should not raise a name-clash error but did because of
        a bug."""
        class A(StateVars):
            _state_vars = [('a', ClassVar(1))]
            process_vars()
        class B(A):
            process_vars()
        
        
    @nose.tools.raises(ValueError)
    def test_normalize_state_vars_5(self):
        """Test state var exception on ('a',,,,)."""
        sv = mmf.objects.objects_._normalize_state_vars([
                ('a=b',1,'doc')])
        
    @nose.tools.raises(mmf.objects.NameClashWarning)
    def test_gather_vars_1(self):
        """Test state var exception on ('a',,,,)."""
        class A(object):
            _state_vars = ['a', 'a=a']
        mmf.objects.objects_._gather_vars(A)

    @nose.tools.raises(mmf.objects.NameClashWarning2)
    def test_local_hiding_1(self):
        """Test hiding variables."""
        class A(StateVars):
            a = 4
            _state_vars = [('a', ClassVar(3))]
            process_vars()
        

    def test_delegates_1(self):
        """Test fetching of documentation from deep."""
        class A(object):
            _state_vars = [
                ('x', None, 'var x'), 
                ('y', None, 'var y')]
            process_vars()

        class B(object):
            _state_vars = [
                ('a', Delegate(A, ['x']))]
            process_vars(archive_check=False)
            j = 1

        class C(object):
            _state_vars = [
                ('c', Delegate(B)),
                ('h=c.a.x'),
                ('j=c.j'),
                ('d=c')]
            process_vars(archive_check=False)

        nose.tools.ok_('var x' in C.__doc__)

    @nose.tools.raises(mmf.objects.NameClashWarning)
    def test_nameclash(self):
        class A(StateVars):
            _state_vars = ['a']
            process_vars()

            def a(self):
                """Clashes with state var."""

    @nose.tools.raises(NameError)
    def test_delegates_2(self):
        """Test missing ref."""
        class A(object):
            _state_vars = ['x=y']
            process_vars()
        
class Doctests(object):
    def test_1(self):
        """Test the constructor semantics.
    
        >>> class A(StateVars):
        ...     _state_vars = [('a', 1),
        ...                    ('b', NotImplemented),
        ...                    ('c', Computed)]
        ...     process_vars()
        ...     def __init__(self, *varargin, **kwargs):
        ...         if 'a' in kwargs:
        ...             print "'a' changed"
        ...         if 'b' in kwargs:
        ...             print "'b' changed"
        ...         if 'c' in kwargs:
        ...             print "'c' changed"
        >>> a = A()
        'a' changed
        >>> a.b = 2
        'b' changed
        >>> a = A(b=2)
        'a' changed
        'b' changed
        """

    def test_delegate_hiding(self):
        """
        >>> class BD(StateVars):
        ...     _state_vars = [('dyadic', False)]
        ...     process_vars()

        >>> class B(StateVars):
        ...     _state_vars = [('bd', Delegate(BD, ['dyadic']))]
        ...     process_vars()

        >>> class _BD(StateVars):
        ...     _state_vars = [('b', Delegate(B), "l"),
        ...                    ('dyadic', True)]
        ...     process_vars()

        >>> class _B(StateVars):
        ...     _state_vars = [('sd0', Delegate(_BD, ['dyadic']))]
        ...     process_vars()
        
        >>> b = _B(dyadic=False)
        >>> b.dyadic
        False
        """
