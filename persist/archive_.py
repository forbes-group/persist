r"""This is an idea for a model of objects that save their state.
Here is a typical usage:

>>> a = Archive()
>>> a.insert(x=3)
'x'
>>> a.insert(y=4)
'y'
>>> s = str(a)

Here you could write to a file::

   f = open('file.py', 'w')
   f.write(s)
   f.close()

And after you could read from the file again::

   f = open('file.py')
   s = f.read()
   f.close()

Now we can restore the archive:
   
>>> d = {}
>>> exec(s, d)
>>> d['x']
3
>>> d['y']
4

Objects can aid this by implementing an archive method, for example::

    def archive_1(self):
        '''Return (rep, args, imports) where obj can be reconstructed
        from the string rep evaluated in the context of args with the
        specified imports = list of (module, iname, uiname) where one
        has either "import module as uiname", "from module import
        iname" or "from module import iname as uiname".
        '''
        args = [('a', self.a), ('b', self.b), ...]

        module = self.__class__.__module__
        name = self.__class__.__name__
        imports = [(module, name, name)]

        keyvals = ["=".join((k, k)) for (k, v) in args]
        rep = "%s(%s)"%(name, ", ".join(keyvals))
        return (rep, args, imports)

The idea is to save state in a file that looks like the following::

   import numpy as _numpy
   a = _numpy.array([1, 2, 3])
   del _numpy

.. note::
   When you want to execute the string, always pass an execution
   context to unpack:

   >>> a = Archive()
   >>> a.insert(x=3)
   'x'
   >>> s = str(a)
   >>> d = {}
   >>> exec(s, d)
   >>> d['x']
   3

   If you just execute the code, it will attempt to delete the
   '__builtins__' module (so as not to clutter the dictionary) and may
   render the interpreter unusable!
   
.. todo::
   - Graph reduction occurs for nodes that have more than one parent.
     This does not consider the possibility that a single node may
     refer to the same object several times.  This has to be examined
     so that non-reducible nodes are not reduced (see the test case
     which fails).
   - :func:`_replace_rep` is stupid (it just does text replacements).
     Make it smart.  Maybe use a refactoring library like :mod:`rope`...
     If this is hard, then the data-file might have to redefine the
     environment locally before each rep.   This would be a pain but
     not impossible.
   - It would be nice to be able to use `import A.B` and then just use
     the name `A.B.x`, `A.B.y` etc.  However, the name `A` could clash
     with other symbols, and it cannot be renamed (i.e. `import A_1.B`
     would not work).  To avoid name clashes, we always use either
     `import A.B as B` or the `from A.B import x` forms which can be
     renamed.
   - Maybe allow rep's to be suites for objects that require construction
     and initialization.  (Could also allow a special method to be called
     to restore the object such as `restore()`.)
"""
__all__  = ['Archive', 'DataSet', 'restore', 'ArchiveError',
            'DuplicateError']

import os
import sys
import string
import parser
import compiler
import token
import symbol
import functools
import inspect
import copy
import textwrap
import __builtin__
import re
import types

import numpy as np
import scipy as sp
import scipy.sparse

import contrib.RADLogic.topsort as topsort

import mmf.utils
import mmf.interfaces as interfaces

class ArchiveError(Exception):
    r"""Archiving error."""

class CycleError(ArchiveError):
    r"""Cycle found in archive."""
    def __init__(self, *v):
        if 0 < len(v):
            self.message = v[0]
    def __str__(self):
        return self.message
    def __repr__(self):
        return repr(self.args)
    
class DuplicateError(ArchiveError):
    r"""Object already exists."""
    def __init__(self, name):
        msg = "Object with name %r already exists in archive."%name
        ArchiveError.__init__(self, msg)

def restore(archive, env={}):
    r"""Return dictionary obtained by evaluating the string arch.
    
    arch is typically returned by converting an Archive instance into
    a string using :func:`str` or :func:`repr`:

    Examples
    --------
    >>> a = Archive()
    >>> a.insert(a=1, b=2)
    ['a', 'b']
    >>> arch = str(a)
    >>> d = restore(arch)
    >>> print "%(a)i, %(b)i"%d
    1, 2
    """
    ld = {}
    ld.update(env)
    exec(archive, ld)
    return ld

