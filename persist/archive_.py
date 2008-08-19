"""This is an idea for a model of objects that save their state.

Objects can aid this by implementing an archive method, for example:

    def archive_1(self):
        '''Return (rep,args,imports) where obj can be reconstructed
        from the string rep evaluated in the context of args with the
        specified imports = list of (module,iname,uiname) where one
        has either "import module as uiname", "from module import
        iname" or "from module import iname as uiname".
        '''
        args = [('a',self.a),('b',self.b),...]

        module = self.__class__.__module__
        name = self.__class__.__name__
        imports = [(module,name,name)]

        keyvals = ["=".join((k,k)) for (k,v) in args]
        rep = "%s(%s)"%(name,",".join(keyvals))
        return (rep,args,imports)

The idea is to save state in a file that looks like the following:

import numpy as _numpy
a = _numpy.array([1,2,3])
del _numpy

BUGS:
- Graph reduction occurs for nodes that have more than one parent.
  This does not consider the possibility that a single node may refer
  to the same object several times.  This has to be examined so that
  non-reducible nodes are not reduced (see the test case which fails).
- _replace_rep() is stupid (it just does text replacements).  Make it
  smart.  Maybe use a refactoring library like rope... If this is
  hard, then the data-file might have to redefine the environment
  locally before each rep.   This would be a pain but not impossible.
- It would be nice to be able to use "import A.B" and then just use
  the name "A.B.x", "A.B.y" etc.  However, the name A could clash with
  other symbols, and it cannot be renamed (i.e. "import A_1.B" would
  not work).  To avoid nameclases, we always use either "import A.B as
  B" or the "from A.B import x" forms which can be renamed.
- Maybe allow rep's to be suites for objects that require construction
  and initialization.  (Could also allow a special method to be called
  to restore the object such as restore().)

"""
__all__  = ['Archive', 'restore', 'ArchiveError', 'DuplicateError']

import sys
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

import numpy as np

import contrib.RADLogic.topsort as topsort

import mmf.utils
import mmf.objects.interfaces

class ArchiveError(Exception):
    """Archiving error."""

class DuplicateError(ArchiveError):
    """Object already exists."""
    def __init__(self,name):
        msg = "Object with name %r already exists in archive."%name
        ArchiveError.__init__(self,msg)

def restore(archive,env={}):
    """Return dictionary obtained by evaluating the string arch.
    
    arch is typically returned by converting an Archive instance into
    a string using str or repr:
    >>> a = Archive()
    >>> a.insert(a=1,b=2)
    ['a', 'b']
    >>> arch = str(a)
    >>> d = restore(arch)
    >>> print "%(a)i,%(b)i"%d
    1,2
    """
    ld = {}
    ld.update(env)
    exec(archive,ld)
    return ld

