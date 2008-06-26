"""This file contains a set of utility functions and classes useful
for various miscellaneous tasks.
"""
__all__ = ['get_args','unique_list',
           'attribute', 'parameter', 'calculate', 
           'StateVarMetaclass', 'MemoizedContainer',
           'option', 'Options', 'class_NamedArray', 'recview',
           'RecView', 'Calculator', 'CalcObject']

from copy import copy,deepcopy
import types
import optparse
import numpy

###########################################################
# Functions
def get_args(kwargs,args):
    """Return a dictionary with only the specified arguments.
    
    Example:
    >>> def f(x,y,z=1): return x+y*z
    >>> def g(x,t): return x*t
    >>> def h(x,**kwargs):
    ...     return (f(x=x,**get_args(kwargs,['y','z'])) +
    ...             g(x=x,**get_args(kwargs,['t'])))
    >>> h(1,y=2,t=3)
    6
    >>> def hh(x,**kwargs):
    ...     return (f(x=x,**get_args(kwargs,f)) +
    ...             g(x=x,**get_args(kwargs,g)))
    >>> hh(1,y=2,t=3)
    6
    """
    try:
        # See if args is a function object
        args = args.func_code.co_varnames
    except:
        pass
    return dict((k,kwargs[k]) for k in kwargs
                if k in args)
        

def all_bases(cls):
    """Return a list of all the parent classes."""
    if len(cls.__bases__) is 0:
        return []
    else:
        bases = []
        bases.extend(cls.__bases__)
        for b in cls.__bases__:
            bases.extend(all_bases(b))
        return bases

def unique_list(l):
    """Make list contain only unique elements."""
    unique = set(l)
    return [x for x in l 
            if x in unique 
            and not unique.remove(x)]

def memoize(f,hash=None):
    """Return a memoizing function.

    >>> def f(x):
    ...    print "Computing f(%s)"%`x`
    ...    return x*x
    >>> g = memoize(f)
    >>> f(3)
    Computing f(3)
    9
    >>> f(3)
    Computing f(3)
    9
    >>> g(3)
    Computing f(3)
    9
    >>> g(3)
    9

    Note that the memoization is
    based on equality testing, and thus may not be suitable for
    floating-point applications."""
    if hash is None:
        hash = {}
    def memoized_f(x,f=f,hash=hash):
        try:
            return hash[x]
        except KeyError:
            res = f(x)
            hash[x] = res
            return res
    return memoized_f

###########################################################
# Classes
class Interface(object):
    """This is a stub allowing the insertion later of an interface
    class.  An interface defines some properties and methods but
    maintains no data and should not be instantiated."""

class CopyConstruct(object):
    """Provides dispatching to allow for copy construction through the
    following methods:
    _copy() : Copy from another instance (Default is to copy __dict__)
    _initialize() : Initialize from multiple arguments.

    It also provides copy services and str and repr services.

    >>> class A(CopyConstruct):
    ...     def _copy(self,obj):
    ...         print "Copying"
    ...         CopyConstruct._copy(self,obj)
    ...     def _init(self,**kwargs):
    ...         print "Initializing"
    ...         CopyConstruct._init(self,**kwargs)
    >>> a = A(x=1,y=2)
    Initializing
    >>> a
    A(y=2,x=1)
    >>> b = A(a)
    Copying
    Initializing
    >>> print b
    y=2
    x=1
    >>> c = copy(b)
    Copying
    Initializing
    >>> c
    A(y=2,x=1)
    """
    def __init__(self,*varargin,**kwargs):
        """Provides default initialization dispatch.
        Define initialization behaviour through
        _copy() and _init().
        _init() is always called.
        """
        if 1 == len(varargin):
            self._copy(varargin[0])
            varargin = varargin[1:]
        self._init(*varargin,**kwargs)
    def _copy(self,obj):
        """Default copy constructor: copies __dict__.  Does not call _init()."""
        self.__dict__.update(obj.__dict__)
    def _init(self,**kwargs):
        """Default initialization: assigns kwargs to __dict__."""
        self.__dict__.update(kwargs)
    def __copy__(self):
        """Return a copy."""
        return self.__class__(self)
    def __repr__(self):
        """Return a string representation of the object.  The items
        argument may be used to override self.items()"""
        keyvals = ["=".join((k,repr(v))) 
                   for (k,v) in self.items()]
        return "%s(%s)"%(self.__class__.__name__,",".join(keyvals))
    def __str__(self):
        """Return a pretty string representation of the objects state.  The
        items argument may be used to override self.items()

        Known bug: If there is nesting, then the format does not look
        good because __str__ provides no way of passing indenting
        information.
        """
        keyvals = ["=".join((k,str(v))) 
                   for (k,v) in self.items()]
        return "\n".join(keyvals)
    def items(self):
        """Return a list of (key,value) pairs representing the state
        of the object.  This is used by str and repr."""
        return self.__dict__.items()