class Archive(object):
    r"""Archival tool.
    
    Maintains a list of symbols to import in order to reconstruct the
    states of objects and contains methods to convert objects to
    strings for archival.

    Attributes
    ----------
    arch : list
       List of `(uname, obj, env)` where `obj` is the object, which
       can be rescontructed from the string `rep` evaluated in the
       context of `args`, `imports`, and `env`.
    ids : dict
       Dictionary mapping names to id's.  If the name corresponds to a
       module, then this is `None`.
    flat : bool, optional
       If `True`, then
    tostring : True, False, optional
       If `True`, then use :meth:`numpy.ndarray.tostring` to
       format numpy strings.  This is more robust, but not
       human-readable and may be larger.
    check_in_insert : False, True, optional
       If `True`, then try to make string representation of each
       object on insertion to allow for early catching of errors.
    datafile : None, str, optional
       If provided, then numpy arrays longer than `array_threshold`
       are archived in binary to this file.  (See also `pytables`).
    pytables : True, False, optional
       If `True` and `datafile` is provided, then use PyTables to
       store the binary data.
    array_threshold : int, optional
       If `datafile` is provided, then numpy arrays with more than
       this many elements will be stored in the data file.
       
    Notes
    -----
    A required invariant is that all `uname` be unique.
    """
    def __init__(self, flat=True, tostring=True,
                 check_on_insert=False,
                 datafile=None, pytables=True,
                 array_threshold=50):
        self.tostring = tostring
        self.flat = flat
        self.imports = []
        self.arch = []
        self.ids = {}

        self._section_sep = ""  # string to separate the sections
        self._numpy_printoptions = {'infstr': 'Inf',
                                    'threshold': np.inf,
                                    'suppress': False,
                                    'linewidth': 200,
                                    'edgeitems': 3,
                                    'precision': 16,
                                    'nanstr': 'NaN'}
        self.check_on_insert = check_on_insert
        self.datafile = datafile
        self.pytables = pytables
        self.array_threshold = array_threshold

    def names(self):
        r"""Return list of unique names in the archive."""
        return [k[0] for k in self.arch]
    
    def archive_1(self, obj, env):
        r"""Return `(rep, args, imports)` where `obj` can be reconstructed
        from the string `rep` evaluated in the context of `args` with the
        specified `imports` = list of `(module, iname, uiname)` where one
        has either `import module as uiname`, `from module import
        iname` or `from module import iname as uiname`.
        """
        if isinstance(obj, interfaces.IArchivable):
            return obj.archive_1(env)

        for class_ in self._dispatch:
            if isinstance(obj, class_):
                return self._dispatch[class_](self, obj, env=env)

        if inspect.isclass(obj):
            return archive_1_obj(obj, env)

        if inspect.ismethod(obj):
            return archive_1_method(obj, env)

        if hasattr(obj, 'archive_1'):
            try:
                return obj.archive_1(env)
            except TypeError:   # pragma: no cover
                1+1             # Needed to deal with coverage bug
        
        return archive_1_repr(obj, env)

    def _archive_ndarray(self, obj, env):
        """Archival of numpy arrays."""
        if (self.datafile is not None
            and self.array_threshold < np.prod(obj.shape)):
            # Data should be archived to a data file.
            if self.pytables:
                import tables
                f = tables.openFile(self.datafile, 'a')
                name = 'array_%i'
                i = 0
                while (name % (i,)) in f.root._v_children.keys():
                    i += 1
                name = name %(i,)
                f.createArray(f.root, name, obj)
                f.close()
                rep = (("(lambda t: (t.root.%s.read(), t.close())[0])"
                        + "(tables.openFile(%r,'r'))") %
                       (name, self.datafile))
                imports = [('tables', None, 'tables')]
                args = []
            else:
                raise NotImplementedError    
        elif (self.tostring
            and obj.__class__ is np.ndarray
            and not obj.dtype.hasobject):
            
            rep = "numpy.fromstring(%r, dtype=%r).reshape(%s)" % (
                obj.tostring(), obj.dtype.str, str(obj.shape))
            imports = [('numpy', None, 'numpy')]
            args = []
        else:
            popts = np.get_printoptions()
            np.set_printoptions(**(self._numpy_printoptions))
            rep = repr(obj)
            np.set_printoptions(**popts)

            module = inspect.getmodule(obj.__class__)

            # Import A.B.C as C
            iname = module.__name__
            mname = iname.rpartition('.')[-1]
        
            constructor = rep.partition("(")[0]
            if not constructor.startswith(mname):
                rep = ".".join([mname, rep])
        
            imports = [(iname, None, mname),
                       ('numpy', 'inf', 'inf'),
                       ('numpy', 'inf', 'Infinity'),
                       ('numpy', 'inf', 'Inf'),
                       ('numpy', 'inf', 'infty'),
                       ('numpy', 'nan', 'nan'),
                       ('numpy', 'nan', 'NaN'),
                       ('numpy', 'nan', 'NAN')]
            args = []
        return (rep, args, imports)

    def _archive_spmatrix(self, obj, env):
        if (sp.sparse.isspmatrix_csc(obj) or
            sp.sparse.isspmatrix_csr(obj) or
            sp.sparse.isspmatrix_bsr(obj)):
            args = (obj.data, obj.indices, obj.indptr)
        elif sp.sparse.isspmatrix_dia(obj):
            args = (obj.data, obj.offsets)
        else:
            raise NotImplementedError(obj.__class__.__name__)

        class_name = obj.__class__.__name__
        imports = [('scipy.sparse', class_name, class_name)]
        rep = '%s(args, shape=%s)' % (class_name, str(obj.shape))
        return (rep, [('args', args)], imports)

    def _archive_func(self, obj, env):
        r"""Attempt to archive the func."""
        return archive_1_obj(obj, env)

    def _archive_list(self, obj, env):
        return archive_1_list(obj, env)

    def _archive_tuple(self, obj, env):
        return archive_1_tuple(obj, env)

    def _archive_dict(self, obj, env):
        return archive_1_dict(obj, env)

    def _archive_float(self, obj, env):
        return archive_1_float(obj, env)

    def _archive_type(self, obj, env):
        return archive_1_type(obj, env)
        
    _dispatch = {
        sp.sparse.base.spmatrix:_archive_spmatrix,
        np.ndarray:_archive_ndarray,
        np.ufunc:_archive_func,
        types.BuiltinFunctionType:_archive_func,
        list:_archive_list,
        tuple:_archive_tuple,
        dict:_archive_dict,
        float:_archive_float,
        complex:_archive_float,
        type:_archive_type}
        
    def unique_name(self, name):
        r"""Return a unique name not contained in the archive."""
        names = _unzip(self.arch)[0]
        return _get_unique(name, names)

    def insert(self, env=None, **kwargs):
        r"""`res = insert(name=obj)` or `res = insert(obj)`: Add the
        `obj` to archive and return a list of `(uname, obj)` pairs.

        If `self.check_on_insert`, then try generating rep (may raise
        an exception).

        If name already exists in the archive, then a DuplicateError
        exception is thrown.

        Parameters
        ----------
        <name> : obj
           Insert `obj` with desired name into the archive.  Name
           cannot be `'env'` and must not start with an underscore
           (these are used for private variables.)
        env : dict, optional
           Dictionary used to resolve names found in repr strings
           (using repr is the last resort option).

        Returns
        -------
        uname : str
           Unique name used to refer to the object.
        obj : object
           The object

        Raises
        ------
        DuplicateError
           If unique is False and name is already in the archive.
        ArchiveError
           If there is a problem archiving an object.

        Examples
        --------
        >>> a = Archive()
        >>> a.insert(x=2)
        'x'
        >>> a.insert(x=2)       # Duplicates are okay.
        'x'
        >>> a.insert(x=3)       # Changes are not...
        Traceback (most recent call last):
           ...
        DuplicateError: Object with name 'x' already exists in archive.
        >>> a.insert(**{a.unique_name('x'):3}) # ...but can make unique label
        'x_1'
        >>> a.insert(a=4, b=5)   # Can insert multiple items
        ['a', 'b']
        >>> a.insert(A=np.array([1, 2, 3]))
        'A'
        >>> print a
        import numpy as _numpy
        x_1 = 3
        a = 4
        A = _numpy.fromstring('\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00', dtype='<i4').reshape((3,))
        x = 2
        b = 5
        del _numpy
        try: del __builtins__
        except NameError: pass

        The default :mod:`numpy` representation for arrays is not very
        friendly, so we might want to use strings instead.  Be aware
        that this might incur a performance hit.
        
        >>> a = Archive(tostring=False)
        >>> a.insert(x=2)
        'x'
        >>> a.insert(A=np.array([1, 2, 3]))
        'A'
        >>> c = np.array([1, 2.0+3j, 3])
        >>> a.insert(c=c)
        'c'
        >>> a.insert(cc=[c, c, [3]])
        'cc'
        >>> a.make_persistent() # doctest: +NORMALIZE_WHITESPACE
        ([('numpy', None, '_numpy'),
          ('numpy', 'inf', '_inf'),
          ('numpy', 'nan', '_nan')],
         [('c', '_numpy.array([ 1.+0.j,  2.+3.j,  3.+0.j])'),
          ('cc', '[c, c, [3]]'),
          ('A', '_numpy.array([1, 2, 3])'),
          ('x', '2')])
        """
        if env is None:
            env = {}

        names = []
        for name in kwargs:
            obj = kwargs[name]
            if name.startswith('_'):
                raise ValueError("name must not start with '_'")

            # First check to see if object is already in archive:
            unames, objs, envs = _unzip(self.arch)
            try:
                ind_obj = objs.index(obj)
            except ValueError:
                ind_obj = None

            try:
                ind_name = unames.index(name)
            except ValueError:
                ind_name = None

            ind = None
            if ind_name is not None:
                # Name already in archive
                if ind_name == ind_obj:
                    ind = ind_name
                else:
                    raise DuplicateError(name)
            else:
                uname = name
            
            if ind is not None:
                # Object already in archive.  We are done
                pass
            else:
                if self.check_on_insert:
                    (rep, args, imports) = self.archive_1(obj, env)

                self.arch.append((uname, obj, env))
                ind = len(self.arch) - 1
                
            assert(ind is not None)
            uname, obj, env = self.arch[ind]
            names.append(uname)            
            self.ids[uname] = id(obj)

        if 1 < len(names):
            return names
        elif 1 == len(names):
            return names[0]
        else:                   # pragma: no cover
            return None

    def make_persistent(self):
        r"""Return `(imports, defs)` representing the persistent
        version of the archive.
        
        Returns
        -------
        imports : list
           Elements are `(module, iname, uiname)` where one of the
           following forms is uses::
           
              from module import iname as uiname
              from module import iname
              import module as uiname

           The second form is used if `iname` is `uiname`, and the
           last form is used if `iname` is `None`.  `uiname` must not
           be `None`.          
        defs : list
           Elements are `(uname, rep)` where `rep` is an expression
           depending on the imports and the previously defined `uname`
           elements.

        Notes
        -----
        The core of the algorithm is a transformation that takes an
        object `obj` and replaces that by a tuple `(rep, args,
        imports)` where `rep` is a string representation of the object
        that can be evaluated using `eval()` in the context provided by
        `args` and `imports`.

        The :meth:`archive_1` method provides this functionality,
        effectively defining a suite describing the dependencies of
        the object.

        Typically, `rep` will be a call to the objects constructor
        with the arguments in `args`.  The constructor is typically
        defined by the imports.

        Objects are hierarchical in that one object will depend on
        others.  Consider for example the following suite::
            
            a = [1, 2, 3]
            b = [4, 5, 6]
            c = dict(a=a, b=b)

        The dictionary `c` could be represeted as this suite, or in a
        single expression::

            c = dict(a=[1, 2, 3], b=[4, 5, 6])
            
        In some cases, one must use a suite, for example::

            a = [1, 2, 3]
            b = [a, a]
            c = dict(a=a, b=b)

        Since everything refers to a single list, one must preserve
        this structure and we cannot expand anything.
        
        These concepts can all be couched in the language of graph
        theory.  The dependency structure forms a "directed graph"
        (DG) and we are looking for an "evaluation order" or
        "topological order", which is found using a "topological
        sorting" algorithm.  We do not presently support cyclic
        dependencies, so we will only archive directed acyclic
        graphs (DAG), but the algorithm must determine if there is
        a cycle and raise an exception in this case.

        We use the :mod:`topsort` library to do this.

        We would also like to (optionally) perform reductions of
        the graph in the sense that we remove a node from the
        list of computed quantities, and include it directly in
        the evaluation of another node.  This can only be done if
        the node has less than two parents.  Two calgorithms can be
        used as specified by :attr:`flat`:

           `'flat'`: The flat algorithm recursively processes the archive
              in a depth first manner, adding each object with a
              temporary name.
           `'tree'`: The recursive algorithm leaves objects within their
              recursive structures

        .. digraph:: example
        
           "A" -> "B" -> "F";
           "A" -> "C" -> "D" -> "G";
           "C" -> "E" -> "G";
           "C" -> "F";

        Example::
        
                                A
                               / \
                              B   C
                              |  /| \
                              | / D  E
                               F   \ /
                                    G
           G = 'G'
           F = 'F'
           D = [G]
           E = [G]
           C = [F, D, E]
           B = [F]
           A = [B, C]
           a = Archive()
           a.insert(A=A)
        
        """

        # First we build the dependency tree using the nodes and a
        # depth first search.  The nodes dictionary maps each id to
        # the tuples (obj, (rep, args, imports), parents) where the
        # children are specified by the "args" and parents is a set of
        # the parent ids.  The nodes dictionary also acts as the
        # "visited" list to prevent cycles.

        names = _unzip(self.arch)[0]
        
        # Generate dependency graph
        try:
            graph = Graph(objects=self.arch,
                          archive_1=self.archive_1)
        except topsort.CycleError, err:
            msg = "Archive contains cyclic dependencies."
            raise CycleError, (msg,) + err.args , sys.exc_info()[-1]

        # Optionally: at this stage perform a graph reduction.
        graph.reduce()

        names_reps = [(node.name, node.rep)
                      for id_ in graph.order
                      for node in [graph.nodes[id_]]]

        # Add any leftover names (aliases):
        names_reps.extend([
            (name, node.name)
            for name in self.ids
            if name not in zip(*names_reps)[0]
            for node in [graph.nodes[self.ids[name]]]])

        return (graph.imports, names_reps)

    def __repr__(self):
        return str(self)

    def __str__(self):
        r"""Return a string representing the archive.

        This string can be saved to a file, and that file imported to
        define the required symbols.
        """
        imports, defs = self.make_persistent()
        import_lines = []
        del_lines = []
        for (module, iname, uiname) in imports:
            assert(iname is not None or uiname is not None)
            if iname is None:
                import_lines.append(
                    "import %s as %s"%(module, uiname))
                del_lines.append("del %s" % (uiname,))
            elif iname == uiname or uiname is None: # pragma: no cover
                # Probably never happens because uinames start with _
                import_lines.append(
                    "from %s import %s"%(module, uiname))
                del_lines.append("del %s" % (uiname,))
            else:
                import_lines.append(
                    "from %s import %s as %s"%(module, iname, uiname))
                del_lines.append("del %s" % (uiname,))

        temp_names = [name for (name, rep) in defs
                      if name.startswith('_')]
        if temp_names:
            del_lines.append("del %s" % (",".join(temp_names),))
                                     
        del_lines.extend([
                "try: del __builtins__",
                "except NameError: pass"])

        lines = "\n".join(["%s = %s"%(uname, rep) 
                           for (uname, rep) in defs])
        imports = "\n".join(import_lines)
        dels = "\n".join(del_lines)

        res = ("\n"+self._section_sep).join([l for l in [imports, lines, dels]
                           if 0 < len(l)])
        return res
   