class Archive(object):
    """Archival tool.
    
    Maintains a list of symbols to import in order to reconstruct the
    states of objects and contains methods to convert objects to
    strings for archival.

    Members:
        arch : List of (uname,obj,env) where obj is
               the the object, which can be rescontructed from the
               string rep evaluated in the contect of args, imports,
               and env.

        check_on_import : If True, then try generating the rep.

    Invariants:
        unames are unique
    """
    def __init__(self,flat=True):
        self.flat = flat
        self.imports = []
        self.arch = []
        self._section_sep = ""  # string to separate the sections
        self._numpy_printoptions = {'infstr': 'Inf',
                                    'threshold': np.inf,
                                    'suppress': False,
                                    'linewidth': 200,
                                    'edgeitems': 3,
                                    'precision': 16,
                                    'nanstr': 'NaN'}
        self.check_on_insert = False

    def archive_1(self,obj,env):
        """Return (rep,args,imports) where obj can be reconstructed
        from the string rep evaluated in the context of args with the
        specified imports = list of (module,iname,uiname) where one
        has either "import module as uiname", "from module import
        iname" or "from module import iname as uiname".
        
        """
        if isinstance(obj,mmf.objects.interfaces.IArchivable):
            return obj.archive_1(env)

        for class_ in self._dispatch:
            if isinstance(obj,class_):
                return self._dispatch[class_](self,obj,env=env)

        if inspect.isclass(obj):
            return archive_1_class(obj,env)

        if hasattr(obj,'archive_1'):
            try:
                return obj.archive_1(env)
            except TypeError:   # pragma: no cover
                1+1             # Needed to deal with coverage bug
        
        return archive_1_repr(obj,env)

    def _archive_ndarray(self,obj,env):
        popts = np.get_printoptions()
        np.set_printoptions(**(self._numpy_printoptions))
        rep = repr(obj)
        np.set_printoptions(**popts)

        module = inspect.getmodule(obj.__class__)

        mname = module.__name__
        
        constructor = rep.partition("(")[0]
        if not constructor.startswith(mname):
            rep = ".".join([mname,rep])
        
        imports = [(mname,None,mname),
                   ('numpy','inf','inf'),
                   ('numpy','inf','Infinity'),
                   ('numpy','inf','Inf'),
                   ('numpy','inf','infty'),
                   ('numpy','nan','nan'),
                   ('numpy','nan','NaN'),
                   ('numpy','nan','NAN')]
        return (rep,{},imports)

    def _archive_list(self,obj,env):
        return archive_1_list(obj,env)

    def _archive_tuple(self,obj,env):
        return archive_1_tuple(obj,env)

    def _archive_dict(self,obj,env):
        return archive_1_dict(obj,env)

    def _archive_float(self,obj,env):
        return archive_1_float(obj,env)

    _dispatch = {
        np.ndarray:_archive_ndarray,
        list:_archive_list,
        tuple:_archive_tuple,
        dict:_archive_dict,
        float:_archive_float,
        complex:_archive_float}
        
    def unique_name(self,name):
        """Return a unique name not contained in the archive."""
        names = _unzip(self.arch)[0]
        return _get_unique(name,names)

    def insert(self,env=None,**kwargs):
        """insert(name=obj): Add the obj to archive with name.

        If self.check_on_insert, then try generating rep (may raise an
        exception).

        If name already exists in the archive, then a DuplicateError
        exception is thrown.

        Parameters:
            name=obj : Insert the obj with name into the ar
            obj     : Object to be archived
            name    : Desired name of object in the archive.  If name is
                      None, then obj must be a dictionary of name:obj.

                      Names must not start with an underscore (these
                      are used for private variables.)

            env     : Dictionary used to resolve names found in repr
                      strings (using repr is the last resort option).
            
        Returns (uname,obj) where uname is the unique name.

        Throws DuplicateError if unique is False and name is already
        in the archive.

        Throws ArchiveError if there is a problem.

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
        >>> a.insert(a=4,b=5)   # Can insert multiple items
        ['a', 'b']
        >>> a.insert(A=np.array([1,2,3]))
        'A'
        >>> print a
        import numpy as _numpy
        from numpy import inf as _inf
        from numpy import nan as _nan
        x = 2
        x_1 = 3
        a = 4
        b = 5
        A = _numpy.array([1, 2, 3])
        del _numpy
        del _inf
        del _nan
        try: del __builtins__
        except NameError: pass
        >>> a = Archive()
        >>> a.insert(x=2)
        'x'
        >>> a.insert(A=np.array([1,2,3]))
        'A'
        >>> c = np.array([1,2.0+3j,3])
        >>> a.insert(c=c)
        'c'
        >>> a.insert(cc=[c,c,[3]])
        'cc'
        >>> a.make_persistent() # doctest: +NORMALIZE_WHITESPACE
        ([('numpy', None, '_numpy'),
          ('numpy', 'inf', '_inf'),
          ('numpy', 'nan', '_nan')],
         [('c', '_numpy.array([ 1.+0.j,  2.+3.j,  3.+0.j])'),
          ('cc', '[c,c,[3]]'),
          ('x', '2'),
          ('A', '_numpy.array([1, 2, 3])')])
        """
        if env is None:
            env = {}

        names = []
        for name in kwargs:
            obj = kwargs[name]
            if name.startswith('_'):
                raise ValueError("name must not start with '_'")

            # First check to see if object is already in archive:
            unames,objs,envs = _unzip(self.arch)
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
                    (rep,args,imports) = self.archive_1(obj,env)

                self.arch.append((uname,obj,env))
                ind = len(self.arch) - 1
                
            assert(ind is not None)
            uname,obj,env = self.arch[ind]
            names.append(uname)

        if 1 < len(names):
            return names
        elif 1 == len(names):
            return names[0]
        else:                   # pragma: no cover
            return None

    def make_persistent(self):
        """Return (imports, defs) representing the persistent version
        of the archive.

        imports : a list of (module,iname,uiname) where one of the
                  following:

                  from module import iname as uiname
                  from module import iname
                  import module as uiname

                  The second form is used if iname is uiname, and the
                  last form is used if iname is None.  uiname must not
                  be None.
        defs : a list of (uname,rep) where rep is an expression
               depending on the imports and the previously defined
               unames.

        Algorithm:
            The core of the algorithm is a transformation that takes
            an object obj and replaces that by a tuple
            (rep,args,imports) where rep is a string representation of
            the object that can be evaluated using eval() in the
            context provided by args and imports.

            The archive_1() method provides this functionality,
            effectively defining a suite describing the dependencies
            of the object.

            Typically, rep will be a call to the objects constructor
            with the arguments in args.  The constructor is typically
            defined by the imports.

            Objects are hierarchical in that one object will depend on
            others.  Consider for example the following suite:
            
            a = [1,2,3]
            b = [4,5,6]
            c = dict(a=a,b=b)

            The dictionary c could be represeted as this suite, or in
            a single expression:

            c = dict(a=[1,2,3],b=[4,5,6])
            
            In some cases, one must use a suite: for example

            a = [1,2,3]
            b = [a,a]
            c = dict(a=a,b=b)

            Since everything refers to a single list, one must
            preserve this structure and we cannot expand anything.

            These concepts can all be couched in the language of graph
            theory.  The dependency structure forms a "directed graph"
            (DG) and we are looking for an "evaluation order" or
            "topological order", which is found using a "topological
            sorting" algorithm.  We do not presently support cyclic
            dependencies, so we will only archive directed acyclic
            graphs (DAG), but the algorithm must determine if there is
            a cycle and raise an exception in this case.

            We use the topsort library to do this.

            We would also like to (optionally) perform reductions of
            the graph in the sense that we remove a node from the
            list of computed quantities, and include it directly in
            the evaluation of another node.  This can only be done if
            the node has less than two parents.

            flat: The flat algorithm recursively processes the archive
                  in a depth first manner, adding each object with a
                  temporary name.
            tree: The recursive algorithm leaves objects within their
                  recursive structures
          
       Example:
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
A = [B,C]
a = Archive()
a.insert(A=A)
        
        """

        # First we build the dependency tree using the nodes and a
        # depth first search.  The nodes dictionary maps each id to
        # the tuples (obj,(rep,args,imports),parents) where the
        # children are specified by the "args" and parents is a set of
        # the parent ids.  The nodes dictionary also acts as the
        # "visited" list to prevent cycles.

        names = _unzip(self.arch)[0]
        
        # Generate dependency graph
        try:
            graph = Graph(objects=self.arch,
                          archive_1=self.archive_1)
        except topsort.CycleError, err:
            new_err = ArchiveError(
                "Archive contains cyclic dependencies.")
            new_err.cycle_err = err
            raise new_err

        # Optionally: at this stage perform a graph reduction.
        graph.reduce()

        names_reps = [(node.name,node.rep)
                      for id_ in graph.order
                      for node in [graph.nodes[id_]]]

        return (graph.imports,names_reps)

    def __repr__(self):
        return str(self)

    def __str__(self):
        """Return a string representing the archive.

        This string can be saved to a file, and that file imported to
        define the required symbols.
        """
        imports, defs = self.make_persistent()
        import_lines = []
        del_lines = []
        for (module,iname,uiname) in imports:
            assert(iname is not None or uiname is not None)
            if iname is None:
                import_lines.append(
                    "import %s as %s"%(module,uiname))
                del_lines.append("del %s"%uiname)
            elif iname == uiname or uiname is None: # pragma: no cover
                # Probably never happens because uinames start with _
                import_lines.append(
                    "from %s import %s"%(module,uiname))
                del_lines.append("del %s"%uiname)
            else:
                import_lines.append(
                    "from %s import %s as %s"%(module,iname,uiname))
                del_lines.append("del %s"%uiname)

        del_lines.extend([
                "try: del __builtins__",
                "except NameError: pass"])

        lines = "\n".join(["%s = %s"%(uname,rep) 
                           for (uname,rep) in defs])
        imports = "\n".join(import_lines)
        dels = "\n".join(del_lines)

        res = ("\n"+self._section_sep).join([l for l in [imports,lines,dels]
                           if 0 < len(l)])
        return res
   
