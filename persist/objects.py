r"""This file contains a set of classes and meta-classes that allow
objects to inherit useful functionality dealing with attributes,
automatic calculations etc.

Overview
--------
The highlight of this module is :class:`StateVars`.  The provides a
powerful method for providing and documenting attributes with
mechanisms for specifying defaults and delegates.

Performance
~~~~~~~~~~~
Attention has been given to making getting attributes as efficient as
if they were standard attributes.  Setting attributes is not so
efficient, however, as many checks are done at this stage.  This
reflects the common usage of attributes such as parameters that are
set only once in a while but accessed frequently.

.. note:: Getting attributes is somewhat inefficient for references as
   lookup must generally be performed.  This penalty can be overcome
   by allowing references to cache values in the local dictionary, but
   this can get out of sync if the referenced values are in a delegate
   and changed via the delegate.

StateVars
---------

.. _init_semantics:

:meth:`__init__` Semantics
~~~~~~~~~~~~~~~~~~~~~~~~~~

In the :class:`StateVars` and its descendants, the role of
:meth:`StateVars.__init__` and the inherited :meth:`__init__` method
changes slightly from the usual role as an initializer.  The semantics
are that of an initializer that ensures the class is in a consistent
state after initialization \emph{and} after variable changes.  The
following changes have been made:

1) :meth:`StateVars.__setattr__` calls :meth:`__init__` whenever a
   variable is assigned.  The name of the change variable is passed as
   a keyword argument so that a clever :meth:`__init__` can avoid
   performing unnecessary computations.  (See also
   :meth:`StateVars.suspend`, :meth:`StateVars.resume`, and
   :meth:`StateVars.initialize`).

   .. warning:: During construction, all default values are also
      assigned, and these assignments are included as keyword
      arguments to :meth:`__init__`.  Thus, there is no way of knowing
      exactly what arguments were specified by the user.  This is
      intentional so that code to compute :class:`Computed` variables
      can simply check for all values that have been set -- default or
      otherwise -- and compute what is needed.

      The workaround is to set a special default value (such as `None`
      or defining a special object containing the value) so that you
      can differentiate from a significant value.  Of course, if the
      user provides exactly this value, you are in the same boat.
      (Consider using a private class for example to prevent this.)

:meth:`StateVars.__new__` also wraps the :meth:`StateVars.__init__`
method defined by the class to provide the following behaviour.  (This
is defined in :func:`_get_processed_vars`.)

2) All assignments of named arguments to the instance attributes takes
   place before :meth:`StateVars.__init__` is called, so this usual
   ``self.a = a`` statements may be omitted.

3) The base class :meth:`__init__` methods are called if
   :attr:`StateVars._call_base__init__` is `True`, otherwise the user
   should call them as usual.

Thus, the main purpose of :meth:`__init__` is to compute all
:class:`Computed` variables from the changed (or initialized) values
of the other class parameters.  Here is a skeleton::

    def __init__(self, *varargin, **kwargs):
        if (1 == len(varargin) and not kwargs):
            # Called as a copy constructor.  State has been copied from
            # other by __new__.  You do not need to copy the
            # attributes here, but may need to copy calculated
            # parameters that are cached.  If kwargs is not empty,
            # then additional values have been specified and need to
            # be processed, so we exclude that case here
            _other = varargin[0]
        elif 1 < len(varargin):
            # Another argument passed without kw.  Error here.
            raise ValueError("StateVars accepts only keyword arguments.")
        else:
            # Process the changed variables as specified in kwargs
            # Call the base __init__ methods unless you explicitly set
            # _call_base__init__ is set
            <BaseClass>.__init__(self, *varagin, **kwargs)

            # For all computed vars, if a dependent variable is in
            # kwargs, then recompute it.

Property Semantics
~~~~~~~~~~~~~~~~~~
Properties can have three roles:

1) As a way of defining dynamically computed data.  In this case the
   property should have no `fset` method and will be stored as a
   :class:`Computed` state var with no storage.
2) As a way of getting and setting other attributes.  These types of
   properties have `fset` but should not be archived, stored etc.  The
   data will be archived and restored when the other data are stored.
   Such properties should *not* be included in `_state_vars`: They
   will instead be listed in the `_settable_properties` attribute.
3) As the preferred way of getting and setting other attributes in a
   way that the data should be stored and archived.  In this case, the
   data attributes used by the property should be directly set in the
   dictionary.  These properties should be included in `_state_vars`
   (which will generate a name clash error, so be sure to add the
   appropriate name to `_ignore_name_clash`).

The first two roles will be deduced automatically if a property exists
but is not in `_state_vars`.  The last role requires both the
existence of the property and an entry in `_state_vars`.

Copy Semantics
~~~~~~~~~~~~~~
Copying in python can be a slippery business, especially if one wants
to maintain some shared data, or to use functions, method, or classes
as data.  First we define

1) "Controlled data" in a :class:`StateVars` instance must be explicitly
   specified in the :attr:`StateVars._state_vars` attribute.  This
   will be copied as specified by the user.
2) "Uncontrolled data" in a :class:`StateVars` instance is that which is
   stored in the `__dict__`.  This is copied as a dictionary would be
   copied with no special processing.

.. todo:: Revisit copying, especially deepcopy to remove the need for
   hacks.

In order to manage the copying and referencing of data we use the
following semantics:

1) All of the real data is assumed to be stored in
   :attr:`__dict__`.  To copy the object, thus, only this
   dictionary needs to be copied.  The methods :meth:`__copy__`
   does this, making sure that the delegates are copied while the
   other attributes are simply referenced.  Method
   :meth:`__deepcopy__` works as usual.
        
2) The method :meth:`items` returns a list of the data
   required to construct the object.  The object should be
   able constructed by passing all of these items to the
   constructor.  Note that the constructor generally must be
   called in order to perform initializations.
   :class:`Computed` and :class:`Excluded` attributes will not
   be included here as they should be recomputed by the
   initialization routines, but references will be.

To Do
-----
.. todo:: Add support for nicely printing: i.e. flags or something to
   indicate how the object should print.
.. todo:: Add :class:`Dependent` like :class:`Required` so that some values can
   be used, represented, etc. but are the result of calculations.  Errors
   or warnings should be issued if the user tries to set these.
.. todo:: Complete :func:`_preprocess` to support optional syntax.
.. todo:: Provide more functionality for subclasses to change default values of
   the parent classes.  For example, if a parent class delegates `x=a.x`, then
   the subclass has to include `('a.x', 5)` in `_state_vars` to change the
   default.  If, instead, the subclass includes `('x', 5)`, then this will
   create a new variable and the delegation will be broken.  This should raise a
   warning.  Perhaps add a new type :class:`Default` so that one can do `('x',
   Default(5))`.  This will raise an error unless `x` is already a properly
   settable attribute in a parent, and will use the previous definition,
   including any delegation. A related issue that this would solve is that there
   is presently no way to provide defaults for non-stored attributes that
   provide both setters and getters.

Known Bugs
----------
.. todo:: Multiple inheritance requires a call to
   :func:`process_vars` even if no new `_state_vars` are added.  There is
   probably no solution without `__metaclass__` trickery.
.. todo:: If a class is defined in a local scope such as a function,
   then the local variables will be added to the class __dict__.  This
   is because of how :func:`process_vars()` works, but I don't know
   how to fix it.  See the test :func:`test_local_scope()`.  Somehow
   the `dic` passed to the metaclass includes local variables...
.. todo:: :meth:`StateVars.__iter__` uses `hasattr`, which calls `getattr`.
   If the user defines getters, then this is can be problematic.

Optional Syntax
---------------

Here is another possible syntax (not yet fully implemented, see
:func:`_preprocess`).  The idea here is to define simple state vars of
the class that are of a special type, either one of the Required,
Delegate etc. etc., or a tuple of length 2 with the second element of
a special type.  Then delete these and add the corresponding entries
to _state_vars.  For example, the following could be equivalent::

   class A(StateVars):
       _state_vars = [
           'a',
           ('b', 0),
           ('x', 1, 'variable x'),
           ('y=x', 'variable y (delegates to y)'),
           ('z', Required, 'a required var'),
           ('c', ClassVar(4), 'a class var')
           ]
       process_vars()

   class A(StateVars):
       a = Attr
       b = 0, Attr
       x = 1, Attr('variable x')
       y = 'x', Ref('variable y (delegates to y)')
       z = Required('a required var'),
       c = 4, ClassVar('a class var')
       process_vars()

.. note:: To do this, we should change the syntax of the various
   classes so that they can accept documentation as their first
   argument (this will be removed by :func:`_preprocess` and placed as
   the third element in the `_state_vars` tuple, but we need to allow
   for this here).
"""
from __future__ import division

__all__ = [
    'InitializationError', 'NameClashWarning', 'NameClashWarning1',
    'NameClashWarning2',
    'Archivable', 'StateVars', 'Container', 
    'process_vars', 
    'Attr', 'Required', 'Excluded', 'Internal', 'Computed', 'Deleted',
    'ClassVar', 'NoCopy', 'Delegate', 'Ref',
    'attribute', 'parameter', 'calculate', 
    'MemoizedContainer', 
    'option', 'Options', 'class_NamedArray', 'recview', 
    'RecView', 'Calculator']
import sys
import warnings

import copy
#import types
import inspect
#import optparse
#import textwrap

#import re

import numpy as np

import mmf.utils
from mmf.utils import isequal

import mmf.archive
#import mmf.interfaces as interfaces
import mmf.utils.text

try:
    from zope.interface.interface import Element as ZopeElement
except ImportError:                     #pragma: no cover
    from types import NoneType as ZopeElement

_ARCHIVE_CHECK = True
__warningregistry__ = {}

###########################################################
# Classes
class Archivable(object):
    r"""Convenience class implementing
    :interface:`interfaces.IArchivable`.

    The user only needs to implement the function :meth:`items`.

    Examples
    --------
    >>> class A(Archivable):
    ...     def __init__(self, a, b):
    ...         self.data = [a, b]
    ...     def items(self):
    ...         return zip(('a', 'b'), self.data)
    >>> a = A(1, 2)
    >>> a
    A(a=1, b=2)
    """
    # interfaces.implements(interfaces.IArchivable)
    # Breaks help.  See zope Bug #181371.
    # https://bugs.launchpad.net/zope3/+bug/181371
    
    def items(self):        # pragma: no cover 
        r"""Return a list `[(name, obj)]` of `(name, object)` pairs
        where the instance can be constructed as
        `ClassName(name1=obj1, name2=obj2, ...)`.

        The default implementation just uses the elements in
        `self.__dict__`.
        """
        return self.__dict__.items()

    ##########################################
    ##
    def __iter__(self):
        r"""Return an iterator through the archive.

        Examples
        --------
        >>> class A(Archivable):
        ...     def __init__(self, a, b):
        ...         self.data = [a, b]
        ...     def items(self):
        ...         return zip(('a', 'b'), self.data)
        >>> a = A(1, 2)
        >>> for k in a: print k
        a
        b
        """
        return (k for (k, v) in self.items())
    
    def archive_1(self, env=None):      # pylint: disable-msg=W0613
        r"""Return (rep, args, imports).
        
        Defines a representation rep of the instance self where the
        instance can be reconstructed from the string rep evaluated in
        the context of args with the specified imports = list of
        (module, iname, uiname) where one has either "import module as
        uiname", "from module import iname" or "from module import
        iname as uiname".
        """
        args = self.items()
        module = self.__class__.__module__
        name = self.__class__.__name__
        imports = [(module, name, name)]

        keyvals = ["=".join((k, k)) for (k, _v) in args]
        rep = "%s(%s)" % (name, ", ".join(keyvals))
        return (rep, args, imports)

    def archive(self, name):
        r"""Return a string representation that can be executed to
        restore the object.

        Examples
        --------
        (Note: We can't actually do this because the class :class:`A`
        cannot be imported from a module if it is defined at the
        interpreter)::

           class A(Archivable):
                def __init__(self, a):
                    self.a = a
                def items(self):
                    return [('a', self.a)]
           a = A(6)            # Create an instance
           s = a.archive('n')  # Get string archive
           env = {}            # Define an environment
           exec(s, env)        # Evaluate the string in env
           o = env['n']        # Access the object from env
           o.a
        """
        arch = mmf.archive.Archive()
        arch.insert(**{name:self})
        return str(arch)

    def __repr__(self):
        return mmf.archive.repr_(self)

    def __str__(self):
        return self.__repr__()

class InitializationError(Exception):
    r"""Initialization failed or incomplete."""

class NameClashWarning(UserWarning):
    r"""Name clash.  Name already defined.

    The default is to ignore warnings of type
    :class:`NameClassWarning1` but show those of type
    :class:`NameClassWarning2` which tend to be more severe.
    If you want to ignore all such errors (after debugging!) so you
    can disable this using :meth:`simplefilter`.  See :mod:`warnings`
    for possible actions: the most common are 'one' or 'ignore'.

    You can also do this on a class by class basis by defining the
    class attribute :attr:`_ignore_name_clash`.  This should be a set
    of the known name clashes.

    .. note:: This may be emitted because of spurious variables added to
       the class __dict__ if the class was defined within a local scope.
    """
    default_action = 'once'

    @classmethod
    def simplefilter(cls, action=None):
        """Filter NameClashWarnings with specified action."""
        if action is None:
            action = cls.default_action

        global __warningregistry__
        __warningregistry__ = {}
        warnings.simplefilter(action, cls)

class NameClashWarning1(NameClashWarning):
    r"""Name clash.  Name already defined.

    This is a less serious warning, for example, it is raised when
    default values are changed.  It is by default disabled.
    """
    default_action = 'ignore'

class NameClashWarning2(NameClashWarning):
    r"""Name clash.  Name already defined.

    This is a more serious warning about name-clashes that are
    indicative of bugs.  It is by default enabled to warn once.
    """
    default_action = 'once'

NameClashWarning1.simplefilter()
NameClashWarning2.simplefilter()

class _Required(object):                # pylint: disable-msg=R0903
    r"""Default value for required attributes.
    
    Examples
    --------
    >>> Required
    Required
    >>> Required('documentation')
    Required('documentation')
    """
    def __init__(self, doc=NotImplemented):
        if doc is not NotImplemented:
            self.doc = doc
            
    def __repr__(self):
        r"""Simple string for describing arguments etc.
        """
        doc = getattr(self, 'doc', NotImplemented)
        if doc is not NotImplemented:
            return "Required(%r)" % (doc, )
        else:
            return "Required"
        
    def __call__(self, doc):
        r"""Return a required object with documentation."""
        return _Required(doc=doc)

Required = _Required()                  # pylint: disable-msg=C0103

class _Deleted(Archivable):
    r"""Deleted variable.

    Use this to remove an attribute previously defined in a base class
    though the `_state_vars`.

    Examples
    --------
    >>> NameClashWarning.simplefilter('error')
    >>> class A(StateVars):
    ...     _state_vars = [('a', 1)]
    ...     process_vars()
    >>> class B(A):
    ...     _state_vars = [('b', 1)]
    ...     process_vars()
    ...     @property
    ...     def a(self):
    ...         return self.b*2
    Traceback (most recent call last):
       ...
    NameClashWarning1: Attempt to redefine attr 'a' with a property in class 'B'
    >>> class B(A):
    ...     _state_vars = [('a', Deleted),
    ...                    ('b', 1)]
    ...     process_vars()
    ...     @property
    ...     def a(self):
    ...         return self.b*2
    >>> b = B()
    >>> b.a
    2

    Despite the variable being deleted, it is still in `_vars` because
    the property without a setter is implemented as a
    :class:`Computed` variable: :func:`process_vars` adds it back.
    >>> 'a' in b._vars
    True

    A property with both setters and getters will not be added back.
    >>> class C(A):
    ...     _state_vars = [('a', Deleted),
    ...                    ('b', 1)]
    ...     process_vars()
    ...     def get_a(self):
    ...         return self.b*2
    ...     def set_a(self, a):
    ...         self.b = a/2
    ...     a = property(get_a, set_a)
    >>> c = C()
    >>> c.a
    2
    >>> 'a' in c._vars
    False
    """
    
Deleted = _Deleted()                    # pylint: disable-msg=C0103

def _is(default, type_):
    r"""Return true if default is a subclass or instance of `type`."""
    try:
        return issubclass(default, type_)
    except TypeError:
        return isinstance(default, type_)

class Attr(Archivable):
    r"""Base class for all attribute types."""

    def items(self):
        r"""Return all items to make object archivable.  The attribute
        names are determined by inspecting the arguments to the
        constructor :meth:`__init__`."""
        items = []
        func_code = self.__init__.im_func.func_code # pylint: disable-msg=E1101
        nargs = func_code.co_argcount

        # pylint: disable-msg=E1101
        defaults = self.__init__.im_func.func_defaults
        if not defaults:
            defaults = []
        for name, var in enumerate(func_code.co_varnames[1:nargs]):
            # Skip self.
            value = getattr(self, var)
            if name < nargs - 1 - len(defaults):
                items.append((var, value))
            elif value != defaults[name - (nargs - 1 - len(defaults))]:
                items.append((var, value))
        return items
            
class HasDefault(Attr):
    r"""Base class for types with default values.

    Examples
    --------
    >>> HasDefault(4)
    HasDefault(value=4)
    
    """
    value = NotImplemented              # Here so that one can always
                                        # access value, even on a class.
    def __init__(self, value):          # pylint: disable-msg=W0231
        self.value = value

class Excluded(HasDefault):
    r"""Excluded variable.

    These are not archived and are intended for either flags to
    indicate that a particular method is executing, or for
    non-essential reporting of internal state/temporary data.
    """
class Internal(Excluded):
    r"""Internal variable.

    These are not archived and are intended for internal use only.
    Functionally equivalent to :class:`Excluded` attributes and are
    presently implemented as these (and reported as these).
    """    
class Computed(HasDefault):
    r"""Computed attributes.

    These are not assignable, and should be computed in
    :meth:`__init__` from other parameters.

    Parameters
    ----------
    save : False, True, optional
       If this is `True`, then the value will be archived
       (i.e. included in a call to :meth:`StateVars.items`) and will
       be directly restored when the object is archived using the
       tools in :class:`mmf.archive`.  Upon construction of a restored
       object, these computed values will be provided in `kwargs` so
       that :meth:`__init__` can refrain from performing long tedious
       calculations.

       .. note:: This is dangerous because one must make sure that the
          proper data is restored --- if any of the other dependent
          parameters change, then the object could be left in an
          inconsistent state.

       .. todo:: As a precaution, :class:`StateVars` should only
          permits this type of construction if *all* items returned by
          :meth:`StateVars.items` are assigned.

    Examples
    --------
    >>> Computed.save
    False
    >>> Computed(save=True)
    Computed(save=True)
    """
    save = False                      # Here so that one can always
                                      # access these, even on a class.

    def __init__(self, value=NotImplemented, save=False):
        HasDefault.__init__(self, value)
        self.save = save
    
class ClassVar(HasDefault):
    r"""Class variables (not associated with instances).

    Consequential class variables should always be defined (and/or
    redefined) through the :attr:`_state_vars` mechanism.
    Inconsequential class variables can bed defined normally but these
    will always be overridden by those defined through the
    :attr:`_state_vars` mechanism once :func:`process_vars()` is
    called.
    """

class _Attr(HasDefault):
    r"""Denotes an attribute.

    Examples
    --------
    >>> _Attr('An attribute with no default')
    _Attr(doc='An attribute with no default')
    >>> _Attr('An attribute with a default', value=5)
    _Attr(doc='An attribute with a default', value=5)
    """
    # pylint: disable-msg=W0231
    def __init__(self, doc, value=NotImplemented):
        self.doc = doc
        self.value = value