def get_imports(obj, env=None):
    r"""Return `imports = [(module, iname, uiname)]` where
    `iname` is the constructor of `obj` to be used and called as::

       from module import iname as uiname
       obj = uiname(...)

    Examples
    --------
    >>> a = np.array([1, 2, 3])
    >>> get_imports(a)
    [('numpy', 'ndarray', 'ndarray')]
    """
    iname = obj.__class__.__name__
    uiname = iname
    try:
        module = obj.__module__
    except AttributeError:
        module = obj.__class__.__module__

    return [(module, iname, uiname)]

def get_toplevel_imports(obj, env=None):
    r"""Return `(imports, uname) = [(module, name, uname)]` where
    `obj` is `module.name`::

       from module import name as uname
       obj = uname

    Examples
    --------
    >>> a = np.array
    >>> get_toplevel_imports(a)
    ([('numpy.core.multiarray', 'array', 'array')], 'array')
    """
    module = inspect.getmodule(obj)
    if module is None:
        module = inspect.getmodule(obj.__class__)

    mname = module.__name__
    name = obj.__name__

    try:
        _obj = getattr(module, name)
        if _obj is not obj: # pragma: nocover
            raise AttributeError
    except AttributeError: # pragma: nocover
        raise ArchiveError(
            "name %s is not in module %s."%(name, mname))

    return ([(mname, name, name)], name)