def get_imports(obj,env=None):
    """Return [imports] = [(module,iname,uiname)] where iname is the
    constructor of obj to be used and called as:

    from module import iname as uiname
    obj = uiname(...)

    Example:
    >>> a = np.array([1,2,3])
    >>> get_imports(a)
    [('numpy', 'ndarray', 'ndarray')]
    """
    iname = obj.__class__.__name__
    uiname = iname
    try:
        module = obj.__module__
    except AttributeError:
        module = obj.__class__.__module__
        
    return [(module,iname,uiname)]

def repr_(obj):
    """Return representation of obj.

    Stand-in repr function for objects that support the archive_1
    method.

    >>> class A(object):
    ...     def __init__(self,x):
    ...         self.x = x
    ...     def archive_1(self):
    ...         return ('A(x=x)',[('x',self.x)],[])
    ...     def __repr__(self):
    ...         return repr_(self)
    >>> A(x=[1])
    A(x=[1])
    """
    (rep,args,imports) = obj.archive_1()
    replacements = {}
    replacements = dict((k,repr(v))
                        for (k,v) in args)
    rep = _replace_rep(rep,replacements=replacements)
    return rep
    
def get_module(obj):
    """Return module in which object is defined."""
    module = inspect.getmodule(obj)
    if module is not __builtin__:
        return module
    else:                       # pragma: no cover
        return None
    