_no_description = "<no description>"
class Required(object):
    """Default value for required arguments."""
    pass

class StateVarMetaclass(type):
    """Metaclass for the generation of classes with inherited state
    variable information.  The class variables _state_vars is used to
    define state variables documentation. Valid forms are:
    1) List of:
       name (no documentation or defaults)
       (name,default) (no documentation)
       (name,default,doc)
    2) Dictionary of name:default (no documentation) or
       (name,documentation):default.

    If _state_var is not defined, then it is left undefined.  In this
    case, values of __dict__ should be considered to be the state
    variables.  An additional list _exclude_vars may be defined to
    indicate that these are not considered state variables.
    (Variables starting with an underscore are implicitly excluded
    unless explicitly included in _state_vars)

    Both _state_vars and _exclude_vars include all inherited values.

    These will be processed along with all base classes to give the
    normal form [(name,default,doc)] where doc is <no description> if no
    documentation is provided and default is NotImplemented if no
    default is provided.
    """
    def __init__(cls,name,bases,dict_):
        """
        >>> class Complex(object):
        ...     "Complex numbers"
        ...     __metaclass__ = StateVarMetaclass
        ...     _state_vars = [('x',0.0,"Real part"),
        ...                    ('y',0.0,"Imaginary part")]
        >>> class Quaternion(Complex):
        ...     "Quaternions"
        ...     _state_vars = dict(z=0.0,t=0.0)    
        >>> help(Complex)       #doctest: +ELLIPSIS
        Help on class Complex in module ...:
        <BLANKLINE>
        class Complex(__builtin__.object)
         |  Complex numbers
         |  
         |  Complex(x=0.0,y=0.0)
         |  
         |  State Variables:
         |      x: Real part
         |      y: Imaginary part
        ...
        >>> help(Quaternion)    #doctest: +ELLIPSIS
        Help on class Quaternion in module ...:
        <BLANKLINE>
        class Quaternion(Complex)
         |  Quaternions
         |  
         |  Quaternion(x=0.0,y=0.0,z=0.0,t=0.0)
         |  
         |  State Variables:
         |      x: Real part
         |      y: Imaginary part
         |      z: <no description>
         |      t: <no description>
        ...

        >>> class A(object):
        ...     __metaclass__ = StateVarMetaclass
        ...     _state_vars = ['a',('b',0.0),('c',1.0,"A variable")]
        ...     _exclude_vars = ['big_var_a']
        >>> help(A)     #doctest: +ELLIPSIS
        Help on class A in module ...:
        <BLANKLINE>
        class A(__builtin__.object)
         |  A(a=,b=0.0,c=1.0)
         |  
         |  State Variables:
         |      a: <no description>
         |      b: <no description>
         |      c: A variable
        ...
        >>> class B(A):
        ...     _state_vars = {
        ...         ('d',
        ...          '''A very long description that we break over lines
        ...          to see how it works'''):5,
        ...         ('e','A short description'):7}
        ...     _exclude_vars = ['big_var_b']
        >>> help(B)     #doctest: +ELLIPSIS
        Help on class B in module ...:
        <BLANKLINE>
        class B(A)
         |  B(a=,b=0.0,c=1.0,d=5,e=7)
         |  
         |  State Variables:
         |      a: <no description>
         |      b: <no description>
         |      c: A variable
         |      d: A very long description that we break over lines
         |           to see how it works
         |      e: A short description
        ...
        >>> B._exclude_vars
        set(['big_var_a', 'big_var_b'])
        """
        super(StateVarMetaclass,cls).__init__(name,bases,dict_)
        
        vars = None             # We do this to allow for no _state_vars
        exclude = None
        defaults = {}
        docs = {}
        for base in all_bases(cls):
            if (hasattr(base,'__metaclass__') and 
                base.__metaclass__ is StateVarMetaclass):
                if hasattr(base,'_state_vars'):
                    if vars is None:
                        vars = []
                    for (var,default,doc) in base._state_vars:
                        if var not in vars:
                            vars.append(var)
                        defaults[var] = default
                        docs[var] = doc
                if hasattr(base,'_exclude_vars'):
                    if exclude is None:
                        exclude = set()
                    exclude.update(base._exclude_vars)
        if hasattr(cls,'_state_vars'):
            if vars is None:
                vars = []
            state_vars = cls._state_vars
            if isinstance(state_vars,list):
                for l in state_vars:
                    default = NotImplemented
                    doc = _no_description
                    if isinstance(l,str):
                        var = l
                    elif isinstance(l,tuple):
                        var = l[0]
                        try:
                            default = l[1]
                            doc = l[2]
                        except IndexError:
                            pass
                    else:
                        raise TypeError(
                            '_state_var must be a list of strings or tuples')
                    if not isinstance(var,str):
                        raise TypeError('Name must be a string (got %s)'%\
                                        repr(var))
                    if var not in vars:
                        vars.append(var)
                    defaults[var] = default
                    docs[var] = doc                    
            elif isinstance(state_vars,dict):
                for key in state_vars:
                    default = NotImplemented
                    doc = _no_description
                    if isinstance(key,str):
                        var = key
                        default = state_vars[key]
                    elif isinstance(key,tuple) and len(key) == 2:
                        var = key[0]
                        doc = key[1]
                        default = state_vars[key]
                    else:
                        raise TypeError('Key must be name or (name,doc)'+
                                        ' (got %s)'%repr(key))
                    
                    if not isinstance(var,str):
                        raise TypeError('Name must be a string'+
                                        ' (got %s)'%repr(var))
                    if var not in vars:
                        vars.append(var)
                    defaults[var] = default
                    docs[var] = doc                    
            else:
                raise TypeError('_state_vars must be a list or dict')

        if hasattr(cls,'_exclude_vars'):
            if exclude is None:
                exclude = set()
            exclude.update(cls._exclude_vars)

        if exclude is not None:
            cls._exclude_vars = exclude

        if vars is not None:
            cls._state_vars = [(key,defaults[key],docs[key]) 
                               for key in vars]
            cls.__doc__ = cls._get__doc__(name,cls._state_vars)
        else:
            cls.__doc__ = cls._get__doc__(name)
    
    def _get__doc__(cls,name,state_vars=[]):
        """Return a formatted document string for the class."""
        args = []
        for (var,default,doc) in state_vars:
            if default is NotImplemented:
                args.append("%s="%var)
            else:
                args.append("%s=%s"%(var,repr(default)))
        args = ",".join(args)
        call = "%s(%s)"%(name,args)
        params = ["    %s: %s"%(name,doc)
                  for (name,default,doc) in state_vars]
        if 0 < len(params):
            params = "\n".join(["","State Variables:"] + params)
        else:
            params = ""
        
        if cls.__doc__ is not None:
            head = "\n".join([cls.__doc__,""])
        else:
            head = ""

        return("\n".join([head,call,params]))