def repr_(obj):
    r"""Return representation of `obj`.

    Stand-in `repr` function for objects that support the `archive_1`
    method.

    Examples
    --------
    >>> class A(object):
    ...     def __init__(self, x):
    ...         self.x = x
    ...     def archive_1(self):
    ...         return ('A(x=x)', [('x', self.x)], [])
    ...     def __repr__(self):
    ...         return repr_(self)
    >>> A(x=[1])
    A(x=[1])
    """
    (rep, args, imports) = obj.archive_1()
    replacements = {}
    replacements = dict((k, repr(v))
                        for (k, v) in args)
    rep = _replace_rep(rep, replacements=replacements)
    return rep
    
def get_module(obj):
    r"""Return module in which object is defined."""
    module = inspect.getmodule(obj)
    if module is not __builtin__:
        return module
    else:                       # pragma: no cover
        return None
    
def archive_1_args(obj, args):
    r"""Return `(rep, args, imports)`.

    Constructs `rep` and `imports` dynamically from `obj` and `args`.

    Examples
    --------
    >>> a = 1
    >>> b = 2
    >>> l = [a, b]
    >>> archive_1_args(l, [('a', a), ('b', b)])
    ('list(a=a, b=b)', [('a', 1), ('b', 2)], [('__builtin__', 'list', 'list')])
    """
    module = obj.__class__.__module__
    name = obj.__class__.__name__
    imports = [(module, name, name)]
    
    keyvals = ["=".join((k, k)) for (k, v) in args]
    rep = "%s(%s)"%(name, ", ".join(keyvals))
    return (rep, args, imports)


def archive_1_repr(obj, env):
    r"""Return `(rep, args, imports)`.
    
    This is the fallback: try to make a rep from the `repr` call.
    """
    imports = []
    args = []
    rep = repr(obj)
    scope = {}
    try:
        module = get_module(obj.__class__)
        if module is not __builtin__:
            scope = copy.copy(module.__dict__)
    except:                     # pragma: no cover
        1+1                     # Needed to deal with coverage bug
    scope.update(env)

    ast = AST(rep)

    for name in ast.names:
        obj = eval(name, scope)
        module = get_module(obj)
        if module:
            imports.append((module.__name__, name, name))
            
    return (rep, args, imports)