class Delegate(HasDefault):
    r"""Delegate Class.

    An attribute with default value `Delegate(A)`  will be initialized
    as `A(**kw)` where the attributes in `A._state_vars` are used as
    keyword arguments.  `Delegate(A, ['x','y'])` is the same except
    only the specified attributes will be used.  Note that the
    delegate constructor must accept these attributes as keyword args.

    A default may also be specified, in which case this will be used
    to initialize the object using the standard copy semantics as
    specified by :class:`NoCopy`.

    Examples
    --------
    This is the simplest delegation to `A`.  All variables in
    `A._state_vars` become members of `D1`:
    
    >>> class A(StateVars):
    ...     _state_vars = [('a', 1), ('b', 2)]
    ...     process_vars()

    >>> class D1(StateVars):
    ...     _state_vars = [
    ...         ('A_', Delegate(A), 'Delegate all vars')
    ...         ]
    ...     process_vars()

    >>> d1 = D1(a=3); print d1
    a=3
    b=2
    A_=a=3
    b=2

    The attributes `a` and `b` are actually the attributes of `A_`:

    >>> d1
    D1(A_=A(a=3))
    
    >>> d1.a=5; print d1
    a=5
    b=2
    A_=a=5
    b=2

    Now we delegate to `B` but include an explicit list of delegates.
    This is the safer thing to do as it reduces the chances of
    name clashes:

    >>> class B(StateVars):
    ...     _state_vars = [('c', 3), ('d', 4)]
    ...     process_vars()

    >>> class D2(StateVars):
    ...     _state_vars = [('B_', Delegate(B, ['c']))]
    ...     process_vars()

    >>> d2 = D2(c=7); print d2
    c=7
    B_=c=7
    d=4

    If you want to delegate to an object that does not use
    `_state_vars`, you must explicitly specify these.  Note that the
    ones you specify in the delegate must be accepted by the
    constructor.

    >>> class C(Archivable):
    ...     def __init__(self, x=1, y=2):
    ...         self.x = x
    ...         self.y = y

    >>> class D3(StateVars):
    ...     _state_vars = [('C_', Delegate(C, ['x','y']))]
    ...     process_vars()
    
    >>> d3 = D3(x=10); d3
    D3(C_=C(y=2, x=10))

    Note that the assignments are made after the attribute `C_` is
    defined, so that the local kwargs overwrite the values passed in
    to `C_`:

    >>> D3(x=12, y=2, C_=C(y=2, x=10))
    D3(C_=C(y=2, x=12))

    Notice that the delegation mechanism creates a new instance of `C`
    here, hence it is shown in the representation.  (It is slightly
    redundant to have kwargs as well but this to show that they are
    indeed attributes.)

    You can also specify a default in the class definition.  You may
    also use :class:`NoCopy` etc.

    >>> c = C(x=-1,y=-2)
    >>> class D4(StateVars):
    ...     _state_vars = [('C_', Delegate(C, ['x','y'],
    ...                                    value=NoCopy(c)))]
    ...     process_vars()

    This is dangerous though, because you will modify the original
    (and then since the default has changed, the changes will not
    appear in the representation!)
    >>> d4 = D4(x=5); d4
    D4()
    >>> c
    C(y=-2, x=5)
    >>> id(c) == id(d4.C_)
    True

    Finally, in order to optimize attribute access, you can specify
    that the delegate should be cached.  This means that the delegated
    attributes will be cached in the instance `__dict__` for efficient
    retrieval.

    .. warning::  This can break code because it means that if you
       change an attribute in the delegate directly, the cache will
       not be updated until :meth:`initialize` is called or the
       corresponding attribute is set via the reference.

    >>> Delegate(None, ['x', 'y'])
    Delegate(cls=None, vars=['x', 'y'])
    >>> Delegate(None)
    Delegate(cls=None)
    >>> Delegate(None, vars=['x'], value=4)
    Delegate(cls=None, vars=['x'], value=4)
    """
    # pylint: disable-msg=W0231, W0622
    def __init__(self, cls, vars=None, value=NotImplemented, cached=False):
        self.cls = cls
        self.vars = vars
        self.value = value
        self.cached = cached

class Ref(Attr):
    r"""Ref Class.  Represents an attribute reference to another
    attribute.

    Examples
    --------
    >>> Ref('x')
    Ref(ref='x')
    >>> Ref('x', cached=True)
    Ref(ref='x', cached=True)
    """
    # pylint: disable-msg=W0231
    def __init__(self, ref, cached=False):
        self.ref = ref
        self.cached = cached
    
class NoCopy(object):                   # pylint: disable-msg=R0903
    r"""Default value for objects that should not be copied (or copied
    with a custom copier copy).  The default semantics are that
    initialization variables are copied with the copier supplied to
    :func:`process_vars` (deepcopy if not specified).

    Examples
    --------
    >>> n = NoCopy(3); n
    NoCopy(3)
    >>> n.copy                  # doctest: +ELLIPSIS
    <function <lambda> at ...>
    >>> n = NoCopy(3, copy='copy'); n
    NoCopy(3, copy='copy')
    >>> n.copy is copy.copy
    True
    >>> n = NoCopy(3, copy='deepcopy'); n
    NoCopy(3, copy='deepcopy')
    >>> n.copy is copy.deepcopy
    True
    >>> n = NoCopy(3, copy=lambda x:x); n # doctest: +ELLIPSIS
    NoCopy(3, copy=<function <lambda> at ...>)
    >>> n.copy                  # doctest: +ELLIPSIS
    <function <lambda> at ...>
    
    """
    def __init__(self, value, copy=False): # pylint: disable-msg=W0621
        self.value = value
        if copy is not False:
            self._copy = copy
    @property
    def copy(self):
        r"""Return the copier"""
        if hasattr(self, '_copy'):
            if "copy" == self._copy:
                return copy.copy
            elif self._copy in ["deep", "deepcopy"]:
                return copy.deepcopy
            else:
                return self._copy
        else:
            return lambda x:x
    def __repr__(self):
        args = [repr(self.value)]
        if hasattr(self, '_copy'):
            args.append('copy=%r'%self._copy)
        return "NoCopy(%s)" % (", ".join(args),)

def _classinitializer(proc):
    r"""Magic decorator to allow class decoration.
    
    One added feature is that the return value of `proc` is used to
    set the docstring.  (This means that `proc` is called twice).
    """
    # basic idea stolen from zope.interface.advice, P.J. Eby
    def newproc(*args, **kw):
        r"""Decorates the function so that it acts as a class
        decorator.  This uses some tricky metaclass magic to attach
        the function to the metaclass without actually changing the
        metaclass.  (Changing the metaclass opens a whole new can of
        worms!)"""
        frame = sys._getframe(1)        # pylint: disable-msg=W0212
        if '__module__' in frame.f_locals and not \
            '__module__' in frame.f_code.co_varnames: # we are in a class
            thetype = frame.f_locals.get("__metaclass__", type)
            def makecls(name, bases, dic):
                r"""Construct the new class and return it."""
                # This dic is the source of a bug: See
                # test_local_scope.  It can have members of the
                # enclosing scope...
                try:
                    cls = thetype(name, bases, dic)
                except TypeError, err: # pragma: no cover
                    if "can't have only classic bases" in str(err):
                        cls = thetype(name, bases + (object, ), dic)
                    else:  # other strange errs, e.g. __slots__ conflicts
                        raise

                # Process the class and then recreate with the updated
                # dictionary.  This allows us to include a new __doc__
                # string for example (because this cannot be
                # assigned).
                res, wrap__init__ = proc(cls, *args, **kw)
                dic.update(res)
                try:
                    cls = thetype(name, bases, dic)
                except TypeError, err: # pragma: no cover
                    if "can't have only classic bases" in str(err):
                        cls = thetype(name, bases + (object, ), dic)
                    else:  # other strange errs, e.g. __slots__ conflicts
                        raise
                wrap__init__(cls)
                # Need to do this after new class is created so
                # _original__init__ has correct im_class.
                
                return cls
            
            frame.f_locals["__metaclass__"] = makecls
        else:                   # pragma: no cover
            proc(*args, **kw)
    newproc.__name__ = proc.__name__    # pylint: disable-msg=W0622
    newproc.__module__ = proc.__module__
    newproc.__doc__ = proc.__doc__      # pylint: disable-msg=W0622
    newproc.__dict__ = proc.__dict__
    return newproc

_NO_DESCRIPTION = "<no description>"
def _normalize_state_vars(state_vars):
    r"""Return the normalized form of state_vars as a list of
    triplets.

    Examples
    --------
    >>> _normalize_state_vars([('a'), # doctest: +NORMALIZE_WHITESPACE
    ...                        ('b', 1),
    ...                        ('c', 2, 'doc'),
    ...                        ('d=c'), 
    ...                        ('e', Ref('c'), 'e doc'),
    ...                        ('f=a.x', 2, 'New f doc'),
    ...                        ('g=a.y', 2),
    ...                       ])
    [('a', NotImplemented, '<no description>'),
     ('b', 1, '<no description>'),
     ('c', 2, 'doc'),
     ('d', Ref(ref='c'), '<no description>'),
     ('e', Ref(ref='c'), 'e doc'),
     ('f', Ref(ref='a.x'), 'New f doc'),
     ('a.x', 2, ''),
     ('g', Ref(ref='a.y'), '<no description>'),
     ('a.y', 2, '')]

    >>> class A(object):
    ...    _state_vars = _normalize_state_vars(['a', 'b'])
    >>> class B(object):
    ...    _state_vars = _normalize_state_vars(['c', ('d', 2, 'var d')])
    >>> _normalize_state_vars([('e', Delegate(A)),
    ...                        ('f', Delegate(B, ['d'])),
    ...                        ('g=f.d')
    ...                ])  # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
    [('a', Ref(ref='e.a'), '<no description>'),
     ('b', Ref(ref='e.b'), '<no description>'),
     ('d', Ref(ref='f.d'), 'var d'),
     ('e', Delegate(cls=<class '...A'>), '<no description>'),
     ('f', Delegate(cls=<class '...B'>, vars=['d']), '<no description>'),
     ('g', Ref(ref='f.d'), '<no description>')]

    >>> _normalize_state_vars({'a':1, ('b', 'doc'):2})
    [('a', 1, '<no description>'), ('b', 2, 'doc')]

    Notes
    -----
    This must cover all of the cases listed in :class:`StateVar`.
    """
    normalized_state_vars = []
    if isinstance(state_vars, list):
        # Process ('x=a.y', <default>, <doc>) ->
        # -> ('x', Ref(ref='a.y'), <doc>) and ('a.y', <default>, '')
        new_state_vars = []
        new_refs = []
        for var_desc in state_vars:
            # Add any extra terms from references and delegates
            if (isinstance(var_desc, tuple) and '=' in str(var_desc[0])):
                var, ref = var_desc[0].split('=')
                if 3 == len(var_desc):
                    doc = var_desc[2]
                elif 3 > len(var_desc):
                    doc = _NO_DESCRIPTION
                else:
                    raise TypeError("Attr must be a str or tuple "+
                                    "of length 3 or less (got %s)" %\
                                        repr(var_desc))
                
                new_state_vars.append((var, Ref(ref), doc))

                if 2 <= len(var_desc):
                    # Add new default specification.
                    if '.' in ref:
                        new_state_vars.append((ref, var_desc[1], ''))
                    else:
                        raise ValueError("\n".join(
                                ["Cannot set default %r for ref '%s=%s'.",
                                 "(Set default for %r instead)"]) %
                                         (var_desc[1], var, ref, ref))

            elif (isinstance(var_desc, tuple)
                  and 2 <= len(var_desc) 
                  and isinstance(var_desc[1], Delegate)):
                cls_state_vars = getattr(var_desc[1].cls, '_state_vars', [])

                new_state_vars.append(var_desc)
                vars_ = var_desc[1].vars
                if vars_ is None:
                    extension = [x for x in cls_state_vars
                                 if not x[0].startswith('_')
                                 and not _is(x[1], Excluded)]
                else:
                    extension = [var_default_doc
                                 for var_default_doc in cls_state_vars
                                 if var_default_doc[0] in vars_]
                    # Add non _state_vars if explicitly specified.

                    if not cls_state_vars:
                        # Add one element for construction zip(*) below
                        cls_state_vars = [(None, NotImplemented, '')]
                    
                    extension.extend(
                        [(v, NotImplemented, _NO_DESCRIPTION)
                         for v in vars_
                         if v not in zip(*cls_state_vars)[0]])

                for var, default, doc in extension:
                    ref = '%s.%s' % (var_desc[0], var)
                    # Insert new references at front so they don't hide
                    # explicit references.
                    new_refs.append((var,
                                     Ref(ref,cached=var_desc[1].cached),
                                     doc))
                    #if default is not NotImplemented:
                    #    state_vars.append((ref, default, ''))
            else:
                new_state_vars.append(var_desc)

        state_vars = new_refs + new_state_vars

        for var_desc in state_vars:
            default = NotImplemented
            doc = _NO_DESCRIPTION
            if isinstance(var_desc, str):
                var = var_desc
            elif isinstance(var_desc, tuple):
                if 1 == len(var_desc):
                    var = var_desc[0]
                elif 2 == len(var_desc):
                    var, default = var_desc
                elif 3 == len(var_desc):
                    var, default, doc = var_desc
                else:
                    raise TypeError("Attr must be a str or tuple "+
                                    "of length 3 or less (got %s)" %\
                                        repr(var_desc))
            else:
                raise TypeError(
                    'state_vars must be a list of strings or tuples')
            if not isinstance(var, str):
                raise TypeError('Name must be a string (got %s)'%\
                                    repr(var))

            # Now process references
            if '=' in var:
                var, ref = var.split('=')
                if default is not NotImplemented: # pragma: no cover
                    raise ValueError("\n".join(
                            ["Cannot set default %r for ref '%s=%s'.",
                             "(Set default for %r instead)"]) %
                                     (default, var, ref, ref))
                default = Ref(ref)

            normalized_state_vars.append((var, default, doc))

    elif isinstance(state_vars, dict):
        state_vars_ = []
        for key in state_vars:
            if isinstance(key, str):
                state_vars_.append((key, state_vars[key]))
            elif isinstance(key, tuple) and len(key) == 2:
                state_vars_.append((key[0], state_vars[key], key[1]))
            else:
                raise TypeError('Key must be name or (name, doc)'+
                                ' (got %s)'%repr(key))
        return _normalize_state_vars(state_vars_)
    else:
        raise TypeError("state_vars must be a list or dict")
    return normalized_state_vars

def _is_attr(attr):
    r"""Return `True` if `attr` is an attribute definition or a tuple of
    length 2 with the second element being an attribute definition.
    These are special and are converted to entries in `_state_vars` by
    :func:`_preprocess`."""
    return (_is(attr, _Required)
            or attr is Deleted
            or _is(attr, Attr)
            or _is(attr, ClassVar)
            or isinstance(attr, Delegate)
            or _is(attr, HasDefault)
            or isinstance(attr, Ref)
            or _is(attr, Excluded)
            or _is(attr, Computed))

def _preprocess(cls):
    r"""Preprocess `cls` converting all attributes in `cls.__dict__`
    that are attribute definitions as defined by :func:`_is_attr` to
    the appropriate entries in `cls._state_vars`"""
    _state_vars = []
    for name in cls.__dict__:
        attr = getattr(cls, name, None)
        if isinstance(attr, tuple) and len(attr) == 2 and _is_attr(attr[1]):
            if _is(attr[1], HasDefault):
                attr[1].value = attr[0]
                attr = attr[1]
            else:
                raise ValueError(
                    ("%s.%s attribute type %r " +
                     "does not have a default (got %r)" %
                     (cls.__name__, name, attr[1], attr[0])))
        if _is(attr, _Required):
            del cls.__dict__[name]
        elif attr is Deleted:
            pass
        elif _is(attr, Attr):
            pass
        elif _is(attr, ClassVar):
            pass
        elif isinstance(attr, Delegate):
            pass
        elif _is(attr, HasDefault):
            pass
        elif isinstance(attr, Ref):
            pass
        elif _is(attr, Excluded):
            pass
        elif _is(attr, Computed):
            pass
    