class CalcObject(CopyConstruct):
    """My object class intended for calculations.

    1) Provides default pickling services __getstate__ and
       __setstate__.  These do the following:
       a) Check for an attribute _state_vars.  If present, then only
          these vars will be archived.
       b) Check for an attribute _exclude_vars.  If present, then these
          will be excluded from the state.
       c) The method initialize() will be called after __setstate__.
    2) Provides nice ouput functions.
    3) Provide descriptions of attributes in class __doc__.
    
    Note that state variables with names begining with underscores
    '_...' are always excluded unless explicitly included in
    _state_vars.

    _state_vars may be a dictionary with default values, or simply a
    list/set of variable names.

    Example:
    >>> class A(CalcObject):
    ...     _state_vars = [('x',10),
    ...                    ('y',100)]
    >>> a = A(x=1.0)
    >>> print a
    x=1.0
    y=100
    >>> a.y = 5
    >>> a
    A(y=5,x=1.0)
    >>> a.z = 6
    >>> a
    A(y=5,x=1.0)

    >>> class B(CalcObject):
    ...     _exclude_vars = ['LargeObject']
    ...     def initialize(self):
    ...         self.LargeObject = 'Elephant'
    >>> b = B(x=5,y=6)
    >>> b.z = 9
    >>> b.LargeObject
    'Elephant'
    >>> b
    B(y=6,x=5,z=9)
    >>> state = b.__getstate__()
    >>> c = B()
    >>> c
    B()
    >>> c.__setstate__(state)
    >>> c
    B(y=6,x=5,z=9)
    >>> print c
    x=5
    y=6
    z=9
    Excluded:
    LargeObject=Elephant
    >>> d = B(c)
    >>> d
    B(y=6,x=5,z=9)

    >>> class C(CalcObject):
    ...     _state_vars = [('x',1,'Parameter x'),
    ...                    ('y',2,'Parameter y')]
    >>> a = C()
    >>> a
    C(y=2,x=1)
    >>> b = C(z=3)
    Traceback (most recent call last):
        ...
    TypeError: z is an invalid keyword argument for <class 'mmf.objects._objects.C'>.
    >>> b = C(x=2,z=3,t=4)
    Traceback (most recent call last):
        ...
    TypeError: ['z', 't'] are invalid keyword arguments for <class 'mmf.objects._objects.C'>.

    One may also use a list rather than a dictionary:
    >>> class D(CalcObject):
    ...     _state_vars = ['x','y']
    >>> a = D(x=3)
    >>> a
    D(x=3)
    >>> a.y = 4
    >>> print a
    x=3
    y=4

    Note, you may use properties: just store the value in __dict__
    with the same name:
    >>> class E(CalcObject):
    ...     _state_vars = ['x','y']
    ...     def set_x(self,x):
    ...         self.__dict__['x'] = x
    ...         print "Setting x"
    ...     def get_x(self):
    ...         print "Getting x"
    ...         return self.__dict__['x']
    ...     x = property(get_x,set_x)
    >>> a = E(y=2)
    >>> a  # Even though x is not set, getattr is called by hasattr...
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

    def __init__(self,*varargin,**kwargs):
        """Set _state_vars and _exclude_vars by inheriting from base
        classes, then call CopyConstruct.__init__ to complete
        initialization.  Default values are also initialized here.

        Use this to 'inherit' state variables.
        >>> class A(CalcObject):
        ...     _state_vars = ['a','b']
        >>> class B(CalcObject):
        ...     _state_vars = {'c':1}
        >>> class C(A,B):
        ...     _state_vars = {'d':2}
        >>> class D(C):
        ...     _state_vars = {'r':Required}
        >>> c = C()
        >>> c
        C(c=1,d=2)
        >>> C.class_keys()
        ['a', 'b', 'c', 'd']
        >>> D(c=1,d=2)
        Traceback (most recent call last):
            ...
        ValueError: Required attribute 'r' not defined.
        """
        self._initializing = True
        required_keys = []
        if hasattr(self,'_state_vars'):
            for (key,default,doc) in self._state_vars:
                if default is NotImplemented:
                    pass
                elif default is Required:
                    required_keys.append(key)
                else:
                    setattr(self,key,default)

        CopyConstruct.__init__(self,*varargin,**kwargs)
        for key in required_keys:
            if not hasattr(self,key):
                raise ValueError("Required attribute '%s' not defined."%key)
        self._initializing = False

    def _copy(self,obj):
        """Copy constructor.  Only copies stateful information"""
        self._init_attrs(dict(obj.items()))

    def _init(self,**kwargs):
        """Default constructor.  Accepts and sets all members
        specified in _state_vars.  Calls initialize().
        
        Constructors should accept keyword arguments for all
        _state_vars but may accept other arguments.  The default,
        however, does not accept kwargs not specified in _state_vars
        if it is defined."""
        self._init_attrs(kwargs)
        self.initialize()

    def _init_attrs(self,kwargs):
        """Initialize attributes from kwargs including only specified
        variables."""
        if hasattr(self,'_state_vars'):
            _state_vars = self._state_vars
            for (var,default,doc) in _state_vars:
                if var in kwargs:
                    setattr(self,var,kwargs.pop(var))
            if len(kwargs) == 1:
                raise TypeError(
                    "%s is an invalid keyword argument for %s."%\
                        (str(kwargs.keys()[0]),self.__class__))
            elif len(kwargs) > 1:
                raise TypeError(
                    "%s are invalid keyword arguments for %s."%\
                        (str(kwargs.keys()),self.__class__))
        else:
            # No _state_vars, so just update from initial arguments.
            for k in kwargs:
                setattr(self,k,kwargs[k])

    def initialize(self):
        """This should perform any initializations required apart from
        directly computing and setting state variables.

        Anything that will not be returned by __getstate__ needs to be
        recomputed here.

        This version does nothing.
        """
        pass

    def __getstate__(self):
        """Return a representation of the function object in a form
        that is picklable.
        
        a) Check for an attribute _state_vars.  If present, then only
           these vars will be archived.
        b) Check for an attribute _exclude_vars.  If present, then these
           will be excluded from the state.
        """
        return dict((k,getattr(self,k)) for k in self.included_keys())
    
    def __setstate__(self,state):
        """Initialize the function from state as returned by
        __getstate__.

        The method initialize() will be called after __setstate__.
        """
        self.__init__(**state)
        self.initialize()


    @classmethod
    def get_args(cls,*varargin,**kwargs):
        """Return the dictionary that is a subset of kwargs containing
        the valid keyword arguments for the current object.

        >>> class A(CalcObject):
        ...     _state_vars = ['a','b']
        >>> class B(CalcObject):
        ...     _state_vars = ['c','d']
        >>> def f(**kwargs):
        ...     a = A(A.get_args(kwargs))
        ...     b = B(B.get_args(kwargs))
        ...     return a,b
        >>> a,b = f(a=1,b=2,c=3,d=4)
        >>> a,b
        (A(a=1,b=2), B(c=3,d=4))

        >>> CalcObject(CalcObject.get_args(a=1,b=2))
        CalcObject(a=1,b=2)
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
            return get_args(kwargs,class_keys)
            

    @classmethod
    def class_keys(cls):
        """Return the keys accepted by the constructor."""
        try:
            include = [var for (var,default,doc) in cls._state_vars]
        except AttributeError:
            include = []

        # Make include contain only one of each variable.
        include_set = set(include)
        include = [var for var in include 
                   if var in include_set
                   and not include_set.remove(var)]
        return include
        
    def included_keys(self):
        """Return set of keys to be included for archiving."""
        # Use _state_vars if defined, otherwise use __dict__
        try:
            include = [var for (var,default,doc) in self._state_vars]
        except AttributeError:
            include = [k for k in self.__dict__.keys() 
                       if k[0] != '_']
            include.sort()

        include = [k for k in include 
                   if hasattr(self,k)]

        # Exclude specified variables
        try:
            exclude = set(self._exclude_vars)
        except AttributeError:
            exclude = set([])

        # Make include contain only one of each variable.
        include_set = set(include) - exclude
        include = [var for var in include 
                   if var in include_set
                   and not include_set.remove(var)]
        return include

    def items(self):
        """Return a list of (key,value) pairs defining the persistant
        state of the object."""
        return self.__getstate__().items()
        
    def __str__(self):
        """Pretty print state, including temporaries.  Print order is
        sorted."""
        included_keys = list(self.included_keys())
        excluded_keys = [k for k in self.__dict__ 
                         if (k not in included_keys and
                             k[0] is not '_')]
        excluded_keys.sort()
        res = "\n".join(["%s=%s"%(k,str(getattr(self,k))) 
                         for k in included_keys])
        if 0 < len(excluded_keys):
            res = "\n".join([res,
                             'Excluded:']
                            +["%s=%s"%(k,str(getattr(self,k)))
                              for k in excluded_keys
                              if k[0] is not '_'])
        return res

