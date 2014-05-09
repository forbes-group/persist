r"""This is an idea for a model of objects that save their state.
Here is a typical usage:

>>> a = Archive()
>>> a.insert(x=3)
'x'
>>> a.insert(y=4)
'y'
>>> s = str(a)

Here you could write to a file::

   with open('file.py', 'w') as f:
       f.write(s)

And after you could read from the file again::

   with open('file.py') as f:
       s = f.read()

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
        args = dict(a=self.a, b=self.b, ...)

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

As a last resort, we consider the `repr` of the object: if this starts with `<`
as is customary for instances of many classes, then we try pickling the object,
otherwise we try using the `repr` (which allows builtin types to be simply
archived for example).

Limitations
-----------
Archives must not contain explicit circular dependencies.  These must be managed
by constructors:

>>> l1 = []
>>> l2 = [l1]
>>> l1.append(l2)
>>> l1                          # repr does not even work...
[[[...]]]
>>> a = Archive()
>>> a.insert(l=l1)
'l'
>>> str(a)
Traceback (most recent call last):
    ...
CycleError: Archive contains cyclic dependencies.

Large Archives
--------------
For small amounts of data, the string representation of
:class:`Archive` is usually sufficient.  For large amounts of binary
data, however, this

is extremely inefficient.  In this case, a separate archive format is
used where the archive is turned into a module that contains a binary
data-file.

.. todo::
   - Consider using imports rather than execfile etc. for loading
     :class:`DataSet` s.  This allows the components to be byte-compiled for
     performance.  (Only really helps if the components have lots of code --
     most of my loading performance issues are due instead to the execution of
     constructors, so this will not help.)  Also important for python 3.0
     conversion.
   - Make sure that numpy arrays from tostring() are *NOT* subject to
     replacement somehow.  Not exactly sure how to reproduce the
     problem, but it is quite common for these to have things like
     '_x' in the string.
   - Graph reduction occurs for nodes that have more than one parent.
     This does not consider the possibility that a single node may
     refer to the same object several times.  This has to be examined
     so that non-reducible nodes are not reduced (see the test case
     which fails).
   - :func:`_replace_rep` is stupid (it just does text replacements).  The
     alternative :func:`_replace_rep_robust` is slow.
   - It would be nice to be able to use `import A.B` and then just use
     the name `A.B.x`, `A.B.y` etc.  However, the name `A` could clash
     with other symbols, and it cannot be renamed (i.e. `import A_1.B`
     would not work).  To avoid name clashes, we always use either
     `import A.B as B` or the `from A.B import x` forms which can be
     renamed.
   - Maybe allow rep's to be suites for objects that require construction
     and initialization.  (Could also allow a special method to be called
     to restore the object such as `restore()`.)
   - Performance: There have been some performance issues:
     c9e9fff8662f: A major improvement was made (this is not in archive!?!).
     daa21ec81421: Another bottleneck was removed.
     23999d0c395e: Some of the code to make unique indices was running in O(n^2)
     time because of expensive "in" lookups.  This was fixed by adding a
     `_maxint` cache. The remaining performance issues appear to be in
     `_replace_rep`.

Developer's Note
================
After issue 12 arose, I decided to change the structure of archives to
minimize the need to replace text.  New archives will evaluate objects in a
local scope.  Here is an example, first in the old format::

   from mmf.objects import Container as _Container
   _y = [1, 2, 3, 4]
   l1 = [_y, [1, _y]]
   l2 = [_y, l1]
   c = _Container(_y=_y, x=1, l=l2)
   del _Container
   del _y
   try: del __builtins__
   except NameError: pass

Now in an explicit local scoping format using dictionaries::

   _g = {}
   _g['_y'] = [1, 2, 3, 4]
   _d = dict(y=_g['_y'])
   l1 = _g['_l1'] = eval('[y, [1, y]]', _d)
   _d = dict(y=_g['_y'],
             l1=l1)
   l2 = _g['_l2'] = eval('[y, l1]', _d)
   _d = dict(x=1,
             _y=_g['_y'],
             l2=l2,
             Container=__import__('mmf.objects',
                                  fromlist=['Container']).Container)
   c = _g['_c'] = eval('Container(x=x, _y=_y, l=l2)', _d)
   del _g, _d
   try: del __builtins__
   except NameError: pass

Now a version using local scopes to eschew :func:`eval`.  One can use either
classes or functions: preliminary profiling shows functions to be slightly
faster - and there is no need for using `global` - so I am using that for now.
Local variables are assigned using keyword arguments.  The idea is to establish
a one-to-one correspondence between functions and each object so that the
representation can be evaluated without requiring textual replacements that have
been the source of errors.

The old format is clearer, but the replacements require render it somewhat
unreliable::

   _y = [1, 2, 3, 4]   # No arguments here
   def _d(y):
       return [y, [1, y]]
   l1 = _d(y=_y)
   def _d(y):
       return [y, l1]
   l2 = _d(y=_y)
   def _d(x):
       from mmf.objects import Container as Container
       return Container(x=x, _y=_y, l=l2)
   c = _d(x=1)
   del _d
   del _y
   try: del __builtins__
   except NameError: pass

"""
from __future__ import division, with_statement

__all__ = ['Archive', 'DataSet', 'restore',
           'ArchiveError', 'DuplicateError', 'repr_',
           'get_imports']

import __builtin__
import ast
import cPickle
import copy
import inspect
import os
import re
import string
import sys
import time
import types
import warnings
from contextlib import contextmanager

import numpy as np
import scipy.sparse
sp = scipy

import contrib.RADLogic.topsort as topsort
import mmf.interfaces as interfaces
import mmf.objects
import mmf.utils

try:
    import h5py
except ImportError:
    h5py = None

try:
    import tables
except ImportError:
    tables = None

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
        msg = "Object with name '%s' already exists in archive." % (name,)
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

@contextmanager
def backup(filename, keep=True):
    """Context to temporarily backup `filename`.

    Moves `filename` to `filename.bak` (or `filename_#.bak` with a number #
    chosen as needed to prevent a clash), then executes the context.
    If `keep` is `False` and no exceptions are raised, then the
    file is removed when the context is finished.
    """ 
    backup_name = None
    if os.path.exists(filename):
        backup_name = filename + ".bak"
        n = 1
        while os.path.exists(backup_name):
            backup_name = filename + "_%i.bak" % (n)
            n += 1
        os.rename(filename, backup_name)

    yield backup_name

    if backup_name and not keep:
        # Remove backup of data
        os.remove(backup_name)