def _gather_vars(cls):
    r"""Return `(vars, original_defaults, defaults, docs, excluded_vars,
    computed_vars, refs, delegates, cached)` gathered from `cls`.

    Returns
    -------
    vars : list
       List of all :attr:`_state_vars` names except private names and
       settable_properties.
    original_defaults : dict
       Dictionary of originally specified default values.  For
       example, this would be the :class:`NoCopy` instance.
    defaults : dict
       Dictionary of default values to be used to construct
       instances.  For example, this would be the :attr:`NoCopy.value`
       instead of the :class:`NoCopy` instance.
    docs : list
       List of documentation strings
    excluded_vars : set
        Set of excluded attributes.
    computed_vars : dict
        Dictionary of computed attribute names with values of
        :attr:`Computed.save`.
    refs : dict
        Dictionary of all references.
    delegates : dict
        Dictionary of all delegate classes
    settable_properties : set
        Set of settable properties not included in vars.
    cached : set
        Set of cached attributes.  In the :meth:`__init__` wrapper
        (defined by :func:`_get_processed_vars`), these variables
        should be set in `__dict__` with the values they reference for
        fast retrieval.
    ignore_name_clash : set
        This is a set of names for which name clashes between
        `cls.__dict__` and `cls._vars`.  This method adds properties
        to this set as the properties are stored in  `cls.__dict__`
        and we add the name to `cls._vars` so that the getters and
        setters will be called.
    
    If `cls` has no :attr:`_state_vars`, then `vars` is `None`.

    >>> class A(object):
    ...     _state_vars = [('a', 1, 'var a'),
    ...                    ('b', 2, 'var b'),
    ...                    ('n', NoCopy(3), 'var n')]
    ...     _doc = {'n': 'var n'}
    >>> class B(A):
    ...     _ignore_name_clash = set(['a'])
    ...     _state_vars = [('a', 3, 'new_a'), ('c', 4, 'c')]
    >>> _gather_vars(B)         # doctest: +NORMALIZE_WHITESPACE
    (['a', 'b', 'n', 'c'],
     {'a': 3, 'c': 4, 'b': 2, 'n': NoCopy(3)},
     {'a': 3, 'c': 4, 'b': 2, 'n': 3},
     {'a': 'new_a', 'c': 'c', 'b': 'var b', 'n': 'var n'},
     set([]), {}, set([]), {}, {}, {}, set([]), set([]), set(['a']))

    >>> class C(object):
    ...    _state_vars = [('x', 1, 'var x'),
    ...                   ('a', Delegate(A, ['b']), _NO_DESCRIPTION),
    ...                   ('b', Ref('a.b'), 'var b')]
    ...    _delegates = {'a': A}
    ...    _doc = {'b': 'var b', 'x': 'var x'}
    >>> class D(object):
    ...    _state_vars = [
    ...        ('c', Delegate(C)),
    ...        ('y=c.x'), 
    ...        ('c.x', 3),
    ...        ('h=c.a.n')]
    >>> _gather_vars(D)    # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
    (['x', 'a', 'b', 'c', 'y', 'c.x', 'h'],
     {'a': Ref(ref='c.a'), 'c': Delegate(cls=<class '...C'>),
      'b': Ref(ref='c.b'),
      'h': Ref(ref='c.a.n'), 'c.x': 3, 'y': Ref(ref='c.x'),
      'x': Ref(ref='c.x')},
     {'c.x': 3},
     {'a': '<no description>', 'c': '<no description>', 'b': 'var b',
      'h': 'var n', 'y': 'var x', 'x': 'var x'},
      set([]), {}, set([]),
      {'a': 'c.a', 'h': 'c.a.n', 'b': 'c.b', 'y': 'c.x', 'x': 'c.x'},
      {'c.b': ['b'], 'c.a.n': ['h'], 'c.x': ['y', 'x'], 'c.a': ['a']},
      {'c': <class '...C'>}, set([]), set([]), set([]))
    """
    #all_bases = mmf.utils.all_bases(cls)
    _preprocess(cls)                  # Preprocess for optional syntax
    all_bases = list(reversed(cls.__bases__))
    if hasattr(cls, '_state_vars'):
        class Class(cls):               # pylint: disable-msg=W0232,R0903
            r"""Dummy class to hold normalized :attr:`_state_vars`."""
            _state_vars = _normalize_state_vars(cls.__dict__.get(
                '_state_vars', []))
        all_bases.append(Class)
    else:
        all_bases.append(cls)
    
    # vars_ == None means no _state_vars which is different than empty
    # _state_vars.
    defaults = {}
    delegates = {}
    cached = set([])
    deleted = set([])
    settable_properties = set([])
    docs = {}
    vars_ = []
    refs_ = {}
    ignore_name_clash = getattr(cls, '_ignore_name_clash', set())
    for base in all_bases:
        # First we gather the complete _state_var list, allowing
        # subclasses to override ClassVar for example.
        if hasattr(base, '_state_vars'):
             # pylint: disable-msg=W0212
            for (var, default, doc) in base._state_vars:
                # By this point, all _state_vars are normalized
                if default is Deleted:
                    deleted.add(var)
                elif var in vars_ and var not in deleted:
                    if var not in ignore_name_clash:
                        warnings.warn(NameClashWarning1(
                            "Attempt to redefine attr '%s' in class '%s'"
                            % (var, cls.__name__)))
                else:
                    vars_.append(var)

                defaults[var] = default

                if var in docs and doc == _NO_DESCRIPTION:
                    # There is already some documentation from an
                    # earlier specification, so keep it:
                    doc = docs[var]
                docs[var] = doc

    # Delete all "Deleted" vars.
    for var in deleted:
        if var not in vars_:
            raise ValueError("Attempt to delete non-existent state var '%s'" 
                             % (var,))
        else:
            while var in vars_:
                vars_.remove(var)
            while var in docs:
                del docs[var]
            while var in defaults:
                del defaults[var]
    
    # Now check for any data descriptors in the class dictionary.
    # If no corresponding var has been specified in _state_vars,
    # then a new entry will be added.  If there is no setter
    # specified, then it will be a Computed var, otherwise it will
    # be a regular variable with a default of NotImplemented.
    # If there is a corresponding var, then this will be used to
    # provide the documentation and default value.
    for var in cls.__dict__:
        desc = getattr(cls, var, None)
        if isinstance(desc, property):
            if var in vars_:
                if var not in ignore_name_clash:
                    warnings.warn(NameClashWarning1((
                        "Attempt to redefine attr %r with a "
                        + "property in class %r")
                        % (var, cls.__name__)))
            elif desc.fset is None:
                ignore_name_clash.add(var)
                vars_.append(var)
                defaults[var] = Computed()
            else:
                settable_properties.add(var)
                defaults.setdefault(var, NotImplemented)

            if var not in docs or docs[var] == _NO_DESCRIPTION:
                if desc.__doc__ is None:
                    docs[var] = _NO_DESCRIPTION
                else:
                    docs[var] = desc.__doc__

    excluded_vars = set()
    computed_vars = {}
    class_vars = set()
    original_defaults = {}

    for var, default in defaults.items():
        original_defaults[var] = default
        if isinstance(default, NoCopy):
            # Continue processing value.  This allows
            # NoCopy(Excluded) for example.
            default = default.value
            
        if default is NotImplemented:
            del defaults[var]
        elif _is(default, ClassVar):
            del defaults[var]
        elif isinstance(default, Delegate):
            delegate = default
            delegates[var] = delegate.cls
            default = delegate.value
            if isinstance(default, NoCopy):
                # Move NoCopy out front
                no_copy = default
                default = default.value
                delegate.value = no_copy.value
                no_copy.value = delegate
                original_defaults[var] = no_copy
            if default is NotImplemented:
                del defaults[var]
            else:
                defaults[var] = default
        elif _is(default, HasDefault):
            if default.value is NotImplemented:
                del defaults[var]
            else:
                defaults[var] = default.value
        elif isinstance(default, Ref):
            refs_[var] = default.ref
            if default.cached:
                cached.add(var)
            del defaults[var]
        else:
            defaults[var] = default

        if _is(default, Excluded):
            excluded_vars.add(var)
        if _is(default, Computed):
            computed_vars[var] = default.save
        if _is(default, ClassVar):
            class_vars.add(var)
        if _is(default, _Required) and default is not Required:
            raise ValueError(
                "Required should not be called " +
                "in _state_vars (got arg %r)" % (default.doc,))
        
        if '.' in var and var in docs:
            # Removed documentation from overridden reference defaults.
            del docs[var]

    # Process the references
    def _get_documentation(var, cls):
        """Return documentation for `var` as an attribute chain in
        class `cls`, or return `_NO_DOCUMENTATION`."""
        try:
            # pylint: disable-msg=W0212
            inds = [n for n, vdd in enumerate(cls._state_vars)
                    if var == vdd[0]]
            if inds:
                # pylint: disable-msg=W0212
                return cls._state_vars[inds[0]][-1]
        except Exception:               #pragma: no cover
            1+1 # pass, pylint: disable-msg=W0104

        attr, _sep, tail = var.partition('.')
        #if sep and hasattr(cls, attr):
        #    return _get_documentation(tail, cls.attr)

        try:
            # pylint: disable-msg=W0212
            return _get_documentation(tail, cls._delegates[attr])
        except Exception:
            pass

        return _NO_DESCRIPTION

    refs = {}
    for var in refs_:
        ref_ = refs_[var]
        ref = refs.get(ref_, ref_) # Dereference
        if '.' in ref:
            head, sep, tail  = ref.partition('.')
            attr = refs.get(head, head)
            ref = "".join((head, sep, tail))
        else:
            attr = ref

        if attr not in vars_:
            raise NameError(
                "Ref %r for var %r not found in class %r."
                % (ref_, var, cls.__name__))
        refs[var] = ref

        if docs.get(var, _NO_DESCRIPTION) == _NO_DESCRIPTION:
            # Get documentation from reference
            if ('.' in ref and attr in delegates):
                # attr and tail defined above if '.' in ref
                docs[var] = _get_documentation(tail, delegates[attr])
            else:
                docs[var] = docs.get(ref, _NO_DESCRIPTION)

    # Make inverse mapping
    irefs = {}
    for ref in refs:
        irefs.setdefault(refs[ref], []).append(ref)

    return (vars_, original_defaults, defaults, docs,
            excluded_vars, computed_vars, class_vars,
            refs, irefs, delegates, settable_properties, cached,
            ignore_name_clash)

def _format_varstring(doc, width=70, indent=''):
    r"""Return the formatted varstring, processing it like a docstring
    and removing indentation.
    >>> _format_varstring("Hi", indent='  ')
    '  Hi'
    >>> a = '''This is an example of how to use a
    ...                        long multiline string to document a
    ...                        parameter.  This paragraph will be
    ...                        wrapped, but special formatting should
    ...                        be preserved if it is indented:
    ...                           1) A series of points
    ...                           2) Here is a longer point
    ...              
    ...                        You can use paragraphs too!  They will
    ...                        also be wrapped for you.'''
    >>> print _format_varstring(a, width=66, indent='  ')
      This is an example of how to use a long multiline string to
      document a parameter.  This paragraph will be wrapped, but
      special formatting should be preserved if it is indented:
         1) A series of points
         2) Here is a longer point
    <BLANKLINE>
      You can use paragraphs too!  They will also be wrapped for you.

    >>> b = ('''This is an example of a docstring which has some
    ...        formatting:
    ...            1) Here is an indented point w/o wrapping.
    ...            2) Another indented point.  This one is a''' + 
    ...     ''' very long line.  This should *not* be wrapped.
    ...     ''')
    >>> print _format_varstring(b, width=66,
    ...                         indent='  ') # doctest: +ELLIPSIS
      This is an example of a docstring which has some formatting:
          1) Here is an indented point w/o wrapping.
          2) Another indented point.  This one is a very long line.  This should *not* be wrapped.
    """
    wrapper = mmf.utils.text.DocWrapper(width=width,
                                        initial_indent=indent,
                                        subsequent_indent=indent)
    return wrapper.fill(doc)

def _get_summary(doc):
    r"""Return `(summary, rest)` where `summary` is the summary (first
    paragraph) of the documentation and `rest` is the rest (i.e.
    ``doc ~ '\n\n'.join((summary, rest))`` except that the summary
    will be trimmed and without line-breaks.).

    Examples
    --------
    >>> _get_summary('''
    ...    This is the summary for
    ...    some documentation.  Multiline.
    ...
    ...    Here is the rest.''')        # doctest: +NORMALIZE_WHITESPACE
    ('This is the summary for some documentation.  Multiline.',
     '\n   Here is the rest.')

    
    """
    
    doclines = doc.splitlines()
    while doclines and not doclines[0].strip():
        doclines.pop(0)

    summary_lines = []
    while doclines and doclines[0].strip():
        summary_lines.append(doclines[0].strip())
        doclines.pop(0)

    summary = ' '.join(summary_lines)

    if doclines:
        rest = "\n".join(doclines)
    else:
        rest = ''    
        
    return summary, rest


def _get_signature(state_vars):
    r"""Return a signature for the class.  This is
    formatted with some features to aid the sphinx documentation
    generation system.
    """
    all_names = dict((var, (default, doc)) # Dictionary for lookup.
                     for (var, default, doc) in state_vars)
    args = []
    for (var, default, _doc) in state_vars:
        if default is NotImplemented:
            args.append("%s="%var)
        elif (_is(default, Computed) or
              _is(default, Excluded) or
              _is(default, ClassVar) or
              isinstance(default, Delegate) or
              '.' in var):
            pass
        else:
            if isinstance(default, Ref):
                if default.ref in all_names:
                    default = all_names[default.ref][0]
                else:
                    continue
            args.append("%s=%s"%(var, default))
    args = ", ".join(args)

    return "(%s)" % (args,)
    
def _get__doc__(cls, state_vars):
    r"""Return a formatted document string for the class.  This is
    formatted with some features to aid the sphinx documentation
    generation system.

    Expects that state_vars has been normalized.

    >>> class A(object):
    ...     '''A simple class with some state_vars.
    ...
    ...     This should implement wrapping of the docstring as
    ...     demonstrated here.
    ...     '''
    ...     _state_vars = [('a', 1, 'Parameter a'),
    ...                    ('b', NotImplemented, 'Parameter b'),
    ...                    ('c', Required, "Parameter c"),
    ...                    ('d', Computed,\
    ...                        '''This is an example of how to use a
    ...                        long multiline string to document a
    ...                        parameter.  The backslash aids in
    ...                        indentation in emacs with python mode.
    ...
    ...                        This paragraph will be
    ...                        wrapped, but special formatting should
    ...                        be preserved if it is indented:
    ...                           1) A series of points
    ...                           2) Here is a longer point.  This
    ...                              will not wrap however because of
    ...                              the initial spaces, so you must
    ...                              format it by hand.'''),
    ...                    ('e', Delegate(Container), 'A Container'),
    ...                    ('e.a', 10, ''), # Default for e.
    ...                    ('f', Ref('e.b'), 'Ref to attribute e.b'),
    ...                    ('e.b', Required, ''),
    ...                    ('c.e', 3, ''),
    ...                   ]
    >>> print _get__doc__(A, A._state_vars) 
    ...                    # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
    A simple class with some state_vars.
    <BLANKLINE>
    Usage: A(a=1, b=, c=Required, f=Required)
    <BLANKLINE>
    This should implement wrapping of the docstring
    as demonstrated here.
    <BLANKLINE>
    **State Variables:**
        a: Parameter a
        b: Parameter b
        c; c.e=3: Parameter c
    <BLANKLINE>
    **Delegates:**
        e = Container(a=10, b=f=Required): A Container
    <BLANKLINE>
    **References:**
        f -> e.b: Ref to attribute e.b
    <BLANKLINE>
    **Computed Variables:**
        d: This is an example of how to use a long multiline string to
           document a parameter.  The backslash aids in indentation in
           emacs with python mode.
    <BLANKLINE>
           This paragraph will be wrapped, but special formatting should
           be preserved if it is indented:
              1) A series of points
              2) Here is a longer point.  This
                 will not wrap however because of
                 the initial spaces, so you must
                 format it by hand.

    >>> mmf.format_for_sphinx(True)
    >>> print _get__doc__(A, A._state_vars)
    A simple class with some state_vars.
    <BLANKLINE>    
    ::
    <BLANKLINE>
       A(a=1,
         b=,
         c=Required,
         f=Required)
    <BLANKLINE>
    This should implement wrapping of the docstring as
    demonstrated here.
    <BLANKLINE>
    **State Variables:**
    <BLANKLINE>
    .. attribute:: A.a
    <BLANKLINE>
       Parameter a
    .. attribute:: A.b
    <BLANKLINE>
       Parameter b
    .. attribute:: A.c; A.c.e=3
    <BLANKLINE>
       Parameter c
    <BLANKLINE>
    **Delegates:**
    <BLANKLINE>
    .. attribute:: A.e = Container(a=10, b=A.f=Required)
    <BLANKLINE>
       A Container
    <BLANKLINE>
    **References:**
    <BLANKLINE>
    .. attribute:: A.f -> A.e.b
    <BLANKLINE>
       Ref to attribute e.b
    <BLANKLINE>
    **Computed Variables:**
    <BLANKLINE>
    .. attribute:: A.d
    <BLANKLINE>    
       This is an example of how to use a long multiline string to
       document a parameter.  The backslash aids in indentation in emacs
       with python mode.
    <BLANKLINE>
       This paragraph will be wrapped, but special formatting should be
       preserved if it is indented:
          1) A series of points
          2) Here is a longer point.  This
             will not wrap however because of
             the initial spaces, so you must
             format it by hand.
    >>> mmf.format_for_sphinx(False) # Reset

    Check that class works!
    >>> class B(StateVars, A):
    ...     process_vars()
    >>> a = B(c=Container(), f=5)
    """
    # Process delegate defaults.
    defaults = {}
    for (var, default, doc) in state_vars:
        if '.' in var:
            head, tail = var.split('.')
            defaults.setdefault(head, []).append((tail, default))

    # Process inverse refs.
    irefs = {}
    for (var, default, doc) in state_vars:
        if isinstance(default, Ref):
            irefs.setdefault(default.ref, []).append(var)

    # Process signature:
    signature = _get_signature(state_vars)

    if mmf.using_sphinx:
        leader = ",\n" + " "*(4+len(cls.__name__))
        format = "::\n\n   %s(%s)" % (
            cls.__name__,
            leader.join(signature[1:-1].split(", ")))
    else:
        format = "Usage: %s%s" % (cls.__name__, signature)

    call = format
    
    delegates = []
    refs = []
    computed = []
    excluded = []
    class_vars = []
    vars_ = []

    if mmf.using_sphinx:
        indent = '   '
        format = ".. attribute:: %%s\n\n%s%%s" % (indent, )
    else:
        format = "    %s: %s"
        indent = '       '

    def fullname(var):
        r"""Return the fullname.  Includes the class fullname if using
        sphinx."""
        if mmf.using_sphinx:
            return ".".join([cls.__name__, var])
        else:
            return var

    for (var, default, doc) in state_vars:
        # Format doc, but strip off the first indent
        doc = _format_varstring(doc, indent=indent)[len(indent):]

        if '.' in var:
            # Just a delegate default 
            pass
        elif _is(default, Computed):
            computed.append(format % (fullname(var), doc))
        elif _is(default, Excluded):
            excluded.append(format % (fullname(var), doc))
        elif _is(default, ClassVar):
            class_vars.append(format % (fullname(var), doc))
        elif isinstance(default, Delegate):
            args = []
            for name, default_ in defaults.get(var, []):
                args.append("=".join(
                    [name]
                    + map(fullname, irefs.get('%s.%s' % (var, name), []))
                    + [str(default_)]))

            name_ = "%s = %s(%s)" % (fullname(var), 
                                     default.cls.__name__,
                                     ", ".join(args))

            delegates.append(format % (name_, doc))
        elif isinstance(default, Ref):
            name_ = "%s -> %s" % (fullname(var), fullname(default.ref))

            refs.append(format % (name_, doc))
        elif var in defaults:
            defs = ["%s.%s=%s" % (fullname(var), n, d) 
                    for n, d in defaults[var]]
            name_ = fullname(var) + "; " + ",".join(defs)

            vars_.append(format % (name_, doc))
        else:
            vars_.append(format % (fullname(var), doc))
    
    def make_str(header, pairs, item_sep="\n", section_sep="\n\n"):
        r"""Return a string concatenating all the pairs of variable
        lists.

        pairs = [(header, [(fullname, doc)]]."""
        sections = [header]
        for (head, nd_list) in pairs:
            if 0 < len(nd_list):
                sections.append(item_sep.join([head] + nd_list))
        return section_sep.join(sections)

    if cls.__doc__ is not None:
        summary, rest = _get_summary(cls.__doc__)
        header = "\n\n".join([summary, call, mmf.utils.text.trim(rest)])
    else:
        header = call

    header = "\n\n".join([header, "\n".join([
        "Attributes",
        "----------"])])
    if mmf.using_sphinx:        # Add extra newlines
        newline = "\n"
    else:                       # Keep compact
        newline = ""

    return make_str(header, [("**Class Variables:**" + newline, class_vars),
                             ("**State Variables:**" + newline, vars_),
                             ("**Delegates:**" + newline, delegates),
                             ("**References:**" + newline, refs),
                             ("**Computed Variables:**" + newline, computed),
                             ("**Excluded Variables:**" + newline, excluded)])

def _get_doc(name, with_docs, default=_NO_DESCRIPTION):
    """Return the documentation associated with `name` in
    `with_docs`.

    Parameters
    ----------
    name : str
       Name of attribute to search for.
    with_docs : {None, interface, obj, list of obj}
       Parse these objects for documentation.  If no documentation is
       provided in the current class, then these will be searched for
       documentation and it used if found.  The first instance that
       has a matching member with a non-empty documentation string
       will be used.
    default : str
       Default value to return if no documentation is found.

    Examples
    --------
    >>> class A(object):
    ...     def f(self):
    ...         'A documented function'
    >>> from zope.interface import Interface, Attribute
    >>> class IB(Interface):
    ...     x = Attribute('Documentation for x')
    ...     def f(self):
    ...         'Another documented function'
    >>> _get_doc('f', [A(), IB])
    'A documented function'
    >>> _get_doc('f', [IB, A])
    'Another documented function'
    >>> _get_doc('x', IB)
    'Documentation for x'
    >>> _get_doc('y', IB)
    '<no description>'
    """
    if with_docs is None:
        return default
    
    if (not isinstance(with_docs, list)
        and not isinstance(with_docs, tuple)):
        with_docs = [with_docs]

    doc = None
    for obj in with_docs:
        if issubclass(type(obj), ZopeElement) and name in obj:
            doc = obj.get(name).getDoc()
        else:
            try:
                doc = getattr(obj, name).__doc__
            except AttributeError:
                1+1 # pass, pylint: disable-msg=W0104
        if doc:
            return doc
    return default
            