class attribute(property): # Need to be a property so help works
    """Attribute class: like property, but with default operators.

    One way to use is to directly make a property with documentation
    and a default value:

    x = attribute(default=1.0,doc='x-coordinate')

    Another way is as a decorator:

    @attribute
    def x(self):
        'x-coordinate'
        return 1.0

    EXAMPLES:
    >>> class Data(object):
    ...     x = attribute(default=1.0,doc='x-coordinate')
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
    def __init__(self,func=None,default=None,doc=""):
        """Initialization."""
        if func is None:
            self.value = default
            self.__doc__ = doc
        else:
            self.value = func(self)
            self.__doc__ = func.__doc__       
    
    def __get__(self,obj,objtype=None):
        if obj is None:
            return self         # Needed so that help facility works
        return self.value

    def __set__(self,obj,value):
        self.value = value

class parameter(property):
    """Parameter class: Turns a function into a parameter.  

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
    def __init__(self,f):
        self.f = f
        self.__name__ = f.__name__
        self.__doc__ = f.__doc__
        if self.__doc__ is None:
            self.__doc__ = ""
    
    def __get__(self,obj,objtype=None):
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

    def __set__(self,obj,value):
        name = self.__name__
        if isinstance(obj,MemoizedContainer):
            if value != obj[name]:
                obj[name] = value
                obj._changed(name)
        else:
            obj.__dict__[name] = value