def archive_1_type(obj, env):
    name = None
    args = {}
    for module in [__builtin__, types]:
        vals = module.__dict__.values()
        if obj in vals:
            name = module.__dict__.keys()[vals.index(obj)]
            imports = [(module.__name__, name, name)]
            rep = name
            break
    if name is None:
        # default
        return archive_1_obj(obj, env)
    
    return (rep, args, imports)
        
    
def archive_1_float(obj, env):
    r"""Deal with float types, including `inf` or `nan`.

    These are floats, but the symbols require the import of
    :mod:`numpy`.

    Examples
    --------
    >>> archive_1_float(np.inf, {})
    ('inf', [], [('numpy', 'inf', 'inf')])
    """
    rep = repr(obj)
    imports = [('numpy', name, name) for name in AST(rep)._get_names()]
    args = []
    
    return (rep, args, imports)

def archive_1_obj(obj, env):
    r"""Archive objects at the top level of a module."""
    module = get_module(obj)
    imports, rep = get_toplevel_imports(obj, env)
    return (rep, {}, imports)

def archive_1_method(obj, env):
    r"""Archive methods."""
    cls = obj.im_class
    instance = obj.im_self
    name = obj.__name__

    if instance is None:
        imports, cls_name = get_toplevel_imports(cls, env)
        rep = ".".join([cls_name, name])
        args = []
    else:
        rep = ".".join(["_instance", name])
        args = [('_instance', instance)]
        imports = []
    return (rep, args, imports)


def _get_rep(obj, arg_rep):
    r"""Return `(rep, imports)` where `rep` = 'Class(args)'` is a call to the
    `obj` constructor.  This is used to represent derived instances of
    builtin types."""
    module = obj.__class__.__module__
    cname = obj.__class__.__name__
    rep = "%s(%s)"%(cname, arg_rep)
    return (rep, (module, cname, cname))
    
def archive_1_list(l, env):
    args = []
    imports = []
    name = '_l_0'
    names = set(env)
    reps = []
    for o in l:
        name = _get_unique(name, names)
        args.append((name, o))
        names.add(name)
        reps.append(name)

    rep = "[%s]"%(", ".join(reps))

    if l.__class__ is not list:
        rep, imp = _get_rep(l, rep)
        imports.append(imp)

    return (rep, args, imports)

def archive_1_tuple(t, env):
    rep, args, imports = archive_1_list(list(t), env=env)
    if len(t) == 1:
        rep = "(%s, )"%(rep[1:-1])
    else:
        rep = "(%s)"%(rep[1:-1])

    if t.__class__ is not tuple:
        rep, imp = _get_rep(t, rep)
        imports.append(imp)

    return (rep, args, imports)

def archive_1_dict(d, env):
    rep, args, imports = archive_1_list(d.items(), env)

    if d.__class__ is not list:
        rep, imp = _get_rep(d, rep)
        imports.append(imp)

    return (rep, args, imports)

def is_simple(obj):
    r"""Return `True` if `obj` is a simple type defined only by its
    representation.

    Examples
    --------
    >>> map(is_simple,
    ...     [True, 1, 'Hi', 1.0, 1.0j, None, 123L])
    [True, True, True, True, True, True, True]
    >>> map(is_simple,
    ...     [[1], (1, ), {'a':2}])
    [False, False, False]
    """
    try:
        class_ = obj.__class__
    except AttributeError:      # pragma: no cover
        result = False
    else:
        result = (
            class_ in [
                bool, int, long,
                str, unicode,
                None.__class__]
            or
            (class_ in [float, complex] 
             and not np.isinf(obj)
             and not np.isnan(obj)))
    if result:
        assert obj == eval(repr(obj))

    return result

class Node(object):
    r"""Represents a Node in the tree as a tuple:
    `(obj, rep, args, name, parents)`

    Attributes
    ----------
    obj : object
       Object the node represents
    rep : str
       String representation of :attr:`obj`.  This depends on the
       names defined in :attr:`args`
    args : list
       List of `(name, obj)` pairs where the specified
       object is referenced in rep by name.
    parents : set
       Set of parent id's
    """
    def __init__(self, obj, rep, args, name, parents=set()):
        self.obj = obj
        self.rep = rep
        self.args = [[name_, obj] for (name_, obj) in args]
        self.name = name
        self.parents = set(parents)

    def __repr__(self):
        r"""Return string representation of node.

        Examples
        --------
        >>> Node(obj=['A'], rep='[x]', args=[('x', 'A')], name='a')
        Node(obj=['A'], rep='[x]', args=[['x', 'A']], name='a', parents=set([]))
        """
        return "Node(obj=%r, rep=%r, args=%r, name=%r, parents=%r)"%(
            self.obj, self.rep, self.args, self.name, self.parents)

    def __str__(self):
        r"""Return string showing node.

        Examples
        --------
        >>> print Node(obj=['A'], rep='[x]', args=[('x', 'A')], name='a')
        Node(a=[x])
        """
        return "Node(%s=%s)"%(self.name, self.rep)

    @property
    def id(self):
        r"""id of node."""
        return id(self.obj)

    @property
    def children(self):
        r"""List of dependent ids"""
        return [id(obj) for (name, obj) in self.args]
    

    def isreducible(self, roots):
        r"""Return True if the node can be reduced.

        A node can be reduced if it is either a simple object with an
        efficient representation (as defined by :meth:`is_simple`), or
        if it has exactly one parent and is not a root node."""
        reducible = (self.id not in roots and
                     (is_simple(self.obj) or 1 == len(self.parents)))
        return reducible