# pylint: disable-msg=W0621
def _get_processed_vars(cls, copy, archive_check, with_docs=None):
    r"""Return (results, `__doc__`) where `results` is a dictionary of
    attributes to be assigned in `cls` after `vars_` have been processed
    and `__doc__` is the new documentation including the variable
    descriptions.

    .. seealso:: See also :func:`process_vars`.
    """
    results = {}
    (vars_, original_defaults, defaults, docs,
     excluded_vars, computed_vars, class_vars,
     refs, irefs, delegates, settable_properties, cached,
     ignore_name_clash) = _gather_vars(cls)
    for name in docs:
        if docs[name] == _NO_DESCRIPTION:
            docs[name] = _get_doc(name=name,
                                  with_docs=with_docs)

    # Perform some sanity checks and helpful errors
    if hasattr(cls, '_nodeps'):
        for s in cls._nodeps:
            if not isinstance(s, str):
                raise ValueError(
                    """_nodeps should just be a list of names: define the
                    actual variables in _state_vars.  Got %s"""
                    %(repr(s),))
            elif s not in vars_:
                raise ValueError(
                    "Vars in _nodeps should also be defined in " 
                    + "_state_vars.  Got %s" % (repr(s),))
                
    # Check that there are no clashes
    for var in [var for var in vars_ if
                var in cls.__dict__ and
                var not in ignore_name_clash]:
        if inspect.isfunction(cls.__dict__[var]):
            warnings.warn(NameClashWarning2((
                "Variable %r conflicts with method of " +
                "the same name in class %r.") %
                                           (var, cls.__name__)))
        elif var in class_vars:
            warnings.warn(NameClashWarning2(
                "Local variable %r hidden in class %r.\n"
                % (var, cls.__name__) +
                "Define all class vars_ using ClassVar in _state_vars."))
        else:
            warnings.warn(NameClashWarning2(
                "Variable %r in _state_vars already in __dict__ of class %r!"
                % (var, cls.__name__)))

    if archive_check:
        arch = mmf.archive.Archive()
        _defaults = dict((_k, defaults[_k]) 
                         for _k in defaults 
                         if _k not in excluded_vars)
        arch.insert(x=_defaults)
        try:
            _arch_rep = str(arch)
            _arch_rep = _arch_rep  # noop to appease lint
        except Exception, err:     # pragma: no cover
            err.archive = arch
            raise
        finally:
            del arch

    results['_vars'] = [v for v in vars_ if '.' not in v]
    results['_state_vars'] = [
        (var, original_defaults[var], docs.get(var, '')) for var in vars_]
    results['_excluded_vars'] = excluded_vars
    results['_computed_vars'] = computed_vars
    results['_class_vars'] = class_vars
    results['_defaults'] = defaults
    results['_delegates'] = delegates
    results['_settable_properties'] = settable_properties
    results['_cached'] = cached
    results['_refs'] = refs
    results['_irefs'] = irefs
    results['_ignore_name_clash'] = ignore_name_clash

    if not copy:
        copy = lambda x:x

    results['_default_copy'] = staticmethod(copy)

    results['_dynamic'] = getattr(cls, '_dynamic', False)

    # Assign class variables
    for var in class_vars:
        value = original_defaults[var].value
        if value is not NotImplemented:
            results[var] = value

    def wrap__init__(cls):
        r"""Wraps the original `cls.__init__` with a new version that
        does processing."""        
        cls._original__init__ = cls.__init__
        def __init__(self, *varargin, **kwargs):
            r"""Wrapper for :meth:`__init__` to set _initializing flag."""
            # pass, pylint: disable-msg=W0212            
            if '_no_init' in self.__dict__:
                # Short circuit for copy construction:
                del self.__dict__['_no_init']
                self.__dict__.pop('_constructing', None)
                return

            init_flag = _start_initializing(self)
            if ('_constructing' in self.__dict__ and not
                1 == len(varargin)):
                # Include defaults if not copy constructing
                for k in self:
                    if k in self._defaults:
                        kwargs.setdefault(k, self._defaults[k])
                self.__dict__.pop('_constructing')

            # Update all cached values.
            for name in self._cached:
                self.__dict__[name] = getattr(self, self._refs[name])
            
            try:
                if self._call_base__init__:
                    for cl in cls.__bases__:
                        cl._original__init__(self, *varargin, **kwargs)
                cls._original__init__(self, *varargin, **kwargs)
            except:                 # pragma: no cover
                raise
            finally:
                self.__dict__.pop('_constructing', None)
                _finish_initializing(self, init_flag)

        # pylint: disable-msg=W0212
        setattr(__init__, '__doc__', cls._original__init__.__doc__)
        cls.__init__ = __init__

    doc = _get__doc__(cls, state_vars=results['_state_vars'])
    return (results, doc, wrap__init__)

@_classinitializer
def process_vars(cls, copy=copy.deepcopy, archive_check=None,
                 with_docs=None):
    r"""Return `(results, wrap__init__)`.  This is a class decorator to
    process the :attr:`_state_vars` attribute of `cls` and to define
    the documentation, and members :attr:`_state_vars`,
    `_excluded_vars`, `_computed_vars`, `_vars`, `_defaults`, and
    `_dynamic`.

    Classes may perform additional processing if required by defining
    the :func:`classmethod` hooks `_pre_hook_process_vars(cls)` and
    `_post_hook_process_vars(cls, results)`.  The latter may modify
    the dictionary `results`.

    Parameters
    ----------
    copy : function, optional
       Default copier.  This is used to make a copy of the passed
       parameter when initializing so that (typically) mutable objects
       are not shared among instances.
    archive_check : bool
       If True, then the default values are checked to ensure that
       they are archivable.
    with_docs : {None, interface, obj, list of obj}
       Parse these objects for documentation.  If no documentation is
       provided in the current class, then these will be searched for
       documentation and it used if found.

    Returns
    -------
    results : dict
       New class dictionary including `'__doc__'`
    wrap__init__ : function
       This function should be used to wrap the original :meth:`__init__`
       method to perform the assignments etc.
       
    Examples
    --------
    >>> class A(object):
    ...     "A simple class"
    ...     _state_vars = [('a', 1, 'Param a'),
    ...                    ('b', 2, 'Param b'),
    ...                    ('c', Computed, 'A computed parameter'),
    ...                    ('c1', Computed(save=True),
    ...                        'A saved computed parameter'),
    ...                    ('e', Excluded, 'An excluded parameter'),
    ...                    ('e1', Excluded(3), 'Excluded with default'),
    ...                    ('f', Excluded)]
    ...     process_vars()
    >>> print A.__doc__
    A simple class
    <BLANKLINE>
    Usage: A(a=1, b=2)
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    **State Variables:**
        a: Param a
        b: Param b
    <BLANKLINE>
    **Computed Variables:**
        c: A computed parameter
        c1: A saved computed parameter
    <BLANKLINE>
    **Excluded Variables:**
        e: An excluded parameter
        e1: Excluded with default
        f: <no description>
    """
    # pylint: disable-msg=W0212
    if archive_check is None:
        archive_check = _ARCHIVE_CHECK
    if hasattr(cls, '_pre_hook_process_vars'):
        cls._pre_hook_process_vars()
    results, doc, wrap__init__  = _get_processed_vars(
        cls, copy=copy, archive_check=archive_check, with_docs=with_docs)
    results['__doc__'] = doc
    if hasattr(cls, '_post_hook_process_vars'):
        cls._post_hook_process_vars(results)
    return results, wrap__init__

def _vars_processed(cls):
    r"""Return True if cls has had its variables processed (or if it
    has inhereted from a proprly processed class without redefining
    any vars_."""
    vars_ = ['_vars', '_state_vars', '_defaults',
            '_excluded_vars', '_computed_vars', '_dynamic',
            '_delegates', '_settable_properties', '_refs', '_irefs']
    if all(map(cls.__dict__.has_key, vars_)):
        # All local variables have been assigned by process_vars, so
        # assume this was done by process_vars.
        result = True
    else:
        # Probably inherited, just check that the variables are
        # equivalent to what would be produced by process_vars.
        res, _doc, _wrap__init__ = _get_processed_vars(
            cls, copy=None, archive_check=False)
        result = True
        for var in vars_:
            result = (result 
                      and hasattr(cls, var) 
                      and isequal(getattr(cls, var), res[var]))
    return result

def _start_initializing(self):
    r"""Set the _initializing semaphore in self and return.

    Use before calling :meth:`__init__` to prevent recursion.  Pass the
    return value to `_finish_initializing` to check that nothing has
    altered the flag in between.  This should be used in a try block.
    """
    _initializing = getattr(self, '_initializing', 0)
    self.__dict__['_initializing'] = _initializing+1
    return _initializing

def _finish_initializing(self, previous_initializing):
    r"""Unset the `_initializing` semaphore in self.
    Use after calling :meth:`__init__`."""
    # pass, pylint: disable-msg=W0212
    try:
        _initializing = self._initializing
    except AttributeError:      # pragma: no cover
        raise InitializationError("_initializing flag not defined:"
                                  " missing _start_initializing().")
    self.__dict__['_initializing'] = _initializing - 1
    if _initializing != previous_initializing + 1: # pragma: no cover
        raise InitializationError("_initializing flag changed from"
                                  " %i to %i between semaphores!" %(
                previous_initializing + 1, _initializing))