class calculate(property):
    """Decorator for calculational functions that should be
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
    def __init__(self,f):
        self.f = f
        self.__name__ = f.__name__
        self.args = f.func_code.co_varnames[:f.func_code.co_argcount]
        if f.__doc__ is not None:
            self.__doc__ = "Calculated: " + f.__doc__
        else:
            self.__doc__ = "Calculated: "
    
    def __get__(self,obj,objtype=None):
        if obj is None:
            value = self                # Needed so that help facility works
        elif isinstance(obj,MemoizedContainer):
            value = obj[self.__name__]
            if value is None:   # Need to recompute
                #kw = {}
                #for n in self.args:
                #    kw[n] = getattr(obj,n)
                #value = self.f(**kw)
                value = self.f(*map(lambda n:getattr(obj,n),self.args))
            obj[self.__name__] = value
        else:
            value = self.f(*map(lambda n:getattr(obj,n),self.args))
        return value

    def __set__(self,obj,value):
        raise AttributeError("can't set attribute")

class MemoizedContainer(dict):
    """The paradigm for this class is that one has a set of parameters
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
    ...     def g(x,f,y):
    ...         "Product of x*f*y = x**3*y"
    ...         print "Computing g("+`x`+","+`f`+","+`y`+")"
    ...         tmp = x*f*y
    ...         return tmp
    >>> d = Data1(y=2.0)
    >>> d.f                     # slow
    Computing f(10.0)
    100.0
    >>> d.f                     # fast
    100.0
    >>> d.g                     # slow
    Computing g(10.0,100.0,2.0)
    2000.0
    >>> d.g                     # fast
    2000.0
    >>> d.y = 3.0
    >>> d.f                     # fast
    100.0
    >>> d.g                     # slow
    Computing g(10.0,100.0,3.0)
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
    >>> class Data3(Data1,Data2):
    ...     @parameter
    ...     def c():
    ...         return 2.0
    ...     @calculate
    ...     def F(c,f,g,h):
    ...         print "Computing F("+`c`+","+`f`+","+`g`+","+`h`+")"
    ...         return c+f*g*h
    >>> class Data(Data3):
    ...     pass
    >>> d = Data()
    >>> d.F
    Computing f(10.0)
    Computing g(10.0,100.0,2.0)
    Computing h(-1.0)
    Computing F(2.0,100.0,2000.0,-1.0)
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
    def __new__(cls,*argv,**kwargs):
        """Return a new instance.  This method also updates the
        class dependencies dictionary.
        """
        self = dict.__new__(cls)
        try:
            cls.initilized
        except:
            cls.initialized = False
            cls.parameters = {}
            cls.calculators = {}
            cls.dependencies = {}   # Dependencies are maintained at the
                                    # class level.
        if not cls.initialized:
            dicts = [cls.__dict__]
            for base in all_bases(cls):
                dicts.append(base.__dict__)
            for dict_ in dicts:
                for (name,attr) in dict_.items():
                    if isinstance(attr,parameter):
                        cls.parameters[name] = attr
                        if not name in cls.dependencies:
                            cls.dependencies[name] = set()
                    if isinstance(attr,calculate):
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
            
    def __init__(self,*argv,**kwargs):
        dict.__init__(self,*argv,**kwargs)
        for p in self.__class__.parameters:
            if not p in self:
                self[p] = self.__class__.parameters[p].f()
        for c in self.__class__.calculators:
            # Initialize calculators to be empty.
            self[c] = None
        
    def _changed(self,name):
        """Called by parameter properties when they are modified.
        This updates the dependency dictionary so that functions will
        recompute their memoized values as needed.
        """
        for dep in self.__class__.dependencies[name]:
            self[dep] = None
            self._changed(dep)