class Graph(object):
    r"""Dependency graph.  Also manages imports.

    This is a graph of objects in memory: these are identified by
    their python :func:`id`.
    """
    def __init__(self, objects, archive_1):
        r"""Initialize the dependency graph with some reserved
        names.

        Parameters
        ----------
        roots : [(id, env)]
        objects : list
           List of top-level objects and names `[(name, obj, env)]`.
           Generated names will be from these and the graph will be
           generated from thes dependents of these objects as
           determined by applying :attr:`archive_1`.
        archive_1 : function
           Function of `(obj, env)` that returns `(rep, args,
           imports)` where `rep` is a representation of `objs`
           descending a single level.  This representation is a string
           expression and can refer to either `name` in the list `args
           = [[name, obj]]` of dependents or the `uiname` in the list
           `imports = [(module, iname, uiname)]` which will be
           imported as::

                from module import iname as uiname
        """
        self.nodes = {}
        self.roots = set([])
        self.envs = {}
        self.imports = []
        self.names = [name for (name, obj, env) in objects]
        self.archive_1 = archive_1

        # First insert the root nodes
        for (name, obj, env) in objects:
            node = self._new_node(obj, env, name)
            self.roots.add(node.id)
            self.envs[node.id] = env
            self.nodes[node.id] = node

        # Now do a depth first search to build the graph.
        for id_ in self.roots:
            self._DFS(node=self.nodes[id_], env=self.envs[id_])
        
        self.order = self._topological_order()

        # Go through all nodes to determine unique names and update
        # reps.  Now that it is sorted we can do this simply.
        for id_ in self.order:
            node = self.nodes[id_]
            if id_ in self.roots:
                # Node is a root node.  Leave name alone
                pass
            else:
                uname = node.name
                if not node.name.startswith('_'):
                    uname = "_" + uname
                uname = _get_unique(uname, self.names)
                self.names.append(uname)
                node.name = uname

            replacements = {}
            for args in node.args:
                name, obj = args
                uname = self.nodes[id(obj)].name
                if not name == uname:
                    replacements[name] = uname
                args[0] = uname

            # This process can create duplicate args, so we remove the
            # duplicates here:
            node.args = mmf.utils.unique_list(node.args)
                
            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.add(node.id)

            node.rep = _replace_rep(node.rep, replacements)

    def _new_node(self, obj, env, name=None):
        r"""Return a new node associated with `obj` and using the
        specified `name`  If `name` is specified, then we assume
        that the `name` is to be exported.  Also process the
        imports of the node."""
        rep, args, imports = self.archive_1(obj, env)
        rep = self._process_imports(rep, args, imports)
        return Node(obj=obj, rep=rep, args=args, name=name)

    def _DFS(self, node, env):
        r"""Visit all nodes in the directed subgraph specified by
        node, and insert them into nodes."""
        for (name, obj) in node.args:
            id_ = id(obj)
            if id_ not in self.nodes:
                node = self._new_node(obj, env, name)
                self.nodes[id_] = node
                self._DFS(node, env)

    def _process_imports(self, rep, args, imports):
        r"""Process imports and add them to self.imports,
        changing names as needed so there are no conflicts
        between `args = [(name, obj)]` and `self.names`."""

        arg_names = _unzip(args)[0]
        # Check for duplicate imports
        new_imports = []
        replacements = {}
        for (module_, iname_, uiname_) in imports:
            mod_inames = zip(*_unzip(self.imports)[:2])
            try:
                ind = mod_inames.index((module_, iname_))
            except ValueError:
                # Get new name.  All import names are local
                uiname = uiname_
                if not uiname.startswith('_'):
                    uiname = "_" + uiname
                uiname = _get_unique(uiname,
                                     self.names + arg_names)
                self.imports.append((module_, iname_, uiname))
                self.names.append(uiname)
            else:
                # Import already specified.  Just refer to it
                module, iname, uiname = self.imports[ind]

            if not uiname == uiname_:
                replacements[uiname_] = uiname

        # Update names of rep in archive
        rep = _replace_rep(rep, replacements)
        return rep

    def edges(self):
        r"""Return a list of edges `(id1, id2)` where object `id1` depends
        on object `id2`."""
        return [(id_, id(obj))
                for id_ in self.nodes
                for (name, obj) in self.nodes[id_].args]

    def _topological_order(self):
        r"""Return a list of the ids for all nodes in the graph in a
        topological order."""
        order = topsort.topsort(self.edges())
        order.reverse()
        # Insert roots (they may be disconnected)
        order.extend([id for id in self.roots if id not in order])
        return order
    
    def _reduce(self, id):
        r"""Reduce the node."""
        node = self.nodes[id]
        if node.isreducible(roots=self.roots):
            replacements = {node.name:node.rep}
            for parent in node.parents:
                pnode = self.nodes[parent]
                pnode.rep = _replace_rep(pnode.rep, replacements)
                pnode.args.remove([node.name, node.obj])
                pnode.args.extend(node.args)
                pnode.args = mmf.utils.unique_list(pnode.args)
            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.remove(id)
                cnode.parents.update(node.parents)
            del self.nodes[id]
    def check(self):
        r"""Check integrity of graph."""
        for id in self.nodes:
            node = self.nodes[id]
            children = node.children
            assert children == mmf.utils.unique_list(children)
            for child in children:
                cnode = self.nodes[child]
                assert id in cnode.parents

    def paths(self, node=None):
        """Return a list of all paths through the graph starting from
        `node`."""
        paths = []
        if node is None:
            for r in self.roots:
                paths.extend(self.paths(r))
        else:
            for c in node.children:
                paths.extend([[node] + p for p in self.paths(c)])
        return paths
        
    def reduce(self):
        r"""Reduce the graph once by combining representations for nodes
        that have a single parent.

       Examples
       --------

       .. digraph:: example
        
           "A" -> "B" -> "F";
           "A" -> "C" -> "D" -> "G";
           "C" -> "E" -> "G";
           "C" -> "F";

        ::
       
                                A
                               / \
                              B   C
                              |  /| \
                              | / D  E
                              'F'  \ /
                                   'G'

       If F and G are builtin, then this is completely reducible,
       otherwise the only reductions that can be made are on B, D, and
       E.

       >>> G = 'G'; F = 'F'
       >>> D = [G]; E = [G]; C = [F, D, E]; B = [F]; A = [B, C]
       >>> a = Archive(); 
       >>> a.insert(A=A)
       'A'
       >>> g = Graph(a.arch, a.archive_1)
       >>> len(g.nodes)
       7
       >>> g.reduce()
       >>> len(g.nodes)         # Completely reducible
       1
       >>> print a
       A = [['F'], ['F', ['G'], ['G']]]
       try: del __builtins__
       except NameError: pass

       If we now make F and G not builtin, then we will not be able to
       reduce them

                                A
                               / \
                              B   C
                              |  /| \
                              | / D  E
                               F   \ /
                               |    G
                              'F'   |
                                   'G'

       >>> G = ['G']; F = ['F']
       >>> D = [G]; E = [G]; C = [F, D, E]; B = [F]; A = [B, C]
       >>> a = Archive(); 
       >>> a.insert(A=A)
       'A'
       >>> g = Graph(a.arch, a.archive_1)
       >>> len(g.nodes)
       9
       >>> g.reduce()
       >>> len(g.nodes)         # Nodes A, F and G remain
       3
       >>> print a
       _l_1 = ['G']
       _l_5 = ['F']
       A = [[_l_5], [_l_5, [_l_1], [_l_1]]]
       del _l_1,_l_5
       try: del __builtins__
       except NameError: pass
       
       If we explicitly add a node, then it can no longer be reduced:
       >>> a.insert(B=B)
       'B'
       >>> g = Graph(a.arch, a.archive_1)
       >>> len(g.nodes)
       9
       >>> g.reduce()
       >>> len(g.nodes)         # Nodes A, F and G remain
       4
       >>> print a
       _l_5 = ['F']
       _l_1 = ['G']
       B = [_l_5]
       A = [B, [_l_5, [_l_1], [_l_1]]]
       del _l_5,_l_1
       try: del __builtins__
       except NameError: pass
       """
        self.check()
        reducible_ids = [id for id in self.order 
                         if self.nodes[id].isreducible(roots=self.roots)]
        for id in reducible_ids:
            self._reduce(id)

        self.order = self._topological_order()