class StateVars(Archivable):
    r"""Base class for objects that support definition of attributes
    through the specification of :attr:`_state_vars` class attributes
    and then processed by :func:`process_vars`.  For example::
    
       class Complex(StateVars):
           "A complex number class."
           _state_vars = [
               ('real', 0, 'Real part'),
               ('imag', 0, 'Imaginary Real part')]
           process_vars()
           ...
    When defining a :class:`StateVars` class one should:

    1) Define the :attr:`_state_vars` attribute as discussed below.
    2) Call :func:`process_vars`.
    3) Define :meth:`__init__` to specifying initialization.  Be sure
       to call :meth:`__init__` for any base classes (not needed if
       inheriting directly from :class:`StateVars`.  Remember that you
       do not need to assign any parameters in :attr:`_state_vars` ---
       these will be assigned in the constructor :meth:`__new__`.
       However, any :class:`Computed` attributes will need to be
       computed here, and one might like to perform checks of the
       parameter values.

       Remember that :meth:`__init__` will be called whenever
       parameter change in a shallow way (i.e. through direct
       assignment).

       See :ref:`init_semantics` for details.
                                                
    4) Profile performance: if performance is too slow then:

       1) Define :attr:`_nodeps`.  This is a list of names that are
          simply used but which do not affect any computations in
          :meth:`__init__`.  Changes to these parameters will no
          longer trigger a call to :meth:`__init__`.
       2) Inspect the `kwargs` argument to :meth:`__init__`.  This
          will include all changed parameters so you can optimize the
          re-initialization to only perform the required updates.
       3) Consider calling :meth:`suspend` and :meth:`resume` in your
          code so that changes can be accumulated and processed by a
          single call to :meth:`__init__` when :meth:`resume` is
          called rather than when each attribute is changed.

    The call to :func:`process_vars` will parse :attr:`_state_vars`
    from the class definition and any superclasses.  These are
    accumulated and described in the following class attributes:

    Attributes
    ----------
    _state_vars : list of tuples
       List of triplets `(name, default, doc)` of the parameters.
    _nodeps : list of str (optional)
       List of names that are not used when initializing.  These
       attributes have "no dependents" and so can be modified without
       triggering a call to :meth:`__init__`.  This is not processed
       by :func:`process_vars` and thus will not include values from
       any superclass.  These must be included again explicitly
       because your class may introduce dependencies not present in
       the parent.
    _vars : list of names
       List of all the variable names, including delegates,
       references, excluded variables etc.  The only names it does not
       contain are the dynamically assigned variables in
       :attr:`__dict__` if :attr:`_dynamic` is `True` and
       :attr:`_settable_properties`.
    _defaults : dict
       Dictionary of default values (these might be copies
       or archived versions of the default values in
       :attr:`_state_vars`)
    _class_vars : set of names
       Set of the names of the class variables defined in :attr:`_state_vars`
    _computed_vars : dict
       Dict of computed attribute names with values of :attr:`Computed.save`.
    _excluded_vars : set
       Set of names allowed to be assigned, but excluded
       from archival (used for temporaries etc.) and will not generate
       calls to :meth:`__init__` when set.
    _dynamic : bool
       If True, then the class will allow dynamic attribute generation
       via assignment, otherwise attempting to assign a new attribute
       will result in an exception.
    _refs : dict
       A dictionary of references providing for aliases and delegation.
    _irefs : dict
       The inverse mapping from a real attribute to a list of the
       references pointing to it.
    _delegates : dict
       A dictionary of the delegate objects that the class will
       construct upon initialization.
    _settable_properties : set
       A set of all settable properties not in _vars.
    _call_base__init__ : bool
       If `True`, then automatically call the base class
       :meth:`__init__` methods.  `False` by default.
    _original__init__ : meth
       This is the original :meth:`__init__` function is stored here.  After
       the class is finished, the original :meth:`__init__` is replaced by a
       wrapper (defined in :func:`_get_processed_vars`) that sets the
       variables and then calls this (as well as the base constructors
       if `_call_base__init__` is `True`.)

    Notes
    -----
    The state variables with names begining with underscores
    '_...' are always excluded unless explicitly included in
    :attr:`_state_vars`.

    :attr:`_state_vars` may be a dictionary with default values, or simply a
    list/set of variable names.  See below for examples.

    We also allow for parameters to delegate to other parameters by
    attributes with the following forms:

    ``('x', Ref('y'), <doc>)``:
       The object will have an attribute `x` that refers to the
       attribute `y`.  The documentation may be changed, but the
       default value must be specified through `y`.
    ``('a', Delegate(A), <doc>)``:
       The attribute `a` will be initialized as an instance of class
       `A` taking it's attributes from the constructor.  All
       attributes with the name `a.*` will be used to provide keyword
       arguments.  In addition, any other attributes of class `A` will
       be promoted to become attributes of the current class.  It is
       an error if they collide with any other attributes.
    ``('a', Delegate(A, ['x', 'y']), <doc>)``:
       Same as above except only the attributes `x` and `y` will be
       promoted.
    ``('a.y', <default>, '')``:
       This is a direct reference to the attribute `a.y`.  If `a` is
       delegated from a class as above, then this can be used to
       provide a (new) default value.  Any documentation is ignored
       here and this parameter is not listed.  Instead, the default is
       listed in the documentation of the parameter `a` itself.
    
    These are the normalized forms.  Shortcuts are:

    ``('x=a.y', <default>, <doc>)``:
       Equivalent to the pair ``('x', Ref('a.y'), <doc>)`` and
       ``('a.y', <default>, '')``
    ``('x=y')``:
       Synonym for ``('x', Ref('y'), _NO_DESCRIPTION)``
    ``('x=a.y', <default>)``:
       Synonym for ``('x=a.y', <default>, _NO_DESCRIPTION)``
 
    Examples
    --------
    >>> class A(StateVars):
    ...     _state_vars = [('x', 10), ('y', 100)]
    ...     process_vars()
    >>> a = A(x=1.0)
    >>> a
    A(x=1.0)
    >>> print a
    x=1.0
    y=100
    >>> a.y = 5
    >>> a
    A(x=1.0, y=5)

    Setting other attributes is not transparently supported...

    >>> a.z = 6
    Traceback (most recent call last):
        ...
    AttributeError: Cannot set attribute 'z' of object 'A'

    You can if you must, however...

    >>> a.__dict__['z'] = 6
    >>> a.z
    6

    But direct assignment is still not supported

    >>> a.z = 7
    Traceback (most recent call last):
        ...
    AttributeError: Cannot set attribute 'z' of object 'A'

    If you forget to call process_vars()...

    >>> class B(A):
    ...     _state_vars = [('LargeObject', Excluded)]

    A helpful reminder is displayed upon use...

    >>> b = B()
    Traceback (most recent call last):
       ...
    InitializationError: 'B' class unprocessed.
        Please call process_vars() in class definition.

    The idea of Excluded parameters is to store large temporary
    calculations for inspection.  These should never be used within
    the class, and production code should function without these
    objects.  They are intended for debugging, or for presenting users
    with intermediate results.  Final results should be returned as
    different persistent structures.

    >>> class B(A):
    ...     _state_vars = [('LargeObject', Excluded)]
    ...     process_vars()
    >>> b = B(x=2)
    >>> print b
    x=2
    y=100
    >>> b.LargeObject = 'Elephant'
    >>> b
    B(x=2)
    >>> print b
    x=2
    y=100
    Excluded:
    LargeObject=Elephant

    The :meth:`__init__` method should do any lengthy calculations.

    >>> class C(StateVars):
    ...     _state_vars = ['x', 'y',
    ...                    ('x2', Computed),
    ...                    ('y2', Computed),
    ...                    ('z', 0),
    ...                    ('t', 0),
    ...                    ('e', Excluded(0))]
    ...     _nodeps = ['z']
    ...     process_vars()
    ...     def __init__(self, **kwargs):
    ...         print "Initializing"
    ...         if 'x' in kwargs:
    ...             print "Calculating x^2"
    ...             self.x2 = self.x**2
    ...         if 'y' in kwargs:
    ...             print "Calculating y^2"
    ...             self.y2 = self.y**2
    >>> c = C(x=1, y=2)
    Initializing
    Calculating x^2
    Calculating y^2
    >>> print c
    x=1
    y=2
    z=0
    t=0
    Computed:
    x2=1
    y2=4
    Excluded:
    e=0

    Note that :meth:`__init__` is also responsible for recomputing
    values if the inputs change.  If the calculations are tedious,
    then a controlled computation like that shown should be used to
    reduce the work.

    .. note:: This recomputing only works for attributes that are
       assigned, i.e. iff :meth:`__setattr__` is called.  If an
       attribute is mutated, then :meth:`__getattr__` is called and
       there is no (efficient) way to determine if it was mutated.

       (Future versions might consider tagging all "accessed"
       attributes, however, in order to determine if a mutable object
       was changed, one would need to store a copy, which could
       provide a bad performance hit).

    >>> c.x = 3
    Initializing
    Calculating x^2
    >>> print c
    x=3
    y=2
    z=0
    t=0
    Computed:
    x2=9
    y2=4
    Excluded:
    e=0
    >>> c.t = 6
    Initializing
    >>> c.z = 7
    >>> c.e = 9
    
    Note that :meth:`__init__` was not called when `z` was assigned
    because it is included in the :attr:`_nodeps` list or when `e`
    was assigned because it is :class:`Excluded`.  Calls to
    :meth:`__init__` can be deferred by using :meth:`suspend` and
    :meth:`resume`:

    >>> c.suspend()
    >>> c.x = 4
    >>> c.y = 6
    >>> c.resume()
    Initializing
    Calculating x^2
    Calculating y^2
    >>> print c
    x=4
    y=6
    z=7
    t=6
    Computed:
    x2=16
    y2=36
    Excluded:
    e=9

    Note, you may use properties.  If these are not included in
    :attr:`_state_vars`, then these will be added to
    `_state_vars` by :func:`process_vars` either as un-stored
    :class:`Computed` attributes or as :attr:`_settable_properties`.
    Neither will be archived or returned by :meth:`items`.

    >>> class E1(StateVars):
    ...     _state_vars = ['y']
    ...     process_vars()
    ...     @property
    ...     def x(self):
    ...         '''Another name for 2*y'''
    ...         print "Getting x=2*y"
    ...         return 2*self.y
    >>> a = E1(y=2) # x is not set but getattr is called by hasattr...
    Getting x=2*y
    >>> a           # x is not set but getattr is called by hasattr...
    Getting x=2*y
    E1(y=2)
    >>> a.x = 6
    Traceback (most recent call last):
       ...
    AttributeError: Cannot set attribute 'x' of object 'E1'

    Here is an example where the property is settable (but still will
    not be archived.)

    >>> class E2(StateVars):
    ...     _state_vars = ['y']
    ...     process_vars()
    ...     def set_x(self, x):
    ...         '''Another name for `2*y`'''
    ...         self.y = x/2
    ...         print "Setting x=2*y"
    ...     def get_x(self):
    ...         print "Getting x=2*y"
    ...         return 2*self.y
    ...     x = property(get_x, set_x)
    >>> a = E2(y=2)
    >>> a
    E2(y=2)
    >>> a.x = 6
    Setting x=2*y
    >>> print a
    y=3.0

    If you want the property to represent stored data, you must
    explicitly include it in :attr:`_state_vars` and suppress the name
    clash warning:
    
    >>> class F(StateVars):
    ...     _ignore_name_clash = set(['x'])
    ...     _state_vars = ['y', 'x']
    ...     process_vars()
    ...     def set_x(self, x):
    ...         '''A stored property'''
    ...         self.__dict__['x'] = x
    ...         print "Setting x"
    ...     def get_x(self):
    ...         print "Getting x"
    ...         return self.__dict__['x']
    ...     x = property(get_x, set_x)
    >>> a = F(y=2)
    Getting x
    >>> a  # Even though x is not set, getattr is called by hasattr...
    Getting x
    F(y=2)
    >>> a.x = 5
    Setting x
    >>> print a
    Getting x
    Getting x
    y=2
    x=5

    If no setter is defined, the property will be included as a
    :class:`Computed` value.

    .. note:: Again, there are some extra Getting calls as
       :func:`hasattr` is called to check if the attribute exists.

    >>> class F(StateVars):
    ...     _ignore_name_clash = set(['y'])
    ...     _state_vars = [
    ...         ('y', 5, 'This property has a default and is stored')]
    ...     process_vars()
    ...     @property
    ...     def x(self):
    ...         '''property `x=2*y`'''
    ...         print "Getting x"
    ...         return self.y*2
    ...     def set_y(self, y):
    ...         self.__dict__['y'] = y
    ...         print "Setting y"
    ...     def get_y(self):
    ...         print "Getting y"
    ...         return self.__dict__['y']
    ...     y = property(get_y, set_y)
    >>> a = F()     # x is not set but getattr is called by hasattr...
    Getting y
    Setting y
    Getting y
    Getting x
    Getting y
    >>> a
    Getting y
    Getting x
    Getting y
    Getting y
    Getting y
    Getting y
    F()
    >>> print a
    Getting y
    Getting y
    Getting x
    Getting y
    Getting x
    Getting y
    y=5
    Computed:
    x=10

    Class variables may also be specified.  This provides a way of
    documenting and requiring class-specific variables.  These
    variables are not archived or printed, but are documented in the
    class.  They act as "class constants".

    >>> class F(StateVars):
    ...     _state_vars = [('A', ClassVar(Required), "Required 'class' var"),
    ...                    ('B', ClassVar(1), "Optional class var"),
    ...                    ('a', 2, "Regular parameter")]
    ...     process_vars()
    >>> help(F)             #doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    Help on class F...
    <BLANKLINE>
    class F(StateVars)
     |  Usage: F(a=2)
     |
     |  **Class Variables:**
     |      A: Required 'class' var
     |      B: Optional class var
     |  
     |  **State Variables:**
     |      a: Regular parameter
     |  
     |  Method resolution order:
    ...
     |  Data and other attributes defined here:
     |  
     |  A = Required
    ...
     |
     |  B = 1
    ...
    >>> print F.__doc__
    Usage: F(a=2)
    <BLANKLINE>
    Attributes
    ----------
    **Class Variables:**
        A: Required 'class' var
        B: Optional class var
    <BLANKLINE>
    **State Variables:**
        a: Regular parameter
    >>> f = F()
    Traceback (most recent call last):
        ...
    AttributeError: Required class variable 'A' not initialized in class 'F'
    >>> class G(F):
    ...     _ignore_name_clash = set(['A', 'B'])
    ...     _state_vars = [('A', ClassVar(2), 'No longer required'),
    ...                    ('B', ClassVar(2))]
    ...     process_vars()
    >>> print G.__doc__
    Usage: G(a=2)
    <BLANKLINE>    
    Attributes
    ----------
    <BLANKLINE>
    **Class Variables:**
        A: No longer required
        B: Optional class var
    <BLANKLINE>
    **State Variables:**
        a: Regular parameter
    >>> g = G()
    >>> g
    G()
    >>> print g
    a=2
    >>> g.A, g.B
    (2, 2)

    If a class variable is specified, it may later be replaced by an
    instance variable through inheritance.  Again, be sure to ignore
    the name clash warning if this is deliberate.

    >>> class H(F):
    ...     _ignore_name_clash = set(['A'])
    ...     _state_vars = [('A', Required)]
    ...     process_vars()
    >>> print H.__doc__
    Usage: H(A=Required, a=2)
    <BLANKLINE>
    Attributes
    ----------
    <BLANKLINE>    
    **Class Variables:**
        B: Optional class var
    <BLANKLINE>
    **State Variables:**
        A: Required 'class' var
        a: Regular parameter
    >>> H(a=2)
    Traceback (most recent call last):
        ...
    ValueError: Required attribute 'A' not defined.

    You may delegate variables to a member variable.  By default
    delegation will allow arguments for the delegate to be passed to
    the delegate from the main object.  First we create two classes
    `A` and `B` that we will use as delegates, then a class `C` that
    delegates to these.  For class `A` will delegate all attributes
    from the class directly using the :class:`Delegate` specifier with
    the class as an argument.  This will specify that the object
    should have an instance `a` constructed from parameters passed
    directly to `C`.  These will all be mirrored with parameters in
    `C` that dispatch directly to the instance `a`.

    >>> class A(StateVars):
    ...     _state_vars = [('x', 1, 'var x')]
    ...     process_vars()

    >>> class B(StateVars):
    ...     _state_vars = [('t', 1, 'var t'),
    ...                    ('z', 2, 'var z')]
    ...     process_vars()

    >>> class C(StateVars):
    ...     _state_vars = [
    ...         ('a', Delegate(A)), # This will be constructed by __new__
    ...         ('b', B()),         # Previously constructed object
    ...         ('y=a.x', 10),      # Ref called y to a.x with new default
    ...         ('b.z', 3)]         # Change of value upon construction.
    ...     process_vars()

    >>> c = C()
    >>> c.a
    A(x=10)
    >>> c.b
    B(z=3)

    An example of delegating a required variable:

    >>> class A(StateVars):
    ...     _state_vars = [('x=b.x', Required),
    ...                    ('b', Container())]
    ...     process_vars()
    >>> a = A(x=[]); a
    A(b=Container(x=[]))
    >>> a.x.append(3); a
    A(b=Container(x=[3]))

    Note how reassignment works:
        
    >>> A(x=[4], b=Container(x=[3]))    
    A(b=Container(x=[4]))

    .. note:: This is not a good idea!  Please ignore... It is
       possible, but fraught with danger (it will break `repr` for
       example!)

       This is best resolved by either making the references
       :class:`Computed` attributes (read-only) or excluding the
       referenced object and making it private.
        
    >>> class A(StateVars):
    ...     _state_vars = [('x=_b.x', Required),
    ...                    ('_b', Excluded(Container()))]
    ...     process_vars()
    >>> A(x=[])                         # doctest: +SKIP
    A(x=[])

    .. todo:: Think about this.  This is not a good solution!  Perhaps one
       should allow delegate objects that are hidden so that the class
       controls them properly with construction etc.

    Delegation also ensures that a new copy of the object will be
    initialized upon copy construction rather than just linked.

    >>> class A(StateVars):
    ...     pass
    >>> class B(StateVars):
    ...     _state_vars = [('a', Delegate(A))]
    ...     process_vars()
    >>> b1 = B()
    >>> b2 = B(b1)
    >>> id(b1.a) == id(b2.a)
    False

    In order to avoid copy construction from copying objects, they
    should have the value NotImplemented:

    >>> class A(StateVars):
    ...     _state_vars = [('c', 1)]
    ...     process_vars()
    >>> a = A()
    >>> a.c = None
    >>> b = A(a)
    >>> print b.c
    None
    >>> a.c = NotImplemented
    >>> b = A(a)
    >>> b.c                             # doctest: +SKIP
    1

    Note that the value here is the default: the NotImplemented value
    of `a.c` is ignored.

    When inheriting from classes that define :meth:`__init__`, one must make
    sure that the base class versions are called, either by setting
    :attr:`_call_base__init__` or explicitly.  (Note that
    :class:`StateVars` only has a dummy :meth:`__init__` method, so if you
    only inherit from this class, or from descendants that do not
    redefine :meth:`__init__`, then you may omit this call, but it is
    considered bad form.)

    >>> class A(StateVars):
    ...     _state_vars = [
    ...         ('a', Required),
    ...         ('c_a', Computed)]
    ...     process_vars()
    ...     def __init__(self, *v, **kw):
    ...         print('Computing c_a...')
    ...         self.c_a = self.a*2
    >>> class B_bad(A):
    ...     _state_vars = [
    ...         ('c_b', Computed)]
    ...     process_vars()
    ...     def __init__(self, *v, **kw):
    ...         print('Computing c_b...')
    ...         self.c_b = self.a*3
    >>> a = A(a=1)
    Computing c_a...
    >>> b = B_bad(a=1)           # This fails to call base constructor
    Computing c_b...
    >>> b.c_a
    Traceback (most recent call last):
        ...
    AttributeError: 'B_bad' object has no attribute 'c_a'


    Here are two correct ways:

    >>> class B1(A):
    ...     _state_vars = [
    ...         ('c_b', Computed)]
    ...     process_vars()
    ...     def __init__(self, *v, **kw):
    ...         A.__init__(self, *v, **kw)
    ...         print('Computing c_b...')
    ...         self.c_b = self.a*3

    >>> class B2(A):
    ...     _state_vars = [
    ...         ('c_b', Computed)]
    ...     _call_base__init__ = True
    ...     process_vars()
    ...     def __init__(self, *v, **kw):
    ...         print('Computing c_b...')
    ...         self.c_b = self.a*3

    >>> b = B1(a=1)
    Computing c_a...
    Computing c_b...
    >>> b.c_a, b.c_b
    (2, 3)
    >>> b = B2(a=1)
    Computing c_a...
    Computing c_b...
    >>> b.c_a, b.c_b
    (2, 3)
    """
    _state_vars = []
    _nodeps = []
    _vars = []
    _defaults = {}
    _computed_vars = {}
    _class_vars = set([])
    _excluded_vars = set([])
    _dynamic = False
    _refs = {}
    _irefs = {}
    _delegates = {}
    _settable_properties = set()
    _call_base__init__ = False
    
    def __new__(cls, *varargin, **kwargs):
        r"""Constructor: this processes kwargs for all of the
        "automatic" state var initialization.  This should generally
        not be overloaded, or overoaded with extreme caution.

        Note that if `varargin` has one item with the :meth:`items
        method, then :meth:`__new__` copy constructs from this object.
        This allows the user to use the idiom `Class(obj)` to return a
        copy, however, this performs all initializations.  For a
        simple copy use :meth:`__copy__` or :meth:`__deepcopy__`.

        If `varargin` has one item that is a list, and there are no
        `kwargs`, then the list is assumed to come from a call to one
        of the copiers and a direct copy is made without a call to
        :meth:`__init__` (suppressed by setting :attr:`_no_init`).
        
        If the behaviour must be altered, the methods
        :meth:`_pre_hook__new__` and :meth:`_post_hook__new__` may be
        used.  These are called within the initialization look.  This
        should only be done as a last resort because it will break the
        semantics of the StateVar class making your code hard to read.
        
        Parameters
        ----------
        self : instance
           If `self` is not `None`, then it is treated as an allocated
           instance.  This allows one to construct subclasses of
           builtin types for example.

        .. todo:: Think about whether or not copiers should be applied
           when doing copy construction if they are explicitly
           specified.

        Notes
        -----
        One non-keyword argument is allowed and signifies copy
        construction.  If there are no more `kwargs` and the object
        has the same type as `cls`, then no initialization is needed
        as signified by :attr:`_no_init` (which is check by :meth:`__init__`). 
        """
        # pass, pylint: disable-msg=W0212
        if 1 == len(varargin):
            # Copy construction.
            arg = varargin[0]
            args = {}
            if isinstance(arg, cls):
                self = arg.__copy__()
                if kwargs:
                    for k in kwargs:
                        setattr(self, k, kwargs[k])
                else:
                    self.__dict__['_no_init'] = True
            elif isinstance(arg, list):
                # Short circuit copy construct from copiers.  It is
                # assumed that the items of the list have been
                # properly copied by one of the copiers.  In this
                # case, __init__ is not called.
                self = Archivable.__new__(cls)
                self.__dict__.update(**dict(arg))
                self.__dict__['_no_init'] = True
            elif hasattr(arg, 'all_items'):
                # This is a full initialization from an object with
                # items, but that is of a different type so
                # initialization and conversion may be required.
                args = dict(arg.all_items())
            elif hasattr(arg, 'items'):
                args = dict(arg.items())
            else:
                raise ValueError("Invalid argument to StateVars: First "+
                                 "argument must be another instance.")
            if args:
                for k in args:
                    if k in cls._delegates:
                        args[k] = copy.copy(args[k])
                args.update(kwargs)
                self = cls.__new__(cls, **args)
            return self
            
        _default_hiding_warning_message = (
            "Attribute %r=%r hidden by default %r in class %r\n" + 
            " - Hiding a ClassVar with an instance var?\n" +
            " - Providing a new default outside of _state_vars?")
        if not _vars_processed(cls):
            raise InitializationError("\n".join([
                        "%r class unprocessed."%cls.__name__,
                        "    Please call process_vars()"
                        " in class definition."]))

        # Check for undefined class variables
        for var in cls._class_vars:
            if getattr(cls, var, NotImplemented) is Required:
                raise AttributeError("Required class variable %r "
                                     "not initialized in class %r"
                                     %(var, cls.__name__))

        if 'self' in kwargs:
            self = kwargs.pop('self')
        else:
            self = Archivable.__new__(cls)

        init_flag = _start_initializing(self)
        try:
            self.__dict__['_constructing'] = True

            if hasattr(self, '_pre_hook__new__'):
                self._pre_hook__new__(varargin, kwargs)

            required_keys = []
            # accumulate the proper defaults and user provided
            # assignments in this dictionary.  Since references
            # (esp. to delegated objects) end up as assignments, we
            # keep track of user-assigned values as well since these
            # should always 
            assignments = {}
            kwargs_ = set()
            def assign(key, value, default=False):
                """Add `(key, value)` to assignments.  If `default` is
                `False`, then raise and error if the value is
                already present, otherwise, only add if it is not
                present."""
                key_ = self._refs.get(key, key)
                if key_ not in assignments:
                    assignments[key_] = value
                elif not default:   # pragma: no cover
                    raise TypeError(("Duplicate assignment " +
                                     "for %r: %r already " + 
                                     "assigned") % (key_, key))

            # Process defaults and assignments
            for (key, default, _doc) in self._state_vars:
                copier = self._default_copy
                if key in kwargs:
                    assign(key, kwargs.pop(key))
                    kwargs_.add(key)
                else:
                    if isinstance(default, NoCopy):
                        # Allow for processing of NoCopy(Required)
                        # etc. by redefining default
                        copier = default.copy
                        default = default.value
                    if (default is NotImplemented or
                        key in cls._class_vars or 
                        key not in cls._defaults):
                        pass
                    elif default is Required:
                        required_keys.append(key)
                    else:
                        try:
                            # This catch-all is to allow for data
                            # descriptors that might fail with an
                            # arbitrary error (such as a KeyError
                            # instead of an AttributeError) if the
                            # default has not been assigned.
                            original_default = getattr(self, key)
                        except:
                            original_default = NotImplemented
                        if (original_default is not NotImplemented
                            and (original_default is not
                                 cls._defaults[key])
                            and key not in getattr(
                                cls, '_ignore_name_clash', set())):
                            # Warn about hiding a default value.
                            warnings.warn(NameClashWarning1(
                                _default_hiding_warning_message%(
                                    key,
                                    repr(original_default),
                                    cls._defaults[key],
                                    cls.__name__)))
                        value = copier(cls._defaults[key])
                        assign(key, value, default=True)

            # Now accumulate delegate defaults
            delegates = {}
            for var in cls._delegates:
                delegate_class = cls._delegates[var]
                kw_ = dict([(v.split('.')[1], assignments.pop(v))
                           for v in assignments.keys()
                           if 1 == v.count('.')
                           and var == v.split('.')[0]])
                delegates[var] = (delegate_class, kw_)

            # Construct delegates
            for var in delegates:
                delegate_class, kw_ = delegates[var]
                if var in assignments:
                    # Use passed in value:
                    delegate = assignments.pop(var)
                    if var in kwargs_:
                        # If the default was provided by the user,
                        # this should have precedence, so only update
                        # those keys the user also provided
                        for k in kw_:
                            if k in kwargs_:
                                setattr(delegate, k, kw_[k])
                    else:
                        # Delegate comes from a default, so update all
                        # arguments.
                        for k in kw_:
                            setattr(delegate, k, kw_[k])
                else:
                    # Construct
                    delegate = delegate_class(**kw_)
                setattr(self, var, delegate)

            # Now make the rest of the assignments.  First the
            # direct assignments, then the indirect 
            for var in [v for v in assignments if '.' not in v]:
                setattr(self, var, assignments[var])
            for var in [v for v in assignments if '.' in v]:
                tmp = [self] + var.split('.')
                setattr(reduce(getattr, tmp[:-1]),
                        tmp[-1], 
                        assignments[var])

            if self._dynamic:
                # Dynamically initialize from the rest of the
                # kwargs
                _vars = [k for k in kwargs if k != '_dynamic']
                for k in _vars:
                    setattr(self, k, kwargs[k])
                    
                if '_dynamic' in kwargs:
                    # Now set it and add _vars to the object if False
                    self._dynamic = kwargs['_dynamic']
                    
                    if not self._dynamic:
                        # No more assignments are allowed, so we must
                        # add these variables to _vars in the
                        # instance.
                        self.__dict__['_vars'] = _vars
                        
            elif len(kwargs) == 1:
                # Unused keyword argument!
                raise TypeError(
                    "%s is an invalid keyword argument for %s."%\
                        (str(kwargs.keys()[0]), self.__class__))
            elif len(kwargs) > 1:
                # Unused keyword arguments!
                raise TypeError(
                    "%s are invalid keyword arguments for %s."%\
                        (str(kwargs.keys()), self.__class__))

            for key in required_keys:
                if (getattr(self, key, Required) is Required and
                    not inspect.isdatadescriptor(
                        getattr(self.__class__, key, None))):
                    raise ValueError(
                        "Required attribute '%s' not defined." % (key,))

            if hasattr(self, '_post_hook__new__'):
                self._post_hook__new__(*varargin, **kwargs)
        except:
            raise
        finally:
            _finish_initializing(self, init_flag)
        return self

    def _pre_hook__new__(self, varargin, kwargs):
        """This is called prior to processing by :meth:`__new__`.  The
        `varargin` and `kwargs` arguments are passed as a list and
        dictionary so that they may be modified if needed to alter the
        behaviour of the class.  Note that these modifications will
        only affect the call to :meth:`__new__` and not the subsequent
        call to :meth:`__init__` (which is generated by the metaclass)."""

    def _post_hook__new__(self, *varargin, **kwargs):
        """This is called after the default processing by
        :meth:`__new__`."""

    def __init__(self, *varargin, **kwargs): # pylint: disable-msg=W0231
        r"""This is the initialization routine.  It is called *after*
        the attributes specified in :attr:`_state_vars` have been
        assigned.

        The user version should perform any after-assignment
        initializations that need to be performed.

        .. note:: Since all of the initial arguments are listed in
           `kwargs`, this can be used as a list of attributes that
           have "changed" allowing the initialization to be
           streamlined. The default :meth:`__setattr__` method will
           call :meth:`__init__` with the changed attribute to allow
           for recalculation.

           This recomputing only works for attributes that are
           assigned, i.e. iff :meth:`__setattr__` is called.  If an
           attribute is mutated, then :meth:`__getattr__` is called
           and there is no (efficient) way to determine if it was
           mutated.
           
        :class:`Computed` values with `True` :attr:`Computed.save`
        will be passed in through `kwargs` when objects are restored
        from an archive.  These parameters in general need not be
        recomputed, but this opens the possibility for an inconsistent
        state upon construction if a user inadvertently provides these
        parameters.  Note that the parameters still cannot be set
        directly.
       
        See :ref:`init_semantics` for details.
        """
        if (1 == len(varargin) and not kwargs):
            # Called as a copy constructor.  State has been copied from
            # other by __new__.  You do not need to copy the
            # attributes here, but may need to copy calculated
            # parameters.  If kwargs is not empty, then additional
            # values have been specified and need to be processed, so
            # we exclude that case here
            _other = varargin[0]

        elif 1 < len(varargin):
            # Another argument passed without kw.  Error here.
            raise ValueError(
                "StateVars accepts only keyword arguments.")
        else:
            # Process the changed variables as specified in kwargs
            pass

    def suspend(self):
        r"""Suspend calls to :meth:`__init__` from
        :meth:`__setattr__`, but keep track of the changes."""
        self.__dict__['_old_values'] = dict((var, getattr(self, var))
                                            for var in self._vars
                                            if hasattr(self, var))
        self.__dict__['_changes'] = {}

    def resume(self):
        r"""Resume calls to :meth:`__init__` from :meth:`__setattr__`,
        first calling :meth:`__init__` with all the cached changes."""
        kwargs = dict((key, self._changes[key]) 
                      for key in self._changes
                      if not isequal(getattr(self, key),
                                     self._old_values.get(key)))
        self.__init__(**kwargs)
        del self.__dict__['_changes']
        del self.__dict__['_old_values']

    def __iter__(self):
        r"""Return an iterator over the attributes."""
        keys = [key for key in self._vars
                if (hasattr(self, key)
                    and key not in self._excluded_vars
                    and key not in self._computed_vars
                    and key not in self._class_vars
                    and key not in self._refs)]
        keys += [key for key in self.__dict__
                 if (key not in self._vars
                     and key not in self._excluded_vars
                     and key not in self._computed_vars
                     and key not in self._class_vars
                     and key not in self._refs
                     and key[0] != '_')]
        
        for k in keys:
            yield k
        
    def items(self, archive=False):     # pylint: disable-msg=W0221
        r"""Return a list `[(name, obj)]` of `(name, object)` pairs where the
        instance can be constructed as `ClassName(name1=obj1,
        name2=obj2, ...)`.

        Parameters
        ----------
        archive : False, True, optional
           If provided, then include :class:`Computed` objects if they have
           their :attr:`Computed.save` flag is `True`.
        """
        res = [(key, getattr(self, key)) for key in self]
        if archive:
            res.extend([(key, getattr(self, key))
                        for key in self._computed_vars
                        if self._computed_vars[key]])
        return res
    
    def all_items(self):
        r"""Return a list `[(name, obj)]` of `(name, object)` pairs
        containing all items available.  This will include computed
        vars, reference, etc. and will likely be redundant.

        See Also
        --------
        :meth:`items`
        """
        return [(key, getattr(self, key)) for key in self._vars
                if hasattr(self, key)]

    def initialize(self, **kwargs):
        r"""Calls :meth:`__init__` passing all assigned attributes.
        This should not typically be needed as the use of suspend and
        resume should function appropriately.  This can be used to set
        a bunch of parameters, however.

        Parameters
        ----------
        <name> : value
           Set the parameter `name` to `value` through the keyword
           argument mechanism.  If no parameters are provided, all
           variables returned by :meth:`items` will be reassigned.

        Examples
        --------
        >>> class A(StateVars):
        ...     _state_vars = ['a', ('x', Computed)]
        ...     process_vars()
        ...     def __init__(self, a=None):
        ...         if a is None:
        ...             print "Initializing: a not changed."
        ...         else:
        ...             print "Initializing: a changed."
        ...             self.x = 2*a
        >>> a = A(a=1); a.x
        Initializing: a changed.
        2
        >>> a.a = 2; a.x
        Initializing: a changed.
        4
        >>> a.suspend()
        >>> a.a = 3
        >>> a.resume(); a.x
        Initializing: a changed.
        6
        >>> a.initialize();
        Initializing: a not changed.
        >>> a.initialize(a=8); a.x
        Initializing: a changed.
        16
        """
        self.suspend()
        if not kwargs:
            kwargs = dict(self.items())
        for key in kwargs:
            setattr(self, key, kwargs[key])
        self.resume()

    @property
    def _settable_vars(self):
        r"""Return the set of settable attributes.

        Computable attributes (in self._computed_vars) are only
          settable if self._initializing.
        Attributes not in self.__dict__, self._vars, or
          self._excluded_vars are only settable if self._dynamic.
        """
        settable_vars = set(self._vars)
        settable_vars.update(self._settable_properties)
        settable_vars.difference_update(self._class_vars)

        if not self._initializing:
            settable_vars.difference_update(self._computed_vars.keys())

        if self._dynamic:
            settable_vars.update(set(self.__dict__.keys()))

        return settable_vars

    def __getattr__(self, name):
        if '.' in name:
            return reduce(getattr, [self] + name.split('.'))

        try:
            return reduce(getattr, [self] + self._refs[name].split('.'))
        except:
            raise AttributeError("%r object has no attribute %r" %
                                 (self.__class__.__name__, name))

        
    def __setattr__(self, name, value):
        r"""Set the attribute name to value and call :meth:`__init__`.

        Only attributes in self._settable_vars will be set, attempts
        to set others will raise an :exc:`AttributeError`.

        If not `self._initializing`, then after any attribute in
        `self._vars` is set, `__init__(name=value)` is called to
        allow the object to reinitialize.
        """
        try:
            if name in self._refs or name in self._settable_vars:
                if name in self._refs:
                    if self._refs[name] in self._computed_vars:
                        raise AttributeError("Cannot set Computed references")
                    setattr(self, self._refs[name], value)
                else:
                    object.__setattr__(self, name, value)

                if (hasattr(self, '_nodeps')
                    and name in self._nodeps
                    or name in self._excluded_vars):
                    # Don't invoke initialization.
                    pass
                elif hasattr(self, '_changes'):
                    # Object is caching changes for future initialization
                    self._changes[name] = value
                elif not self._initializing:
                    # Otherwise, reinitialize now
                    self.__init__(**{name:value})
            elif '.' in name:
                names = name.split('.')
                setattr(reduce(getattr, [self] + names[:-1]),
                        names[-1],
                        value)
            else:
                descriptor = getattr(type(self), name, None)
                if inspect.isdatadescriptor(descriptor):
                    descriptor.__set__(self, value)
                elif self._dynamic:
                    self.__dict__[name] = value
                else:
                    raise AttributeError
        except AttributeError, err:
            msg = "Cannot set attribute %r of object %r" % (
                name, self.__class__.__name__)
            err.args = tuple([msg] + list(err.args[1:]))
            raise
        except Exception:               # pragma: no cover
            raise

    def _isdefault(self, name):
        r"""Return True if attribute name is the same as the
        default."""
        return ((not hasattr(self, name)
                 and self._defaults[name] is NotImplemented) or
                (hasattr(self, name)
                 and name in self._defaults
                 and isequal(getattr(self, name), self._defaults[name])))

    def _changed_vars(self):
        r"""Return a list of attributes that differ from the default
        values."""
        return [var for var in self if not self._isdefault(var)]

    @property
    def _all_vars(self):
        r"""List of all variables in order except for temporaries
        starting with an underscore."""
        vars_ = list(self._vars)
        vars_.extend([p for p in self._settable_properties
                      if p in self._computed_vars and p not in vars_])
        if self._dynamic:
            vars_ += [key for key in self.__dict__
                     if (key not in vars_ and
                         key[0] != '_')]
        return vars_

    def __repr__(self):
        r"""Return a string representation of the object.  The items
        argument may be used to override self.items()"""
        keyvals = ["%s=%r" % (var, getattr(self, var))
                   for var in self._changed_vars()]
        return "%s(%s)" % (self.__class__.__name__, ", ".join(keyvals))
    
    def __str__(self):
        r"""Pretty print state, including excluded variables.  Print order is
        sorted."""

        all_vars = self._all_vars
        vars_ = [(k, getattr(self, k)) for k in all_vars
                if (hasattr(self, k) and
                    k not in self._excluded_vars and
                    k not in self._computed_vars and
                    k not in self._class_vars)]
        excluded = [(k, getattr(self, k)) for k in all_vars
                     if (k in self._excluded_vars and 
                         hasattr(self, k))]
        computed = [(k, getattr(self, k, NotImplemented))
                    for k in all_vars
                    if k in self._computed_vars]
        
        res = "\n".join(["%s=%s"%(k, v) 
                         for (k, v) in vars_])

        if 0 < len(computed):
            res = "\n".join([res,
                             'Computed:']
                            +["%s=%s"%(k, str(v))
                              for (k, v) in computed])
            
        if 0 < len(excluded):
            res = "\n".join([res,
                             'Excluded:']
                            +["%s=%s"%(k, str(v))
                              for (k, v) in excluded])
        return res

    @classmethod
    def get_args(cls, *varargin, **kwargs):
        r"""Return the dictionary that is a subset of kwargs containing
        the valid keyword arguments for the current object.

        >>> class A(StateVars):
        ...     _state_vars = ['a', 'b']
        ...     process_vars()
        >>> class B(StateVars):
        ...     _state_vars = ['c', 'd']
        ...     process_vars()
        >>> def f(**kwargs):
        ...     a = A(A.get_args(kwargs))
        ...     b = B(B.get_args(kwargs))
        ...     return a, b
        >>> a, b = f(a=1, b=2, c=3, d=4)
        >>> a, b
        (A(a=1, b=2), B(c=3, d=4))

        >>> Container(Container.get_args(a=1, b=2))
        Container(a=1, b=2)
        """
        if 0 == len(varargin):
            pass
        elif 1 == len(varargin):
            dict_ = varargin[0]
            dict_.update(kwargs)
            kwargs = dict_
        else:
            raise ValueError("get_args takes one dictionary argument.")

        class_keys = cls.class_keys()
        if 0 == len(class_keys):
            # Variables determined dynamically, so all arguments
            # accepted.
            return kwargs
        else:
            return mmf.utils.get_args(kwargs, class_keys)

    @classmethod
    def getargspec(cls):
        r"""Get the names and default values of the constructor.

        A tuple of four things is returned: (args, varargs, varkw, defaults).
        'args' is a list of the argument names (it may contain nested lists).
        'varargs' and 'varkw' are the names of the * and ** arguments or None.
        'defaults' is an n-tuple of the default values of the last n arguments.

        >>> StateVars.getargspec()
        ([], None, None, ())
        >>> Container.getargspec()
        ([], None, 'kwargs', ())
        >>> class D(StateVars):
        ...     _state_vars = [('a', 0), ('b', Required), ('c', NotImplemented)]
        ...     process_vars()
        >>> D.getargspec()
        (['b', 'a', 'c'], None, None, (0, NotImplemented))
        """
        varargs = None

        required_args = [var for (var, default, _doc) in cls._state_vars
                         if default is Required]
        optional_args = [var for (var, default, _doc) in cls._state_vars
                         if default is not Required]
        defaults = tuple(default for (_var, default, _doc) in cls._state_vars
                         if default is not Required)
        args = required_args + optional_args
        if cls._dynamic:
            varkw = 'kwargs'
        else:
            varkw = None

        return (args, varargs, varkw, defaults)
        
    @classmethod
    def class_keys(cls):
        r"""Return the keys accepted by the constructor.

        >>> StateVars.class_keys()
        []
        >>> class A(StateVars):
        ...     _state_vars = ['a', 'b']
        ...     process_vars()
        >>> A.class_keys()
        ['a', 'b']
        """
        include = [var for (var, _default, _doc) in cls._state_vars]

        # Make include contain only one of each variable.
        include_set = set(include)
        include = [var for var in include 
                   if var in include_set
                   and not include_set.remove(var)]
        return include

    def __copy__(self):
        r"""Return a shallow copy.

        .. note:: Delegates will be copied with :func:`copy.copy`, not
           just referred to.
        """
        dict_ = self.__dict__
        items = [(k, dict_[k]) for k in dict_
                 if k not in self._delegates]
        items.extend([(k, copy.copy(dict_[k])) for k in dict_
                      if k in self._delegates])
        return self.__class__(items)

    def __deepcopy__(self, memo=None):
        r"""Provide copying facilites."""
        dict_ = self.__dict__
        items = [(k, copy.deepcopy(dict_[k], memo=memo)) for k in dict_]
        return self.__class__(items)

    def archive_1(self, env=None):
        r"""Return `(rep, args, imports)`.

        Same as :meth:`Archivable.archive_1` except passes
        `archive=True` to :meth:`items`.
        """
        args = self.items(archive=True)
        module = self.__class__.__module__
        name = self.__class__.__name__
        imports = [(module, name, name)]

        keyvals = ["=".join((k, k)) for (k, _v) in args]
        rep = "%s(%s)" % (name, ", ".join(keyvals))
        return (rep, args, imports)