class Calculator:
    """This class represents some data and values that must be
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
    >>> class E(C,D):
    ...     def calculate(self):
    ...         C.calculate(self)
    ...         D.calculate(self)
    >>> c = C()
    >>> c.x = 2.0
    >>> c.y = 3.0
    >>> d = D(z=5.0)
    >>> e = E(c,d)
    >>> e.calculate()
    >>> e.a
    4.0
    >>> e.b
    24.0
    >>> e.c
    125.0
    >>> e
    E(y=3.0,x=2.0,z=5.0)
    """

    def _initialize_parameters(self):
        """Find all parameters and initialize them to their default
        values.  Return class dictionary of parameters."""
        cls = self.__class__
        if not 'parameters' in cls.__dict__:
            cls.parameters = {}

        dicts = [cls.__dict__]
        for base in all_bases(cls):
            dicts.append(base.__dict__)
        for dict_ in dicts:
            for (name,attr) in dict_.items():
                if isinstance(attr,parameter):
                    cls.parameters[name] = attr
#        [[cls.parameters.__setattr__(name,attr) for (name,attr) in\
#          dict_.items() if isinstance(attr,parameter)] for dict_ in dicts]
        return cls.parameters
            
    def __init__(self,*argv,**kwargs):
        initial_values = {}
        for obj in [a for a in argv if isinstance(a,Calculator)]:
            for p in obj.__class__.parameters :
                initial_values[p] = getattr(obj,p)
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
        """Return representation of object.
        """
        repr = self.__class__.__name__+"("
        for p in self.__class__.parameters:
            repr = repr + p + "=" + `getattr(self,p)` + ","
        return repr[:-1]+")"

class metaO(type):
    def __new__(meta, clsname, bases, attrs):
        for name, attr in attrs.items():
            if isinstance(attr, attribute):
                attrs[name] = newreadonlyprop(clsname, name, attr)
        return super(metaO, meta).__new__(meta, clsname, 
                                                bases, attrs)

class O(object):
    """A simple class to allow for attribute creation with documentation.

    >> class Coord(O):
    ...     x = attribute(default=0,
    ...                   doc='x-coordinate')
    ...     y = attribute(default=0,
    ...                   doc='y-coordinate')
    >> c = Coord(x=1,y=2)
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
    """
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
    def __init__(self,func=None,doc=None,default=None):
        if func is not None:
            if doc is None:
                doc = func.__doc__
            if default is None:
                default = func()
        if doc is None:
            doc = "Undocumented Option"
        self.__doc = doc
        self.__set__(self,default)
        
        
    def __get__(self,obj,type_):
        if obj is None:
            return self
        return self.__value
    
    def __set__(self,obj,value):
        if value is None:
            self.__value = None
        else:
            self.__value = type("OptionOfType_%s"%(type(value).__name__),
                                (type(value),), 
                                {'__doc__': self.__doc})(value)
    def __repr__(self):
        return "option(default=" + \
               repr(self.__value) + \
               ",doc=" + \
               repr(self.__doc) + ")"

    def __str__(self):
        return str(self.__value)
    
