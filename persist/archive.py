r"""This is an idea for a model of objects that save their state.
Here is a typical usage:

>>> a = Archive()
>>> a.insert(x=3)
>>> a.insert(y=4)
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

    def get_persistent_rep(self):
        '''Return `(rep, args, imports)`.

        Define a persistent representation `rep` of the instance self where
        the instance can be reconstructed from the string rep evaluated in the
        context of dict args with the specified imports = list of `(module,
        iname, uiname)` where one has either `import module as uiname`, `from
        module import iname` or `from module import iname as uiname`.
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

- Archives must not contain explicit circular dependencies.  These must be
  managed by constructors:

    >>> l1 = []
    >>> l2 = [l1]
    >>> l1.append(l2)
    >>> l1                          # repr does not even work...
    [[[...]]]
    >>> a = Archive()
    >>> a.insert(l=l1)
    >>> str(a)
    Traceback (most recent call last):
        ...
    CycleError: Archive contains cyclic dependencies.

- Only some sparse matrices are supported:

     >>> M = np.random.random((10, 10))
     >>> a = Archive()
     >>> a.insert(lil=sp.sparse.lil_matrix(M))
     >>> a
     Traceback (most recent call last):
     NotImplementedError: lil_matrix

Large Archives
--------------
For small amounts of data, the string representation of
:class:`Archive` is usually sufficient.  For large amounts of binary
data, however, this is extremely inefficient.  In this case, a separate archive
format is used where the archive is turned into a module that contains a binary
datafile or datadir.

Developer's Note
----------------
.. todo::
   - Consider allowing components to be byte-compiled for performance.  (Only
     really helps if the components have lots of code -- most of my loading
     performance issues are due instead to the execution of constructors, so
     this will not help.)  The issue here is fact that byte compilation takes
     place in a parallel process that may not finish before a dataset is updated,
     invalidating the byte-compiled files.
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
     23999d0c395e: Some of the code to make unique indices was running in
     O(n^2) time because of expensive "in" lookups.  This was fixed by adding a
     `_maxint` cache. The remaining performance issues appear to be in
     `_replace_rep`.

After issue 12 arose, I decided to change the structure of archives to
minimize the need to replace text.  New archives will evaluate objects in a
local scope.  Here is an example, first in the old format::

   from objects import Container as _Container
   _y = [1, 2, 3, 4]
   l1 = [_y, [1, _y]]
   l2 = [_y, l1]
   c = _Container(_y=_y, x=1, l=l2)
   del _Container
   del _y
   try: del __builtins__, _arrays
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
             Container=__import__('objects',
                                  fromlist=['Container']).Container)
   c = _g['_c'] = eval('Container(x=x, _y=_y, l=l2)', _d)
   del _g, _d
   try: del __builtins__, _arrays
   except NameError: pass

Now a version using local scopes to eschew :func:`eval`.  One can use either
classes or functions: preliminary profiling shows functions to be slightly
faster - and there is no need for using `global` - so I am using that for now.
Local variables are assigned using keyword arguments.  The idea is to establish
a one-to-one correspondence between functions and each object so that the
representation can be evaluated without requiring textual replacements that
have been the source of errors.

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
       from objects import Container as Container
       return Container(x=x, _y=_y, l=l2)
   c = _d(x=1)
   del _d
   del _y
   try: del __builtins__, _arrays
   except NameError: pass

"""
from __future__ import division, with_statement

from collections import OrderedDict
from contextlib import contextmanager
try:                            # Python 3 version
    import builtins
    import pickle
except ImportError:             # pragma: no cover
                                # Python 2 version
    import cPickle as pickle
    import __builtin__ as builtins
import ast
import copy
import imp
import inspect
import logging
import os
import re
import string
import sys
import time
import types
import warnings

import six

from ._contrib.RADLogic import topsort

try:
    import numpy as np
except ImportError:             # pragma: no cover
    np = None

try:
    import scipy.sparse
    sp = scipy
except ImportError:             # pragma: no cover
    sp = None

try:
    import h5py
except ImportError:             # pragma: no cover
    h5py = None

from . import interfaces
from . import objects

__all__ = ['Archive', 'DataSet', 'restore',
           'ArchiveError', 'DuplicateError', 'repr_',
           'get_imports']


_HDF5_EXTS = set(['hf5', 'hd5', 'hdf5'])


class ArchiveError(Exception):
    r"""Archiving error."""


class CycleError(ArchiveError):
    r"""Cycle found in archive."""
    message = "Archive contains cyclic dependencies."

    def __init__(self, *v):
        self.args = v

    def __str__(self):
        return self.message


class DuplicateError(ArchiveError):
    r"""Object already exists."""

    def __init__(self, name):
        msg = "Object with name '%s' already exists in archive." % (name,)
        ArchiveError.__init__(self, msg)


def unique_list(l, preserve_order=True):
    """Make list contain only unique elements but preserve order.

    >>> l = [1,2,4,3,2,3,1,0]
    >>> unique_list(l)
    [1, 2, 4, 3, 0]
    >>> l
    [1, 2, 4, 3, 2, 3, 1, 0]
    >>> unique_list(l, preserve_order=False)
    [0, 1, 2, 3, 4]
    >>> unique_list([[1],[2],[2],[1],[3]])
    [[1], [2], [3]]

    See Also
    --------
    http://www.peterbe.com/plog/uniqifiers-benchmark
    """
    try:
        if preserve_order:
            s = set()
            return [x for x in l if x not in s and not s.add(x)]
        else:
            return list(set(l))
    except TypeError:  # Special case for non-hashable types
        res = []
        for x in l:
            if x not in res:
                res.append(x)
        return res