class Container(StateVars):
    r"""Simple container class.  This is just a StateVars class with
    allowed dynamic allocation.

    Examples
    --------
    >>> a = Container(a=1, b=2)
    >>> print a
    a=1
    b=2
    >>> a.z = 4
    >>> print a
    a=1
    b=2
    z=4

    We also include an update method that updates the dictionary

    >>> a.update(Container(b=3, c=4))
    >>> print a
    a=1
    c=4
    b=3
    z=4

    If you specify `_dynamic` in the constructor, then the Container
    will no longer accept new variable definitions:

    >>> c = Container(a=1, b=2, _dynamic=False)
    >>> print c
    a=1
    b=2
    >>> c.z = 4
    Traceback (most recent call last):
        ...
    AttributeError: Cannot set attribute 'z' of object 'Container'
    """
    _dynamic = True
    def update(self, container):
        r"""Update the items from container."""
        for (key, value) in container.items():
            setattr(self, key, value)
    
'''        
class CopyConstruct(object):
    r"""Provides dispatching to allow for copy construction through the
    following methods:
    _copy() : Copy from another instance (Default is to copy __dict__)
    _initialize() : Initialize from multiple arguments.

    It also provides copy services and str and repr services.

    >> class A(CopyConstruct):
    ...     def _copy(self, obj):
    ...         print "Copying"
    ...         CopyConstruct._copy(self, obj)
    ...     def _init(self, **kwargs):
    ...         print "Initializing"
    ...         CopyConstruct._init(self, **kwargs)
    >> a = A(x=1, y=2)
    Initializing
    >> a
    A(y=2, x=1)
    >> b = A(a)
    Copying
    Initializing
    >> print b
    y=2
    x=1
    >> c = copy(b)
    Copying
    Initializing
    >> c
    A(y=2, x=1)
    """
    def __init__(self, *varargin, **kwargs):
        r"""Provides default initialization dispatch.
        Define initialization behaviour through
        _copy() and _init().
        _init() is always called.
        """
        if 1 == len(varargin):
            self._copy(varargin[0])
            varargin = varargin[1:]
        self._init(*varargin, **kwargs)
    def _copy(self, obj):
        r"""Default copy constructor: copies __dict__.  Does not call _init()."""
        self.__dict__.update(obj.__dict__)
    def _init(self, **kwargs):
        r"""Default initialization: assigns kwargs to __dict__."""
        self.__dict__.update(kwargs)
    def __copy__(self):
        r"""Return a copy."""
        return self.__class__(self)
    def __repr__(self):
        r"""Return a string representation of the object.  The items
        argument may be used to override self.items()"""
        keyvals = ["=".join((k, repr(v))) 
                   for (k, v) in self.items()]
        return "%s(%s)"%(self.__class__.__name__, ", ".join(keyvals))
    def __str__(self):
        r"""Return a pretty string representation of the objects state.  The
        items argument may be used to override self.items()

        Known bug: If there is nesting, then the format does not look
        good because __str__ provides no way of passing indenting
        information.
        """
        keyvals = ["=".join((k, str(v))) 
                   for (k, v) in self.items()]
        return "\n".join(keyvals)
    def items(self):
        r"""Return a list of `(key, value)` pairs representing the state
        of the object.  This is used by str and repr."""
        return self.__dict__.items()

class StateVarMetaclass(type):
    r"""Metaclass for the generation of classes with inherited state
    variable information.  The class variables :attr:`_state_vars` is used to
    define state variables documentation. Valid forms are:
    1) List of:
       name (no documentation or defaults)
       (name, default) (no documentation)
       (name, default, doc)
    2) Dictionary of name:default (no documentation) or
       (name, documentation):default.

    If :attr:`_state_vars` is not defined, then it is left undefined.  In this
    case, values of __dict__ should be considered to be the state
    variables.  An additional list _excluded_vars may be defined to
    indicate that these are not considered state variables.
    (Variables starting with an underscore are implicitly excluded
    unless explicitly included in :attr:`_state_vars`)

    Both :attr:`_state_vars` and _excluded_vars include all inherited values.

    These will be processed along with all base classes to give the
    normal form [(name, default, doc)] where doc is <no description> if no
    documentation is provided and default is NotImplemented if no
    default is provided.
    """
    def __init__(cls, name, bases, dict_):
        r"""
        >>> class Complex(object):
        ...     "Complex numbers"
        ...     __metaclass__ = StateVarMetaclass
        ...     _state_vars = [('x', 0.0, "Real part"),
        ...                    ('y', 0.0, "Imaginary part")]
        >>> class Quaternion(Complex):
        ...     "Quaternions"
        ...     _state_vars = dict(z=0.0, t=0.0)    
        >>> help(Complex)       #doctest: +ELLIPSIS
        Help on class Complex in module ...:
        <BLANKLINE>
        class Complex(__builtin__.object)
         |  Complex numbers
         |  
         |  Complex(x=0.0, y=0.0)
         |  
         |  **State Variables:**
         |      x: Real part
         |      y: Imaginary part
        ...
        >>> help(Quaternion)    #doctest: +ELLIPSIS
        Help on class Quaternion in module ...:
        <BLANKLINE>
        class Quaternion(Complex)
         |  Quaternions
         |  
         |  Quaternion(x=0.0, y=0.0, z=0.0, t=0.0)
         |  
         |  **State Variables:**
         |      x: Real part
         |      y: Imaginary part
         |      z: <no description>
         |      t: <no description>
        ...

        >>> class A(object):
        ...     __metaclass__ = StateVarMetaclass
        ...     _state_vars = ['a',
        ...                    ('b', 0.0),
        ...                    ('c', 1.0, "A variable"),
        ...                    ('big_var_a', Excluded)]
        >>> help(A)     #doctest: +ELLIPSIS
        Help on class A in module ...:
        <BLANKLINE>
        class A(__builtin__.object)
         |  A(a=, b=0.0, c=1.0)
         |  
         |  **State Variables:**
         |      a: <no description>
         |      b: <no description>
         |      c: A variable
        ...
        >>> class B(A):
        ...     _state_vars = {
        ...         ('d',
        ...          "A very long description that we break over lines
        ...          to see how it works"): 5,
        ...         ('e', 'A short description'): 7,
        ...         'big_var_a':Excluded)}
        >>> help(B)     #doctest: +ELLIPSIS
        Help on class B in module ...:
        <BLANKLINE>
        class B(A)
         |  B(a=, b=0.0, c=1.0, d=5, e=7)
         |  
         |  **State Variables:**
         |      a: <no description>
         |      b: <no description>
         |      c: A variable
         |      d: A very long description that we break over lines
         |           to see how it works
         |      e: A short description
        ...
        >>> B._excluded_vars
        set(['big_var_a', 'big_var_b'])
        """
        super(StateVarMetaclass, cls).__init__(name, bases, dict_)
        
        vars = None             # We do this to allow for no _state_vars
        exclude = None
        defaults = {}
        docs = {}
        if hasattr(cls, '_state_vars'):
            if vars is None:
                vars = []
            _state_vars = cls._state_vars
            if isinstance(_state_vars, list):
                for l in _state_vars:
                    default = NotImplemented
                    doc = _NO_DESCRIPTION
                    if isinstance(l, str):
                        var = l
                    elif isinstance(l, tuple):
                        var = l[0]
                        try:
                            default = l[1]
                            doc = l[2]
                        except IndexError:
                            pass
                    else:
                        raise TypeError(
                            '_state_vars must be a list of strings or tuples')
                    if not isinstance(var, str):
                        raise TypeError('Name must be a string (got %s)'%\
                                        repr(var))
                    if var not in vars:
                        vars.append(var)
                    defaults[var] = default
                    docs[var] = doc                    
            elif isinstance(_state_vars, dict):
                for key in _state_vars:
                    default = NotImplemented
                    doc = _NO_DESCRIPTION
                    if isinstance(key, str):
                        var = key
                        default = _state_vars[key]
                    elif isinstance(key, tuple) and len(key) == 2:
                        var = key[0]
                        doc = key[1]
                        default = _state_vars[key]
                    else:
                        raise TypeError('Key must be name or (name, doc)'+
                                        ' (got %s)'%repr(key))
                    
                    if not isinstance(var, str):
                        raise TypeError('Name must be a string'+
                                        ' (got %s)'%repr(var))
                    if var not in vars:
                        vars.append(var)
                    defaults[var] = default
                    docs[var] = doc                    
            else:
                raise TypeError('_state_vars must be a list or dict')
        if hasattr(cls, '_excluded_vars'):
            if exclude is None:
                exclude = set()
            exclude.update(cls._excluded_vars)
        for base in mmf.utils.all_bases(cls):
            if (hasattr(base, '__metaclass__') and 
                base.__metaclass__ is StateVarMetaclass):
                if hasattr(base, '_state_vars'):
                    if vars is None:
                        vars = []
                    for (var, default, doc) in base._state_vars:
                        if var not in vars:
                            vars.append(var)
                        defaults[var] = default
                        docs[var] = doc
                if hasattr(base, '_excluded_vars'):
                    if exclude is None:
                        exclude = set()
                    exclude.update(base._excluded_vars)

        if exclude is not None:
            cls._excluded_vars = exclude
        if vars is not None:
            cls._state_vars = [(key, defaults[key], docs[key]) 
                              for key in vars]
            cls.__doc__ = _get__doc__(cls, cls._state_vars)
        else:
            cls.__doc__ = _get__doc__(cls, cls._state_vars)
    

class CalcObject(CopyConstruct, Archivable):
    r"""My object class intended for calculations.

    1) Provides default pickling services __getstate__ and
       __setstate__.  These do the following:
       a) Check for an attribute _state_vars.  If present, then only
          these vars will be archived.
       b) Check for an attribute _excluded_vars.  If present, then these
          will be excluded from the state.
       c) The method initialize() will be called after __setstate__.
    2) Provides nice ouput functions.
    3) Provide descriptions of :attr:`_state_vars` in class __doc__.
    
    Note that state variables with names begining with underscores
    '_...' are always excluded unless explicitly included in
    :attr:`_state_vars`.

    :attr:`_state_vars` may be a dictionary with default values, or simply a
    list/set of variable names.

    Example:
    >>> class A(CalcObject):
    ...     _state_vars = [('x', 10),
    ...                    ('y', 100)]
    >>> a = A(x=1.0)
    >>> print a
    x=1.0
    y=100
    >>> a.y = 5
    >>> a
    A(x=1.0, y=5)
    >>> a.z = 6
    >>> a
    A(x=1.0, y=5)

    >>> class B(CalcObject):
    ...     _excluded_vars = ['LargeObject']
    ...     def initialize(self):
    ...         self.LargeObject = 'Elephant'
    >>> b = B(x=5, y=6)
    >>> b.z = 9
    >>> b.LargeObject
    'Elephant'
    >>> b
    B(x=5, y=6, z=9)
    >>> state = b.__getstate__()
    >>> c = B()
    >>> c
    B()
    >>> c.__setstate__(state)
    >>> c
    B(x=5, y=6, z=9)
    >>> print c
    x=5
    y=6
    z=9
    Excluded:
    LargeObject=Elephant
    >>> d = B(c)
    >>> d
    B(x=5, y=6, z=9)

    >>> class C(CalcObject):
    ...     _state_vars = [('x', 1, 'Parameter x'),
    ...                    ('y', 2, 'Parameter y')]
    >>> a = C()
    >>> a
    C(x=1, y=2)
    >>> b = C(z=3)              # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    TypeError: z is an invalid keyword argument for <class '...C'>.
    >>> b = C(x=2, z=3, t=4)      # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    TypeError: ['z', 't'] are invalid keyword arguments for <class '...C'>.

    One may also use a list rather than a dictionary:
    >>> class D(CalcObject):
    ...     _state_vars = ['x', 'y']
    >>> a = D(x=3)
    >>> a
    D(x=3)
    >>> a.y = 4
    >>> print a
    x=3
    y=4

    Note, you may use properties: just store the value in __dict__
    with the same name.  Note that this is a name clash, so be sure to
    ignore the error:
    
    >>> class E(CalcObject):
    ...     _ignore_name_clash = set(['x'])
    ...     _state_vars = ['x', 'y']
    ...     def set_x(self, x):
    ...         self.__dict__['x'] = x
    ...         print "Setting x"
    ...     def get_x(self):
    ...         print "Getting x"
    ...         return self.__dict__['x']
    ...     x = property(get_x, set_x)
    >>> a = E(y=2)
    >>> a  # Even though x is not set, getattr is called by hasattr...
    Getting x
    Getting x
    E(y=2)
    >>> a.x = 5
    Setting x
    >>> print a
    Getting x
    Getting x
    x=5
    y=2
    """
    __metaclass__ = StateVarMetaclass

    def __init__(self, *varargin, **kwargs):
        r"""Set :attr:`_state_vars` and _excluded_vars by inheriting from base
        classes, then call CopyConstruct.__init__ to complete
        initialization.  Default values are also initialized here.

        Use this to 'inherit' state variables.
        >>> class A(CalcObject):
        ...     _state_vars = ['a', 'b']
        >>> class B(CalcObject):
        ...     _state_vars = {'c':1}
        >>> class C(A, B):
        ...     _state_vars = {'d':2}
        >>> class D(C):
        ...     _state_vars = {'r':Required}
        >>> c = C()
        >>> c
        C(c=1, d=2)
        >>> C.class_keys()
        ['a', 'b', 'c', 'd']
        >>> D(c=1, d=2)
        Traceback (most recent call last):
            ...
        ValueError: Required attribute 'r' not defined.
        """
        init_flag = _start_initializing(self)
        try:
            required_keys = []
            if hasattr(self, '_state_vars'):
                for (key, default, doc) in self._state_vars:
                    if default is NotImplemented:
                        pass
                    elif default is Required:
                        required_keys.append(key)
                    else:
                        setattr(self, key, default)
                        
            for key in required_keys:
                if not hasattr(self, key):
                    raise ValueError("Required attribute '%s'"
                                     " not defined."%key)
        except:
            raise
        finally:
            _finish_initializing(self, init_flag)

    def _copy(self, obj):
        r"""Copy constructor.  Only copies stateful information"""
        self._init_attrs(dict(obj.items()))

    def _init(self, **kwargs):
        r"""Default constructor.  Accepts and sets all members
        specified in :attr:`_state_vars`.  Calls initialize().
        
        Constructors should accept keyword arguments for all
        :attr:`_state_vars` but may accept other arguments.  The default,
        however, does not accept kwargs not specified in :attr:`_state_vars`
        if it is defined."""
        self._init_attrs(kwargs)
        self.initialize()

    def _init_attrs(self, kwargs):
        r"""Initialize :attr:`_state_vars` from kwargs including only specified
        variables."""
        if hasattr(self, '_state_vars'):
            _state_vars = self._state_vars
            for (var, default, doc) in _state_vars:
                if var in kwargs:
                    setattr(self, var, kwargs.pop(var))
            if len(kwargs) == 1:
                raise TypeError(
                    "%s is an invalid keyword argument for %s."%\
                        (str(kwargs.keys()[0]), self.__class__))
            elif len(kwargs) > 1:
                raise TypeError(
                    "%s are invalid keyword arguments for %s."%\
                        (str(kwargs.keys()), self.__class__))
        else:
            # No _state_vars, so just update from initial arguments.
            for k in kwargs:
                setattr(self, k, kwargs[k])

    def initialize(self):
        r"""This should perform any initializations required apart from
        directly computing and setting state variables.

        Anything that will not be returned by __getstate__ needs to be
        recomputed here.

        This version does nothing.
        """
        pass

    def __getstate__(self):
        r"""Return a representation of the function object in a form
        that is picklable.
        
        a) Check for an attribute :attr:`_state_vars`.  If present, then only
           these vars will be archived.
        b) Check for an attribute _excluded_vars.  If present, then these
           will be excluded from the state.
        """
        return dict((k, getattr(self, k)) for k in self.included_keys())
    
    def __setstate__(self, state):
        r"""Initialize the function from state as returned by
        __getstate__.

        The method initialize() will be called after __setstate__.
        """
        self.__init__(**state)
        self.initialize()


    @classmethod
    def get_args(cls, *varargin, **kwargs):
        r"""Return the dictionary that is a subset of kwargs containing
        the valid keyword arguments for the current object.

        >>> class A(CalcObject):
        ...     _state_vars = ['a', 'b']
        >>> class B(CalcObject):
        ...     _state_vars = ['c', 'd']
        >>> def f(**kwargs):
        ...     a = A(A.get_args(kwargs))
        ...     b = B(B.get_args(kwargs))
        ...     return a, b
        >>> a, b = f(a=1, b=2, c=3, d=4)
        >>> a, b
        (A(a=1, b=2), B(c=3, d=4))

        >>> CalcObject(CalcObject.get_args(a=1, b=2))
        CalcObject(a=1, b=2)
        """
        if 0 == len(varargin):
            pass
        elif 1 == len(varargin):
            dict = varargin[0]
            dict.update(kwargs)
            kwargs = dict
        else:
            raise ValueError("get_args takes one dictionary argument.")

        class_keys = cls.class_keys()
        if 0 == len(class_keys):
            # Variables determined dynamically, so all arguments
            # accepted.
            return kwargs
        else:
            return mmf.utils.get_args(kwargs, class_keys)

    @classmethod
    def _getargspec(cls):
        r"""Get the names and default values of the constructor.

        A tuple of four things is returned: (args, varargs, varkw, defaults).
        'args' is a list of the argument names (it may contain nested lists).
        'varargs' and 'varkw' are the names of the * and ** arguments or None.
        'defaults' is an n-tuple of the default values of the last n arguments.

        >>> class C(CalcObject):
        ...     pass
        >>> C.getargspec()
        ([], None, 'kwargs', ())
        >>> class D(CalcObject):
        ...     _state_vars = [('a', 0),
        ...                    ('b', Required),
        ...                    ('c', NotImplemented)]
        >>> D.getargspec()
        (['b', 'a', 'c'], None, None, (0, NotImplemented))
        """
        varargs = None
        try:
            required_args = [var for (var, default, doc) in cls._state_vars
                             if default is Required]
            optional_args = [var for (var, default, doc) in cls._state_vars
                             if default is not Required]
            defaults = tuple(default for (var, default, doc) in cls._state_vars
                             if default is not Required)
            args = required_args + optional_args
            varkw = None
        except AttributeError:
            args = []
            defaults = ()
            varkw = 'kwargs'
        return (args, varargs, varkw, defaults)
        
    @classmethod
    def class_keys(cls):
        r"""Return the keys accepted by the constructor."""
        try:
            include = [var for (var, default, doc) in cls._state_vars]
        except AttributeError:
            include = []

        # Make include contain only one of each variable.
        include_set = set(include)
        include = [var for var in include 
                   if var in include_set
                   and not include_set.remove(var)]
        return include
        
    def included_keys(self):
        r"""Return set of keys to be included for archiving."""
        # Use _state_vars if defined, otherwise use __dict__
        try:
            include = [var for (var, default, doc) in self._state_vars]
        except AttributeError:
            include = [k for k in self.__dict__.keys() 
                       if k[0] != '_']
            include.sort()

        include = [k for k in include 
                   if hasattr(self, k)]

        # Exclude specified variables
        try:
            exclude = set(self._excluded_vars)
        except AttributeError:
            exclude = set([])

        # Make include contain only one of each variable.
        include_set = set(include) - exclude
        include = [var for var in include 
                   if var in include_set
                   and not include_set.remove(var)]
        return include

    def items(self):
        r"""Return a list of `(key, value)` pairs defining the
        persistent state of the object.

        Objects are ordered as specified by :meth:`included_keys`.
        
        """
        state = self.__getstate__()

        items = [(k, state.pop(k)) for k in self.included_keys() 
                 if k in state]
        items.extend(state.items())
        return items

    def _get_args(self):
        r"""Support archiving of objects for Archivable.
        
        Return a list [(name, obj)] of (name, object) pairs where the
        instance can be constructed as
        ClassName(name1=obj1, name2=obj2, ...).

        >>> c = CalcObject(a=1, b=2)
        >>> print c.archive('c') # doctest: +NORMALIZE_WHITESPACE +ELLIPSIS
        from ..._objects import CalcObject as _CalcObject
        c = _CalcObject(a=1, b=2)
        del _CalcObject
        try: del __builtins__
        except NameError: pass
        """
        return self.items()
        
    def __str__(self):
        r"""Pretty print state, including temporaries.  Print order is
        sorted."""
        included_keys = list(self.included_keys())
        excluded_keys = [k for k in self.__dict__ 
                         if (k not in included_keys and
                             k[0] is not '_')]
        excluded_keys.sort()
        res = "\n".join(["%s=%s"%(k, str(getattr(self, k))) 
                         for k in included_keys])
        if 0 < len(excluded_keys):
            res = "\n".join([res,
                             'Excluded:']
                            +["%s=%s"%(k, str(getattr(self, k)))
                              for k in excluded_keys
                              if k[0] is not '_'])
        return res
'''
class attribute(property): # Need to be a property so help works
    r"""Attribute class: like property, but with default operators.

    One way to use is to directly make a property with documentation
    and a default value:

    x = attribute(default=1.0, doc='x-coordinate')

    Another way is as a decorator:

    @attribute
    def x(self):
        'x-coordinate'
        return 1.0

    Examples
    --------
    >>> class Data(object):
    ...     x = attribute(default=1.0, doc='x-coordinate')
    ...     @attribute
    ...     def y(self):
    ...         'y-coordinate'
    ...         return -1.0
    >>> d = Data()
    >>> d.x
    1.0
    >>> d.x = 4
    >>> d.x
    4
    >>> d.y
    -1.0
    >>> d.y = 2.0
    >>> d.y
    2.0
    >>> help(d)         # doctest: +ELLIPSIS
    Help on Data in module ...:
    <BLANKLINE>
    class Data(__builtin__.object)
    ...
     |  x
     |      x-coordinate
     |  
     |  y
     |      y-coordinate
    """
    def __init__(self, func=None, default=None, doc=""):
        r"""Initialization."""
        if func is None:
            self.value = default
            self.__doc__ = doc
        else:
            self.value = func(self)
            self.__doc__ = func.__doc__       
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self         # Needed so that help facility works
        return self.value

    def __set__(self, obj, value):
        self.value = value