class Options(object):
    """Options class.  This class acts as a container.  It provides
    methods to display the members.  One can also define member
    functions, but their names must start with an underscore: all
    non-underscored names are assumed to be 'options'.

    The values defined in the base class are used as defaults.  They
    will be deepcopied for each instance.  Note that this means
    recursive data should not be used for parameters.

    Use in conjunction with the option decorator to provide
    documentation for the options.

    EXAMPLES:
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
       >>> d2 = Options(x=3,y=4)
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
    def __init__(self,c=None,**kwargs):
        """
        """
        for (k,i) in self.__class__.__dict__.items():
            # Add copies of of all class members that don't start with
            # an underscore
            if "_" != k[0]:
                self._add(key=k,value=deepcopy(i))
        if type(c) is list:
            for k in c:
                self._add(key=k)
        elif type(c) is dict:
            for k in c:
                self._add(key=k,value=c[k])
        for k in kwargs:
            self._add(key=k,value=kwargs[k])

    def __getitem__(self,name):
        """Provide item access."""
        return self.__dict__[name]

    def __setitem__(self,name,value):
        """Provide item access."""
        self.__setattr__(name,value)

    def _add(self,key,value=None):
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

    def _getOptions(self,prefix=None,opts=None,items=None):
        """Return complete list of options and values including all
        sub-options.

        >>> d = Options({'x':3,'y':4,'cc.x':5,'cc.y':6})
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
            if isinstance(item,Options):
                item._getOptions(prefix=newPrefix,
                                 opts=opts_opts,
                                 items=opts_items)
            else:
                opts.append(newPrefix)
                items.append(item)
        opts += opts_opts
        items += opts_items
        return (opts,items)

    def __setattr__(self,name,value):
        """Only allow defined options to be set."""
        if name in self.__dict__:
            object.__setattr__(self,name,value)
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
        (opts,items) = self._getOptions()
        lines = [dummyName+"="+self.__class__.__name__+"("+`opts`+")"]
        (opts,items) = self._getOptions(prefix=dummyName)
        lines += [k+"="+str(i) for (k,i) in zip(opts,items)]
        return "\n".join(lines)

def recview(a,names,formats=None,dtype=None):
    """Return a view of a as a recarray with defined field names.

    >>> from numpy import array
    >>> a = array([[1,2,3],[4,5,6]])
    >>> r = recview(a,['x', 'y', 'z'])
    >>> print r
    [[(1, 2, 3)]
     [(4, 5, 6)]]
    >>> r.x = 0
    >>> a
    array([[0, 2, 3],
           [0, 5, 6]])
    """
    r = numpy.rec.fromrecords(a,names=names)
    return a.view(r.dtype).view(numpy.rec.recarray)


class RecView(numpy.recarray):
    """A simple subclass of the numpy recarray record array class that
    provides automatic conversion to a recarray.  To subclass, simply
    define _names as a list of the field names and _array as a default
    array.

    >>> from numpy import array
    >>> class Coord(RecView):
    ...     _array = array([1.0,2.0])
    ...     _names = ['x', 'y']
    >>> c = Coord()
    >>> c.x
    array([ 1.])
    """
    def __new__(cls,record=None):
        """
        """
        if record is None:
            record = cls._array
        if 1 == record.ndim:
            record = [record]
        self = numpy.rec.fromrecords(record,names=cls._names).view(cls)
        return self