def _unzip(q, n=3):
    r"""Unzip q to lists.

    If len(q) = 0, then assumes that q was zipped from n lists.

    Example:
    >>> _unzip(zip([1, 2, 3], [4, 5, 6]))
    [[1, 2, 3], [4, 5, 6]]
    >>> _unzip([], n=3)
    [[], [], []]
    >>> _unzip([('a', 'b', 'c'), ('d', 'e', 'f')])
    [['a', 'd'], ['b', 'e'], ['c', 'f']]

    """
    if 0 == len(q):
        return [[] for n in range(n)]
    else:
        return map(list, zip(*q))

def _get_unique(name, names, sep='_'):
    r"""Return a unique name not in `names` starting with `name`.

    Parameters
    ----------
    name : str
       Base name.  Resulting name will start with this.
    names : [str]
       List of previously defined names.  The new name will not be in
       `names`.
    sep : str
       The new name will be something like `name + sep + str(i)` where
       `i` is an integer.
    
    Examples
    --------
    >>> names = ['a', 'a.1', 'b']
    >>> _get_unique('c', names)
    'c'
    >>> _get_unique('a', names, sep='.')
    'a.2'
    >>> _get_unique('b', names)
    'b_1'
    >>> _get_unique('b_1', names)
    'b_1'
    >>> _get_unique('a.1', names, sep='.')
    'a.2'
    >>> _get_unique('a_', ['a_'], sep='_')
    'a__1'
    >>> _get_unique('', [])
    '_1'
    >>> _get_unique('', ['_1', '_2'])
    '_3'
    """
    # Matches extension for unique names so they can be incremented.
    
    _extension_re = re.compile(r'(.*)%s(\d+)$'%re.escape(sep))

    
    if name and name not in names:
        uname = name
    else:
        match = _extension_re.match(name)
        if match is None:
            base = name
            c = 1
        else:
            base, c = match.groups()
            c = int(c) + 1

        while True:
            uname = sep.join((base, "%i"%c))
            if uname not in names:
                break
            c += 1
    return uname

class ReplacementError(Exception):
    r"""Replacements not consistent with parse tree."""
    def __init__(self, old, new, expected, actual):
        Exception.__init__(self,
            "Replacement %s->%s: Expected %i, replaced %i"%(
                old, new, expected, actual))

def _replace_rep(rep, replacements, check=False):
    r"""Return rep with all replacements made.

    Parameters:
    rep : str
       String expression to make replacements in
    replacements : dict
       Dictionary of replacements.
    
    >>> _replace_rep('n = array([1, 2, 3])', dict(array='array_1'))
    'n = array_1([1, 2, 3])'
    >>> _replace_rep('a + aa', dict(a='c'))
    'c + aa'
    >>> _replace_rep('(a, a)', dict(a='c'))
    '(c, c)'
    >>> _replace_rep("a + 'a'", dict(a='c'), check=True)
    Traceback (most recent call last):
        ...
    ReplacementError: Replacement a->c: Expected 1, replaced 2
    """
    if check:
        rep_names = AST(rep).names
        counts = dict((n, rep_names.count(n)) for n in replacements)

    identifier_tokens = string.letters + string.digits + "_"
    for old in replacements:
        new = replacements[old]
        l = len(old)
        i = rep.find(old)
        i_rep = []                  # Indices to replace
        while 0 <= i:
            prev = rep[i-1:i]
            next = rep[i+l:i+l+1]
            if ((not next or next not in identifier_tokens)
                and
                (not prev or prev not in identifier_tokens)):

                # Now get previous and next non-whitespace characters
                c = i+l
                while c < len(rep) and rep[c] in string.whitespace:
                    c = c + 1
                next = rep[c:c+1]

                c = i-1
                while 0 <= c and rep[c] in string.whitespace:
                    c = c - 1
                prev = rep[c:c+1]
                if (not next or next not in "="):
                    # Test for keyword arguments
                    i_rep.append(i)
            i = rep.find(old, i+1)

        n_rep = len(i_rep)

        parts = []
        i0 = 0
        for i in i_rep:
            parts.append(rep[i0:i])
            i0 = i + l
        parts.append(rep[i0:])
        rep = new.join(parts)

        if check and not n_rep == counts[old]:
            raise ReplacementError(old, replacements[old], counts[old], n_rep)
    return rep
    """
            re_ = r'''(?P<a>        # Refer to the group by name <a>
                       [^\w\.]      # Either NOT a valid identifier 
                       | ^)         # OR the start of the string
                      (%s)          # The literal to be matched
                      (?P<b>[^\w=]  # Either NOT a valid identifer
                       | $)'''      # OR the end.
            regexp = re.compile(re_%(re.escape(old)), re.VERBOSE)
            n_rep = 0
            while True: 
                (rep, m) = regexp.subn(r"\g<a>%s\g<b>"%(replacements[old]), rep)
                if m == 0: break
                n_rep += m
   """