class Archive(object):
    r"""Archival tool.

    Maintains a list of symbols to import in order to reconstruct the
    states of objects and contains methods to convert objects to
    strings for archival.

    A set of options is provided that allow large pieces of data to be
    stored externally.  These pieces of data (:mod:`numpy` arrays)
    will need to be stored at the time of archival and restored prior
    to executing the archival string.  (See :attr:`array_threshold`
    and :attr:`data`).

    Attributes
    ----------
    arch : list
       List of `(uname, obj, env)` where `obj` is the object, which
       can be reconstructed from the string `rep` evaluated in the
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
    data : dict
       This is a dictionary of objects that need to be explicitly
       stored outside of the string archive.  The archival string
       returned by :meth:`__str__` should be evaluated in an
       environment with a dictionary-like object with the name
       :attr:`data_name`  containing this dictionary.
    array_threshold : int, optional
       Numpy arrays with more than this many elements will not be
       archived.  Instead, they will be stored in :attr:`data` and
       will need to be stored externally.  (If this is `inf`, then all
       data will be stored the string representation of the archive.)
    data_name : str
       This is the name of the dictionary-like object containing
       external objects.  This need not be provided, but it will not
       be allowed as a valid name for other data in the archive.
    datafile : None, str, optional
       If provided, then numpy arrays longer than
       :attr:`array_threshold` are archived in binary to this file.
       (See also `hdf5`).  Otherwise, they will be stored in
       :attr:`data` which must be manually archived and restored
       externally.  The data will be written when
       :meth:`make_persistent` is called.
    hdf5 : True, False, optional
       If `True` and `datafile` is provided, then use hdf5 via the h5py package
       to store the binary data.
    backup_data : bool
       If `True` and :attr:`datafile` already exists, then a backup of
       the data will first be made with an extension `'.bak'` or
       `'_#.bak'` if backups already exists.  Otherwise, the file will
       be overwritten.  (Actually, a backup will always be made, but
       if the creation of the new file is successful, then the backup
       will be deleted if this is `False`.)
    allowed_names : [str], optional
       If provided, then these names will be considered acceptable.
       This allows for 'private' names to be used by specialized
       structures.
    gname_prefix : str, optional
       This string is used to prefix all global variables.
    scoped : bool, optional
       If `True`, then the representation is "scoped": i.e. a series of function
       definitions.  This allows each entry to be evaluated in a local scope
       without the need for textual replacements in the representation (which
       can be either costly or error-prone).  The resulting output is not as
       compact (can be on the order of 4 times larger), nor as legible, but
       archiving can be much faster.
    robust_replace : bool, optional
       If `True`, then :func:`_replace_rep_robust` instead of
       :func:`_replace_rep`.  This is much more robust, but can be much slower
       as it invokes the python parser.

    Notes
    -----
    A required invariant is that all `uname` be unique.

    Examples
    --------
    First we make a simple archive as a string (no external storage)
    and then restore it.

    >>> arch = Archive(scoped=False) # Old form of scoped
    >>> arch.insert(x=4)
    'x'

    We can include functions and classes: These are stored by their
    names and imports.

    >>> import numpy as np
    >>> arch.insert(f=np.sin, g=restore)
    ['g', 'f']

    Here we include a list and a dictionary containing that list.  The
    resulting archive will only have one copy of the list since it is
    referenced.

    >>> l0 = ['a', 'b']
    >>> l = [1, 2, 3, l0]
    >>> d = dict(l0=l0, l=l, s='hi')
    >>> arch.insert(d=d, l=l)
    ['d', 'l']

    Presently the archive is just a graph of objects and string
    representations of the objects that have been directly inserted.
    For instance, `l0` above has not been directly included, so if it
    were to change at this point, this would affect the archive.

    To make the archive persistent so there is no dependence on
    external objects, we call :meth:`make_persistent`.  This would
    also save any external data as we shall see later.

    >>> _tmp = arch.make_persistent()

    This is not strictly needed as it will be called implicitly by the
    following call to :meth:`__str__` which returns the string
    representation.  (Note also that this will thus be called whenever
    the archive is printed.)

    >>> s = str(arch)
    >>> print s
    from mmf.archive... import restore as _restore
    from numpy import sin as _sin
    from __builtin__ import dict as _dict
    _l_5 = ['a', 'b']
    l = [1, 2, 3, _l_5]
    d = _dict([('s', 'hi'), ('l', l), ('l0', _l_5)])
    g = _restore
    f = _sin
    x = 4
    del _restore
    del _sin
    del _dict
    del _l_5
    try: del __builtins__
    except NameError: pass

    Now we can restore this by executing the string.  This should be
    done in a dictionary environment.

    >>> res = {}
    >>> exec(s, res)
    >>> res['l']
    [1, 2, 3, ['a', 'b']]
    >>> res['d']['l0']
    ['a', 'b']

    Note that the shared list here is the same list:

    >>> id(res['l'][3]) == id(res['d']['l0'])
    True
    """
    data_name = '_arrays'

    def __init__(self, flat=True, tostring=True,
                 check_on_insert=False, array_threshold=np.inf,
                 datafile=None, hdf5=bool(h5py), allowed_names=None,
                 gname_prefix='_g', scoped=True, robust_replace=True):
        self.tostring = tostring
        self.flat = flat
        self.imports = []
        self.arch = []
        self.ids = {}
        if not allowed_names:
            allowed_names = []
        self.allowed_names = allowed_names
        self.gname_prefix = gname_prefix

        self._section_sep = ""  # string to separate the sections
        self._numpy_printoptions = {'infstr': 'Inf',
                                    'threshold': np.inf,
                                    'suppress': False,
                                    'linewidth': 200,
                                    'edgeitems': 3,
                                    'precision': 16,
                                    'nanstr': 'NaN'}
        self.check_on_insert = check_on_insert
        self.data = {}
        self.datafile = datafile
        self.hdf5 = hdf5
        self.array_threshold = array_threshold
        self.scoped = scoped
        self.robust_replace = robust_replace

        self._maxint = -1       # Cache of maximum int label in archive

        if hdf5 and not h5py:
            raise ArchiveError(
                "HDF5 requested but h5py could not be imported.")

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
        if (interfaces.IArchivable.providedBy(obj) or
            isinstance(obj, interfaces.IArchivable) or
            isinstance(obj, mmf.objects.Archivable)):
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
                1 + 1           # Needed to deal with coverage bug

        rep = repr(obj)
        if rep.startswith('<'):
            try:
                return archive_1_pickle(obj, env)
            except cPickle.PickleError, err:
                raise ArchiveError(
                    "Could not archive object %s.  Even tried pickling!")
        else:
            return archive_1_repr(obj, env, rep=rep)

    def _archive_ndarray(self, obj, env):
        """Archival of numpy arrays."""
        if self.array_threshold < np.prod(obj.shape):
            # Data should be archived to a data file.
            array_prefix = 'array_'
            i = self._maxint + 1
            array_name = array_prefix + str(i)
            while array_name in self.data:
                # This should only execute a few times if the user, for example,
                # included manually an element with name "array_<n>" for
                # example.
                i += 1
                array_name = array_prefix + str(i)
            self._maxint = i
            self.data[array_name] = obj
            rep = "%s['%s']" % (self.data_name, array_name)
            args = {}
            imports = []
        elif (self.tostring
              and obj.__class__ is np.ndarray
              and not obj.dtype.hasobject):

            rep = "numpy.fromstring(%r, dtype=%r).reshape(%s)" % (
                obj.tostring(), obj.dtype.str, str(obj.shape))
            imports = [('numpy', None, 'numpy')]
            args = {}
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
            args = {}
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
        return (rep, dict(args=args), imports)

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
        sp.sparse.base.spmatrix: _archive_spmatrix,
        np.ndarray: _archive_ndarray,
        np.ufunc: _archive_func,
        types.BuiltinFunctionType: _archive_func,
        types.FunctionType: _archive_func,
        list: _archive_list,
        tuple: _archive_tuple,
        dict: _archive_dict,
        float: _archive_float,
        complex: _archive_float,
        type: _archive_type}

    def unique_name(self, name):
        r"""Return a unique name not contained in the archive."""
        names = _unzip(self.arch)[0]
        return UniqueNames(names).unique(name)

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
        >>> a = Archive(scoped=False) # Old format for doctest
        >>> a.insert(x=2)
        'x'
        >>> a.insert(x=2)       # Duplicates are okay.
        'x'
        >>> a.insert(x=3)       # Changes are not...
        Traceback (most recent call last):
           ...
        DuplicateError: Object with name 'x' already exists in archive.
        >>> a.insert(**{a.unique_name('x'):3}) # ...but can make unique label
        'x_0'
        >>> a.insert(a=4, b=5)   # Can insert multiple items
        ['a', 'b']
        >>> a.insert(A=np.array([1, 2, 3]))
        'A'
        >>> print a                     # doctest: +SKIP
        import numpy as _numpy
        x_1 = 3
        a = 4
        x = 2
        b = 5
        A = _numpy.fromstring('\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00', dtype='<i4').reshape((3,))
        del _numpy
        try: del __builtins__
        except NameError: pass

        For testing purposes we have to sort the lines of the output:

        >>> print "\n".join(sorted(str(a).splitlines()))
        A = _numpy.fromstring('\x01\x00\x00\x00\x02\x00\x00\x00\x03\x00\x00\x00', dtype='<i4').reshape((3,))
        a = 4
        b = 5
        del _numpy
        except NameError: pass
        import numpy as _numpy
        try: del __builtins__
        x = 2
        x_0 = 3

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

        Names must not start with an underscore:

        >>> a.insert(_x=5)
        Traceback (most recent call last):
           ...
        ValueError: name must not start with '_'

        This can be overridden by using :attr:`allowed_names`:

        >>> a.allowed_names.append('_x')
        >>> a.insert(_x=5)
        '_x'
        >>> a.make_persistent() # doctest: +NORMALIZE_WHITESPACE
        ([('numpy', None, '_numpy'),
          ('numpy', 'inf', '_inf'),
          ('numpy', 'nan', '_nan')],
         [('c', '_numpy.array([ 1.+0.j,  2.+3.j,  3.+0.j])'),
          ('cc', '[c, c, [3]]'),
          ('A', '_numpy.array([1, 2, 3])'),
          ('x', '2'),
          ('_x', '5')])
        """
        if env is None:
            env = {}

        names = []
        for name in kwargs:
            obj = kwargs[name]
            if (name.startswith('_')
                and name not in self.allowed_names):
                raise ValueError("name must not start with '_'")

            # First check to see if object is already in archive:
            unames, objs, envs = _unzip(self.arch)

            obj_ids = map(id, objs)
            obj_id = id(obj)
            obj_ind = None
            if obj_id in obj_ids:
                obj_ind = obj_ids.index(obj_id)

            name_ind = None
            if name in unames:
                name_ind = unames.index(name)

            ind = None
            if name_ind is not None:
                # Name already in archive
                if name_ind == obj_ind:
                    ind = name_ind
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
        version of the archive.  If :attr:`datafile` is specified and
        there is data in :attr:`data` (large arrays), then these are
        also stored (requires :attr:`hdf5`) at this time.

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

        ##names = _unzip(self.arch)[0]

        # Generate dependency graph
        try:
            graph = Graph(objects=self.arch,
                          archive_1=self.archive_1,
                          robust_replace=self.robust_replace)
        except topsort.CycleError, err:
            msg = "Archive contains cyclic dependencies."
            raise CycleError, (msg, ) + err.args , sys.exc_info()[-1]

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

        # Archive the data to file if requested.
        if self.data and self.datafile is not None:
            with self._backup(self.datafile):
                if self.hdf5 and h5py:
                    with h5py.File(self.datafile) as f:
                        for name in self.data:
                            f[name] = self.data[name]
                else:
                    raise NotImplementedError(
                        "Data can presently only be saved with hdf5")

        return (graph.imports, names_reps)

    def __repr__(self):
        return str(self)

    def _get_import_lines(self, imports):
        r"""Return `(import_lines, del_lines)`.

        Parameters
        ----------
        imports : [(module, iname, uname)]
        """
        import_lines = []
        del_lines = []
        for (module, iname, uiname) in imports:
            assert(iname is not None or uiname is not None)
            if iname is None:
                import_lines.append(
                    "import %s as %s"%(module, uiname))
                del_lines.append("del %s" % (uiname,))
            elif iname == uiname or uiname is None:  # pragma: no cover
                # Probably never happens because uinames start with _
                import_lines.append(
                    "from %s import %s"%(module, uiname))
                del_lines.append("del %s" % (uiname,))
            else:
                import_lines.append(
                    "from %s import %s as %s"%(module, iname, uiname))
                del_lines.append("del %s" % (uiname,))
        return import_lines, del_lines

    def __str__(self):
        r"""Return a string representing the archive.

        This string can be saved to a file, and that file imported to
        define the required symbols.
        """
        if self.scoped:
            return self.scoped__str__()
        else:
            return self.unscoped_str()

    def unscoped_str(self):
        r"""Return an unscoped string representation with all objects defined in
        the global scope.  This requires renaming and textual replacement."""
        imports, defs = self.make_persistent()
        import_lines, del_lines = self._get_import_lines(imports)
        temp_names = [name for (name, rep) in defs
                      if (name.startswith('_')
                          and name not in self.allowed_names)]
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

    def scoped__str__(self):
        r"""Return the scoped version of the string representation."""
        # Generate dependency graph
        try:
            graph = _Graph(objects=self.arch,
                           archive_1=self.archive_1,
                           gname_prefix=self.gname_prefix)
        except topsort.CycleError, err:
            msg = "Archive contains cyclic dependencies."
            raise CycleError, (msg, ) + err.args, sys.exc_info()[-1]

        # Optionally: at this stage perform a graph reduction.
        #graph.reduce()

        results = []
        names = set()
        for _id in graph.order:
            node = graph.nodes[_id]
            name = node.name
            assert name not in names
            names.add(name)

            if node.args or node.imports:
                results.append(
                    "\n".join([
                        "",
                        "def %(name)s(%(args)s):%(imports)s",
                        "    return %(rep)s",
                        "%(name)s = %(name)s()"])
                    % dict(name=name,
                           argnames=",".join(node.args.keys()),
                           args=",".join([
                                "=".join([
                                    _a,
                                    graph.nodes[id(node.args[_a])].name])
                               for _a in node.args]),
                           imports="\n    ".join(
                               [""] + self._get_import_lines(node.imports)[0]),
                           rep=node.rep))
            else:
                results.append(
                    "%(name)s = %(rep)s"
                    % dict(name=name, rep=node.rep))

        # Add any leftover names (aliases):
        for name in self.ids:
            if name in names:
                continue
            node = graph.nodes[self.ids[name]]
            results.append(" = ".join([name, node.name]))

        # Archive the data to file if requested.
        if self.data and self.datafile is not None:
            with backup(self.datafile, keep=self.backup_data):
                if self.hdf5 and h5py:
                    with h5py.File(self.datafile) as f:
                        for name in self.data:
                            f[name] = self.data[name]
                else:
                    raise NotImplementedError(
                        "Data can presently only be saved with hdf5")

        gnames = ", ".join(_n for _n in names
                           if _n.startswith(self.gname_prefix)
                           and _n not in self.allowed_names)
        if gnames:
            results.append("del %s" % (gnames,))
        results.extend([
            "try: del __builtins__",
            "except NameError: pass"])

        return "\n".join(results)


def get_imports(obj, env=None):
    r"""Return `imports = [(module, iname, uiname)]` where
    `iname` is the constructor of `obj` to be used and called as::

       from module import iname as uiname
       obj = uiname(...)

    This may be useful when writing :meth:`~mmf.IArchivable.archive_1`
    methods.

    Examples
    --------
    >>> import numpy as np
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

    if hasattr(module, name):
        _obj = getattr(module, name)
        if _obj is not obj:  # pragma: nocover
            raise AttributeError
    else:  # pragma: nocover
        raise ArchiveError(
            "name %s is not in module %s."%(name, mname))

    return ([(mname, name, name)], name)