def restore(archive, env={}):
    r"""Return dictionary obtained by evaluating the string arch.

    arch is typically returned by converting an Archive instance into
    a string using :func:`str` or :func:`repr`:

    Examples
    --------
    >>> a = Archive()
    >>> a.insert(a=1, b=2)
    >>> arch = str(a)
    >>> d = restore(arch)
    >>> print("%(a)i, %(b)i"%d)
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


class ArrayManager(object):
    """Class for managing arrays on disk.

    Provides methods for saving an loading arrays to/from disk in a variety of
    formats.
    """

    hdf5_code = """
    def {DATA_NAME}():
        import os.path, numpy, h5py
        try: dir = os.path.dirname(__file__)
        except NameError: dir = {DIRNAME:s}
        res = {{}}
        with h5py.File(os.path.join(dir, {FILENAME:s}), 'r') as f:
            for name in {NAMES}:
                res[name] = numpy.asarray(f[name])
        return res

    {DATA_NAME} = {DATA_NAME}()
    """

    npz_code = """
    def {DATA_NAME}():
        import os.path, numpy
        try: dir = os.path.dirname(__file__)
        except NameError: dir = {DIRNAME:s}
        res = {{}}
        with numpy.load(os.path.join(dir, {FILENAME:s})) as f:
            for name in {NAMES}:
                res[name] = numpy.asarray(f[name])
        return res

    {DATA_NAME} = {DATA_NAME}()
    """

    npy_code = """
    def {DATA_NAME}():
        import os.path, numpy
        try: dir = os.path.dirname(__file__)
        except NameError: dir = {DIRNAME:s}
        res = {{}}
        for name in {NAMES}:
            filename = os.path.join(dir, {FILENAME:s}, name + ".npy")
            res[name] = numpy.asarray(numpy.load(filename))
        return res

    {DATA_NAME} = {DATA_NAME}()
    """

    @staticmethod
    def get_ext(filename):
        """Return the extension of filename"""
        basename = os.path.basename(filename)
        ext = ''
        if os.path.extsep in basename:
            ext = basename.split(os.path.extsep)[-1].lower()
        return ext

    @classmethod
    def save_arrays(cls, arrays, dirname='.', filename=None, keep=False,
                    data_format='npy', arrays_name='_arrays'):
        """Return `(rep, files)` and save the array.

        Arguments
        ---------
        arrays : dict
           Mapping from names (must be valid python identifiers) to data arrays.
        dirname : str
           Name of directory in which to archive the data.
        filename : str
           Name of file in which to archive the data.  If not provided, then arrays
           are stored in files with names as specified in the `arrays` dict. (Only
           relevant for `npz` and `hdf5` formats which can store multiple arrays.)
        data_format : 'hdf5', 'npy', 'npz'
           Format of data on disk.
        arrays_name : str
           Name of dictionary in which to store the `arrays` dict in the executable
           string.

        Returns
        -------
        rep : str
           String containing code that can be executed to load the arrays as
           part of a package/module.  After executing this code, the arrays
           will be available in the variable `arrays_name`.
        files : list(str)
           List of filenames of created files.
        """
        files = []
        if data_format == 'npy':
            if filename is not None:
                dirname = os.path.join(dirname, filename)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            for name in arrays:
                _filename = os.path.join(dirname,
                                         os.path.extsep.join([name, 'npy']))
                with backup(_filename, keep=keep):
                    np.save(_filename, arrays[name])
                    files.append(_filename)
            res = cls.npy_code
        elif data_format in ['hdf5', 'npz']:
            if filename is None:
                raise ValueError(
                    "Must specify filename for data_format={}"
                    .format(repr(data_format)))
            ext = cls.get_ext(filename)
            if data_format == 'hdf5' and ext not in _HDF5_EXTS:
                filename = os.path.extsep.join([filename, 'hd5'])
            elif data_format == 'npz' and ext != 'npz':
                filename = os.path.extsep.join([filename, 'npz'])
            _filename = os.path.join(dirname, filename)
            with backup(_filename, keep=keep):
                if data_format == 'hdf5':
                    res = cls.hdf5_code
                    with h5py.File(_filename) as f:
                        for name in arrays:
                            f[name] = arrays[name]
                else:  # data_format == 'npz'
                    res = cls.npz_code
                    np.savez(_filename, **arrays)
                files.append(_filename)
        else:
            raise NotImplementedError(
                "Expected data_format in ['hdf5', 'npz', 'npy'], got {}"
                .format(repr(data_format)))

        if filename is None:
            filename = ''

        rep = ('\n'.join([_l[4:] for _l in res.splitlines()])).format(
            DATA_NAME=arrays_name,
            NAMES="[{}]".format(', '.join(map(repr, arrays))),
            DIRNAME=repr(dirname),
            FILENAME=repr(filename))
        return rep, files

    @staticmethod
    def load_arrays(rep, arrays_name='_arrays'):
        d = {}
        exec(rep, d)
        return d[arrays_name]


_EXTS = {
    'hdf5': '.hd5',
    'npy': '',
    'npz': '.npz'
}


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
       If `True`, then use a depth-first algorithm to reduce the dependency
       graph, otherwise use a tree.  (See :meth:`make_persistent`.)
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
    backup_data : bool
       If `True` then a backup of the data will first be made with an extension
       `'.bak'` or `'_#.bak'` if backups already exists.  Otherwise, the file will
       be overwritten.  (Actually, a backup will always be made, but if the
       creation of the new file is successful, then the backup will be deleted if
       this is `False`.)
    single_item_mode : bool
       If `True`, then only one item is allowed in the archive at a time, and
       the importable representation saved by `Archive.save()` will replace the
       imported module with this item.  This is primarily for use with DataSet
       but might be of use elsewhere.  See `Archive.save()` for details.
    allowed_names : [str], optional
       If provided, then these names will be considered acceptable.
       This allows for 'private' names to be used by specialized
       structures.  These must not start with `gname_prefix`.
    gname_prefix : str, optional
       This string is used to prefix all global variables.
    scoped : bool, optional
       If `True`, then the representation is "scoped": i.e. a series of
       function definitions.  This allows each entry to be evaluated in a local
       scope without the need for textual replacements in the representation
       (which can be either costly or error-prone).  The resulting output is
       not as compact (can be on the order of 4 times larger), nor as legible,
       but archiving can be much faster.
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

    We can include functions and classes: These are stored by their
    names and imports.

    >>> import numpy as np
    >>> arch.insert(f=np.sin, g=restore)

    Here we include a list and a dictionary containing that list.  The
    resulting archive will only have one copy of the list since it is
    referenced.

    >>> l0 = ['a', 'b']
    >>> l = [1, 2, 3, l0]
    >>> d = dict(l0=l0, l=l, s='hi')
    >>> arch.insert(d=d, l=l)

    Presently the archive is just a graph of objects and string
    representations of the objects that have been directly inserted.
    For instance, `l0` above has not been directly included, so if it
    were to change at this point, this would affect the archive.

    To make the archive persistent so there is no dependence on
    external objects, we call :meth:`make_persistent`.

    >>> _tmp = arch.make_persistent()

    This is not strictly needed as it will be called implicitly by the
    following call to :meth:`__str__` which returns the string
    representation.  (Note also that this will thus be called whenever
    the archive is printed.)

    >>> s = str(arch)
    >>> print(s)
    from numpy import sin as _sin
    from persist.archive import restore as _restore
    from builtins import dict as _dict
    _g11 = ['a', 'b']
    l = [1, 2, 3, _g11]
    d = _dict([('l0', _g11), ('l', l), ('s', 'hi')])
    x = 4
    f = _sin
    g = _restore
    del _sin
    del _restore
    del _dict
    del _g11
    try: del __builtins__, _arrays
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

    **Single Item Mode**

    Archives can also be used in single item mode.  This is primarly intended
    for used with DataSets, but could be of use to users.  In this mode, only
    one item can be inserted.  When saving these archives as a module, upon
    import, the module will be replaced with the actual item.  This is used in
    the DataSet format to allow delayed importing of large objects:

    >>> a = Archive(single_item_mode=True)
    >>> a.insert(x=1)
    >>> a.insert(y=2)
    Traceback (most recent call last):
       ...
    ValueError: Can't insert 'y' into single_item_mode=True archive with 'x'.
    """
    data_name = '_arrays'

    def __init__(self, flat=True, tostring=True, check_on_insert=False,
                 array_threshold=None,
                 backup_data=True, single_item_mode=False,
                 allowed_names=None, gname_prefix='_g',
                 scoped=True, robust_replace=True):
        self.tostring = tostring
        self.flat = flat
        self.imports = []
        self.arch = []
        self.ids = {}
        self.backup_data = backup_data
        if not allowed_names:
            allowed_names = []
        self.allowed_names = allowed_names
        self.gname_prefix = gname_prefix
        self.single_item_mode = single_item_mode

        self._section_sep = ""  # string to separate the sections
        if np:
            self._numpy_printoptions = {'infstr': 'Inf',
                                        'threshold': np.inf,
                                        'suppress': False,
                                        'linewidth': 200,
                                        'edgeitems': 3,
                                        'precision': 16,
                                        'nanstr': 'NaN'}
            if array_threshold is None:
                array_threshold = np.inf

        self.array_threshold = array_threshold

        self.check_on_insert = check_on_insert
        self.data = {}

        self.scoped = scoped
        self.robust_replace = robust_replace

        self._maxint = -1       # Cache of maximum int label in archive
        self._ids = OrderedDict()

    def get_id(self, obj):
        """Return a unique id for the object.

        This function is used as a proxy for the builtin id function so that id
        numbers are generated in sequential order based on calls to this
        function.  This makes the sorting of nodes in the graph predictable for
        tests.  (Otherwise some tests depend on the ordering of `id()` which
        varies from run to run.)
        """
        return self._ids.setdefault(id(obj), len(self._ids))

    def names(self):
        r"""Return list of unique names in the archive."""
        return [k[0] for k in self.arch]

    def get_persistent_rep(self, obj, env):
        r"""Return `(rep, args, imports)` where `obj` can be reconstructed
        from the string `rep` evaluated in the context of `args` with the
        specified `imports` = list of `(module, iname, uiname)` where one
        has either `import module as uiname`, `from module import
        iname` or `from module import iname as uiname`.
        """
        if (interfaces.IArchivable.providedBy(obj)
                or isinstance(obj, objects.Archivable)):
            return obj.get_persistent_rep(env)

        for class_ in self._dispatch:
            if isinstance(obj, class_):
                return self._dispatch[class_](self, obj, env=env)

        if inspect.ismethod(obj):
            return get_persistent_rep_method(obj, env)

        if inspect.isfunction(obj) and (
                getattr(obj, '__qualname__', obj.__name__)
                != obj.__name__):
            return get_persistent_rep_classmethod(obj, env)
            
        if hasattr(obj, 'get_persistent_rep'):
            try:
                return obj.get_persistent_rep(env)
            except TypeError as e:
                warnings.warn("\n".join([
                    "Found get_persistent_rep() but got TypeError:",
                    str(e)]))

        if hasattr(obj, 'archive_1'):
            warnings.warn("archive_1 is deprecated: use get_persistent_rep",
                          DeprecationWarning)
            try:
                return obj.archive_1(env)
            except TypeError as e:
                warnings.warn("\n".join([
                    "Found archive_1() but got TypeError:",
                    str(e)]))

        rep = repr(obj)
        if rep.startswith('<'):
            try:
                return get_persistent_rep_pickle(obj, env)
            except (pickle.PickleError, AttributeError):
                raise ArchiveError(
                    "Could not archive object {}.  Even tried pickling!"
                    .format(rep))
        else:
            return get_persistent_rep_repr(obj, env, rep=rep)

    def _archive_ndarray(self, obj, env):
        """Archival of numpy arrays."""
        if self.array_threshold < np.prod(obj.shape):
            # Data should be archived to a data file.
            array_name = None
            for array_name in self.data:
                # Check if array exists first
                if self.data[array_name] is obj:
                    break
                else:
                    array_name = None

            if array_name is None:
                array_prefix = 'array_'
                i = self._maxint + 1
                array_name = array_prefix + str(i)
                while array_name in self.data:
                    # This should only execute a few times if the user, for
                    # example, included manually an element with name
                    # "array_<n>" for example.
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

            rep = "numpy.frombuffer(%r, dtype=%r).reshape(%s)" % (
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
        if (sp.sparse.isspmatrix_csc(obj)
                or sp.sparse.isspmatrix_csr(obj)
                or sp.sparse.isspmatrix_bsr(obj)):
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
        if getattr(obj, '__qualname__', obj.__name__) != obj.__name__:
            # Class method
            return get_persistent_rep_classmethod(obj, env)
        return get_persistent_rep_obj(obj, env)

    def _archive_list(self, obj, env):
        return get_persistent_rep_list(obj, env)

    def _archive_tuple(self, obj, env):
        return get_persistent_rep_tuple(obj, env)

    def _archive_dict(self, obj, env):
        return get_persistent_rep_dict(obj, env)

    def _archive_float(self, obj, env):
        return get_persistent_rep_float(obj, env)

    def _archive_type(self, obj, env):
        return get_persistent_rep_type(obj, env)

    _dispatch = {
        types.BuiltinFunctionType: _archive_func,
        types.FunctionType: _archive_func,
        list: _archive_list,
        tuple: _archive_tuple,
        dict: _archive_dict,
        float: _archive_float,
        complex: _archive_float,
        type: _archive_type}
    
    if hasattr(types, 'ClassType'):
        # Old-style classes in python 2.
        _dispatch[types.ClassType] = _archive_type

    if np:
        _dispatch.update({
            np.ndarray: _archive_ndarray,
            np.ufunc: _archive_func})

    if sp:
        _dispatch.update({
            sp.sparse.base.spmatrix: _archive_spmatrix
        })

    def unique_name(self, name):
        r"""Return a unique name not contained in the archive."""
        names = _unzip(self.arch)[0]
        return UniqueNames(names).unique(name)

    def insert(self, v=None, env=None, **kwargs):
        r"""Insert named object pairs (kwargs) into the archive.

        If `self.check_on_insert`, then try generating rep (may raise
        an exception).

        If name already exists in the archive, then a `DuplicateError`
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
        >>> a.insert(x=2)       # Duplicates are okay.
        >>> a.insert(x=3)       # Changes are not...
        Traceback (most recent call last):
           ...
        DuplicateError: Object with name 'x' already exists in archive.
        >>> a.insert(**{a.unique_name('x'):3}) # ...but can make unique label
        >>> a.insert(a=4, b=5)   # Can insert multiple items
        >>> a.insert(A=np.array([1, 2, 3]))
        >>> print(a)                     # doctest: +SKIP
        import numpy as _numpy
        x = 2
        x_0 = 3
        A = _numpy.frombuffer('\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00', dtype='<i8').reshape((3,))
        b = 5
        a = 4
        del _numpy
        try: del __builtins__, _arrays
        except NameError: pass

        For testing purposes we have to sort the lines of the output:

        >>> print("\n".join(sorted(str(a).splitlines())))
        A = _numpy.frombuffer(b'\x01\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00', dtype='<i8').reshape((3,))
        a = 4
        b = 5
        del _numpy
        except NameError: pass
        import numpy as _numpy
        try: del __builtins__, _arrays
        x = 2
        x_0 = 3

        The default :mod:`numpy` representation for arrays is not very
        friendly, so we might want to use strings instead.  Be aware
        that this might incur a performance hit.

        >>> a = Archive(tostring=False)
        >>> a.insert(x=2)
        >>> a.insert(A=np.array([1, 2, 3]))
        >>> c = np.array([1, 2.0+3j, 3])
        >>> a.insert(c=c)
        >>> a.insert(cc=[c, c, [3]])
        >>> a.make_persistent() # doctest: +NORMALIZE_WHITESPACE
        ([('numpy', None, '_numpy'),
          ('numpy', 'inf', '_inf'),
          ('numpy', 'nan', '_nan')],
         [('c', '_numpy.array([1.+0.j, 2.+3.j, 3.+0.j])'),
          ('cc', '[c, c, [3]]'),
          ('x', '2'),
          ('A', '_numpy.array([1, 2, 3])')])

        Names must not start with an underscore:

        >>> a.insert(_x=5)
        Traceback (most recent call last):
           ...
        ValueError: name must not start with '_'

        This can be overridden by using :attr:`allowed_names`:

        >>> a.allowed_names.append('_x')
        >>> a.insert(_x=5)
        >>> a.make_persistent() # doctest: +NORMALIZE_WHITESPACE
        ([('numpy', None, '_numpy'),
          ('numpy', 'inf', '_inf'),
          ('numpy', 'nan', '_nan')],
         [('c', '_numpy.array([1.+0.j,  2.+3.j, 3.+0.j])'),
          ('cc', '[c, c, [3]]'),
          ('x', '2'),
          ('A', '_numpy.array([1, 2, 3])'),
          ('_x', '5')])
        """
        if v is not None:
            raise ValueError(
                'Insert objects with a key: insert(x=3), not insert({})'
                .format(v))

        if env is None:
            env = {}

        names = []
        if self.single_item_mode:
            if len(kwargs) != 1:
                raise ValueError(
                    "Can't insert {} items when single_item_mode=True"
                    .format(len(kwargs)))
            name = list(kwargs)[0]
            if self.arch and name not in self.names():
                raise ValueError(
                    "Can't insert {} into single_item_mode=True archive with {}."
                    .format(repr(name), repr(self.names()[0])))
            
        for name in kwargs:
            obj = kwargs[name]
            if (name.startswith('_') and name not in self.allowed_names):
                raise ValueError("name must not start with '_'")

            # First check to see if object is already in archive:
            unames, objs, envs = _unzip(self.arch)

            obj_ids = list(map(self.get_id, objs))
            obj_id = self.get_id(obj)
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
                    (rep, args, imports) = self.get_persistent_rep(obj, env)

                self.arch.append((uname, obj, env))
                ind = len(self.arch) - 1

            assert(ind is not None)
            uname, obj, env = self.arch[ind]
            names.append(uname)
            self.ids[uname] = self.get_id(obj)

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

        The :meth:`get_persistent_rep` method provides this functionality,
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
        the node has less than two parents.  In the future, different
        algorithms can be specified with :attr:`flat`:

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

        # #names = _unzip(self.arch)[0]

        # Generate dependency graph
        try:
            graph = Graph(objects=self.arch,
                          get_persistent_rep=self.get_persistent_rep,
                          robust_replace=self.robust_replace,
                          get_id=self.get_id)
        except topsort.CycleError as err:
            six.reraise(CycleError, CycleError(*err.args), sys.exc_info()[-1])
        
        # Optionally: at this stage perform a graph reduction.
        graph.reduce()
        names_reps = [(node.name, node.rep)
                      for id_ in graph.order
                      for node in [graph.nodes[id_]]]

        # Add any leftover names (aliases):
        names_reps.extend([
            (name, node.name)
            for name in self.ids
            if name not in list(zip(*names_reps))[0]
            for node in [graph.nodes[self.ids[name]]]])

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
                    "import {} as {}".format(module, uiname))
                del_lines.append("del {}".format(uiname))
            elif iname == uiname or uiname is None:  # pragma: no cover
                # Probably never happens because uinames start with _
                import_lines.append(
                    "from {} import {}".format(module, uiname))
                del_lines.append("del {}".format(uiname))
            else:
                import_lines.append(
                    "from {} import {} as {}".format(module, iname, uiname))
                del_lines.append("del {}".format(uiname))
        return import_lines, del_lines

    def __str__(self):
        r"""Return a string representing the archive.

        This string can be saved to a file, and that file imported to
        define the required symbols.
        """
        if self.scoped:
            res = self.scoped__str__()
        else:
            res = self.unscoped_str()

        return res

    def _get_del_lines(self):
        return ["try: del __builtins__, {}".format(self.data_name),
                "except NameError: pass"]
    
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

        del_lines.extend(self._get_del_lines())

        lines = "\n".join(["{} = {}".format(uname, rep)
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
                           get_persistent_rep=self.get_persistent_rep,
                           gname_prefix=self.gname_prefix,
                           allowed_names=set(self.allowed_names),
                           get_id=self.get_id)
        except topsort.CycleError as err:
            six.reraise(CycleError, CycleError(*err.args), sys.exc_info()[-1])

        # Optionally: at this stage perform a graph reduction.
        # graph.reduce()

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
                           argnames=",".join(sorted(node.args)),
                           args=",".join([
                                "=".join([
                                    _a,
                                    graph.nodes[self.get_id(node.args[_a])].name])
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

        gnames = ", ".join(_n for _n in names
                           if _n.startswith(self.gname_prefix)
                           and _n not in self.allowed_names)
        if gnames:
            results.append("del %s" % (gnames,))
        results.extend(self._get_del_lines())

        return "\n".join(results)

    def save_data(self, datafile=None, filename=None, data_format='npy'):
        """Save any arrays in `self.data` to disk.

        Arguments
        ---------
        data_format : 'npy', 'npz', 'hdf5
            Data format used to store binary data.
        """
        files = []
        rep = None
        if self.data:
            if datafile is not None:
                dirname = datafile
                if filename is None and data_format != 'npy':
                    dirname = os.path.dirname(datafile)
                    filename = os.path.basename(datafile)

                rep, files = ArrayManager.save_arrays(arrays=self.data,
                                                      dirname=dirname,
                                                      filename=filename,
                                                      keep=self.backup_data,
                                                      data_format=data_format)
            else:
                warnings.warn(
                    "Data arrays {} exist but no datafile specified. "
                    .format(sorted(self.data))
                    + "Save data manually and populate in _arrays dict.")
        
        return rep, files

    def save(self, dirname, name=None, package=True, arrays_name='_arrays',
             data_format='npy', force=False, clear_on_reload=True):
        """Save the archive to disk as an importable package or module.

        Arguments
        ---------
        dirname : str
           Package will be placed in this directory
        name : str
           Name for the package.  May be omitted if in single_item_mode, in
           which case the name will be the name of the single item.
        arrays_name : str
           Name of file/dir in which to store arrays that exceed
           `self.array_threshold`.
        package : bool
           If `True`, then the archive will be stored as a package in::
           
              <dirname>/<name>/__init__.py
              <dirname>/<name>/<arrays_name>.<ext>

           where the extension is determined by `data_format`.  Otherwise,
           the archive will be stored as a module::

              <dirname>/<name>.py
              <dirname>/<name><arrays_name>.<ext>

        data_format : 'npy', 'npz', 'hdf5
            Data format used to store binary data.
        force : bool
           If `False`, then an exception is raised if any of the files above
           exist.  If `True` then they are overwritten and optionally backed up
           depending on the value of `self.backup_data`.
        clear_on_reload : bool
           If `True`, then a search of `sys.modules` is made for any submodules
           that are not modules and these are deleted so they can be properly
           reloaded.  This is mainly intended for DataSet usage.
        """
        # First form the string - this will populate self.data if needed (we
        # need this for the following checks.
        string_rep = str(self)

        if name is None:
            if self.single_item_mode:
                name = self.names()[0]
            else:
                raise ValueError("Must provide name unless single_item_mode=True")

        # First check for existing files.
        arrays_file = arrays_name + _EXTS[data_format]
        if package:
            init_file = os.path.join(dirname, name, '__init__.py')
            package_dir = os.path.join(dirname, name)
        else:
            init_file = os.path.join(dirname, name + '.py')
            arrays_file = name + arrays_file
            package_dir = dirname
            
        if os.path.exists(dirname):
            if not os.path.isdir(dirname):
                raise ValueError(
                    "File dirname={} exists and is not a directory.".format(dirname))

            if not force:
                if os.path.exists(init_file):
                    raise ValueError("File {} exists and force=False."
                                     .format(init_file))
                _arrays_file = os.path.join(package_dir, arrays_file)
                if self.data and os.path.exists(_arrays_file):
                    raise ValueError("File {} exists and force=False."
                                     .format(_arrays_file))
            if (package
                    and os.path.exists(package_dir)
                    and not os.path.isdir(package_dir)):
                # package_dir is a file
                if force:
                    with backup(package_dir, keep=True):
                        pass
                else:
                    raise ValueError(
                        "File dirname/name={} exists and is not a directory."
                        .format(package_dir))
                
        else:
            logging.info("Making directory {} for archive.".format(dirname))
            os.makedirs(dirname)

        # Now actually save the data.
        if package:
            if not os.path.exists(package_dir):
                logging.info("Making directory {} for archive.".format(package_dir))
                os.makedirs(package_dir)
                
        array_rep, array_files = self.save_data(datafile=package_dir,
                                                filename=arrays_file,
                                                data_format=data_format)
        with backup(init_file, keep=self.backup_data):
            with open(init_file, 'w') as f:
                if array_rep:
                    f.write(array_rep)
                f.write(string_rep)
                if self.single_item_mode:
                    assert 1 == len(self.arch)
                    # Special case of a single item archive.  Make module the
                    # single object.
                    f.write("\n".join([
                        "",
                        "import sys",
                        "sys.modules[__name__] = {NAME}"
                        .format(NAME=self.names()[0])]))
                elif clear_on_reload:
                    # clear all special single item imports
                    f.write(_G_CLEAR_SINGLE_ITEM_MODULES_CODE)


_G_CLEAR_SINGLE_ITEM_MODULES_CODE = '''
def _g_clear_single_item_modules():
    """Find and remove all replaced single_item_mode modules
    from sys.modules and the module dictionary.
    """
    import sys, types
    if not __name__ in sys.modules:
        return
    this_module = sys.modules[__name__]
    for key in list(this_module.__dict__):
        sub_module = __name__ + '.' + key  # Name of submodule
        if (sub_module in sys.modules
                and not isinstance(sys.modules[sub_module], types.ModuleType)):
            del this_module.__dict__[key]
            del sys.modules[sub_module]
_g_clear_single_item_modules()
del _g_clear_single_item_modules
'''
        

def get_imports(obj, env=None):
    r"""Return `imports = [(module, iname, uiname)]` where
    `iname` is the constructor of `obj` to be used and called as::

       from module import iname as uiname
       obj = uiname(...)

    This may be useful when writing :meth:`~IArchivable.get_persistent_rep`
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
    ([('numpy...', 'array', 'array')], 'array')
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
        raise ArchiveError("name {0} is not in module {0}.".format(name))

    return ([(mname, name, name)], name)


def repr_(obj, robust=True):
    r"""Return representation of `obj`.

    Stand-in `repr` function for objects that support the `get_persistent_rep`
    method.

    Examples
    --------
    >>> class A(object):
    ...     def __init__(self, x):
    ...         self.x = x
    ...     def get_persistent_rep(self):
    ...         return ('A(x=x)', dict(x=self.x), [])
    ...     def __repr__(self):
    ...         return repr_(self)
    >>> A(x=[1])
    A(x=[1])
    """
    (rep, args, imports) = obj.get_persistent_rep()
    replacements = dict((k, repr(args[k])) for k in args)
    rep = _replace_rep(rep, replacements=replacements, robust=robust)
    return rep


def get_module(obj):
    r"""Return module in which object is defined."""
    return inspect.getmodule(obj)


def get_persistent_rep_args(obj, args):
    r"""Return `(rep, args, imports)`.

    Constructs `rep` and `imports` dynamically from `obj` and `args`.

    Examples
    --------
    >>> a = 1
    >>> b = 2
    >>> l = [a, b]
    >>> get_persistent_rep_args(l, dict(a=a, b=b))
    ('list(a=a, b=b)', {'a': 1, 'b': 2}, [('builtins', 'list', 'list')])
    """
    module = obj.__class__.__module__
    name = obj.__class__.__name__
    imports = [(module, name, name)]

    keyvals = ["=".join((k, k)) for k in args]
    rep = "{}({})".format(name, ", ".join(keyvals))
    return (rep, args, imports)


def get_persistent_rep_repr(obj, env, rep=None):
    r"""Return `(rep, args, imports)`.

    This is the fallback: try to make a rep from the `repr` call.
    """
    imports = []
    args = {}

    module = get_module(obj.__class__)
    scope = copy.copy(module.__dict__)
    scope.update(env)
    rep = repr(obj)

    _ast = AST(rep)

    for name in _ast.names:
        obj = eval(name, scope)
        module = get_module(obj)
        if module:
            imports.append((module.__name__, name, name))

    return (rep, args, imports)


def get_persistent_rep_pickle(obj, env):
    r"""Last resort - archive by pickle."""
    rep = "loads(%s)" % repr(
        pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL))
    args = {}
    imports = [('pickle', 'loads', 'loads')]
    return (rep, args, imports)


def get_persistent_rep_type(obj, env):
    # Special cases
    if type(None) is obj:
        return ('type(None)', {}, [])
    name = None
    args = {}
    for module in [builtins, types]:
        obj_id = id(obj)
        val_ids = list(map(id, module.__dict__.values()))
        if obj_id in val_ids:
            name = module.__dict__[val_ids.index(obj_id)]
            imports = [(module.__name__, name, name)]
            rep = name
            break
    if name is None:
        # default
        return get_persistent_rep_obj(obj, env)

    return (rep, args, imports)


def get_persistent_rep_float(obj, env):
    r"""Deal with float types, including `inf` or `nan`.

    These are floats, but the symbols require the import of
    :mod:`numpy`.

    Examples
    --------
    >>> get_persistent_rep_float(np.inf, {})
    ('inf', {}, [('numpy', 'inf', 'inf')])
    """
    rep = repr(obj)
    imports = [('numpy', name, name) for name in AST(rep)._get_names()]
    args = {}

    return (rep, args, imports)


def get_persistent_rep_obj(obj, env):
    r"""Archive objects at the top level of a module."""
    imports, rep = get_toplevel_imports(obj, env)
    return (rep, {}, imports)


def get_persistent_rep_method(obj, env):
    r"""Archive methods."""
    if sys.version_info < (3, 0):
        instance = obj.im_self
    else:
        instance = obj.__self__
    cls = instance.__class__
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


def get_persistent_rep_classmethod(obj, env):
    r"""Archive methods."""
    rep = obj.__qualname__
    module = inspect.getmodule(obj)
    mname = module.__name__
    cname, _name = rep.split('.', 1)
    imports = [(mname, cname, cname)]
    args = {}
    return (rep, args, imports)


def _get_rep(obj, arg_rep):
    r"""Return `(rep, imports)` where `rep` = 'Class(args)'` is a call to the
    `obj` constructor.  This is used to represent derived instances of
    builtin types."""
    module = obj.__class__.__module__
    cname = obj.__class__.__name__
    rep = "{}({})".format(cname, arg_rep)
    return (rep, (module, cname, cname))


def get_persistent_rep_list(l, env):
    args = {}
    imports = []
    name = '_l_0'
    names = set(env)
    reps = []
    unames = UniqueNames(names).unique_names(name)
    for o in l:
        name = next(unames)
        args[name] = o
        names.add(name)
        reps.append(name)

    rep = "[{}]".format(", ".join(reps))

    if l.__class__ is not list:
        rep, imp = _get_rep(l, rep)
        imports.append(imp)

    return (rep, args, imports)


def get_persistent_rep_tuple(t, env):
    rep, args, imports = get_persistent_rep_list(list(t), env=env)
    if len(t) == 1:
        rep = "({}, )".format(rep[1:-1])
    else:
        rep = "({})".format(rep[1:-1])

    if t.__class__ is not tuple:
        rep, imp = _get_rep(t, rep)
        imports.append(imp)

    return (rep, args, imports)


def get_persistent_rep_dict(d, env):
    rep, args, imports = get_persistent_rep_list(list(d.items()), env)
    rep, imp = _get_rep(d, rep)
    imports.append(imp)

    return (rep, args, imports)


def is_simple(obj):
    r"""Return `True` if `obj` is a simple type defined only by its
    representation.

    Examples
    --------
    >>> list(map(is_simple,
    ...          [True, 1, 'Hi', 1.0, 1.0j, None, 123]))
    [True, True, True, True, True, True, True]
    >>> list(map(is_simple,
    ...          [[1], (1, ), {'a':2}]))
    [False, True, False]
    """
    if hasattr(obj, '__class__'):
        class_ = obj.__class__
        classes = [bool, int, str, None.__class__]
        if sys.version_info < (3, 0):
            classes.extend([long, unicode])
        result = (
            class_ in classes
            or (class_ in [float, complex]
                and not (np and (np.isinf(obj)) or np.isnan(obj)))
            or (class_ == tuple and all(map(is_simple, obj)))
        )
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
    children : list, None
       List of children id's.  If `None`, then it is constructed from `args`.
       In this case it is imperative that each instance of an object in `rep`
       has a unique identifier, even if it refers to the same object in memory.
    parents : list
       List of parent id's
    """
    def __init__(self, obj, rep, args, name, imports=None,
                 children=None, parents=None, get_id=id):
        self.get_id = get_id
        self.obj = obj
        self.rep = rep
        self.args = dict(**args)
        self.name = name
        if children is None:
            children = [self.get_id(self.args[_name]) for _name in self.args]
        self.children = children
        if parents is None:
            parents = []
        self.parents = parents
        self.imports = imports

    def __repr__(self):
        r"""Return string representation of node.

        Examples
        --------
        >>> Node(obj=['A'], rep='[x]', args=dict(x='A'), name='a')
        Node(obj=['A'], rep='[x]', args={'x': 'A'}, name='a', imports=None,
             children=[...], parents=[])
        """
        return (
            ("Node(obj=%r, rep=%r, args=%r, name=%r, imports=%r, "
             + "children=%r, parents=%r)")
            % (self.obj, self.rep, self.args, self.name, self.imports,
               self.children, self.parents))

    def __str__(self):
        r"""Return string showing node.

        Examples
        --------
        >>> print(Node(obj=['A'], rep='[x]', args=dict(x='A'), name='a'))
        Node(a=[x])
        """
        return "Node({}={})".format(self.name, self.rep)

    @property
    def id(self):
        r"""id of node."""
        return self.get_id(self.obj)

    def isreducible(self, roots):
        r"""Return `True` if the node can be reduced.

        A node can be reduced if it is not a root node, and is either a simple
        object with an efficient representation (as defined by
        :meth:`is_simple`), or has exactly one parent."""
        reducible = (self.id not in roots
                     and (is_simple(self.obj) or 1 == len(self.parents)))
        return reducible


class Graph(object):
    r"""Dependency graph.  Also manages imports.

    This is a graph of objects in memory: these are identified by
    their python :func:`id`.
    """
    def __init__(self, objects, get_persistent_rep, robust_replace=True,
                 gname_prefix='_g', allowed_names=set(), get_id=id):
        r"""Initialize the dependency graph with some reserved
        names.

        Parameters
        ----------
        roots : [(id, env)]
        objects : list
           List of top-level objects and names `[(name, obj, env)]`.
           Generated names will be from these and the graph will be
           generated from the dependents of these objects as
           determined by applying :attr:`get_persistent_rep`.  It is assumed
           that all these names are unique.
        get_persistent_rep : function
           Function of `(obj, env)` that returns `(rep, args,
           imports)` where `rep` is a representation of `objs`
           descending a single level.  This representation is a string
           expression and can refer to either `name` in the dict `args`
           of dependents or the `uiname` in the list
           `imports = [(module, iname, uiname)]` which will be
           imported as::

                from module import iname as uiname
        """
        self.get_id = get_id
        self.nodes = {}
        self.roots = set()
        self.envs = {}
        self.imports = []
        self.gname_prefix = gname_prefix
        self.allowed_names = allowed_names

        self.names = UniqueNames(set([name for (name, obj, env)
                                      in objects]))
        self.get_persistent_rep = get_persistent_rep
        self.robust_replace = robust_replace

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

        # Go through all nodes to determine unique names and update
        # reps.  Now that it is sorted we can do this simply.
        for _id in self.order:
            node = self.nodes[_id]
            if _id in self.roots:
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
                uname = self.nodes[self.get_id(obj)].name
                args[uname] = obj
                if not name == uname:
                    replacements[name] = uname
            node.args = args

            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.append(node.id)

            node.rep = _replace_rep(node.rep, replacements,
                                    robust=self.robust_replace)

    def gname(self, obj):
        r"""Return a unique global name for the specified object.

        This name is `self.gname_prefix` followed by the object's id.
        """
        return self.gname_prefix + str(self.get_id(obj))

    def _new_node(self, obj, env, name):
        r"""Return a new node associated with `obj` and using the
        specified `name`.  Also process the imports of the node."""
        rep, args, imports = self.get_persistent_rep(obj, env)
        rep = self._process_imports(rep, args, imports)
        return Node(obj=obj, rep=rep, args=args, name=name, imports=imports,
                    get_id=self.get_id)

    def _DFS(self, node, env):
        r"""Visit all nodes in the directed subgraph specified by
        node, and insert them into nodes."""
        for _name in node.args:
            obj = node.args[_name]
            id_ = self.get_id(obj)
            if id_ not in self.nodes:
                new_node = self._new_node(obj, env, self.gname(obj))
                self.nodes[id_] = new_node
                self._DFS(new_node, env)

    def _process_imports(self, rep, args, imports):
        r"""Process imports and add them to self.imports,
        changing names as needed so there are no conflicts
        between `args = {name: obj}` and `self.names`.
        """
        arg_names = sorted(args)

        # Check for duplicate imports
        replacements = {}
        for (module_, iname_, uiname_) in imports:
            mod_inames = list(zip(*_unzip(self.imports)[:2]))
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
        return [(id_, self.get_id(obj))
                for id_ in self.nodes
                for (name, obj) in self.nodes[id_].args.items()]

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
        replacements = {node.name: node.rep}
        for parent in node.parents:
            pnode = self.nodes[parent]
            pnode.rep = _replace_rep(pnode.rep, replacements,
                                     robust=self.robust_replace)
            pnode.children.remove(id)
            if node.name in pnode.args:
                # It may have been removed already...
                del pnode.args[node.name]

            pnode.args.update(node.args)
        for child in node.children:
            cnode = self.nodes[child]
            cnode.parents.remove(id)
            cnode.parents.extend(node.parents)
        del self.nodes[id]

    def check(self):
        r"""Check integrity of graph."""
        for id in self.nodes:
            node = self.nodes[id]
            children = node.children
            for child in children:
                cnode = self.nodes[child]
                assert id in cnode.parents

    def paths(self, id=None):
        """Return a list of all paths through the graph starting from `id`."""
        paths = []
        if id is None:
            for r in self.roots:
                paths.extend(self.paths(r))
        else:
            children = self.nodes[id].children
            if not children:
                paths.append([id])
            else:
                for c in children:
                    paths.extend([[id] + p for p in self.paths(c)])

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
        >>> g = Graph(a.arch, a.get_persistent_rep)
        >>> len(g.nodes)
        7
        >>> g.reduce()
        >>> len(g.nodes)         # Completely reducible
        1
        >>> print(a)
        A = [['F'], ['F', ['G'], ['G']]]
        try: del __builtins__, _arrays
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
        >>> g = Graph(a.arch, a.get_persistent_rep)
        >>> len(g.nodes)
        9
        >>> g.reduce()
        >>> len(g.nodes)         # Nodes A, F and G remain
        3
        >>> print(a)
        _g7 = ['G']
        _g3 = ['F']
        A = [[_g3], [_g3, [_g7], [_g7]]]
        del _g7,_g3
        try: del __builtins__, _arrays
        except NameError: pass

        If we explicitly add a node, then it can no longer be reduced:

        >>> a.insert(B=B)
        >>> g = Graph(a.arch, a.get_persistent_rep)
        >>> len(g.nodes)
        9
        >>> g.reduce()
        >>> len(g.nodes)         # Nodes A, F and G remain
        4
        >>> print(a)
        _g3 = ['F']
        _g7 = ['G']
        B = [_g3]
        A = [B, [_g3, [_g7], [_g7]]]
        del _g3,_g7
        try: del __builtins__, _arrays
        except NameError: pass


        Here is a graph that previously was problematic. Reducing this graph
        should not break the loop since A contains two copies of F which need to
        be identical.

                                 A
                                / \
                                \ /
                                 F
                                 |
                                'F'

        >>> F = ['F']
        >>> A = [F, F]
        >>> a = Archive(scoped=False);
        >>> a.insert(A=A)
        >>> g = Graph(a.arch, a.get_persistent_rep, get_id=a.get_id)
        >>> len(g.nodes)
        3
        >>> g.reduce()
        >>> len(g.nodes)
        2
        >>> print(a)
        _g1 = ['F']
        A = [_g1, _g1]
        del _g1
        try: del __builtins__, _arrays
        except NameError: pass

        Here is a similar graph that is reducible since the terminal is a
        "simple" object.

                                 A
                                / \
                                \ /
                                'F'

        >>> F = 'F'
        >>> A = [F, F]
        >>> a = Archive(scoped=False);
        >>> a.insert(A=A)
        >>> g = Graph(a.arch, a.get_persistent_rep, get_id=a.get_id)
        >>> len(g.nodes)
        2
        >>> g.reduce()
        >>> len(g.nodes)
        1
        >>> print(a)
        A = ['F', 'F']
        try: del __builtins__, _arrays
        except NameError: pass
        """
        self.check()
        reducible_ids = [id for id in self.order
                         if self.nodes[id].isreducible(roots=self.roots)]
        for id in reducible_ids:
            self._reduce(id)

        self.order = self._topological_order()


class _Graph(Graph):
    r"""Simplified dependency graph for use with scoped files.

    This is a graph of objects in memory: these are identified by
    their python :func:`id`.  Unlike :class:`Graph`, this does not bother with
    unique names and replacements.  The output routine must make sure each
    object is evaluated in a separate scope.

    .. note::
       To improve performance, it is assumed that the names of `objects`
       are unique and do not start with an underscore `_`.
    """
    def __init__(self, objects, get_persistent_rep,
                 gname_prefix='_g', allowed_names=set(), get_id=id):
        r"""Initialize the dependency graph with some reserved
        names.

        Parameters
        ----------
        roots : [(id, env)]
        objects : list
           List of top-level objects and names `[(name, obj, env)]`.
           Generated names will be from these and the graph will be
           generated from the dependents of these objects as
           determined by applying :attr:`get_persistent_rep`.  It is assumed
           that all these names are unique.
        get_persistent_rep : function
           Function of `(obj, env)` that returns `(rep, args,
           imports)` where `rep` is a representation of `objs`
           descending a single level.  This representation is a string
           expression and can refer to either `name` in the dict `args`
           of dependents or the `uiname` in the list
           `imports = [(module, iname, uiname)]` which will be
           imported as::

                from module import iname as uiname
        """
        self.get_id = get_id
        self.nodes = {}
        self.roots = set()
        self.envs = {}
        self.imports = []
        self.gname_num = 0
        self.gname_prefix = gname_prefix
        self.allowed_names = allowed_names

        self.get_persistent_rep = get_persistent_rep
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
        for _id in self.order:
            node = self.nodes[_id]
            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.append(node.id)

    def _new_node(self, obj, env, name):
        r"""Return a new node associated with `obj` and using the
        specified `name`. Also process the imports of the node."""
        self.names.add(name)
        rep, args, imports = self.get_persistent_rep(obj, env)
        return Node(obj=obj, rep=rep, args=args, name=name, imports=imports,
                    get_id=self.get_id)

    # edges = Graph.edges
    # _topological_order = Graph._topological_order
    # check = Graph.check
    # paths = Graph.paths

    def _reduce(self, id):      # pragma: no cover
        raise NotImplementedError

    def reduce(self):           # pragma: no cover
        raise NotImplementedError


def _unzip(q, n=3):
    r"""Unzip q to lists.

    If len(q) = 0, then assumes that q was zipped from n lists.

    Example:
    >>> _unzip(list(zip([1, 2, 3], [4, 5, 6])))
    [[1, 2, 3], [4, 5, 6]]
    >>> _unzip([], n=3)
    [[], [], []]
    >>> _unzip([('a', 'b', 'c'), ('d', 'e', 'f')])
    [['a', 'd'], ['b', 'e'], ['c', 'f']]

    """
    if 0 == len(q):
        return [[]] * n
    else:
        return list(map(list, zip(*q)))


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

        return next(self.unique_names(name))

    def unique_names(self, name):
        r"""Return a generator that generates a sequence of sequential unique
        names.

        Examples
        --------
        >>> names = UniqueNames(['a', 'a.1', 'b_1'])
        >>> gen = names.unique_names('c')
        >>> next(gen), next(gen)
        ('c', 'c_0')
        >>> gen = names.unique_names('a')
        >>> next(gen), next(gen)
        ('a_0', 'a_1')
        >>> gen = names.unique_names('b')
        >>> next(gen), next(gen)
        ('b_2', 'b_3')
        >>> gen = names.unique_names('')
        >>> next(gen), next(gen)
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

    identifier_tokens = string.ascii_letters + string.digits + "_"

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
                    and (not prev or prev not in identifier_tokens)):

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
    r"""
            re_ = r'''(?P<a>        # Refer to the group by name <a>
                       [^\w\.]      # Either NOT a valid identifier
                       | ^)         # OR the start of the string
                      (%s)          # The literal to be matched
                      (?P<b>[^\w=]  # Either NOT a valid identifer
                       | $)'''      # OR the end.
            regexp = re.compile(re_%(re.escape(old)), re.VERBOSE)
            n_rep = 0
            while True:
                (rep, m) = regexp.subn(r"\g<a>%s\g<b>"%(replacements[old]),rep)
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

    line_offsets = [0]
    for _line in rep.splitlines():
        offset = line_offsets[-1] + len(_line) + 1  # include \n
        line_offsets.append(offset)
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

    >>> for (nx, mu) in sorted(dat):
    ...     ds._insert(dat[(nx, mu)], info=(nx, mu))
    ['x_0']
    ['x_1']
    ['x_2']
    ['x_3']

    >>> print(ds)
    DataSet './...' containing ['mus', 'nxs', 'x_0', 'x_1', 'x_2', 'x_3']

    Here is the complete set of info:

    This information is stored in the :attr:`_info_dict` dictionary as
    a set of records.  Don't modify this directly though as this will
    not properly write the data...

    >>> [(k, ds[k]) for k in sorted(ds)]
    [('mus', 'Chemical potentials'),
     ('nxs', 'Particle numbers'),
     ('x_0', (10, 1.2)),
     ('x_1', (10, 2.5)),
     ('x_2', (20, 1.2)),
     ('x_3', (20, 2.5))]
    >>> [(k, getattr(ds, k)) for k in sorted(ds)]
    [('mus', [1.2, 2.5]),
     ('nxs', [10, 20]),
     ('x_0', array([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])),
     ('x_1', array([2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5])),
     ('x_2', array([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2,
                    1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])),
     ('x_3', array([2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5,
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
       array([2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,
              2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5,  2.5])

    If you want to modify the data set, then create a new data set
    object pointing to the same place:

    >>> ds1 = DataSet(modname, 'w')
    >>> print(ds1)
    DataSet './...' containing ['mus', 'nxs', 'x_0', 'x_1', 'x_2', 'x_3']

    This may be modified, but see the warnings above.

    >>> import numpy as np
    >>> ds1.x_0 = np.ones(5)

    This should work, but fails within doctests.  Don't know why...::

       >> reload(mod1)                    # doctest: +SKIP
       <module '...' from '.../archive/.../__init__.py'>

    Here we open a read-only copy:

    >>> ds2 = DataSet(modname)
    >>> ds2.x_0
    array([1., 1., 1., 1., 1.])
    >>> ds2.x_0 = 6
    Traceback (most recent call last):
       ...
    ValueError: DataSet opened in read-only mode.
    >>> shutil.rmtree(t)

    """
    _lock_file_name = "_locked"

    def __init__(self, module_name, mode='r', path=".",
                 synchronize=True,
                 _reload=False,
                 array_threshold=100,
                 data_format='npy',
                 backup_data=False,
                 name_prefix='x_',
                 timeout=60,
                 scoped=True):
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
           can write at a time.

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
        array_threshold : int
           Threshold size above which arrays are stored using the format
           specified in the `data_format` flag.
        data_format : 'npy', 'hdf5', 'npz'
           Format to use for storing arrays that exceed the array_threshold.
        backup_data : bool
           If `True`, then backup copies of overwritten data will be
           saved.
        timeout : int, optional
           Time (in seconds) to wait for a writing lock to be released
           before raising an :exc:`IOException` exception.  (Default
           is 60s.)
        scoped : bool, optional
           If `True`, then the representation is "scoped": i.e. a series of
           function definitions.  This allows each entry to be evaluated in a
           local scope without the need for textual replacements in the
           representation (which can be either costly or error-prone).  The
           resulting output is not as compact (can be on the order of 4 times
           larger), nor as legible, but archiving can be much faster.

        .. warning:: The locking mechanism is to prevent two archives
           from clobbering upon writing.  It is not designed to
           prevent reading invalid information from a partially
           written archive (the reading mechanism does not use the
           locks).
        """
        self._synchronize = synchronize
        self._mode = mode
        self._array_threshold = array_threshold
        self._data_format = data_format
        self._module_name = module_name
        self._path = path
        self._backup_data = backup_data
        self._name_prefix = name_prefix
        self._info_dict = {}
        self._timeout = timeout
        self._maxint = -1
        self._closed = False
        self._lock_file = ""
        self._scoped = scoped

        mod_dir = os.path.join(path, module_name)
        key_file = os.path.join(mod_dir, '_this_dir_is_a_DataSet')

        if os.path.exists(mod_dir):
            if not os.path.exists(key_file):
                raise ValueError(
                    ("Directory %s exists and is not a DataSet repository. " +
                     "Please choose a unique location. ") % (mod_dir,))

        elif mode == 'r':
            raise ValueError(
                ("Default mode is read-only but directory %s does "
                 "not exist. Please choose an existing DataSet or "
                 "specify write mode with mode='w'.") % (mod_dir,))
        elif mode == 'w':
            logging.info("Making directory %s for output." % (mod_dir,))
            os.makedirs(mod_dir)
            open(key_file, 'w').close()
        else:
            raise NotImplementedError("mode=%s not supported" % (mode,))

        if not synchronize:
            self._lock()

        self._load()

        # Needed for pre 2.6 python version to support tab completion
        if sys.version_info < (2, 6):  # pragma: no cover
            self.__members__ = sorted(self._info_dict)

    def _import(self, name='__init__'):
        """Return the attribute `name` from the dataset.

        Arguments
        ---------
        name : str
           Name of attribute.  The default value `__init__` will load the
           `_info_dict`.
        """
        archive_file = os.path.join(self._path,
                                    self._module_name,
                                    "{:s}.py".format(name))
        if os.path.exists(archive_file):
            _mod = UniqueNames(sys.modules).unique(name)

            # Bytecode is written in parallel, thus there is a chance that
            # changing the attribute to quickly will invalidate the .pyc file
            # if the .py file is written before the original byte compilation
            # process finishes.  For now, we disable byte compilation
            # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
            _dont_write_bytecode = sys.dont_write_bytecode
            sys.dont_write_bytecode = True
            try:
                if sys.version_info < (3, 0):
                    res = imp.load_source(_mod, archive_file)
                else:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(_mod, archive_file)
                    res = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(res)
                if name == '__init__':
                    res = res._info_dict
                else:
                    res = sys.modules[_mod]
                    del sys.modules[_mod]
            finally:
                sys.dont_write_bytecode = _dont_write_bytecode
        else:
            if name == '__init__':
                res = {}
            else:
                res = None
        return res
        
    def _load(self):
        r"""Create the data set from an existing repository."""
        self._info_dict = self._import()

    def _lock(self):
        r"""Actually write the lock file, waiting for timeout if  needed.

        Store the lock file name in `self._lock`.
        """
        if self._closed:
            raise IOError("DataSet has been closed")

        lock_file = os.path.join(self._path, self._module_name,
                                 self._lock_file_name)

        if os.path.exists(lock_file):
            tic = time.time()
            # Archive locked
            while time.time() - tic < self._timeout:
                if not os.path.exists(lock_file):
                    # Lock release, so make lock-file
                    open(lock_file, 'w').close()
                    self._lock_file = lock_file
                    return
                time.sleep(0.5)
            # Timeout
            raise IOError(
                "DataSet locked.  Please close or remove lock '%s'" %
                (lock_file,))
        else:
            open(lock_file, 'w').close()
            self._lock_file = lock_file

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
                        "Lock already established! " +
                        "(Reentry not supported)")
                else:
                    self._lock()
            else:
                # Lock should have been established upon construction
                if (not self._lock_file
                        or not os.path.exists(self._lock_file)):
                    raise IOError("Lost lock on %s!" % self._lock_file)
            yield
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
        if name.startswith('_') or name not in self:
            if name == "close":
                # Special case to allow access to _close without polluting the
                # namespace
                return self._close
            raise AttributeError(
                "'%s' object has no attribute '%s'" %
                (self.__class__.__name__, name))

        return self._import(name)

    def __setattr__(self, name, value):
        r"""Store the specified attribute to disk."""
        if name.startswith('_'):
            # Provide access to state variables.
            return object.__setattr__(self, name, value)

        if self._mode == 'r':
            raise ValueError("DataSet opened in read-only mode.")

        with self._ds_lock():              # Establish lock
            arch = Archive(array_threshold=self._array_threshold,
                           single_item_mode=True,
                           scoped=self._scoped,
                           backup_data=self._backup_data)
            arch.insert(**{name: value})
            arch.save(dirname=os.path.join(self._path, self._module_name),
                      name=name,
                      package=False,
                      data_format=self._data_format,
                      force=True,
                      arrays_name='_data')

        # Needed for pre 2.6 python version to support tab completion
        if sys.version_info < (2, 6):
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
        `__init__.py` file using an Archive.
        """
        if self._mode == 'r':
            raise ValueError("DataSet opened in read-only mode.")

        with self._ds_lock():
            if self._synchronize:
                self._load()

            self._info_dict[name] = info

            if self._module_name:
                arch = Archive(allowed_names=['_info_dict'],
                               scoped=self._scoped,
                               backup_data=self._backup_data)
                arch.insert(_info_dict=self._info_dict)
                arch.save(dirname=self._path,
                          name=self._module_name,
                          package=True,
                          data_format=self._data_format,
                          force=True)
            
    def __str__(self):
        if self._synchronize:
            self._load()
        return ("DataSet %r containing %s" % (
            os.path.join(self._path, self._module_name),
            str(sorted(self._info_dict))))

    def __repr__(self):
        return ("DataSet(%s)" %
                ", ".join(["%s=%s" % (k, repr(getattr(self, '_' + k)))
                           for k in ['module_name', 'path',
                                     'synchronize',
                                     'array_threshold', 'backup_data',
                                     'name_prefix', ]]))

    def _keys(self):
        return sorted(self._info_dict)

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

        # Why did I do this?  I don't use it...
        # mod_dir = os.path.join(self._path, self._module_name)
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

    def _close(self):
        self._unlock()
        self._closed = True

    def __del__(self):
        r"""Make sure we unlock archive."""
        self._close()