class AST(object):
    r"""Class to represent and explore the AST of expressions."""
    def __init__(self, expr):
        self.__dict__['expr'] = expr
        self.__dict__['ast'] = compiler.parse(expr)
        self.__dict__['names'] = self._get_names()
    @property
    def expr(self):
        r"""Expression"""
        return self.__dict__['expr']

    @property
    def ast(self):
        r"""AST for expression"""
        return self.__dict__['ast']
        
    @property
    def names(self):
        r"""Symbols references in expression."""
        return self.__dict__['names']

    def _get_names(self):        
        names = []
        def _descend(node):
            if isinstance(node, compiler.ast.Name):
                names.append(node.name)
            try:
                map(_descend, node.getChildren())
            except AttributeError:
                return

        _descend(self.ast)
        return sorted(names)

class DataSet(object):
    r"""Stores data with associated keys in a module that can be
    imported later to retrieve the data.  The keys are all loaded at
    import but the data is only loaded when required.
    
    Examples
    --------
    >>> nxs = [10,20]
    >>> mus = [1,2]
    >>> dat = dict([((nx, mu), np.ones(nx)*mu)
    ...             for mu in mus
    ...             for nx in nxs])
    >>> import tempfile                 # Make a unique temporary module
    >>> t = tempfile.mkdtemp(dir='.')
    >>> os.rmdir(t)
    >>> modname = t[2:]
    >>> ds = DataSet(modname)
    >>> for (nx, mu) in dat:
    ...     ds.insert(dat[(nx, mu)], (nx, mu))

    >>> mod1 = __import__(modname)
    >>> mod1.keys
    ['x_1', 'x_2', 'x_3', 'x_4']
    >>> nx, mu = mod1.x_1            # Get info: already loaded
    >>> x = mod1.load('x_1')         # Data loaded only at this point.
    >>> x.shape[0] == nx
    True
    >>> x[0] == mu
    True
    >>> del x                           # Data freed as soon as GC works.
    >>> mod1.dataset.insert(np.ones(1000), name='y')
    >>> mod1 = reload(mod1);
    >>> mod1.keys
    ['x_4', 'x_2', 'x_3', 'x_1', 'y']
    >>> import shutil; shutil.rmtree('./' + modname)
    """
    _init__str = """
import mmf.archive

keys = %(keys)s
__d = {}
exec(%(info_arch)s, __d)
%(assign)s
dataset = mmf.archive.DataSet(%(args)s, _reload=True)
dataset.info_arch = mmf.archive.Archive(datafile='data.hd5')
dataset.info_arch.insert(**__d)
dataset.data_reps = %(data_reps)s
del __d
del mmf

load = dataset.load

""" 
    def __init__(self, module_name, path="",
                 verbose=False, _reload=False):
        self.verbose = verbose
        if _reload:
            self.module_name = module_name
            self.path = path
            return
        
        mod = None
        try:
            mod = __import__(module_name)
        except ImportError:
            pass

        if mod is not None:
            raise ValueError(
                "Module module_name=%s already exists." % (module_name,) +
                "Please choose a unique name.")

        mod_dir = os.path.join(path, module_name)
        if os.path.exists(mod_dir):
            raise ValueError(
                "Directory %s exists.  Please choose a unique location." % 
                (mod_dir,))
        else:
            if self.verbose:
                print("Making directory %s for output." % (mod_dir,))
            os.makedirs(mod_dir)

        self.module_name = module_name
        self.path = path
        self.info_arch = mmf.archive.Archive(
            datafile=os.path.join(path, 'data.hd5'))
        self.data_reps = {}

        self._write()

    def _write(self):
        r"""Make the module `__init__.py` file."""
        init_str = (self._init__str %
                    dict(keys=repr(self.keys),
                         args=",".join([repr(self.module_name),
                                        "path=%r" % (self.path,),
                                        "verbose=%r" % (self.verbose)]),
                         info_arch=repr(str(self.info_arch)),
                         assign="\n".join("%s = __d[%s]" % (name,
                                                            repr(name))
                                          for name in self.keys),
                         data_reps=repr(self.data_reps)))

        mod_dir = os.path.join(self.path, self.module_name)
        f = open(os.path.join(mod_dir, '__init__.py'), 'w')
        f.write(init_str)
        f.close()

    @property
    def keys(self):
        return self.info_arch.names()
    
    def insert(self, data, info=None, name="x_1"):
        r"""Store `info` and `data` in the archive under `name`"""
        name = mmf.archive.archive_._get_unique(name, self.keys)
        name = self.info_arch.insert(**{name: info})
        arch = mmf.archive.Archive(
            datafile=os.path.join(
            self.path, self.module_name, 'data_%s.hd5' % (name,)))

        data_name = arch.insert(**{name: data})
        self.data_reps[name] = (data_name, str(arch))
        self._write()    

    def load(self, name):
        __d = {}
        data_name, rep = self.data_reps[name]
        exec(rep, __d)
        res = __d[data_name]
        del __d
        return res


# Testing
from mmf.utils.mmf_test import run
run(__name__, __file__, locals())