def repr_(obj, robust=True):
    r"""Return representation of `obj`.

    Stand-in `repr` function for objects that support the `archive_1`
    method.

    Examples
    --------
    >>> class A(object):
    ...     def __init__(self, x):
    ...         self.x = x
    ...     def archive_1(self):
    ...         return ('A(x=x)', dict(x=self.x), [])
    ...     def __repr__(self):
    ...         return repr_(self)
    >>> A(x=[1])
    A(x=[1])
    """
    (rep, args, imports) = obj.archive_1()
    replacements = dict((k, repr(args[k])) for k in args)
    rep = _replace_rep(rep, replacements=replacements, robust=robust)
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
    >>> archive_1_args(l, dict(a=a, b=b))
    ('list(a=a, b=b)', {'a': 1, 'b': 2}, [('__builtin__', 'list', 'list')])
    """
    module = obj.__class__.__module__
    name = obj.__class__.__name__
    imports = [(module, name, name)]

    keyvals = ["=".join((k, k)) for k in args]
    rep = "%s(%s)"%(name, ", ".join(keyvals))
    return (rep, args, imports)


def archive_1_repr(obj, env, rep=None):
    r"""Return `(rep, args, imports)`.

    This is the fallback: try to make a rep from the `repr` call.
    """
    imports = []
    args = {}
    if rep is None:
        rep = repr(obj)
    scope = {}
    try:
        module = get_module(obj.__class__)
        if module is not __builtin__:
            scope = copy.copy(module.__dict__)
    except:                     # pragma: no cover
        1+1                     # Needed to deal with coverage bug
    scope.update(env)

    _ast = AST(rep)

    for name in _ast.names:
        obj = eval(name, scope)
        module = get_module(obj)
        if module:
            imports.append((module.__name__, name, name))

    return (rep, args, imports)


def archive_1_pickle(obj, env):
    r"""Last resort - archive by pickle."""
    rep = "loads(%s)" % repr(
        cPickle.dumps(obj, protocol=cPickle.HIGHEST_PROTOCOL))
    args = {}
    imports = [('cPickle', 'loads', 'loads')]
    return (rep, args, imports)


def archive_1_type(obj, env):
    name = None
    args = {}
    for module in [__builtin__, types]:
        obj_id = id(obj)
        val_ids = map(id, module.__dict__.values())
        if obj_id in val_ids:
            name = module.__dict__.keys()[val_ids.index(obj_id)]
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
    ('inf', {}, [('numpy', 'inf', 'inf')])
    """
    rep = repr(obj)
    imports = [('numpy', name, name) for name in AST(rep)._get_names()]
    args = {}

    return (rep, args, imports)