class parameter(property):
    r"""Parameter class: Turns a function into a parameter.  

    This has several benifits: 1) The docstring of the function
    describes the parameter.  2) The return value is used to
    initialize the parameter.  3) If the parameter is an instance of the
    class MemoizedContainer, then memoization is used and the signal _changed
    is sent when the parameter is modified.
    
    >>> class Data(object):
    ...     @parameter
    ...     def x():
    ...         "x coordinate"  # Documentation
    ...         return 10.0     # Default value
    >>> d = Data()
    >>> d.x
    10.0
    >>> d.x = 6
    >>> d.x
    6

    If you want fast parameter access, use the dictionary directly:
    >>> d.__dict__['x']
    6
    """
    def __init__(self, f):
        self.f = f
        self.__name__ = f.__name__
        self.__doc__ = f.__doc__
        if self.__doc__ is None:
            self.__doc__ = ""
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        else:
            try:
                return obj[self.__name__]
            except:
                pass
            try:
                return obj.__dict__[self.__name__]
            except:
                pass
            return self.f()

    def __set__(self, obj, value):
        name = self.__name__
        if isinstance(obj, MemoizedContainer):
            if not isequal(value, obj[name]):
                obj[name] = value
                obj._changed(name)
        else:
            obj.__dict__[name] = value

class calculate(property):
    r"""Decorator for calculational functions that should be
    memoized.  Memoization only happens with instances of MemoizedContainer.

    >>> class Data(object):
    ...     @calculate
    ...     def f(x):
    ...         "The square of x"
    ...         return x**2
    >>> d = Data()
    >>> d.x = 6
    >>> d.f
    36
    """
    def __init__(self, f):
        self.f = f
        self.__name__ = f.__name__
        self.args = f.func_code.co_varnames[:f.func_code.co_argcount]
        if f.__doc__ is not None:
            self.__doc__ = "Calculated: " + f.__doc__
        else:
            self.__doc__ = "Calculated: "
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            value = self                # Needed so that help facility works
        elif isinstance(obj, MemoizedContainer):
            value = obj[self.__name__]
            if value is None:   # Need to recompute
                #kw = {}
                #for n in self.args:
                #    kw[n] = getattr(obj, n)
                #value = self.f(**kw)
                value = self.f(*map(lambda n:getattr(obj, n), self.args))
            obj[self.__name__] = value
        else:
            value = self.f(*map(lambda n:getattr(obj, n), self.args))
        return value

    def __set__(self, obj, value):
        raise AttributeError("can't set attribute")

class MemoizedContainer(dict):
    r"""The paradigm for this class is that one has a set of parameters
    (call them x[0], x[1] etc.) and a set of functions that depend on
    these parameters (call them f[0], f[1] etc.).  The idea is that
    the functions should compute the value only once and memoize it
    until the parameters that it depends on change.

    To do this, define all the bare parameters using the parameter
    class.  Then define all of the functions as standard functions
    with arguments that have the same name as the parameters.  The
    argument list determines the dependencies.  These should be
    defined as functions, and should not accept the parameter self.
    The actual member functions will be defined later by __new__.

    If you would like to define helper functions that are not
    memoized, prefix them with an underscore.

    >>> class Data1(MemoizedContainer):
    ...     @parameter
    ...     def x():
    ...         "x coordinate"  # Documentation
    ...         return 10.0     # Default value
    ...     @parameter
    ...     def y():
    ...         "y coordinate"
    ...         return 2.0
    ...     @parameter
    ...     def z():
    ...         "z coordinate"
    ...         return -2.0
    ...     @calculate
    ...     def f(x):
    ...         "The square of x"
    ...         print "Computing f("+`x`+")"
    ...         return x**2
    ...     @calculate
    ...     def g(x, f, y):
    ...         "Product of x*f*y = x**3*y"
    ...         print "Computing g("+`x`+", "+`f`+", "+`y`+")"
    ...         tmp = x*f*y
    ...         return tmp
    >>> d = Data1(y=2.0)
    >>> d.f                     # slow
    Computing f(10.0)
    100.0
    >>> d.f                     # fast
    100.0
    >>> d.g                     # slow
    Computing g(10.0, 100.0, 2.0)
    2000.0
    >>> d.g                     # fast
    2000.0
    >>> d.y = 3.0
    >>> d.f                     # fast
    100.0
    >>> d.g                     # slow
    Computing g(10.0, 100.0, 3.0)
    3000.0
    >>> d.g                     # fast
    3000.0
    >>> try: d.g = 5
    ... except AttributeError, err:
    ...     print err
    can't set attribute
    >>> d.dependencies
    {'y': set(['g']), 'x': set(['g', 'f']), 'z': set([]), 'g': set([]), 'f': set(['g'])}

    One can also use multiple inheritance to combine parameters:

    >>> class Data2(MemoizedContainer):
    ...     @parameter
    ...     def a():
    ...         return -1.0     # Default value
    ...     @parameter
    ...     def b():
    ...         return 2.0
    ...     @calculate
    ...     def h(a):
    ...         print "Computing h("+`a`+")"
    ...         return a**3
    >>> class Data3(Data1, Data2):
    ...     @parameter
    ...     def c():
    ...         return 2.0
    ...     @calculate
    ...     def F(c, f, g, h):
    ...         print "Computing F("+`c`+", "+`f`+", "+`g`+", "+`h`+")"
    ...         return c+f*g*h
    >>> class Data(Data3):
    ...     pass
    >>> d = Data()
    >>> d.F
    Computing f(10.0)
    Computing g(10.0, 100.0, 2.0)
    Computing h(-1.0)
    Computing F(2.0, 100.0, 2000.0, -1.0)
    -199998.0
    >>> d.g
    2000.0
    >>> d.F
    -199998.0

    For faster bare parameter access, use the dictionary

    >>> d.x                     # slow
    10.0
    >>> d['x']                  # fastest
    10.0
    """
    def __new__(cls, *argv, **kwargs):
        r"""Return a new instance.  This method also updates the
        class dependencies dictionary.
        """
        self = dict.__new__(cls)
        try:
            cls.initialized
        except:
            cls.initialized = False
            cls.parameters = {}
            cls.calculators = {}
            cls.dependencies = {}   # Dependencies are maintained at the
                                    # class level.
        if not cls.initialized:
            dicts = [cls.__dict__]
            for base in mmf.utils.all_bases(cls):
                dicts.append(base.__dict__)
            for dict_ in dicts:
                for (name, attr) in dict_.items():
                    if isinstance(attr, parameter):
                        cls.parameters[name] = attr
                        if not name in cls.dependencies:
                            cls.dependencies[name] = set()
                    if isinstance(attr, calculate):
                        cls.calculators[name] = attr
                        if not name in cls.dependencies:
                            cls.dependencies[name] = set()
                        for arg in attr.args:
                            if not arg in cls.dependencies:
                                cls.dependencies[arg] = set([name])
                            else:
                                cls.dependencies[arg] = \
                                    cls.dependencies[arg].union([name])
        return self
            
    def __init__(self, *argv, **kwargs):
        dict.__init__(self, *argv, **kwargs)
        for p in self.__class__.parameters:
            if not p in self:
                self[p] = self.__class__.parameters[p].f()
        for c in self.__class__.calculators:
            # Initialize calculators to be empty.
            self[c] = None
        
    def _changed(self, name):
        r"""Called by parameter properties when they are modified.
        This updates the dependency dictionary so that functions will
        recompute their memoized values as needed.
        """
        for dep in self.__class__.dependencies[name]:
            self[dep] = None
            self._changed(dep)