def class_NamedArray(array_,names=None):
    """Return a class that is a subclass of array_.__class__ but that
    allows the elements to be accessed through a named member syntax.

    For example, if array_=array([1.0,2.0]) and names=array(['x', 'y'])
    then c[0] == c.x, and c[1]==c.y

    The preferred usage is to define a class which inherits from the
    returned class.  The arguments will then defined the names and the
    default values for objects instantiated from this class.  The
    advantage of proceeding this way is that the name of the class
    will be well defined and usefull rather than the generic "NamedArray".
    
    >>> from numpy import array
    >>> a = array([0.0,0.0,0.0])
    >>> n = array(['x', 'y', 'z'])
    >>> class CoordArray(class_NamedArray(a,n)): 
    ...     pass
    >>> c0 = CoordArray()
    >>> c0
    CoordArray([ 0.,  0.,  0.])

    You can initialize the array from a sequence, and use keyword
    arguments to set specific values.  If you do not initialize, then
    the default values are used.  The initialization array need not be
    complete: it just initializes the first n values.
    >>> c = CoordArray([1,3],y=2)
    >>> c
    CoordArray([ 1.,  2.,  0.])
    >>> (c.x,c.y)
    (CoordArray([ 1.]), CoordArray([ 2.]))
    >>> c.x = 3; c.y = 4
    >>> print c
    CoordArray(y=4.0,x=3.0,z=0.0)
    
    Note that one may have repeated labels:
    
    >>> a = array([[0,0],[0,0]])
    >>> n = array([['x', 'y'],['y', 'z']])
    >>> class MatArray(class_NamedArray(a,n)): 
    ...     pass
    >>> c = MatArray(x=1,y=2,z=3)
    >>> c
    MatArray([[1, 2],
           [2, 3]])
    >>> c.y
    MatArray([2, 2])
    >>> c.y = [4,5]
    >>> c
    MatArray([[1, 4],
           [5, 3]])


    >>> a = array([0,0,0])
    >>> n = array(['x', 'y', 'z'])
    >>> class MatArray(class_NamedArray(a,n)): 
    ...     pass
    >>> c = MatArray(vals=[1,2,3])
    >>> c
    MatArray([1, 2, 3])
    >>> c.t = 6
    >>> c.t
    6
    """
    base_class = array_.__class__
    fields = {}
    for n in numpy.unique1d(names.ravel()):
        fields[n] = numpy.where(n == names)
            
    class NamedArray(base_class):
        __slots__ = []
        _array = array_
        _type = base_class
        _fields = fields

        def __new__(cls,vals=None,**kwargs):
            """Return an initialized instance of a NamedArray object.
            
            vals: an interable object of proper length to assign should 
            self = __new__(cls,vals)
            """
            self = cls._type.__new__(cls,
                                     shape=cls._array.shape,
                                     dtype=cls._array.dtype)
            self[:] = cls._array
            if vals is not None:
                self[0:len(vals)] = vals

            for k in kwargs:
                self.__setattr__(k,kwargs[k])

            return self

        def __getattr__(self,name):
            """Get the value of the named parameter.

            c.x is equivalent to c[c._names['x']]
            """
            try:
                return self[self._fields[name]]
            except:
                return self._type.__getattribute__(self,name)

        def __setattr__(self,name,value):
            """Set the value of the named parameter.

            c.x is equivalent to c[c._names['x']]
            """
            try:
                self[self._fields[name]] = value
            except:
                self._type.__setattr__(self,name,value)

        def __str__(self):
            """Print the array nicely using the keyword syntax."""
            ans = self.__class__.__name__ + "("
            for key in self._fields:
                value = self[self._fields[key]]
                if 1 == numpy.prod(value.size):
                    value = value.ravel()[0]
                ans = ans + key + "=" + `value` + ","
            ans = ans[:-1]+")"
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
Main Window Size: (540,400) 

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
    def __init__(self,name,default=None,doc=None,
                 section=None,type_=None):
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
        self.__set__(self,default)
        
    def __get__(self,obj,type_=None):
        if obj is None:
            return self
        return self.__value
    
    def __set__(self,obj,value):
        self.__value = type("MemberOfType_%s"%(type(value).__name__),
                            (type(value),), 
                            {'__doc__': self.__doc})(value)



class Resources(object):
    """Class to represent a collection of resources.

    >> class WindowResources(Resources):
    ...     size = Resource("Main Window Size",
    ...                     (540,400),
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
    >>> class C(object):
    ...     __metaclass__ = StateVarMetaclass
    ...     _state_vars = 3
    Traceback (most recent call last):
        ...
    TypeError: _state_vars must be a list or dict

    >>> class C(object):
    ...     __metaclass__ = StateVarMetaclass
    ...     _state_vars = [1,2,3]
    Traceback (most recent call last):
        ...
    TypeError: _state_var must be a list of strings or tuples

    >>> class C(object):
    ...     __metaclass__ = StateVarMetaclass
    ...     _state_vars = ['a',(3,2)]
    Traceback (most recent call last):
        ...
    TypeError: Name must be a string (got 3)

    >>> class C(object):
    ...     __metaclass__ = StateVarMetaclass
    ...     _state_vars = {('a',3,4):5}
    Traceback (most recent call last):
        ...
    TypeError: Key must be name or (name,doc) (got ('a', 3, 4))

    >>> class C(object):
    ...     __metaclass__ = StateVarMetaclass
    ...     _state_vars = {(1,3):5}
    Traceback (most recent call last):
        ...
    TypeError: Name must be a string (got 1)

    >>> class C(object):
    ...     __metaclass__ = StateVarMetaclass
    >>> help(C)                 #doctest: +ELLIPSIS
    Help on class C in module ...:
    <BLANKLINE>
    class C(__builtin__.object)
     |  C()
    ...
    """
# Testing
import mmf_test
mmf_test.defineModuleTests(__name__,__file__,locals())