def archive_1_obj(obj, env):
    r"""Archive objects at the top level of a module."""
    ##module = get_module(obj)
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
        args = {}
    else:
        rep = ".".join(["_instance", name])
        args = dict(_instance=instance)
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
    args = {}
    imports = []
    name = '_l_0'
    names = set(env)
    reps = []
    unames = UniqueNames(names).unique_names(name)
    for o in l:
        name = unames.next()
        args[name] = o
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
    if hasattr(obj, '__class__'):
        class_ = obj.__class__
        result = (
            class_ in [
                bool, int, long,
                str, unicode,
                None.__class__]
            or
            (class_ in [float, complex]
             and not np.isinf(obj)
             and not np.isnan(obj)))
    else:                       # pragma: no cover
        result = False
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
    args : dict
       Dictionary where value `obj` is referenced in `rep` by key `name`.
    parents : set
       Set of parent id's
    """
    def __init__(self, obj, rep, args, name, imports=None, parents=set()):
        self.obj = obj
        self.rep = rep
        self.args = dict(**args)
        self.name = name
        self.parents = set(parents)
        self.imports = imports

    def __repr__(self):
        r"""Return string representation of node.

        Examples
        --------
        >>> Node(obj=['A'], rep='[x]', args=dict(x='A'), name='a')
        Node(obj=['A'], rep='[x]', args={'x': 'A'}, name='a', imports=None,
             parents=set([]))
        """
        return (
            "Node(obj=%r, rep=%r, args=%r, name=%r, imports=%r, parents=%r)"
            % (self.obj, self.rep, self.args, self.name, self.imports,
               self.parents))

    def __str__(self):
        r"""Return string showing node.

        Examples
        --------
        >>> print Node(obj=['A'], rep='[x]', args=dict(x='A'), name='a')
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
        return [id(self.args[name]) for name in self.args]

    def isreducible(self, roots):
        r"""Return `True` if the nodeg can be reduced.

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
    def __init__(self, objects, archive_1, robust_replace=True):
        r"""Initialize the dependency graph with some reserved
        names.

        Parameters
        ----------
        roots : [(id, env)]
        objects : list
           List of top-level objects and names `[(name, obj, env)]`.
           Generated names will be from these and the graph will be
           generated from thes dependents of these objects as
           determined by applying :attr:`archive_1`.  It is assumed that all
           these names are unique.
        archive_1 : function
           Function of `(obj, env)` that returns `(rep, args,
           imports)` where `rep` is a representation of `objs`
           descending a single level.  This representation is a string
           expression and can refer to either `name` in the dict `args`
           of dependents or the `uiname` in the list
           `imports = [(module, iname, uiname)]` which will be
           imported as::

                from module import iname as uiname
        """
        self.nodes = {}
        self.roots = set()
        self.envs = {}
        self.imports = []
        self.names = UniqueNames(set([name for (name, obj, env)
                                      in objects]))
        self.archive_1 = archive_1
        self.robust_replace = robust_replace

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
                uname = self.names.unique(uname)
                node.name = uname

            replacements = {}
            args = {}
            for name in node.args:
                obj = node.args[name]
                uname = self.nodes[id(obj)].name
                args[uname] = obj
                if not name == uname:
                    replacements[name] = uname
            node.args = args

            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.add(node.id)

            node.rep = _replace_rep(node.rep, replacements,
                                    robust=self.robust_replace)

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
        for name, obj in node.args.iteritems():
            id_ = id(obj)
            if id_ not in self.nodes:
                node = self._new_node(obj, env, name)
                self.nodes[id_] = node
                self._DFS(node, env)

    def _process_imports(self, rep, args, imports):
        r"""Process imports and add them to self.imports,
        changing names as needed so there are no conflicts
        between `args = {name: obj}` and `self.names`."""
        arg_names = args.keys()
        # Check for duplicate imports

        ##new_imports = []
        replacements = {}
        for (module_, iname_, uiname_) in imports:
            mod_inames = zip(*_unzip(self.imports)[:2])
            if (module_, iname_) in mod_inames:
                # Import already specified.  Just refer to it
                ind = mod_inames.index((module_, iname_))
                module, iname, uiname = self.imports[ind]
            else:
                # Get new name.  All import names are local
                uiname = uiname_
                if not uiname.startswith('_'):
                    uiname = "_" + uiname
                uiname = self.names.unique(uiname, arg_names)
                self.imports.append((module_, iname_, uiname))

            if not uiname == uiname_:
                replacements[uiname_] = uiname

        # Update names of rep in archive
        rep = _replace_rep(rep, replacements, robust=self.robust_replace)
        return rep

    def edges(self):
        r"""Return a list of edges `(id1, id2)` where object `id1` depends
        on object `id2`."""
        return [(id_, id(obj))
                for id_ in self.nodes
                for (name, obj) in self.nodes[id_].args.iteritems()]

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
            replacements = {node.name: node.rep}
            for parent in node.parents:
                pnode = self.nodes[parent]
                pnode.rep = _replace_rep(pnode.rep, replacements,
                                         robust=self.robust_replace)
                del pnode.args[node.name]
                pnode.args.update(node.args)
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
       >>> a = Archive(scoped=False);
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
       reduce them::

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
       >>> a = Archive(scoped=False);
       >>> a.insert(A=A)
       'A'
       >>> g = Graph(a.arch, a.archive_1)
       >>> len(g.nodes)
       9
       >>> g.reduce()
       >>> len(g.nodes)         # Nodes A, F and G remain
       3
       >>> print a
       _l_5 = ['F']
       _l_1 = ['G']
       A = [[_l_5], [_l_5, [_l_1], [_l_1]]]
       del _l_5,_l_1
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
       B = [_l_5]
       _l_1 = ['G']
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


class _Graph(object):
    r"""Simplified dependency graph for use with scoped files.

    This is a graph of objects in memory: these are identified by
    their python :func:`id`.  Unlike :class:`Graph`, this does not bother with
    unique names and replacements.  The output routine must make sure each
    object is evaluated in a separate scope.

    .. note::
       To improve performance, it is assumed that the names of `objects`
       are unique and do not start with an underscore `_`.
    """
    def __init__(self, objects, archive_1,
                 gname_prefix='_g', allowed_names=set()):
        r"""Initialize the dependency graph with some reserved
        names.

        Parameters
        ----------
        roots : [(id, env)]
        objects : list
           List of top-level objects and names `[(name, obj, env)]`.
           Generated names will be from these and the graph will be
           generated from thes dependents of these objects as
           determined by applying :attr:`archive_1`.  It is assumed that all
           these names are unique.
        archive_1 : function
           Function of `(obj, env)` that returns `(rep, args,
           imports)` where `rep` is a representation of `objs`
           descending a single level.  This representation is a string
           expression and can refer to either `name` in the dict `args`
           of dependents or the `uiname` in the list
           `imports = [(module, iname, uiname)]` which will be
           imported as::

                from module import iname as uiname
        """
        self.nodes = {}
        self.roots = set()
        self.envs = {}
        self.imports = []
        self.gname_num = 0
        self.gname_prefix = gname_prefix
        self.allowed_names = allowed_names
        self.archive_1 = archive_1
        self.names = set()

        # First insert the root nodes
        for (name, obj, env) in objects:
            node = self._new_node(obj, env, name)
            self.roots.add(node.id)
            self.envs[node.id] = env
            self.nodes[node.id] = node

        # Now do a depth first search to build the graph.
        for _id in self.roots:
            self._DFS(node=self.nodes[_id], env=self.envs[_id])

        self.order = self._topological_order()

        # Add all reverse links from child to parent nodes.
        for _id_ in self.order:
            node = self.nodes[_id]
            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.add(node.id)

    def _new_node(self, obj, env, name=None):
        r"""Return a new node associated with `obj` and using the
        specified `name`  If `name` is specified, then we assume
        that the `name` is to be exported.  Also process the
        imports of the node."""
        if name is None:
            name = self.gname
        else:
            assert not name.startswith(self.gname_prefix)
            assert name not in self.names
        self.names.add(name)
        rep, args, imports = self.archive_1(obj, env)
        return Node(obj=obj, rep=rep, args=args, name=name, imports=imports)

    @property
    def gname(self):
        r"""Return a unique global name.  These start with an underscore."""
        while True:
            gname = self.gname_prefix + str(self.gname_num)
            self.gname_num += 1
            if gname not in self.allowed_names:
                break
        return gname

    def _DFS(self, node, env):
        r"""Visit all nodes in the directed subgraph specified by
        node, and insert them into nodes."""
        for _name in node.args:
            obj = node.args[_name]
            id_ = id(obj)
            if id_ not in self.nodes:
                new_node = self._new_node(obj, env)
                self.nodes[id_] = new_node
                self._DFS(new_node, env)

    def edges(self):
        r"""Return a list of edges `(id1, id2)` where object `id1` depends
        on object `id2`."""
        return [(id_, id(obj))
                for id_ in self.nodes
                for (name, obj) in self.nodes[id_].args.iteritems()]

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
        raise NotImplementedError
        node = self.nodes[id]
        if node.isreducible(roots=self.roots):
            replacements = {node.name: node.rep}
            for parent in node.parents:
                pnode = self.nodes[parent]
                pnode.rep = _replace_rep(pnode.rep, replacements,
                                         robust=self.robust_replace)
                del pnode.args[node.name]
                pnode.args.update(node.args)
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


class UniqueNames(object):
    """Profiling indicates that the generation of unique names is a significant
    bottleneck.  This class is used to manage unique names in an efficient
    manner.
    """
    def __init__(self, names=None, sep='_'):
        """
        Parameters
        ----------
        names : set
           Set of names.  New names will not clash with these.
        """
        self.sep = sep
        self.extension_re = re.compile(r'(.*)%s(\d+)$' % re.escape(sep))
        self.names = set(names)

        # This is a dictionary of numbers associated with each base such that
        # sep.join([base, num]) will be a unique name for all num >=
        # bases[base].
        self.bases = {}
        for name in self.names:
            self._reserve(name)

    def _reserve(self, name):
        r"""Update :attr:`bases` so that `name` will be consider used.  Does not
        add `name` to :attr:`names`.
        """
        match = self.extension_re.match(name)
        if match:
            base, c = match.groups()
            c = int(c)
        else:
            base = name
            c = -1
        c += 1
        self.bases[base] = max(c, self.bases.get(base, c))

    def unique(self, name, others=None):
        r"""Return a unique version of `name` with the same base.

        Parameter
        ---------
        name : str
           Desired name or base.
        others : set(str)
           Set of additional names to avoid conflicts with.  These are not added
           to :attr:`names`, but will increment :attr:`bases`.

        >>> un = UniqueNames(set(['a', 'b_3']))
        >>> un.unique('a')
        'a_0'
        >>> un.unique('a')
        'a_1'
        >>> un.unique('a_4')
        'a_4'
        >>> un.unique('a_2')
        'a_5'
        >>> un.unique('b')
        'b_4'
        >>> un.unique('b', set(['b_5']))
        'b_6'

        Here is a regression test:
        >>> names = set(['a', 'a.1', 'bdf4'])
        >>> UniqueNames(names).unique('c')
        'c'
        >>> UniqueNames(names, sep='.').unique('a')
        'a.2'
        >>> UniqueNames(names, sep='df').unique('bdf4')
        'bdf5'
        >>> UniqueNames(names).unique('b_1')
        'b_1'
        >>> UniqueNames(names, sep='.').unique('a.1')
        'a.2'
        >>> UniqueNames(['a_'], sep='_').unique('a_')
        'a__0'
        >>> UniqueNames([]).unique('')
        '_0'
        >>> UniqueNames(['_1', '_2']).unique('')
        '_3'
        """
        if others:
            for _name in others:
                self._reserve(_name)

        return self.unique_names(name).next()

    def unique_names(self, name):
        r"""Return a generator that generates a sequence of sequential unique
        names.

        Examples
        --------
        >>> names = UniqueNames(['a', 'a.1', 'b_1'])
        >>> gen = names.unique_names('c')
        >>> gen.next(), gen.next()
        ('c', 'c_0')
        >>> gen = names.unique_names('a')
        >>> gen.next(), gen.next()
        ('a_0', 'a_1')
        >>> gen = names.unique_names('b')
        >>> gen.next(), gen.next()
        ('b_2', 'b_3')
        >>> gen = names.unique_names('')
        >>> gen.next(), gen.next()
        ('_0', '_1')
        """
        match = self.extension_re.match(name)
        if match:
            base, _c = match.groups()
            c = int(_c)
        elif name:
            base = name
            c = -1
        else:
            # If the name is empty, we must start at 0.
            base = name
            c = 0

        _c = self.bases.get(base, -1)
        if _c < 0 and name:
            uname = name
            c = max(c, -1)
        else:
            c = max(c, _c)
            uname = self.sep.join([base, str(c)])

        # uname is unique and base + sep + str(c + 1) will be the next unique
        # name
        while True:
            self.bases[base] = c + 1
            assert uname not in self.names
            self.names.add(uname)
            yield uname
            c = self.bases[base]
            uname = self.sep.join([base, str(c)])


class ReplacementError(Exception):
    r"""Replacements not consistent with parse tree."""
    def __init__(self, old, new, expected, actual):
        Exception.__init__(self,
                           "Replacement %s->%s: Expected %i, replaced %i" % (
                               old, new, expected, actual))


def _replace_rep(rep, replacements, check=False, robust=True):
    r"""Return rep with all replacements made.

    Parameters
    ----------
    rep : str
       String expression to make replacements in
    replacements : dict
       Dictionary of replacements.

    Examples
    --------
    >>> _replace_rep('n = array([1, 2, 3])', dict(array='array_1'))
    'n = array_1([1, 2, 3])'
    >>> _replace_rep('a + aa', dict(a='c'))
    'c + aa'
    >>> _replace_rep('(a, a)', dict(a='c'))
    '(c, c)'
    >>> _replace_rep("a + 'a'", dict(a='c'), robust=False)
    "c + 'c'"
    >>> _replace_rep("a + 'a'", dict(a='c'), check=True, robust=False)
    Traceback (most recent call last):
        ...
    ReplacementError: Replacement a->c: Expected 1, replaced 2
    >>> _replace_rep("a + 'a'", dict(a='c'))
    "c + 'a'"

    Notes
    -----
    In order to improve the replacements and eliminate the possibility
    of a replacement overwriting a previous replacement, we first
    construct a string with % style replacements and the effect the
    replacements.
    """
    if robust:
        return _replace_rep_robust(rep, replacements)

    if check:
        rep_names = AST(rep).names
        counts = dict((n, rep_names.count(n)) for n in replacements)

    identifier_tokens = string.letters + string.digits + "_"

    if replacements:
        # Replace all % characters so they are not interpreted as
        # format specifiers in the final replacement
        rep = rep.replace("%", "%%")

    for old in replacements:
        replacement_str = "%(" + old + ")s"
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
                c = i + l
                while c < len(rep) and rep[c] in string.whitespace:
                    c = c + 1
                next = rep[c:c+1]

                c = i - 1
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

        rep = replacement_str.join(parts)

        if check and not n_rep == counts[old]:
            raise ReplacementError(old, replacements[old], counts[old], n_rep)

    # Now do all the replacements en mass
    if replacements:
        rep = rep % replacements

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


def _replace_rep_robust(rep, replacements):
    r"""Return rep with all replacements made.

    Parameters
    ----------
    rep : str
       String expression to make replacements in
    replacements : dict
       Dictionary of replacements.

    Examples
    --------
    >>> _replace_rep_robust('n = array([1, 2, 3])', dict(array='array_1'))
    'n = array_1([1, 2, 3])'
    >>> _replace_rep_robust('a + aa', dict(a='c'))
    'c + aa'
    >>> _replace_rep_robust('(a, a)', dict(a='c'))
    '(c, c)'
    >>> _replace_rep_robust("a + 'a'", dict(a='c'))
    "c + 'a'"

    Notes
    -----
    This version is extremely robust, but very slow.  It uses the python parser.
    """
    if not replacements:
        return rep
    names = [_n for _n in ast.walk(ast.parse(rep))
             if _n.__class__ is ast.Name
             and _n.ctx.__class__ is not ast.Store]
    if not names:
        return rep
    if '_inf_numpy' in rep:
        import pdb;pdb.set_trace()
        print rep, replacements
    line_offsets = np.cumsum([0] + map(lambda _x:len(_x) + 1, # include \n
                                       rep.splitlines()))
    splits = sorted((_n.lineno - 1, _n.col_offset, len(_n.id), _n.id)
                     for _n in names)
    ind = 0
    results = []
    for _line, _col, _len, _id in splits:
        offset = line_offsets[_line] + _col
        results.append(rep[ind:offset])
        assert rep[offset:].startswith(_id)
        assert _len == len(_id)
        results.append(replacements.get(_id, _id))
        ind = offset + _len
    results.append(rep[ind:])
    res = "".join(results)
    return res


class AST(object):
    r"""Class to represent and explore the AST of expressions."""
    def __init__(self, expr):
        self.__dict__['expr'] = expr
        self.__dict__['ast'] = ast.parse(expr)
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
        return [_n.id for _n in ast.walk(ast.parse(self.expr))
                if _n.__class__ is ast.Name
                and _n.ctx.__class__ is not ast.Store]

class Arch(object):
    r"""Maintains a collection of objects and provides a mechanism for
    storing them on disk.

    Attributes
    ----------
    archive_name : str
       Special name of the archive in the imported module.  Variables
       of this name are not permitted in the archive.
    archive_prefix : str
       Private variables used to store unnamed objects start with
       this.  Variables names starting with this prefix are not
       permitted in the archive.
    autoname_prefix : str
       Variables inserted without a name are given an automatically
       generated name that starts with this.
    data : dict
       This is the dictionary of `(info, data, rep)` pairs where `info` is
       metadata.  If `data` is `NotImplemented` then it has not yet
       been loaded, and it should be loaded by executing the string
       `rep` which specifies where the data is stored.
    """
    def __init__(self, module_name=None, path = '.',
                 archive_prefix='_', archive_name='archive',
                 autoname_prefix='x_'):
        self.path = path
        self.module_name = module_name
        self.archive_name = archive_name
        self.archive_prefix = archive_prefix
        self.autoname_prefix = autoname_prefix
        self.data = {}

    def _check_name_okay(self, name):
        r"""Raise :exc:`ValueError` if `name` clashes with
        :attr:`archive_prefix` or :attr:`archive_name`."""
        if (name == self.archive_name
            or name.startswith(self.archive_prefix)):
            raise ValueError(
                "Variable name must not be archive_name = %s or start "
                "with archive_prefix = %s.  Got name=%s." %
                (self.archive_name, self.archive_prefix, name))

    def insert(self, data=None, name=None, info=None):
        r"""Insert `data` into :attr:`data_dict` with name `name` and
        add the metadata `info` to :attr:`info_dict`.
        """
        self._check_name(name)
        self.data[name] = (info, data)

    def __setitem__(self, name, data):
        r"""Add the entry to :attr:`data`.  Note that this does not
        allow metadata to be specified."""
        self.insert(data=data, name=name)

    def __getitem__(self, name):
        r"""Return the data associated with `name`.  If the data has
        not yet been loaded from disk, then this triggers the load."""

        (info, data) = self.data[name]
        if data is NotImplemented:
            return self.load(name)
        else:
            return data

    def write(self, module_name=None, path=None):
        r"""Write the archive to disk."""
        if path is None:
            path = self.path
        if module_name is None:
            module_name = self.module_name
        if module_name is None:
            raise ValueError(
                "Need to specify module_name before calling write.")

        arch = mmf.archive.Archive(datafile=os.path.join(path, 'data.hd5'))
        for name in self.data:
            arch.insert(name=self.data[name])

        mod_dir = os.path.join(path, module_name)
        if os.path.exists(mod_dir):
            if not os.path.isdir(mod_dir):
                raise ValueError(
                    "Module directory %s exists as a file!"
                    % mod_dir)

            # Directory already exists.  Update it.
        else:
            os.mkdirs(mod_dir)


        with open(os.path.join(mod_dir, '__init__.py'), 'w') as f:
            #f.write(init_str)  #???
            pass

    def load(self, name):
        r"""Load the data associated with `name` into :attr:`data` and
        return this."""


class DataSet(object):
    r"""Creates a module `module_name` in the directory `path`
    representing a set of data.

    The data set consists of a set of names other not starting with an
    underscore `'_'`.  Accessing (using :meth:`__getattr__` or equivalent)
    any of these names will trigger a dynamic load of the data
    associated with that name.  This data will not be cached, so if
    the returned object is deleted, the memory should be freed,
    allowing for the use of data sets larger than available
    memory. Assigning (using :meth:`__setattr__` or equivalent) these will
    immediately store the corresponding data to disk.

    In addition to the data proper, some information can be associated
    with each object that will be loaded each time the archive is
    opened.  This information is accessed using :meth:`__getitem__`
    and :meth:`__setitem__` and will be stored in the `__init__.py`
    file of the module.

    .. note:: A potential problem with writable archives is one of
       concurrency: two open instances of the archive might have
       conflicting updates.  We have two mechanisms for dealing with
       this as specified by the `synchronize` flag.

    .. warning:: The mechanism for saving is dependent on :meth:`__setattr__`
       and :meth:`__setitem__` being called.  This means that you must not rely
       on mutating members.  This will not trigger a save. For example, the
       following will not behave as expected:

       >>> import tempfile, shutil, os # Make a unique temporary module
       >>> t = tempfile.mkdtemp(dir='.')
       >>> os.rmdir(t)
       >>> modname = t[2:]
       >>> ds = DataSet(modname, 'w')
       >>> ds.d = dict(a=1, b=2)        # Will write to disk
       >>> ds1 = DataSet(modname, 'r')
       >>> ds1.d                        # See?
       {'a': 1, 'b': 2}

       This is dangerous... Do not do this.

       >>> ds.d['a'] = 6                # No write!
       >>> ds1.d['a']                   # This was not updated
       1

       Instead, do something like this: Store the mutable object in a
       local variable, manipulate it, then reassign it:

       >>> d = ds.d
       >>> d['a'] = 6
       >>> ds.d = d                     # This assignment will write
       >>> ds1.d['a']
       6
       >>> shutil.rmtree(t)

    Examples
    --------

    First we make the directory that will hold the data.  Here we use
    the :mod:`tempfile` module to make a unique name.

    >>> import tempfile, shutil       # Make a unique temporary module
    >>> t = tempfile.mkdtemp(dir='.')
    >>> os.rmdir(t)
    >>> modname = t[2:]

    Now, make the data set.

    >>> ds = DataSet(modname, 'w')

    Here is the data we are going to store.

    >>> import numpy as np
    >>> nxs = [10, 20]
    >>> mus = [1.2, 2.5]
    >>> dat = dict([((nx, mu), np.ones(nx)*mu)
    ...             for mu in mus
    ...             for nx in nxs])

    Now we add the data.  It is written upon insertion:

    >>> ds.nxs = nxs
    >>> ds.mus = mus

    If you want to include information about each point, then you can
    do that with the dictionary interface:

    >>> ds['nxs'] = 'Particle numbers'
    >>> ds['mus'] = 'Chemical potentials'

    This information will be loaded every time, but the data will only
    be loaded when requested.

    Here is a typical usage, storing data with some associated
    metadata in one shot using :meth:`_insert`.  This a public member,
    but we still use an underscore so that there is no chance of a
    name conflict with a data member called 'insert' should a user
    want one...

    >>> for (nx, mu) in dat:
    ...     ds._insert(dat[(nx, mu)], info=(nx, mu))
    ['x_0']
    ['x_1']
    ['x_2']
    ['x_3']

    >>> print(ds)
    DataSet './...' containing ['mus', 'nxs', 'x_2', 'x_3', 'x_0', 'x_1']

    Here is the complete set of info:

    This information is stored in the :attr:`_info_dict` dictionary as
    a set of records.  Don't modify this directly though as this will
    not properly write the data...

    >>> [(k, ds[k]) for k in sorted(ds)]
    [('mus', 'Chemical potentials'),
     ('nxs', 'Particle numbers'),
     ('x_0', (10, 2.5)),
     ('x_1', (20, 1.2)),
     ('x_2', (10, 1.2)),
     ('x_3', (20, 2.5))]
    >>> [(k, getattr(ds, k)) for k in sorted(ds)]
    [('mus', [1.2, 2.5]),
     ('nxs', [10, 20]),
     ('x_0', array([ 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5])),
     ('x_1', array([ 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2,
                     1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])),
     ('x_2', array([ 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])),
     ('x_3', array([ 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5,
                     2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5]))]

    .. todo:: Fix module interface...

    To load the archive, you can import it as a module::

       >> mod1 = __import__(modname)

    The info is again available in `info_dict` and the actual data
    can be loaded using the `load()` method.  This allows for the data
    set to include large amounts of data, only loading what is needed::

       >> mod1._info_dict['x_0'].info
       (20, 2.5)
       >> mod1._info_dict['x_0'].load()
       array([ 2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,
               2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5])

    If you want to modify the data set, then create a new data set
    object pointing to the same place:

    >>> ds1 = DataSet(modname, 'w')
    >>> print(ds1)
    DataSet './...' containing ['mus', 'nxs', 'x_2', 'x_3', 'x_0', 'x_1']

    This may be modified, but see the warnings above.

    >>> import numpy as np
    >>> ds1.x_0 = np.ones(5)

    This should work, but fails within doctests.  Don't know why...::

       >> reload(mod1)                    # doctest: +SKIP
       <module '...' from '.../mmf/archive/.../__init__.py'>

    Here we open a read-only copy:

    >>> ds2 = DataSet(modname)
    >>> ds2.x_0
    array([ 1.,  1.,  1.,  1.,  1.])
    >>> ds2.x_0 = 6
    Traceback (most recent call last):
       ...
    ValueError: DataSet opened in read-only mode.
    >>> shutil.rmtree(t)

    """
    _lock_file_name = "_locked"

    def __init__(self, module_name, mode='r', path=".",
                 synchronize=True,
                 verbose=False, _reload=False,
                 array_threshold=100, backup_data=False,
                 name_prefix='x_',
                 timeout=60):
        r"""Constructor.  Note that all of the parameters are stored
        as attributes with a leading underscore appended to the name.

        Parameters
        ----------
        synchronize : bool, optional
           If this is `True` (default), then before any read or write,
           the data set will refresh all variables from their current
           state on disk.  The resulting data set (with the new
           changes) will then be saved on disk.  During the write, the
           archive will be locked so that only one :class:`DataSet`
           and write at a time.

           If it is `False`, then locking is performed once a writable
           :class:`DataSet` is opened and only one writable instance
           will be able to be created at a time.
        module_name : str
           This is the name of the module under `path` where the data set
           will be stored.
        mode : 'r', 'w'
           Read only or read/write.
        path : str
           Directory to make data set module.
        name_prefix : str
           This -- appended with an integer -- is used to form unique
           names when :meth:`insert` is called without specifying a name.
        verbose : bool
           If `True`, then report actions.
        array_threshold : int
           Threshold size above which arrays are stored as hd5 files.
        backup_data : bool
           If `True`, then backup copies of overwritten data will be
           saved.
        timeout : int, optional
           Time (in seconds) to wait for a writing lock to be released
           before raising an :exc:`IOException` exception.  (Default
           is 60s.)

        .. warning:: The locking mechanism is to prevent two archives
           from clobbering upon writing.  It is not designed to
           prevent reading invalid information from a partially
           written archive (the reading mechanism does not use the
           locks).
        """
        self._synchronize = synchronize
        self._mode = mode
        self._verbose = verbose
        self._array_threshold = array_threshold
        self._module_name = module_name
        self._path = path
        self._backup_data = backup_data
        self._name_prefix = name_prefix
        self._info_dict = {}
        self._timeout = timeout
        self._maxint = -1

        # If a writing lock is established, then the name of the lock
        # file will be set here.  This serves as a flag.  Locking is
        # implemented through the with mechanism.
        if synchronize:
            self._lock_file = ""
        else:
            # Establish lock now or fail...
            self._lock_file = self._lock()

        mod_dir = os.path.join(path, module_name)
        key_file = os.path.join(mod_dir, '_this_dir_is_a_DataSet')
        if os.path.exists(mod_dir):
            if not os.path.exists(key_file):
                raise ValueError(
                    ("Directory %s exists and is not a DataSet repository. "
                     "Please choose a unique location. ") % (mod_dir,))

            self._load()
        elif mode == 'w':
            if self._verbose:
                print("Making directory %s for output." % (mod_dir,))
            os.makedirs(mod_dir)
            open(key_file, 'w').close()
        else:
            raise ValueError(
                ("Default mode is read-only but directory %s does "
                 "not exist. Please choose an existing DataSet or "
                 "specify write mode with mode='w'.") % (mod_dir,))

        # Needed for pre 2.6 python version to support tab completion
        if sys.version < "2.6":
            self.__members__ = self._info_dict.keys()

    def _load(self):
        r"""Create the data set from an existing repository."""
        curdir = os.path.abspath(os.curdir)
        os.chdir(self._path)
        d = {}
        init_file = os.path.join(self._module_name, '__init__.py')
        if os.path.exists(init_file):
            execfile(init_file, d)
            self._info_dict = d.get('_info_dict', {})
        else:
            self._info_dict = {}
        del d
        os.chdir(curdir)

    def _lock(self):
        r"""Actually write the lock file, waiting for timeout if
        needed.  Return the lock file name on success"""
        lock_file = os.path.join(self._path, self._module_name,
                                 self._lock_file_name)

        if os.path.exists(lock_file):
            tic = time.time()
            # Archive locked
            while tic + self._timeout < time.time():
                if not os.path.exists(lock_file):
                    # Lock release, so make lock-file
                    open(lock_file, 'w').close()
                    return lock_file
                time.sleep(0.5)
            # Timeout
            raise IOError(
                "DataSet locked.  Please close or remove lock '%s'" %
                (lock_file,))
        else:
            open(lock_file, 'w').close()
            return lock_file

    def _unlock(self):
        r"""Actually remove the lock file."""
        if self._lock_file:
            if os.path.exists(self._lock_file):
                os.remove(self._lock_file)
                self._lock_file = ""
            else:
                warnings.warn("Lock file %s lost or missing!" %
                              (self._lock_file,))

    @contextmanager
    def _ds_lock(self):
        r"""Lock the data set for writing."""
        try:
            if self._synchronize:
                if self._lock_file:
                    raise NotImplementedError(
                        "Lock already established! "
                        "(Reentry not supported)")
                else:
                    self._lock_file = self._lock()
            else:
                # Lock should have been established upon construction
                if (not self._lock_file
                    or not os.path.exists(self._lock_file)):
                    raise IOError("Lost lock on %s!" % self._lock_file)
            yield
        except:
            raise
        finally:
            r"""Reset the data set writing lock."""
            if self._synchronize:
                self._unlock()

    def __iter__(self):
        return self._info_dict.__iter__()

    def __dir__(self):
        r"""Provides :func:`get` support fr tab completion etc."""
        return [k for k in self]

    def __getattr__(self, name):
        r"""Load the specified attribute from disk."""
        if name.startswith('_') or not name in self:
            # Provide access to state variables.
            raise AttributeError(
                "'%s' object has no attribute '%s'" %
                (self.__class__.__name__, name))

        archive_file = os.path.join(self._path,
                                    self._module_name,
                                    "%s.py" % (name,))
        if os.path.exists(archive_file):
            d = {}
            __d = {Archive.data_name: d}

            datafile = os.path.join(self._path,
                                    self._module_name,
                                    "data_%s.hd5" % (name,))
            f = None
            if os.path.exists(datafile):
                with h5py.File(datafile, 'r') as f:
                    for k in f:
                        d[k] = np.asarray(f[k])
            try:
                execfile(archive_file, __d)
            except KeyError, err:
                if f is None:
                    raise
                else:
                    msg = "\n".join([
                        "No datafile '%s' found to load '%s'.",
                        (datafile, name)])
                    f.close()
                    raise KeyError(msg)
            res = __d[name]
            del d
            del __d
        else:
            res = None
        return res

    def __setattr__(self, name, value):
        r"""Store the specified attribute to disk."""
        if name.startswith('_'):
            # Provide access to state variables.
            return object.__setattr__(self, name, value)

        if self._mode == 'r':
            raise ValueError("DataSet opened in read-only mode.")

        with self._ds_lock():              # Establish lock
            arch = Archive(array_threshold=self._array_threshold)
            arch.insert(**{name: value})
            archive_file = os.path.join(self._path,
                                        self._module_name,
                                        "%s.py" % (name,))
            with backup(archive_file, keep=self._backup_data):
                # This conversion does all the work, and may throw
                # exceptions, so we do this before trying to write.
                arch_rep = str(arch)
                with open(archive_file, 'w') as f:
                    f.write(arch_rep)

            datafile = os.path.join(self._path,
                                    self._module_name,
                                    "data_%s.hd5" % (name,))
            with backup(datafile, keep=self._backup_data):
                if arch.data:
                    if self.hdf5 and h5py:
                        with h5py.File(datafile) as f:
                            for _name in arch.data:
                                f[_name] = arch.data[_name]
                    else:
                        raise NotImplementedError(
                            "Data can presently only be saved with hdf5")

        # Needed for pre 2.6 python version to support tab completion
        if sys.version < "2.6":
            self.__members__.append(name)

        if name not in self._info_dict:
            # Set default info to None.
            self[name] = None

    def __contains__(self, name):
        r"""Fast containment test."""
        if self._synchronize:
            self._load()
        return name in self._info_dict

    def __getitem__(self, name):
        r"""Return the info associate with `name`."""
        if self._synchronize:
            self._load()
        return self._info_dict[name]

    def __setitem__(self, name, info):
        r"""Set the info associate with `name` and write the module
        `__init__.py` file."""
        if self._mode == 'r':
            raise ValueError("DataSet opened in read-only mode.")

        with self._ds_lock():
            if self._synchronize:
                self._load()

            self._info_dict[name] = info

            if self._module_name:
                arch = Archive(allowed_names=['_info_dict'])
                arch.insert(_info_dict=self._info_dict)
                init_file = os.path.join(
                    self._path, self._module_name, '__init__.py')

                with backup(init_file):
                    with open(init_file, 'w') as f:
                        f.write(str(arch))

    def __str__(self):
        if self._synchronize:
            self._load()
        return ("DataSet %r containing %s" % (
            os.path.join(self._path, self._module_name),
            str(self._info_dict.keys())))

    def __repr__(self):
        return ("DataSet(%s)" %
                ", ".join(["%s=%s" % (k, repr(getattr(self, '_' + k)))
                           for k in ['module_name', 'path',
                                     'synchronize',
                                     'verbose',
                                     'array_threshold', 'backup_data',
                                     'name_prefix', ]]))

    def _keys(self):
        return self._info_dict.keys()

    def _insert(self, *v, **kw):
        r"""Store object and info in the archive under `name`.
        Returns a list of the names added.

        Call as `_insert(name=obj, info=info)` or `insert(obj,
        info=info)`.   The latter form will generate a unique name.

        When the data set is imported, the `info` will be restored as
        `info_dict[name].info` but the actual data `obj` will not be
        restored until `info_dict[name].load()` is called.
        """
        names = set()
        if self._mode == 'r':
            raise ValueError("DataSet opened in read-only mode.")
        if 'info' in kw:
            info = kw.pop('info')
        else:
            info = None

        #Why did I do this?  I don't use it...
        #mod_dir = os.path.join(self._path, self._module_name)
        for name in kw:
            self[name] = info
            self.__setattr__(name, kw[name])
            names.add(name)

        for obj in v:
            i = self._maxint + 1
            name = self._name_prefix + str(i)
            while name in self._info_dict:
                i += 1
                name = self._name_prefix + str(i)
            self._maxint = i
            self[name] = info
            self.__setattr__(name, obj)
            names.add(name)
        return list(names)

    def __del__(self):
        r"""Make sure we unlock archive."""
        self._unlock()