class Calculator:
    r"""This class represents some data and values that must be
    calculated by a function calculate.

    >>> class C(Calculator):
    ...     @parameter
    ...     def x(): return 1.0
    ...     @parameter
    ...     def y(): return 2.0
    ...     def calculate(self):
    ...         self.a = 2*self.x
    ...         self.b = self.a*self.x*self.y
    >>> class D(Calculator):
    ...     @parameter
    ...     def z(): return 3.0
    ...     def calculate(self):
    ...         self.c = self.z**3
    >>> class E(C, D):
    ...     def calculate(self):
    ...         C.calculate(self)
    ...         D.calculate(self)
    >>> c = C()
    >>> c.x = 2.0
    >>> c.y = 3.0
    >>> d = D(z=5.0)
    >>> e = E(c, d)
    >>> e.calculate()
    >>> e.a
    4.0
    >>> e.b
    24.0
    >>> e.c
    125.0
    >>> e
    E(y=3.0, x=2.0, z=5.0)
    """

    def _initialize_parameters(self):
        r"""Find all parameters and initialize them to their default
        values.  Return class dictionary of parameters."""
        cls = self.__class__
        if not 'parameters' in cls.__dict__:
            cls.parameters = {}

        dicts = [cls.__dict__]
        for base in mmf.utils.all_bases(cls):
            dicts.append(base.__dict__)
        for dict_ in dicts:
            for (name, attr) in dict_.items():
                if isinstance(attr, parameter):
                    cls.parameters[name] = attr
#        [[cls.parameters.__setattr__(name, attr) for (name, attr) in\
#          dict_.items() if isinstance(attr, parameter)] for dict_ in dicts]
        return cls.parameters
            
    def __init__(self, *argv, **kwargs):
        initial_values = {}
        for obj in [a for a in argv if isinstance(a, Calculator)]:
            for p in obj.__class__.parameters :
                initial_values[p] = getattr(obj, p)
        initial_values.update(kwargs)
        parameters = self._initialize_parameters()
        for p in parameters:
            if not p in initial_values:
                self.__dict__[p] = self.__class__.parameters[p].f()
            else:
                self.__dict__[p] = initial_values[p]
        if not 'calculate' in self.__class__.__dict__:
            self.__class__.__dict__['calculate'] = Calculator.calculate
        self.calculate()

    def __repr__(self):
        r"""Return representation of object.
        """
        return "%s(%s)"%(self.__class__.__name__,
                         ", ".join(["%s=%r"%(p, getattr(self, p))
                                    for p in self.__class__.parameters]))

    def calculate(self):
        raise NotImplementedError
    
class metaO(type):
    def __new__(meta, clsname, bases, attrs):
        for name, attr in attrs.items():
            if isinstance(attr, attribute):
                attrs[name] = newreadonlyprop(clsname, name, attr)
        return super(metaO, meta).__new__(meta, clsname,
                                                bases, attrs)

class O(object):
    r"""A simple class to allow for attribute creation with documentation.

    >> class Coord(O):
    ...     x = attribute(default=0,
    ...                   doc='x-coordinate')
    ...     y = attribute(default=0,
    ...                   doc='y-coordinate')
    >> c = Coord(x=1, y=2)
    >> help(c)

    Incomplete!!!!

    See for help:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/157768
    http://www.python.org/download/releases/2.2.3/descrintro/#cooperation
    """    

#############################################
# Options Idea:
# Here is an idea for specifying members
class option(parameter):
    r"""
    >>> class A(object):
    ...     x = option(doc='Description of member x',
    ...                default=0)
    ...     name = option(default='')
    >>> a = A()
    >>> a.x
    0
    >>> a.x = 1
    >>> a.x
    1
    >>> a.x.__doc__
    'Description of member x'
    >>> a.name = "MyName"
    >>> a.name.__doc__
    'Undocumented Option'
    """
    def __init__(self, func=None, doc=None, default=None):
        if func is not None:
            if doc is None:
                doc = func.__doc__
            if default is None:
                default = func()
        if doc is None:
            doc = "Undocumented Option"
        self.__doc = doc
        self.__set__(self, default)
        
        
    def __get__(self, obj, type_):
        if obj is None:
            return self
        return self.__value
    
    def __set__(self, obj, value):
        if value is None:
            self.__value = None
        else:
            self.__value = type("OptionOfType_%s"%(type(value).__name__),
                                (type(value), ),
                                {'__doc__': self.__doc})(value)
    def __repr__(self):
        return "option(default=" + \
               repr(self.__value) + \
               ", doc=" + \
               repr(self.__doc) + ")"

    def __str__(self):
        return str(self.__value)
    
class Options(object):
    r"""Options class.  This class acts as a container.  It provides
    methods to display the members.  One can also define member
    functions, but their names must start with an underscore: all
    non-underscored names are assumed to be 'options'.

    The values defined in the base class are used as defaults.  They
    will be deepcopied for each instance.  Note that this means
    recursive data should not be used for parameters.

    Use in conjunction with the option decorator to provide
    documentation for the options.

    Examples
    --------
    Here are some examples of direct usage:

    >>> d1 = Options(['x', 'y', 'cc.x', 'cc.y'])
    >>> d1.x = 3
    >>> d1['y'] = 4
    >>> d1.cc.x = 5
    >>> d1.cc.y = 6
    >>> d1
    Options({'y': 4, 'x': 3, 'cc': Options({'y': 6, 'x': 5})})
    >>> print d1
    opts=Options(['x', 'y', 'cc.x', 'cc.y'])
    opts.x=3
    opts.y=4
    opts.cc.x=5
    opts.cc.y=6

    You may define options with keywords too:

    >>> d2 = Options(x=3, y=4)
    >>> d2
    Options({'y': 4, 'x': 3})

    Here is an example which defines a base class with defaults:

    >>> class MyOpts(Options):
    ...   x = 1
    ...   y = 2
    ...   z = [2]               # This will get copied
    >>> c1 = MyOpts()
    >>> c2 = MyOpts()
    >>> c2.z[0] = 3
    >>> print c1                # Note that z does not change here
    opts=MyOpts(['x', 'y', 'z'])
    opts.x=1
    opts.y=2
    opts.z=[2]
    >>> print c2                # It only changes here.
    opts=MyOpts(['x', 'y', 'z'])
    opts.x=1
    opts.y=2
    opts.z=[3]
 
    Here is an example with the option decorator:

    >>> class MyOpts(Options):
    ...     @option
    ...     def abs_tol():
    ...         'Absolute tolerance'
    ...         return 2e-16
    ...     
    ...     rel_tol = option(default=2e-8,
    ...                      doc='Relative tolerance')
    >>> c1 = MyOpts()
    >>> print c1
    opts=MyOpts(['abs_tol', 'rel_tol'])
    opts.abs_tol=2e-16
    opts.rel_tol=2e-08

    """
    def __init__(self, c=None, **kwargs):
        """
        """
        for (k, i) in self.__class__.__dict__.items():
            # Add copies of of all class members that don't start with
            # an underscore
            if "_" != k[0]:
                self._add(key=k, value=copy.deepcopy(i))
        if type(c) is list:
            for k in c:
                self._add(key=k)
        elif type(c) is dict:
            for k in c:
                self._add(key=k, value=c[k])
        for k in kwargs:
            self._add(key=k, value=kwargs[k])

    def __getitem__(self, name):
        """Provide item access."""
        return self.__dict__[name]

    def __setitem__(self, name, value):
        """Provide item access."""
        self.__setattr__(name, value)

    def _add(self, key, value=None):
        """ """
        subKeys = key.split(".")
        k = subKeys[0]
        if 1 == len(subKeys):
            self.__dict__[k] = value
        else:
            if k in self.__dict__:
                self.__dict__[k]._add(key=".".join(subKeys[1:]),
                                      value=value)
            else:
                self.__dict__[k] = Options()
                self.__dict__[k]._add(key=".".join(subKeys[1:]),
                                      value=value)

    def _getOptions(self, prefix=None, opts=None, items=None):
        """Return complete list of options and values including all
        sub-options.

        >>> d = Options({'x':3, 'y':4, 'cc.x':5, 'cc.y':6})
        >>> d._getOptions()
        (['x', 'y', 'cc.x', 'cc.y'], [3, 4, 5, 6])
        """
        if opts is None:
            opts = []

        if items is None:
            items = []

        opts_opts = []
        opts_items = []
        d = self.__dict__
        keys = d.keys()
        keys.sort()
        for k in keys:
            if prefix is None:
                newPrefix = k
            else:
                newPrefix = prefix+"."+k
            item = d[k]
            if isinstance(item, Options):
                item._getOptions(prefix=newPrefix,
                                 opts=opts_opts,
                                 items=opts_items)
            else:
                opts.append(newPrefix)
                items.append(item)
        opts += opts_opts
        items += opts_items
        return (opts, items)

    def __setattr__(self, name, value):
        """Only allow defined options to be set."""
        if name in self.__dict__:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(
                str(self.__class__.__name__) + 
                " object has no attribute " + 
                str(name))

    def __repr__(self):
        """Return representation of object.
        """
        return self.__class__.__name__+"("+dict.__repr__(self.__dict__)+")"

    def __str__(self):
        """Return representation of object.
        """
        dummyName = "opts"
        (opts, items) = self._getOptions()
        lines = [dummyName+"="+self.__class__.__name__+"("+`opts`+")"]
        (opts, items) = self._getOptions(prefix=dummyName)
        lines += [k+"="+str(i) for (k, i) in zip(opts, items)]
        return "\n".join(lines)

def recview(a, names, formats=None, dtype=None):
    """Return a view of a as a recarray with defined field names.

    >>> from numpy import array
    >>> a = array([[1, 2, 3], [4, 5, 6]])
    >>> r = recview(a, ['x', 'y', 'z'])
    >>> print r
    [[(1, 2, 3)]
     [(4, 5, 6)]]
    >>> r.x = 0
    >>> a
    array([[0, 2, 3],
           [0, 5, 6]])
    """
    r = np.rec.fromrecords(a, names=names)
    return a.view(r.dtype).view(np.rec.recarray)


class RecView(np.recarray):
    """A simple subclass of the numpy recarray record array class that
    provides automatic conversion to a recarray.  To subclass, simply
    define `_names` as a list of the field names and `_array` as a default
    array.

    >>> from numpy import array
    >>> class Coord(RecView):
    ...     _array = array([1.0, 2.0])
    ...     _names = ['x', 'y']
    >>> c = Coord()
    >>> c.x
    array([ 1.])
    """
    def __new__(cls, record=None):
        """
        """
        if record is None:
            record = cls._array
        if 1 == record.ndim:
            record = [record]
        self = np.rec.fromrecords(record, names=cls._names).view(cls)
        return self

def class_NamedArray(array_, names=None):
    """Return a class that is a subclass of `array_.__class__` but that
    allows the elements to be accessed through a named member syntax.

    For example, if `array_ = array([1.0, 2.0])` and 
    `names = array(['x', 'y'])` then `c[0] == c.x`, and `c[1] == c.y`

    The preferred usage is to define a class which inherits from the
    returned class.  The arguments will then defined the names and the
    default values for objects instantiated from this class.  The
    advantage of proceeding this way is that the name of the class
    will be well defined and usefull rather than the generic "NamedArray".
    
    >>> from numpy import array
    >>> a = array([0.0, 0.0, 0.0])
    >>> n = array(['x', 'y', 'z'])
    >>> class CoordArray(class_NamedArray(a, n)): 
    ...     pass
    >>> c0 = CoordArray()
    >>> c0
    CoordArray([ 0.,  0.,  0.])

    You can initialize the array from a sequence, and use keyword
    arguments to set specific values.  If you do not initialize, then
    the default values are used.  The initialization array need not be
    complete: it just initializes the first n values.

    >>> c = CoordArray([1, 3], y=2)
    >>> c
    CoordArray([ 1.,  2.,  0.])
    >>> (c.x, c.y)
    (CoordArray([ 1.]), CoordArray([ 2.]))
    >>> c.x = 3; c.y = 4
    >>> print c
    CoordArray(y=4.0, x=3.0, z=0.0)
    
    Note that one may have repeated labels:
    
    >>> a = array([[0, 0], [0, 0]])
    >>> n = array([['x', 'y'], ['y', 'z']])
    >>> class MatArray(class_NamedArray(a, n)): 
    ...     pass
    >>> c = MatArray(x=1, y=2, z=3)
    >>> c
    MatArray([[1, 2],
           [2, 3]])
    >>> c.y
    MatArray([2, 2])
    >>> c.y = [4, 5]
    >>> c
    MatArray([[1, 4],
           [5, 3]])


    >>> a = array([0, 0, 0])
    >>> n = array(['x', 'y', 'z'])
    >>> class MatArray(class_NamedArray(a, n)): 
    ...     pass
    >>> c = MatArray(vals=[1, 2, 3])
    >>> c
    MatArray([1, 2, 3])
    >>> c.t = 6
    >>> c.t
    6
    """
    base_class = array_.__class__
    fields = {}
    for n in np.unique(names.ravel()):
        fields[n] = np.where(n == names)
            
    class NamedArray(base_class):
        __slots__ = []
        _array = array_
        _type = base_class
        _fields = fields

        def __new__(cls, vals=None, **kwargs):
            """Return an initialized instance of a NamedArray object.
            
            vals: an interable object of proper length to assign should 
            self = __new__(cls, vals)
            """
            self = cls._type.__new__(cls,
                                     shape=cls._array.shape,
                                     dtype=cls._array.dtype)
            self[:] = cls._array
            if vals is not None:
                self[0:len(vals)] = vals

            for k in kwargs:
                self.__setattr__(k, kwargs[k])

            return self

        def __getattr__(self, name):
            """Get the value of the named parameter.

            c.x is equivalent to c[c._names['x']]
            """
            try:
                return self[self._fields[name]]
            except:
                return self._type.__getattribute__(self, name)

        def __setattr__(self, name, value):
            """Set the value of the named parameter.

            c.x is equivalent to c[c._names['x']]
            """
            try:
                self[self._fields[name]] = value
            except:
                self._type.__setattr__(self, name, value)

        def __str__(self):
            """Print the array nicely using the keyword syntax."""
            args = []
            for key in self._fields:
                value = self[self._fields[key]]
                if 1 == np.prod(value.size):
                    value = value.ravel()[0]
                args.append("%s=%s"%(key, value))
            ans = "%s(%s)"%(self.__class__.__name__,
                            ", ".join(args))
            return ans
            
    return NamedArray

################################################################
# Resources idea
# Idea for providing a set of "options" or resources with the option
# of the resources be archived to a file.
#
# Here is a sample "configuration file" as a string:
"""
# Initial size of the main window.
Main Window Size: (540, 400) 

# Initial Background colour for main window. 
Background Colour: "White"

[Font Information]
# This section contains font information.

# Main text font size (point size)
Text Size: 12
"""


class Resource(object):
    """Represents a resource with default values and archival
    ability."""
    def __init__(self, name, default=None, doc=None,
                 section=None, type_=None):
        """
        :Parameters:
        name : str
            Name of resource.  This will be used in the resource file
            to uniquely identify the resource.  Names should not
            contain colons.
        default : type_
            Default value for resource.
        section : str | None
            Name of the section in which to group the resource.  Names
            may be repeated if they occur in different sections.
            Sections should not contain the characters "[" or "]".
        type_ : type
            Type of resource.  This will be used to coerce the string
            value of the resource (obtained using repr) into an
            object.  If not specified, then the type of the default
            value will be used.
        doc : str | None
            Description of the resource.  Will be included in the
            resource file as a comment.
        """
        self.__name = name
        self.__section = None
        self.__doc = doc
        if default is None:
            default = type_()
        self.__set__(self, default)
        
    def __get__(self, obj, type_=None):
        if obj is None:
            return self
        return self.__value
    
    def __set__(self, obj, value):
        self.__value = type("MemberOfType_%s"%(type(value).__name__),
                            (type(value), ),
                            {'__doc__': self.__doc})(value)



class Resources(object):
    """Class to represent a collection of resources.

    >> class WindowResources(Resources):
    ...     size = Resource("Main Window Size",
    ...                     (540, 400),
    ...                     "Initial size of the main window.")
    ...     bg_colour = Resource("Background Colour",
    ...                          "White",
    ...                          "Initial Background colour for main window.")
    ...     font_info = Section("Font Information",
    ...                         "This section contains font information")
    ...     text_size = Resource("Text Size",
    ...                          12,
    ...                          "Main text font size (point size)",
    ...                          section=font_info)
    >> wr = WindowResources()
    """

class _ExceptionCoverageTests:
    """
    >>> class C(StateVars):
    ...     _state_vars = 3
    ...     process_vars()
    Traceback (most recent call last):
        ...
    TypeError: state_vars must be a list or dict

    >>> class C(StateVars):
    ...     _state_vars = [1, 2, 3]
    ...     process_vars()
    Traceback (most recent call last):
        ...
    TypeError: state_vars must be a list of strings or tuples

    >>> class C(StateVars):
    ...     _state_vars = ['a', (3, 2)]
    ...     process_vars()
    Traceback (most recent call last):
        ...
    TypeError: Name must be a string (got 3)

    >>> class C(StateVars):
    ...     _state_vars = {('a', 3, 4):5}
    ...     process_vars()
    Traceback (most recent call last):
        ...
    TypeError: Key must be name or (name, doc) (got ('a', 3, 4))

    >>> class C(object):
    ...     _state_vars = {(1, 3):5}
    ...     process_vars()
    Traceback (most recent call last):
        ...
    TypeError: Name must be a string (got 1)

    >>> class C(StateVars):
    ...     process_vars()
    >>> help(C)                 #doctest: +ELLIPSIS
    Help on class C in module ...:
    <BLANKLINE>
    class C(StateVars)
     |  Usage: C()
    ...

    """