def archive_1_args(obj, args):
    """Return (rep,args,imports).

    Constructs rep and imports dynamically from obj and args.

    >>> a = 1
    >>> b = 2
    >>> l = [a,b]
    >>> archive_1_args(l,[('a',a),('b',b)])
    ('list(a=a,b=b)', [('a', 1), ('b', 2)], [('__builtin__', 'list', 'list')])
    """
    module = obj.__class__.__module__
    name = obj.__class__.__name__
    imports = [(module,name,name)]
    
    keyvals = ["=".join((k,k)) for (k,v) in args]
    rep = "%s(%s)"%(name,",".join(keyvals))
    return (rep,args,imports)


def archive_1_repr(obj,env):
    """Return (rep,args,imports).
    
    This is the fallback: try to make a rep from the repr call.
    """
    imports = []
    args = []
    rep = repr(obj)
    scope = {}
    try:
        module = inspect.getmodule(obj.__class__)
        if module is not __builtin__:
            scope = copy.copy(module.__dict__)
    except:                     # pragma: no cover
        1+1                     # Needed to deal with coverage bug
    scope.update(env)

    ast = AST(rep)

    for name in ast.names:
        obj = eval(name,scope)
        module = get_module(obj)
        if module:
            imports.append((module.__name__,name,name))
            
    return (rep, args, imports)

def archive_1_float(obj,env):
    """Deal with float types, including inf or nan.

    These are floats, but the symbols require the import of numpy.

    >>> archive_1_float(np.inf,{})
    ('inf', [], [('numpy', 'inf', 'inf')])
    """
    rep = repr(obj)
    imports = [('numpy',name,name) for name in AST(rep)._get_names()]
    args = []
    
    return (rep, args, imports)

def archive_1_class(obj,env):
    """Archive classes."""
    module = inspect.getmodule(obj)
    mname = module.__name__
    name = obj.__name__
    imports = [(mname,name,name)]
    rep = name
    return (rep,{},imports)

def archive_1_list(l,env):
    args = []
    imports = []
    name = '_l_0'
    names = set(env)
    reps = []
    for o in l:
        name = _get_unique(name,names)
        args.append((name,o))
        names.add(name)
        reps.append(name)
    rep = "[%s]"%(",".join(reps))
    return (rep,args,imports)

def archive_1_tuple(t,env):
    rep,args,imports = archive_1_list(t,env=env)
    if len(t) == 1:
        rep = "(%s,)"%(rep[1:-1])
    else:
        rep = "(%s)"%(rep[1:-1])

    return (rep,args,imports)

def archive_1_dict(d,env):
    rep,args,imports = archive_1_list(d.items(),env)
    rep = "dict(%s)"%rep
    return (rep,args,imports)

def is_simple(obj):
    """Return True if obj is a simple type defined only by its
    representation.

    >>> map(is_simple,
    ...     [True,1,'Hi',1.0,1.0j,None,123L])
    [True, True, True, True, True, True, True]
    >>> map(is_simple,
    ...     [[1],(1,),{'a':2}])
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
    """Represents a Node in the tree as a tuple:
    (obj,rep,args,name,parents)
    obj : object the node represents
    rep : string representation of obj.  This depends on the
        names defined in args
    args : list of (name,obj) pairs where the specified
        object is referenced in rep by name.
    parents : set of parent id's
    """
    def __init__(self,obj,rep,args,name,parents=set()):
        self.obj = obj
        self.rep = rep
        self.args = [[name_,obj] for (name_,obj) in args]
        self.name = name
        self.parents = set(parents)

    def __repr__(self):
        """Return string representation of node.

        >>> Node(obj=['A'],rep='[x]',args=[('x','A')],name='a')
        Node(obj=['A'],rep='[x]',args=[['x', 'A']],name='a',parents=set([]))
        """
        return "Node(obj=%r,rep=%r,args=%r,name=%r,parents=%r)"%(
            self.obj,self.rep,self.args,self.name,self.parents)

    def __str__(self):
        """Return string showing node.
        >>> print Node(obj=['A'],rep='[x]',args=[('x','A')],name='a')
        Node(a=[x])
        """
        return "Node(%s=%s)"%(self.name,self.rep)

    @property
    def id(self):
        """id of node."""
        return id(self.obj)

    @property
    def children(self):
        """List of dependent ids"""
        return [id(obj) for (name,obj) in self.args]
    

    def isreducible(self,roots):
        """Return True if the node can be reduced.

        A node can be reduced if it is either a simple object with an
        efficient representation (as defined by is_simple), or if it
        has exactly one parent and is not a root node."""
        reducible = (self.id not in roots and
                     (is_simple(self.obj) or 1 == len(self.parents)))
        return reducible


class Graph(object):
    """Dependency graph.  Also manages imports.

    """
    def __init__(self,objects,archive_1):
        """Initialize the dependency graph with some reserved
        names.

        Parameters:
            roots : [(id,env)]
            objects : list of top-level objects and names
                [(name,obj,env)].  Generated names will be from these and
                the graph will be generated from thes dependents of
                these objects as determined by applying archive_1.
            archive_1 : Function of (obj,env) that returns
                (rep,args,imports) where rep is a representation of
                objs descending a single level.  This representation
                is a string expression and can refer to either names
                in the list args = [[name,obj]] of dependents or the
                uinames in the list imports = [(module,iname,uiname)]
                which will be imported as

                from module import iname as uiname
        """
        self.nodes = {}
        self.roots = []
        self.envs = {}
        self.imports = []
        self.names = [name for (name,obj,env) in objects]
        self.archive_1 = archive_1

        # First insert the root nodes
        for (name,obj,env) in objects:
            node = self._new_node(obj,env,name)
            self.roots.append(node.id)
            self.envs[node.id] = env
            self.nodes[node.id] = node

        # Now do a depth first search to build the graph.
        for id_ in self.roots:
            self._DFS(node=self.nodes[id_],env=self.envs[id_])
        
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
                uname = _get_unique(uname,self.names)
                self.names.append(uname)
                node.name = uname

            replacements = {}
            for args in node.args:
                name,obj = args
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

            node.rep = _replace_rep(node.rep,replacements)

    def _new_node(self,obj,env,name=None):
        """Return a new node associated with obj and using the
        specified name  If name is specified, then we assume
        that the name is to be exported.  Also process the
        imports of the node."""
        rep, args, imports = self.archive_1(obj,env)
        rep = self._process_imports(rep,args,imports)
        return Node(obj=obj,rep=rep,args=args,name=name)

    def _DFS(self,node,env):
        """Visit all nodes in the directed subgraph specified by
        node, and insert them into nodes."""
        for (name, obj) in node.args:
            id_ = id(obj)
            if id_ not in self.nodes:
                node = self._new_node(obj,env,name)
                self.nodes[id_] = node
                self._DFS(node,env)

    def _process_imports(self,rep,args,imports):
        """Process imports and add them to self.imports,
        changing names as needed so there are no conflicts
        between args = [(name,obj)] and self.names."""

        arg_names = _unzip(args)[0]
        # Check for duplicate imports
        new_imports = []
        replacements = {}
        for (module_, iname_, uiname_) in imports:
            mod_inames = zip(*_unzip(self.imports)[:2])
            try:
                ind = mod_inames.index((module_,iname_))
            except ValueError:
                # Get new name.  All import names are local
                uiname = uiname_
                if not uiname.startswith('_'):
                    uiname = "_" + uiname
                uiname = _get_unique(uiname,
                                     self.names + arg_names)
                self.imports.append((module_,iname_,uiname))
                self.names.append(uiname)
            else:
                # Import already specified.  Just refer to it
                module, iname, uiname = self.imports[ind]

            if not uiname == uiname_:
                replacements[uiname_] = uiname

        # Update names of rep in archive
        rep = _replace_rep(rep,replacements)
        return rep

    def edges(self):
        """Return a list of edges (id1, id2) where object id1 depends
        on object id2."""
        return [(id_,id(obj))
                for id_ in self.nodes
                for (name,obj) in self.nodes[id_].args]

    def _topological_order(self):
        """Return a list of the ids for all nodes in the graph in a
        topological order."""
        order = topsort.topsort(self.edges())
        order.reverse()
        # Insert roots (they may be disconnected)
        order.extend([id for id in self.roots if id not in order])
        return order
    
    def _reduce(self,id):
        """Reduce the node."""
        node = self.nodes[id]
        if node.isreducible(roots=self.roots):
            replacements = {node.name:node.rep}
            for parent in node.parents:
                pnode = self.nodes[parent]
                pnode.rep = _replace_rep(pnode.rep,replacements)
                pnode.args.remove([node.name,node.obj])
                pnode.args.extend(node.args)
                pnode.args = mmf.utils.unique_list(pnode.args)
            for child in node.children:
                cnode = self.nodes[child]
                cnode.parents.remove(id)
                cnode.parents.update(node.parents)
            del self.nodes[id]
    def check(self):
        """Check integrity of graph."""
        for id in self.nodes:
            node = self.nodes[id]
            children = node.children
            assert children == mmf.utils.unique_list(children)
            for child in children:
                cnode = self.nodes[child]
                assert id in cnode.parents
            
    def reduce(self):
        """Reduce the graph once by combining representations for nodes
        that have a single parent.

       Example:
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
       >>> D = [G]; E = [G]; C = [F, D, E]; B = [F]; A = [B,C]
       >>> a = Archive(); 
       >>> a.insert(A=A)
       'A'
       >>> g = Graph(a.arch,a.archive_1)
       >>> len(g.nodes)
       7
       >>> g.reduce()
       >>> len(g.nodes)         # Completely reducible
       1
       >>> print a
       A = [['F'],['F',['G'],['G']]]
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
       >>> D = [G]; E = [G]; C = [F, D, E]; B = [F]; A = [B,C]
       >>> a = Archive(); 
       >>> a.insert(A=A)
       'A'
       >>> g = Graph(a.arch,a.archive_1)
       >>> len(g.nodes)
       9
       >>> g.reduce()
       >>> len(g.nodes)         # Nodes A, F and G remain
       3
       >>> print a
       _l_1 = ['G']
       _l_5 = ['F']
       A = [[_l_5],[_l_5,[_l_1],[_l_1]]]
       try: del __builtins__
       except NameError: pass
       
       If we explicitly add a node, then it can no longer be reduced:
       >>> a.insert(B=B)
       'B'
       >>> g = Graph(a.arch,a.archive_1)
       >>> len(g.nodes)
       9
       >>> g.reduce()
       >>> len(g.nodes)         # Nodes A, F and G remain
       4
       >>> print a
       _l_5 = ['F']
       _l_1 = ['G']
       B = [_l_5]
       A = [B,[_l_5,[_l_1],[_l_1]]]
       try: del __builtins__
       except NameError: pass
       """
        self.check()
        reducible_ids = [id for id in self.order 
                         if self.nodes[id].isreducible(roots=self.roots)]
        for id in reducible_ids:
            self._reduce(id)

        self.order = self._topological_order()

def _unzip(q,n=3):
    """Unzip q to lists.

    If len(q) = 0, then assumes that q was zipped from n lists.

    Example:
    >>> _unzip(zip([1,2,3],[4,5,6]))
    [[1, 2, 3], [4, 5, 6]]
    >>> _unzip([],n=3)
    [[], [], []]
    >>> _unzip([('a','b','c'),('d','e','f')])
    [['a', 'd'], ['b', 'e'], ['c', 'f']]

    """
    if 0 == len(q):
        return [[] for n in range(n)]
    else:
        return map(list,zip(*q))

def _get_unique(name,names,sep='_'):
    """Return a unique name not in names starting with name.
    
    >>> names = ['a','a.1','b']
    >>> _get_unique('c',names)
    'c'
    >>> _get_unique('a',names,sep='.')
    'a.2'
    >>> _get_unique('b',names)
    'b_1'
    >>> _get_unique('b_1',names)
    'b_1'
    >>> _get_unique('a.1',names,sep='.')
    'a.2'
    """
    # Matches extension for unique names so they can be incremented.
    
    _extension_re = re.compile(r'(.*)%s(\d?)$'%re.escape(sep))

    if name not in names:
        uname = name
    else:
        match = _extension_re.match(name)
        if match is None:
            base = name
            c = 1
        else:
            base,c = match.groups()
            c = int(c) + 1

        while True:
            uname = sep.join((base,"%i"%c))
            if uname not in names:
                break
            c += 1
    return uname

class ReplacementError(Exception):
    """Replacements not consistent with parse tree."""
    def __init__(self,old,new,expected,actual):
        Exception.__init__(self,
            "Replacement %s->%s: Expected %i, replaced %i"%(
                old,new,expected,actual))

def _replace_rep(rep,replacements):
    """Return rep with all replacements made.

    Inputs:
        rep : String expression to make replacements in
        replacements : Dictionary of replacements.
    
    >>> _replace_rep('n = array([1,2,3])',dict(array='array_1'))
    'n = array_1([1,2,3])'
    >>> _replace_rep('a + aa',dict(a='c'))
    'c + aa'
    >>> _replace_rep("a + 'a'",dict(a='c'))
    Traceback (most recent call last):
        ...
    ReplacementError: Replacement a->c: Expected 1, replaced 2
    """
    rep_names = AST(rep).names
    counts = dict((n,rep_names.count(n)) for n in replacements)
    for old in replacements:
        re_ = r'''(?P<a>        # Refer to the group by name <a>
                   [^\w\.]      # Either NOT a valid identifier 
                   | ^)         # OR the start of the string
                  (%s)          # The literal to be matched
                  (?P<b>[^\w=]   # Either NOT a valid identifer
                   | $)'''      # OR the end.
        regexp = re.compile(re_%(re.escape(old)),re.VERBOSE)
        (rep,n) = regexp.subn(r"\g<a>%s\g<b>"%(replacements[old]),rep)
        if not n == counts[old]:
            raise ReplacementError(old,replacements[old],counts[old],n)
    return rep

class AST(object):
    """Class to represent and explore the AST of expressions."""
    def __init__(self,expr):
        self.__dict__['expr'] = expr
        self.__dict__['ast'] = compiler.parse(expr)
        self.__dict__['names'] = self._get_names()
    @property
    def expr(self):
        """Expression"""
        return self.__dict__['expr']

    @property
    def ast(self):
        """AST for expression"""
        return self.__dict__['ast']
        
    @property
    def names(self):
        """Symbols references in expression."""
        return self.__dict__['names']

    def _get_names(self):        
        names = []
        def _descend(node):
            if isinstance(node, compiler.ast.Name):
                names.append(node.name)
            try:
                map(_descend,node.getChildren())
            except AttributeError:
                return

        _descend(self.ast)
        return sorted(names)

# Testing
import run
run.run(__name__,__file__,locals())